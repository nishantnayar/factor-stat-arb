"""Diagnostic: half-life distribution of proxy-residual spreads across the universe.

Fits the proxy mapper + OU model for every universe stock and reports the
distribution of mean-reversion half-lives and proxy/AR(1) fit quality, plus how
many names would pass various half-life bounds. Use it to calibrate the discovery
screen (the pairs 5-72h bounds are too tight for factor residuals).

Usage:
    uv run scripts/analyze_residual_halflife.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.services.strategy_engine.factor_stat_arb.data import (  # noqa: E402
    clean_returns,
    load_price_matrix,
    to_log_returns,
)
from src.services.strategy_engine.factor_stat_arb.proxies import (  # noqa: E402
    PROXY_ETFS,
    load_symbol_sectors,
    load_universe_symbols,
)
from src.services.strategy_engine.factor_stat_arb.proxy_mapper import ProxyMapper  # noqa: E402
from src.services.strategy_engine.factor_stat_arb.residual_ou import fit_ou  # noqa: E402


def main() -> int:
    universe = load_universe_symbols()
    sectors = load_symbol_sectors()

    etf_px = load_price_matrix(symbols=PROXY_ETFS)
    start = etf_px.index.min()  # ETFs only span ~2y; align stocks to that window
    stk_px = load_price_matrix(symbols=universe, start=start)

    etf_ret = clean_returns(to_log_returns(etf_px))
    stk_ret = clean_returns(to_log_returns(stk_px))
    mapper = ProxyMapper(etf_ret)

    rows = []
    for sym in stk_ret.columns:
        try:
            fit = mapper.fit_symbol(stk_ret[sym], sectors.get(sym))
            # Fit OU on the drift-free residual level, not the raw (alpha-drifting)
            # log-price spread.
            ou = fit_ou(mapper.residual_level(stk_ret[sym], fit))
        except Exception:  # noqa: BLE001
            continue
        rows.append(
            {
                "symbol": sym,
                "proxy_r2": fit.r2,
                "mean_reverting": ou.mean_reverting,
                "half_life": ou.half_life if ou.mean_reverting else np.nan,
                "ar1_r2": ou.r2,
            }
        )

    df = pd.DataFrame(rows)
    n = len(df)
    mr = df["mean_reverting"].sum()
    print(f"universe fitted: {n} stocks")
    print(f"mean-reverting (0<b<1): {mr} ({mr / n:.0%})")

    hl = df.loc[df["mean_reverting"], "half_life"]
    print("\nhalf-life (hours) percentiles among mean-reverting:")
    for p in (5, 10, 25, 50, 75, 90, 95):
        print(f"  p{p:<2}: {hl.quantile(p / 100):8.0f}")

    print("\nnames passing half-life bounds (min_r2=0):")
    for lo, hi in [(5, 72), (24, 200), (24, 400), (48, 500), (72, 800)]:
        k = int(((hl >= lo) & (hl <= hi)).sum())
        print(f"  {lo:>3}-{hi:<3}h: {k:4d} ({k / n:.0%})")

    # does proxy fit quality relate to half-life?
    good = df[df["mean_reverting"]]
    if len(good) > 10:
        corr = good["proxy_r2"].corr(good["half_life"])
        print(f"\ncorr(proxy_r2, half_life): {corr:+.2f}")
        print("half-life by proxy_r2 tercile:")
        good = good.assign(
            tier=pd.qcut(good["proxy_r2"], 3, labels=["low", "mid", "high"])
        )
        print(good.groupby("tier", observed=True)["half_life"].median().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
