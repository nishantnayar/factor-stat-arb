"""
Confidence Model

Predicts the probability that a factor-residual basket's next signal will be
profitable, using a LightGBM classifier trained on closed trade history.

Per docs/PROJECT_SPEC.md's "Explainability layer":
    Training data: closed basket_trades history (label: profitable yes/no).
    Features:      OU half-life, OU R2 (proxy fit quality), proxy loading
                   stability over time, recent volume regime, sector momentum.
    Model:         LightGBM classifier.
    Explanation:   SHAP values per candidate signal.

v1 scope: no live paper trades exist yet (milestone 7 produces those), so
training bootstraps from FactorBacktestEngine's simulated trades, persisted as
BasketBacktestRun.trade_log. The feature set here uses what's already computed
and persisted at discovery time (half_life_hours, proxy_r2, z_score_abs_mean,
rank_score, sector) plus a simple recent-volume-regime ratio computed from
market_data. Proxy-loading-stability and sector-momentum features are
deferred - documented as a future extension, not built here.

Usage:
    from src.services.strategy_engine.factor_stat_arb.confidence_model import (
        ConfidenceModel,
        build_training_frame,
    )

    frame = build_training_frame()  # DataFrame of features + label
    model = ConfidenceModel().fit(frame)
    proba = model.predict_proba(candidate_features_df)
    shap_values = model.explain(candidate_features_df)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, List, Optional

import lightgbm as lgb
import numpy as np
import pandas as pd
import shap
from loguru import logger
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.config.database import get_engine

FEATURE_COLUMNS = [
    "half_life_hours",
    "proxy_r2",
    "z_score_abs_mean",
    "rank_score",
    "sector",
    "volume_regime",
]
CATEGORICAL_COLUMNS = ["sector"]
LABEL_COLUMN = "profitable"


# ---------------------------------------------------------------------------
# Training data
# ---------------------------------------------------------------------------


def _load_basket_features(engine: Optional[Engine] = None) -> pd.DataFrame:
    """Per-basket features as persisted in basket_registry at discovery time."""
    engine = engine or get_engine("trading")
    sql = text(
        "SELECT id AS basket_id, sector, symbols, half_life_hours, "
        "min_correlation AS proxy_r2, z_score_abs_mean, rank_score "
        "FROM strategy_engine.basket_registry"
    )
    with engine.connect() as conn:
        return pd.read_sql(sql, conn)


def _load_backtest_trades(engine: Optional[Engine] = None) -> pd.DataFrame:
    """Flatten each BasketBacktestRun.trade_log into one row per simulated trade."""
    engine = engine or get_engine("trading")
    sql = text(
        "SELECT basket_id, trade_log FROM strategy_engine.basket_backtest_run "
        "WHERE trade_log IS NOT NULL"
    )
    with engine.connect() as conn:
        runs = pd.read_sql(sql, conn)

    rows = []
    for _, run in runs.iterrows():
        for trade in run["trade_log"] or []:
            pnl = trade.get("pnl")
            if pnl is None:
                continue
            rows.append({"basket_id": run["basket_id"], "profitable": pnl > 0})
    return pd.DataFrame(rows)


def volume_regime(
    symbols: List[str], engine: Optional[Engine] = None, recent_days: int = 5
) -> float:
    """
    Ratio of recent average daily volume to the trailing-90-day baseline,
    averaged across the basket's symbols. > 1 means volume is elevated
    versus the recent baseline; NaN if no volume data is available.
    """
    if not symbols:
        return float("nan")
    engine = engine or get_engine("trading")
    end = datetime.utcnow()
    recent_start = end - timedelta(days=recent_days)
    baseline_start = end - timedelta(days=90)

    sql = text(
        "SELECT symbol, timestamp, volume FROM data_ingestion.market_data "
        "WHERE symbol = ANY(:symbols) AND data_source = 'yahoo_adjusted' "
        "AND timestamp >= :baseline_start AND volume IS NOT NULL"
    )
    with engine.connect() as conn:
        df = pd.read_sql(
            sql,
            conn,
            params={"symbols": symbols, "baseline_start": baseline_start},
        )
    if df.empty:
        return float("nan")

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    recent = df[df["timestamp"] >= pd.Timestamp(recent_start, tz="UTC")]
    if recent.empty or df["volume"].mean() == 0:
        return float("nan")

    recent_avg = recent["volume"].mean()
    baseline_avg = df["volume"].mean()
    if baseline_avg == 0:
        return float("nan")
    return float(recent_avg / baseline_avg)


def build_training_frame(engine: Optional[Engine] = None) -> pd.DataFrame:
    """
    Join basket_registry features with basket_backtest_run.trade_log labels.

    Returns one row per simulated trade with FEATURE_COLUMNS + LABEL_COLUMN.
    """
    engine = engine or get_engine("trading")
    baskets = _load_basket_features(engine)
    trades = _load_backtest_trades(engine)
    if baskets.empty or trades.empty:
        return pd.DataFrame(columns=FEATURE_COLUMNS + [LABEL_COLUMN])

    baskets = baskets.copy()
    baskets["volume_regime"] = baskets["symbols"].apply(
        lambda syms: volume_regime(list(syms), engine)
    )

    merged = trades.merge(baskets, on="basket_id", how="inner")
    return merged[FEATURE_COLUMNS + [LABEL_COLUMN]].dropna(
        subset=[c for c in FEATURE_COLUMNS if c != "sector"] + [LABEL_COLUMN]
    )


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


@dataclass
class ConfidenceModel:
    """
    LightGBM classifier predicting P(profitable) for a factor basket signal,
    with SHAP-based per-prediction explanations.
    """

    model: Optional[lgb.LGBMClassifier] = None
    _explainer: Optional["shap.TreeExplainer"] = None

    def fit(self, frame: pd.DataFrame, **lgbm_params: Any) -> "ConfidenceModel":
        """
        Train on a frame shaped like build_training_frame()'s output.

        Raises ValueError if the frame has fewer than 20 rows or only one
        label class (LightGBM needs both classes represented).
        """
        if len(frame) < 20:
            raise ValueError(
                f"need at least 20 labeled trades to train, got {len(frame)}"
            )
        if frame[LABEL_COLUMN].nunique() < 2:
            raise ValueError("training frame must contain both label classes")

        x = frame[FEATURE_COLUMNS].copy()
        for col in CATEGORICAL_COLUMNS:
            x[col] = x[col].astype("category")
        y = frame[LABEL_COLUMN].astype(int)

        params: dict[str, Any] = {
            "n_estimators": 100,
            "max_depth": 4,
            "random_state": 42,
        }
        params.update(lgbm_params)
        clf = lgb.LGBMClassifier(**params)
        clf.fit(x, y, categorical_feature=CATEGORICAL_COLUMNS)

        self.model = clf
        self._explainer = shap.TreeExplainer(clf)
        logger.info(f"ConfidenceModel trained on {len(frame)} trades")
        return self

    def _prepared(self, features: pd.DataFrame) -> pd.DataFrame:
        x = features[FEATURE_COLUMNS].copy()
        for col in CATEGORICAL_COLUMNS:
            x[col] = x[col].astype("category")
        return x

    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        """P(profitable) for each row in `features` (shaped like FEATURE_COLUMNS)."""
        if self.model is None:
            raise RuntimeError("call fit() before predict_proba()")
        proba: np.ndarray = self.model.predict_proba(self._prepared(features))[:, 1]
        return proba

    def explain(self, features: pd.DataFrame) -> np.ndarray:
        """Per-feature SHAP values for each row in `features`."""
        if self._explainer is None:
            raise RuntimeError("call fit() before explain()")
        values: np.ndarray = self._explainer.shap_values(self._prepared(features))
        return values
