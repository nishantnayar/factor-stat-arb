"""Discover factor-residual baskets and upsert them into BasketRegistry.

Wires the factor_stat_arb pieces together for every universe stock:
  1. Regress the stock's returns on tradable ETF proxies (SPY + sector ETF).
  2. Build the drift-free residual level and fit an OU process.
  3. Screen on proxy fit quality + OU half-life, rank the survivors, and upsert
     the top candidates into strategy_engine.basket_registry (is_active=False,
     pending manual review - same convention as pairs/baskets discovery).

A PCA factor model is fit once for context (how much common structure exists).

The registry is shared with the Johansen basket strategy, so some columns are
repurposed for the factor case (documented at build_candidate()):
  hedge_weights = +1 on the stock, -beta on each proxy (a log-price spread basket)
  coint_pvalue  = 1 - proxy_r2 (an OLS-fit-quality analog, lower is better)
  min_correlation = proxy_r2 (regression fit strength)

Usage:
    uv run scripts/discover_factor_baskets.py                 # discover + upsert
    uv run scripts/discover_factor_baskets.py --dry-run       # no DB writes
    uv run scripts/discover_factor_baskets.py --top-n 25 --limit 200
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402

from src.shared.database.base import db_transaction  # noqa: E402
from src.shared.database.models.strategy_models import BasketRegistry  # noqa: E402
from src.services.strategy_engine.factor_stat_arb.data import (  # noqa: E402
    clean_returns,
    load_price_matrix,
    to_log_returns,
)
from src.services.strategy_engine.factor_stat_arb.factor_model import FactorModel  # noqa: E402
from src.services.strategy_engine.factor_stat_arb.proxies import (  # noqa: E402
    PROXY_ETFS,
    load_symbol_sectors,
    load_universe_symbols,
)
from src.services.strategy_engine.factor_stat_arb.proxy_mapper import ProxyMapper  # noqa: E402
from src.services.strategy_engine.factor_stat_arb.residual_ou import (  # noqa: E402
    DEFAULT_MAX_HALF_LIFE,
    DEFAULT_MIN_HALF_LIFE,
    fit_ou,
)

DEFAULT_MIN_PROXY_R2 = 0.30
DEFAULT_MAX_ALLOCATION_PCT = 0.05


def zscore_window_for(half_life: float) -> int:
    """Rolling z-score window ~ one half-life, bounded to a sane range."""
    return int(np.clip(round(half_life), 60, 300))


def rolling_zscore_abs_mean(level: pd.Series, window: int) -> float:
    """Mean absolute rolling z-score of the residual level (tradability proxy)."""
    m = level.rolling(window, min_periods=window // 2).mean()
    s = level.rolling(window, min_periods=window // 2).std()
    z = ((level - m) / s).replace([np.inf, -np.inf], np.nan).dropna()
    return float(z.abs().mean()) if not z.empty else 0.0


def build_candidate(
    symbol: str,
    sector: Optional[str],
    mapper: ProxyMapper,
    stock_returns: pd.Series,
    min_proxy_r2: float,
    min_half_life: float,
    max_half_life: float,
    max_allocation_pct: float,
) -> Optional[dict]:
    """Evaluate one stock; return a registry-row dict or None if it fails a gate.

    Proxy selection uses fit_symbol_auto: SPY + sector ETF, extended with one
    extra sector ETF only if it materially improves adj_r2 (see proxy_mapper.py).
    Extended fits are flagged in notes with "REVIEW: extended proxy set" so the
    Streamlit Factor Lab can surface them for human review before activation --
    the sector label was likely an incomplete description of the stock's
    exposure, so the pick is worth a manual look, not a hard gate.
    """
    try:
        fit = mapper.fit_symbol_auto(stock_returns, sector)
    except ValueError:
        return None
    if fit.r2 < min_proxy_r2:
        return None

    level = mapper.residual_level(stock_returns, fit)
    try:
        ou = fit_ou(level)
    except ValueError:
        return None
    if not ou.passes(min_half_life=min_half_life, max_half_life=max_half_life):
        return None

    z_window = zscore_window_for(ou.half_life)
    z_abs_mean = rolling_zscore_abs_mean(level, z_window)
    rank_score = fit.r2 * z_abs_mean

    weights = fit.basket_weights()  # {stock: 1, proxy: -beta, ...}
    betas_str = ", ".join(f"{k}={v:.2f}" for k, v in fit.betas.items())
    review_tag = "REVIEW: extended proxy set | " if fit.extended else ""
    return {
        "name": f"FSA_{symbol}",
        "sector": sector,
        "symbols": list(weights.keys()),
        "hedge_weights": {k: round(v, 6) for k, v in weights.items()},
        "half_life_hours": round(ou.half_life, 2),
        "coint_pvalue": round(1.0 - fit.r2, 6),  # OLS-fit-quality analog
        "min_correlation": round(fit.r2, 4),  # regression fit strength
        "z_score_window": z_window,
        "z_score_abs_mean": round(z_abs_mean, 4),
        "rank_score": round(rank_score, 6),
        "max_hold_hours": round(ou.half_life * 3, 2),
        "max_allocation_pct": max_allocation_pct,
        "notes": (
            f"{review_tag}factor residual | proxies={fit.proxies} | {betas_str} | "
            f"alpha={fit.alpha:.2e} | proxy_r2={fit.r2:.2f} | ou_hl={ou.half_life:.0f}h"
        ),
    }


def discover(
    min_proxy_r2: float,
    min_half_life: float,
    max_half_life: float,
    max_allocation_pct: float,
    top_n: Optional[int],
    limit: Optional[int],
) -> pd.DataFrame:
    universe = load_universe_symbols()
    if limit:
        universe = universe[:limit]
    sectors = load_symbol_sectors()

    etf_px = load_price_matrix(symbols=PROXY_ETFS)
    start = etf_px.index.min()  # align stocks to the ETF window (~2y hourly)
    etf_ret = clean_returns(to_log_returns(etf_px))
    stk_ret = clean_returns(
        to_log_returns(load_price_matrix(symbols=universe, start=start))
    )
    print(
        f"universe: {len(stk_ret.columns)} stocks, {len(stk_ret)} bars; proxies: {len(etf_ret.columns)}"
    )

    # Context: how much common factor structure is in the universe.
    try:
        fm = FactorModel(var_threshold=0.6).fit(stk_ret)
        print(
            f"factor structure: {fm.k_} PCs explain {fm.total_variance_explained():.0%} of variance"
        )
    except Exception as e:  # noqa: BLE001
        print(f"factor model skipped: {type(e).__name__}: {e}")

    mapper = ProxyMapper(etf_ret)
    rows = []
    for symbol in stk_ret.columns:
        cand = build_candidate(
            symbol,
            sectors.get(symbol),
            mapper,
            stk_ret[symbol],
            min_proxy_r2,
            min_half_life,
            max_half_life,
            max_allocation_pct,
        )
        if cand:
            rows.append(cand)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.sort_values("rank_score", ascending=False).reset_index(drop=True)
    if top_n:
        df = df.head(top_n)
    return df


def upsert(results: pd.DataFrame) -> list[int]:
    """Upsert candidates into basket_registry (is_active=False)."""
    ids: list[int] = []
    now = datetime.now(tz=timezone.utc)
    with db_transaction() as session:
        for _, row in results.iterrows():
            values = dict(
                name=row["name"],
                sector=row["sector"],
                symbols=row["symbols"],
                hedge_weights=row["hedge_weights"],
                half_life_hours=float(row["half_life_hours"]),
                coint_pvalue=float(row["coint_pvalue"]),
                min_correlation=float(row["min_correlation"]),
                z_score_window=int(row["z_score_window"]),
                z_score_abs_mean=float(row["z_score_abs_mean"]),
                rank_score=float(row["rank_score"]),
                max_hold_hours=float(row["max_hold_hours"]),
                max_allocation_pct=float(row["max_allocation_pct"]),
                notes=row["notes"],
                is_active=False,
                last_validated=now,
            )
            update = {
                k: values[k]
                for k in (
                    "sector",
                    "symbols",
                    "hedge_weights",
                    "half_life_hours",
                    "coint_pvalue",
                    "min_correlation",
                    "z_score_window",
                    "z_score_abs_mean",
                    "rank_score",
                    "max_hold_hours",
                    "max_allocation_pct",
                    "notes",
                    "last_validated",
                )
            }
            update["updated_at"] = now
            stmt = (
                pg_insert(BasketRegistry)
                .values(**values)
                .on_conflict_do_update(
                    constraint="basket_registry_name_key", set_=update
                )
                .returning(BasketRegistry.id)
            )
            ids.append(session.execute(stmt).scalar_one())
    return ids


def main() -> int:
    p = argparse.ArgumentParser(description="Discover factor-residual baskets")
    p.add_argument("--min-proxy-r2", type=float, default=DEFAULT_MIN_PROXY_R2)
    p.add_argument("--min-half-life", type=float, default=DEFAULT_MIN_HALF_LIFE)
    p.add_argument("--max-half-life", type=float, default=DEFAULT_MAX_HALF_LIFE)
    p.add_argument("--max-alloc", type=float, default=DEFAULT_MAX_ALLOCATION_PCT)
    p.add_argument("--top-n", type=int, default=50)
    p.add_argument("--limit", type=int, default=None, help="limit universe (testing)")
    p.add_argument("--dry-run", action="store_true", help="no DB writes")
    args = p.parse_args()

    df = discover(
        args.min_proxy_r2,
        args.min_half_life,
        args.max_half_life,
        args.max_alloc,
        args.top_n,
        args.limit,
    )
    if df.empty:
        print("No candidates passed the screen.")
        return 0

    print(f"\n{len(df)} candidates (top by rank_score):")
    cols = [
        "name",
        "sector",
        "min_correlation",
        "half_life_hours",
        "z_score_abs_mean",
        "rank_score",
    ]
    print(df[cols].head(15).to_string(index=False))

    if args.dry_run:
        print("\n[dry-run] no DB writes.")
        return 0
    ids = upsert(df)
    print(
        f"\nUpserted {len(ids)} baskets to strategy_engine.basket_registry (is_active=False)."
    )
    print(
        "Review, then: UPDATE strategy_engine.basket_registry SET is_active=true WHERE id=<id>;"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
