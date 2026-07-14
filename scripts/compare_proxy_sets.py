"""Compare candidate ETF proxy sets per stock to check whether SPY + sector ETF
is actually the best available hedge, or whether a narrower/wider set fits better.

Kept to a realistic 2-3 proxy budget throughout (what the strategy can actually
trade and explain) -- comparing against all 11 sector ETFs at once is not a fair
fight, since adj_r2's fixed per-regressor penalty barely dents collinear/
redundant proxies, so a kitchen-sink set always "wins" without producing a
tradable or interpretable hedge.

For each stock, fits several named proxy sets and reports adj_r2 (comparable
across set sizes, unlike raw r2 which never decreases as proxies are added):
  broad_only        SPY alone
  sector_only       sector ETF alone
  broad_plus_sector SPY + sector ETF (the current discover_factor_baskets.py default)
  broad_plus_best2  SPY + sector ETF + the single next-best sector ETF by
                     |correlation| with the stock's returns (checks for a
                     missed second sector exposure without a full 12-ETF dump)

Usage:
    uv run scripts/compare_proxy_sets.py                  # full universe
    uv run scripts/compare_proxy_sets.py --limit 100
    uv run scripts/compare_proxy_sets.py --symbols AAPL,XOM,JPM
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.services.strategy_engine.factor_stat_arb.data import (  # noqa: E402
    clean_returns,
    load_price_matrix,
    to_log_returns,
)
from src.services.strategy_engine.factor_stat_arb.proxies import (  # noqa: E402
    BROAD_ETF,
    PROXY_ETFS,
    load_symbol_sectors,
    load_universe_symbols,
    sector_etf,
)
from src.services.strategy_engine.factor_stat_arb.proxy_mapper import (  # noqa: E402
    ProxyMapper,
)

DEFAULT_TOP_N = 30


def candidate_sets_for(
    mapper: ProxyMapper, stock_returns: pd.Series, sector: str | None
) -> dict[str, list[str]]:
    etf = sector_etf(sector)
    sets: dict[str, list[str]] = {"broad_only": [BROAD_ETF]}
    if etf:
        sets["sector_only"] = [etf]
        sets["broad_plus_sector"] = [BROAD_ETF, etf]
        second = mapper.best_second_sector_etf(stock_returns, {BROAD_ETF, etf})
        if second:
            sets["broad_plus_best2"] = [BROAD_ETF, etf, second]
    return sets


def compare(symbols: list[str] | None, limit: int | None) -> pd.DataFrame:
    universe = symbols or load_universe_symbols()
    if limit:
        universe = universe[:limit]
    sectors = load_symbol_sectors()

    etf_px = load_price_matrix(symbols=PROXY_ETFS)
    start = etf_px.index.min()
    etf_ret = clean_returns(to_log_returns(etf_px))
    stk_ret = clean_returns(
        to_log_returns(load_price_matrix(symbols=universe, start=start))
    )
    print(
        f"universe: {len(stk_ret.columns)} stocks, {len(stk_ret)} bars; "
        f"proxies: {len(etf_ret.columns)}"
    )

    mapper = ProxyMapper(etf_ret)
    rows = []
    for symbol in stk_ret.columns:
        sector = sectors.get(symbol)
        candidates = candidate_sets_for(mapper, stk_ret[symbol], sector)
        fits = mapper.compare_proxy_sets(stk_ret[symbol], candidates)
        if not fits:
            continue
        best_name = max(fits, key=lambda n: fits[n].adj_r2)
        row = {"symbol": symbol, "sector": sector, "best_set": best_name}
        for name, fit in fits.items():
            row[f"{name}_adj_r2"] = round(fit.adj_r2, 4)
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    default_col = "broad_plus_sector_adj_r2"
    if default_col in df.columns:
        df["default_wins"] = df["best_set"] == "broad_plus_sector"
        df["best_adj_r2"] = df.apply(
            lambda row: row[f"{row['best_set']}_adj_r2"], axis=1
        )
        df["adj_r2_gain"] = (df["best_adj_r2"] - df[default_col]).round(4)
    return df


def main() -> int:
    p = argparse.ArgumentParser(description="Compare ETF proxy sets per stock")
    p.add_argument("--symbols", type=str, default=None, help="comma-separated")
    p.add_argument("--limit", type=int, default=None, help="limit universe")
    p.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    p.add_argument(
        "--min-gain",
        type=float,
        default=0.02,
        help="adj_r2 gain over broad_plus_sector to count as a material win",
    )
    args = p.parse_args()

    symbols = args.symbols.split(",") if args.symbols else None
    df = compare(symbols, args.limit)
    if df.empty:
        print("No candidates fit.")
        return 0

    if "default_wins" in df.columns:
        win_rate = df["default_wins"].mean()
        print(
            f"\nbroad_plus_sector (current default) is best fit for "
            f"{win_rate:.0%} of {len(df)} stocks"
        )
        material = df[
            ~df["default_wins"] & (df["adj_r2_gain"] >= args.min_gain)
        ].sort_values("adj_r2_gain", ascending=False)
        print(
            f"\nStocks where an alternate proxy set gains >= {args.min_gain} "
            f"adj_r2 ({len(material)} of {len(df)}):"
        )
        print(material.head(args.top_n).to_string(index=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
