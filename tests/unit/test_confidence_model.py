"""Unit tests for ConfidenceModel (no DB)."""

import numpy as np
import pandas as pd
import pytest

from src.services.strategy_engine.factor_stat_arb.confidence_model import (
    FEATURE_COLUMNS,
    LABEL_COLUMN,
    ConfidenceModel,
)


def _synthetic_frame(n=200, seed=0) -> pd.DataFrame:
    """Trades where higher rank_score/proxy_r2 and lower half_life predict profit."""
    rng = np.random.default_rng(seed)
    sectors = rng.choice(["Tech", "Financials", "Energy"], size=n)
    half_life = rng.uniform(48, 400, n)
    proxy_r2 = rng.uniform(0.2, 0.9, n)
    z_abs_mean = rng.uniform(0.5, 3.0, n)
    rank_score = proxy_r2 * z_abs_mean
    volume_regime = rng.uniform(0.5, 2.0, n)

    score = proxy_r2 + rank_score - half_life / 400 + rng.normal(0, 0.1, n)
    profitable = score > np.median(score)

    return pd.DataFrame(
        {
            "half_life_hours": half_life,
            "proxy_r2": proxy_r2,
            "z_score_abs_mean": z_abs_mean,
            "rank_score": rank_score,
            "sector": sectors,
            "volume_regime": volume_regime,
            LABEL_COLUMN: profitable,
        }
    )


@pytest.mark.unit
class TestConfidenceModel:
    def test_fit_requires_minimum_rows(self):
        frame = _synthetic_frame(n=10)
        with pytest.raises(ValueError, match="at least 20"):
            ConfidenceModel().fit(frame)

    def test_fit_requires_both_label_classes(self):
        frame = _synthetic_frame(n=50)
        frame[LABEL_COLUMN] = True
        with pytest.raises(ValueError, match="both label classes"):
            ConfidenceModel().fit(frame)

    def test_predict_proba_before_fit_raises(self):
        model = ConfidenceModel()
        with pytest.raises(RuntimeError, match="call fit"):
            model.predict_proba(_synthetic_frame(n=5)[FEATURE_COLUMNS])

    def test_explain_before_fit_raises(self):
        model = ConfidenceModel()
        with pytest.raises(RuntimeError, match="call fit"):
            model.explain(_synthetic_frame(n=5)[FEATURE_COLUMNS])

    def test_fit_predict_explain_roundtrip(self):
        frame = _synthetic_frame(n=200)
        model = ConfidenceModel().fit(frame)

        proba = model.predict_proba(frame[FEATURE_COLUMNS])
        assert len(proba) == len(frame)
        assert np.all((proba >= 0) & (proba <= 1))

        shap_values = model.explain(frame[FEATURE_COLUMNS].iloc[:10])
        assert shap_values.shape[0] == 10
        assert shap_values.shape[1] == len(FEATURE_COLUMNS)

    def test_model_beats_random_on_synthetic_signal(self):
        frame = _synthetic_frame(n=300, seed=1)
        train, test = frame.iloc[:240], frame.iloc[240:]
        model = ConfidenceModel().fit(train)

        proba = model.predict_proba(test[FEATURE_COLUMNS])
        preds = proba > 0.5
        accuracy = (preds == test[LABEL_COLUMN].to_numpy()).mean()

        assert accuracy > 0.55
