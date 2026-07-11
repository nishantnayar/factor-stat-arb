"""
Basket Discovery Script

Finds statistically validated N-stock baskets for intraday pairs trading
using Johansen cointegration (multi-asset generalization of Engle-Granger).

The Johansen test finds a cointegrating vector [w1, w2, ..., wN] such that
    spread = w1*log(P1) + w2*log(P2) + ... + wN*log(PN)
is stationary and mean-reverting.  The eigenvector with the smallest eigenvalue
gives the fastest mean reversion - directly minimizing half-life.

Usage:
    python scripts/discover_baskets.py --sector "Regional Banks"
    python scripts/discover_baskets.py --sector Technology --min-basket-size 3 --top 5
    python scripts/discover_baskets.py --sector "Regional Banks" --max-pvalue 0.05
"""

import asyncio
import math
import sys
from datetime import date, datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import click
import numpy as np
import pandas as pd
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.shared.database.base import db_readonly_session, db_transaction
from src.shared.database.models.market_data import MarketData
from src.shared.database.models.strategy_models import BasketRegistry
from src.shared.database.models.symbols import Symbol

# ---------------------------------------------------------------------------
# Re-use data loading helpers from discover_pairs (same DB schema)
# ---------------------------------------------------------------------------


def get_active_symbols() -> List[Dict]:
    """Fetch all active symbols with sector info from DB."""
    with db_readonly_session() as session:
        stmt = (
            select(Symbol.symbol, Symbol.sector, Symbol.name)
            .where(Symbol.status == "active")
            .order_by(Symbol.symbol)
        )
        rows = session.execute(stmt).fetchall()
    return [{"symbol": r.symbol, "sector": r.sector, "name": r.name} for r in rows]


def get_hourly_closes(
    symbols: List[str],
    start_date: date,
    end_date: date,
    data_source: str = "yahoo_adjusted",
) -> pd.DataFrame:
    """
    Fetch hourly close prices for given symbols over a date range.
    Returns a DataFrame indexed by timestamp with one column per symbol.
    """
    with db_readonly_session() as session:
        stmt = (
            select(
                MarketData.timestamp,
                MarketData.symbol,
                MarketData.close,
            )
            .where(
                and_(
                    MarketData.symbol.in_(symbols),
                    MarketData.data_source == data_source,
                    MarketData.timestamp >= start_date,
                    MarketData.timestamp < end_date + timedelta(days=1),
                    MarketData.close.isnot(None),
                )
            )
            .order_by(MarketData.timestamp)
        )
        rows = session.execute(stmt).fetchall()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=["timestamp", "symbol", "close"])
    df["close"] = df["close"].astype(float)

    pivot = df.pivot_table(
        index="timestamp", columns="symbol", values="close", aggfunc="last"
    )
    pivot.index = pd.to_datetime(pivot.index, utc=True)
    pivot.sort_index(inplace=True)

    if not isinstance(pivot, pd.DataFrame):
        raise TypeError("internal: pivot_table must return DataFrame")
    return pivot


# ---------------------------------------------------------------------------
# Statistical tests
# ---------------------------------------------------------------------------


def johansen_cointegration(
    prices_df: pd.DataFrame,
) -> Tuple[float, List[float]]:
    """
    Run Johansen cointegration test on log prices of N assets.

    Returns (min_pvalue, hedge_weights) where:
      - min_pvalue is the trace statistic p-value for the r=0 hypothesis
        (i.e. probability of seeing this trace statistic if no cointegration)
      - hedge_weights is the first cointegrating eigenvector, normalized so
        weights[0] = 1.0  (sign is flipped if weights[0] < 0)
    """
    from statsmodels.tsa.vector_ar.vecm import coint_johansen

    log_prices = np.log(prices_df.dropna())
    if len(log_prices) < 60:
        return 1.0, [1.0] * len(prices_df.columns)

    result = coint_johansen(log_prices, det_order=0, k_ar_diff=1)

    # trace_stat_crit_vals shape: (num_assets, 3) for 10%, 5%, 1% crit values
    # cvt: critical values for trace statistic
    # lr1: trace statistics
    trace_stat = result.lr1[0]
    crit_val_5pct = result.cvt[0, 1]

    # Approximate p-value: 0.01 if stat > 1% crit, 0.05 if > 5%, else 0.10+
    # statsmodels does not give exact p-values for Johansen; use conservative approx.
    crit_1pct = result.cvt[0, 2]
    if trace_stat > crit_1pct:
        p_value = 0.01
    elif trace_stat > crit_val_5pct:
        p_value = 0.05
    else:
        p_value = 0.15

    # First eigenvector = fastest mean-reverting cointegrating combination
    evec = result.evec[:, 0]

    # Normalize so first weight = 1.0, flip sign if needed
    if evec[0] < 0:
        evec = -evec
    evec = evec / evec[0]

    return float(p_value), [float(w) for w in evec]


def compute_basket_spread(
    prices_df: pd.DataFrame,
    hedge_weights: List[float],
) -> pd.Series:
    """
    Compute basket spread: spread = sum(w_i * log(P_i)) for each row.
    Drops rows where any price is missing.
    """
    log_prices = np.log(prices_df.dropna())
    weights = np.array(hedge_weights)
    spread = log_prices.values @ weights
    return pd.Series(spread, index=log_prices.index, name="spread")


def compute_half_life(spread: pd.Series) -> float:
    """
    Mean-reversion half-life via AR(1) on delta-spread.
    Returns inf if the series is not mean-reverting.
    """
    from statsmodels.regression.linear_model import OLS
    from statsmodels.tools import add_constant

    spread = spread.dropna()
    if len(spread) < 30:
        return float("inf")

    delta = spread.diff().dropna()
    lagged = spread.shift(1).dropna()

    aligned = pd.concat([delta, lagged], axis=1).dropna()
    if len(aligned) < 20:
        return float("inf")

    y = aligned.iloc[:, 0].values
    x = add_constant(aligned.iloc[:, 1].values)
    model = OLS(y, x).fit()
    beta = float(model.params[1])

    if beta >= 0:
        return float("inf")

    return float(-np.log(2) / np.log(1 + beta))


def compute_min_pairwise_correlation(prices_df: pd.DataFrame) -> float:
    """Minimum Pearson correlation on log returns across all pairs in the basket."""
    log_returns = np.log(prices_df).diff().dropna()
    cols = log_returns.columns.tolist()
    min_corr = 1.0
    for i, c1 in enumerate(cols):
        for c2 in cols[i + 1 :]:
            c = float(log_returns[c1].corr(log_returns[c2]))
            if c < min_corr:
                min_corr = c
    return min_corr


def compute_basket_stats(spread: pd.Series, z_window: int) -> Dict:
    """Compute rolling z-score stats for a basket spread."""
    roll_mean = spread.rolling(z_window).mean()
    roll_std = spread.rolling(z_window).std()
    z_score = (spread - roll_mean) / roll_std

    return {
        "current_z_score": float(z_score.iloc[-1]) if not z_score.empty else 0.0,
        "z_score_abs_mean": float(z_score.abs().mean()) if not z_score.empty else 0.0,
    }


# ---------------------------------------------------------------------------
# Basket discovery
# ---------------------------------------------------------------------------


def _prefilter_by_correlation(
    price_df: pd.DataFrame,
    max_symbols: int,
    min_corr: float,
) -> pd.DataFrame:
    """
    Reduce the symbol universe before the combinatorial search.

    1. Compute pairwise Pearson correlations on log returns.
    2. Keep only symbols whose average absolute correlation with others >= min_corr.
    3. From the survivors, take the top max_symbols by average absolute correlation.

    This turns e.g. 139 Financial Services symbols into ~20-30, cutting
    C(139,3..5) = 417M combos down to C(25,3..5) = ~13K.
    """
    log_ret = np.log(price_df).diff().dropna()
    corr_matrix = log_ret.corr().abs()
    # Mean correlation of each symbol with every other symbol
    avg_corr = (corr_matrix.sum(axis=1) - 1) / (len(corr_matrix) - 1)

    survivors = avg_corr[avg_corr >= min_corr].index.tolist()
    if len(survivors) < 3:
        logger.warning(
            f"Only {len(survivors)} symbols survive min_corr={min_corr:.2f} - "
            "lowering threshold to keep top 30 by avg correlation"
        )
        survivors = avg_corr.nlargest(min(30, len(avg_corr))).index.tolist()

    # Cap at max_symbols, taking the most correlated ones
    top = avg_corr[survivors].nlargest(max_symbols).index.tolist()
    logger.info(
        f"Correlation pre-filter: {len(price_df.columns)} -> {len(top)} symbols "
        f"(avg_corr >= {min_corr:.2f}, top {max_symbols})"
    )
    return price_df[top]


def discover_baskets(
    price_df: pd.DataFrame,
    symbols_meta: Dict[str, Dict],
    min_basket_size: int = 3,
    max_basket_size: int = 3,
    max_pvalue: float = 0.05,
    min_half_life_hours: float = 5.0,
    max_half_life_hours: float = 72.0,
    min_overlap_bars: int = 180,
    max_symbols: int = 25,
    min_corr_prefilter: float = 0.3,
    top_n: int = 3,
) -> pd.DataFrame:
    """
    Run the full basket discovery pipeline and return a ranked DataFrame.

    Applies a correlation pre-filter to reduce the symbol universe before
    iterating combinations, keeping the search tractable for large sectors.
    """
    # Correlation pre-filter to reduce combinatorial explosion
    price_df = _prefilter_by_correlation(price_df, max_symbols, min_corr_prefilter)

    symbols = list(price_df.columns)
    results: List[Dict] = []

    n = len(symbols)
    total_combos = sum(
        math.comb(n, k) for k in range(min_basket_size, max_basket_size + 1) if k <= n
    )
    logger.info(
        f"Testing {total_combos} combinations (basket sizes {min_basket_size}-{max_basket_size})"
        f" from {n} symbols..."
    )

    checked = 0
    rejected_overlap = 0
    rejected_pvalue = 0
    rejected_half = 0

    for size in range(min_basket_size, max_basket_size + 1):
        for combo in combinations(symbols, size):
            checked += 1
            if checked % 20 == 0:
                logger.info(
                    f"  Progress: {checked}/{total_combos} checked, {len(results)} candidates"
                )

            subset = price_df[list(combo)].dropna()
            if len(subset) < min_overlap_bars:
                rejected_overlap += 1
                continue

            # Step 1: Johansen cointegration
            p_value, hedge_weights = johansen_cointegration(subset)
            if p_value > max_pvalue:
                rejected_pvalue += 1
                continue

            # Step 2: Compute basket spread and half-life
            spread = compute_basket_spread(subset, hedge_weights)
            half_life_bars = compute_half_life(spread)

            # Data is daily bars (yahoo_adjusted); convert to hours (7 trading hrs/day)
            half_life = half_life_bars * 7.0

            if half_life == float("inf") or half_life < min_half_life_hours:
                rejected_half += 1
                continue
            if half_life > max_half_life_hours:
                rejected_half += 1
                continue

            # Step 3: Z-score window = 2x half-life, capped at 60
            z_window = min(max(10, int(2 * half_life)), 60)
            stats = compute_basket_stats(spread, z_window)

            # Step 4: Min pairwise correlation (quality guard)
            min_corr = compute_min_pairwise_correlation(subset)

            # Step 5: Rank score
            rank_score = (1 - p_value) * max(min_corr, 0.0) * stats["z_score_abs_mean"]

            sector = symbols_meta.get(combo[0], {}).get("sector", "Unknown")
            sorted_syms = sorted(combo)
            name = sector.replace(" ", "") + "_" + "_".join(sorted_syms)

            results.append(
                {
                    "name": name,
                    "symbols": list(combo),
                    "sector": sector,
                    "hedge_weights": [round(w, 6) for w in hedge_weights],
                    "coint_pvalue": round(p_value, 4),
                    "half_life_hours": round(half_life, 1),
                    "z_score_window": z_window,
                    "min_correlation": round(min_corr, 4),
                    "z_score_abs_mean": round(stats["z_score_abs_mean"], 4),
                    "current_z_score": round(stats["current_z_score"], 3),
                    "rank_score": round(rank_score, 4),
                    "overlap_bars": len(subset),
                }
            )

    logger.info(
        f"Discovery funnel: checked={checked} overlap_fail={rejected_overlap}"
        f" pvalue_fail={rejected_pvalue} half_fail={rejected_half} passed={len(results)}"
    )

    if not results:
        logger.warning("No baskets passed all filters.")
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df.sort_values("rank_score", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)

    ranked = df.head(top_n)
    if not isinstance(ranked, pd.DataFrame):
        raise TypeError("internal: DataFrame.head must return DataFrame")
    return ranked


# ---------------------------------------------------------------------------
# DB upsert
# ---------------------------------------------------------------------------


def upsert_baskets(results_df: pd.DataFrame) -> List[int]:
    """Upsert discovered baskets into basket_registry (is_active=False)."""
    upserted: List[int] = []
    now = datetime.now(tz=timezone.utc)

    with db_transaction() as session:
        for _, row in results_df.iterrows():
            stmt = (
                pg_insert(BasketRegistry)
                .values(
                    name=row["name"],
                    sector=row.get("sector"),
                    symbols=row["symbols"],
                    hedge_weights=row["hedge_weights"],
                    half_life_hours=float(row["half_life_hours"]),
                    coint_pvalue=float(row["coint_pvalue"]),
                    min_correlation=float(row["min_correlation"]),
                    z_score_window=int(row["z_score_window"]),
                    z_score_abs_mean=float(row["z_score_abs_mean"]),
                    rank_score=float(row["rank_score"]),
                    max_hold_hours=float(row["half_life_hours"]) * 3,
                    is_active=False,
                    last_validated=now,
                )
                .on_conflict_do_update(
                    constraint="basket_registry_name_key",
                    set_={
                        "symbols": row["symbols"],
                        "hedge_weights": row["hedge_weights"],
                        "half_life_hours": float(row["half_life_hours"]),
                        "coint_pvalue": float(row["coint_pvalue"]),
                        "min_correlation": float(row["min_correlation"]),
                        "z_score_window": int(row["z_score_window"]),
                        "z_score_abs_mean": float(row["z_score_abs_mean"]),
                        "rank_score": float(row["rank_score"]),
                        "max_hold_hours": float(row["half_life_hours"]) * 3,
                        "last_validated": now,
                        "updated_at": now,
                    },
                )
                .returning(BasketRegistry.id)
            )
            result = session.execute(stmt)
            basket_id = result.scalar_one()
            upserted.append(basket_id)

    return upserted


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.option(
    "--sector",
    default=None,
    type=str,
    help="Filter to a specific sector (e.g. 'Regional Banks')",
)
@click.option(
    "--min-basket-size",
    default=3,
    type=int,
    show_default=True,
    help="Minimum number of stocks in basket",
)
@click.option(
    "--max-basket-size",
    default=3,
    type=int,
    show_default=True,
    help="Maximum number of stocks in basket",
)
@click.option(
    "--max-symbols",
    default=25,
    type=int,
    show_default=True,
    help="Max symbols to test after correlation pre-filter (keeps most correlated)",
)
@click.option(
    "--min-corr-prefilter",
    default=0.3,
    type=float,
    show_default=True,
    help="Min average absolute pairwise correlation to survive pre-filter",
)
@click.option(
    "--max-pvalue",
    default=0.05,
    type=float,
    show_default=True,
    help="Maximum Johansen trace statistic p-value",
)
@click.option(
    "--min-half-life",
    default=5.0,
    type=float,
    show_default=True,
    help="Minimum mean-reversion half-life in hours",
)
@click.option(
    "--max-half-life",
    default=72.0,
    type=float,
    show_default=True,
    help="Maximum mean-reversion half-life in hours",
)
@click.option(
    "--top",
    "top_n",
    default=3,
    type=int,
    show_default=True,
    help="Number of top baskets to display and save",
)
@click.option(
    "--days-back",
    default=252,
    type=int,
    show_default=True,
    help="Days of hourly history to pull",
)
@click.option(
    "--data-source",
    default="yahoo_adjusted",
    show_default=True,
    help="Data source in market_data table",
)
def main(
    sector: Optional[str],
    min_basket_size: int,
    max_basket_size: int,
    max_pvalue: float,
    min_half_life: float,
    max_half_life: float,
    top_n: int,
    days_back: int,
    data_source: str,
    max_symbols: int,
    min_corr_prefilter: float,
) -> None:
    """
    Discover statistically validated N-stock baskets via Johansen cointegration.

    The Johansen test extends Engle-Granger to N assets and directly finds the
    cointegrating vector with the fastest mean reversion (shortest half-life).

    Examples:

        # Regional Banks sector, default settings (top 3 baskets)
        python scripts/discover_baskets.py --sector "Regional Banks"

        # Technology sector, 3-4 stock baskets only
        python scripts/discover_baskets.py --sector Technology --max-basket-size 4

        # Relaxed p-value filter
        python scripts/discover_baskets.py --sector "Regional Banks" --max-pvalue 0.10
    """
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
    )

    asyncio.run(
        run_discovery(
            sector_filter=sector,
            min_basket_size=min_basket_size,
            max_basket_size=max_basket_size,
            max_pvalue=max_pvalue,
            min_half_life=min_half_life,
            max_half_life=max_half_life,
            top_n=top_n,
            days_back=days_back,
            data_source=data_source,
            max_symbols=max_symbols,
            min_corr_prefilter=min_corr_prefilter,
        )
    )


async def run_discovery(
    sector_filter: Optional[str],
    min_basket_size: int,
    max_basket_size: int,
    max_pvalue: float,
    min_half_life: float,
    max_half_life: float,
    top_n: int,
    days_back: int,
    data_source: str,
    max_symbols: int = 25,
    min_corr_prefilter: float = 0.3,
) -> List[int]:
    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)

    logger.info(f"Basket Discovery - {start_date} to {end_date} ({days_back} days)")
    logger.info(
        f"Filters: p-value <= {max_pvalue:.2f}, half-life {min_half_life:.0f}-{max_half_life:.0f}h,"
        f" basket size {min_basket_size}-{max_basket_size}"
    )

    # Load symbols
    symbols_list = get_active_symbols()
    if not symbols_list:
        logger.error("No active symbols found in DB.")
        return []

    symbols = [s["symbol"] for s in symbols_list]
    symbols_meta = {s["symbol"]: s for s in symbols_list}
    logger.info(f"Found {len(symbols)} active symbols")

    # Filter by sector
    if sector_filter:
        symbols = [s for s in symbols if symbols_meta[s].get("sector") == sector_filter]
        logger.info(f"Sector filter '{sector_filter}': {len(symbols)} symbols")
        if len(symbols) < min_basket_size:
            logger.error(
                f"Need at least {min_basket_size} symbols in sector. Found {len(symbols)}."
            )
            return []

    # Load prices
    logger.info(f"Loading hourly closes for {len(symbols)} symbols...")
    price_df = get_hourly_closes(symbols, start_date, end_date, data_source)

    if price_df.empty:
        logger.error(
            f"No price data found for data_source='{data_source}' in date range."
        )
        return []

    # Drop symbols with too little data
    min_bars = 30 * 7
    coverage = price_df.count()
    symbols_with_data = coverage[coverage >= min_bars].index.tolist()
    price_df = price_df[symbols_with_data]
    logger.info(f"Symbols with sufficient data (>= 30 days): {len(symbols_with_data)}")

    if len(symbols_with_data) < min_basket_size:
        logger.error(f"Need at least {min_basket_size} symbols with sufficient data.")
        return []

    # min_overlap: require at least 70% coverage of the requested window
    min_overlap_bars = max(180, int(days_back * 0.7))
    logger.info(f"min_overlap_bars={min_overlap_bars} (70% of {days_back} days)")

    # Run discovery
    results_df = discover_baskets(
        price_df=price_df,
        symbols_meta=symbols_meta,
        min_basket_size=min_basket_size,
        max_basket_size=max_basket_size,
        max_pvalue=max_pvalue,
        min_half_life_hours=min_half_life,
        max_half_life_hours=max_half_life,
        min_overlap_bars=min_overlap_bars,
        max_symbols=max_symbols,
        min_corr_prefilter=min_corr_prefilter,
        top_n=top_n,
    )

    if results_df.empty:
        logger.warning("\nNo baskets found matching all criteria.")
        logger.info("Try: --max-pvalue 0.10 --max-half-life 120 --min-basket-size 3")
        return []

    # Print results table
    print("\n" + "=" * 100)
    print(
        f"  TOP {len(results_df)} BASKETS - Ranked by coint strength x correlation x z volatility"
    )
    print("=" * 100)

    display_cols = [
        "name",
        "sector",
        "coint_pvalue",
        "half_life_hours",
        "z_score_window",
        "min_correlation",
        "z_score_abs_mean",
        "current_z_score",
        "rank_score",
    ]

    pd.set_option("display.float_format", "{:.4f}".format)
    pd.set_option("display.max_columns", 20)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 40)

    print(results_df[display_cols].to_string(index=True))

    print("\n" + "=" * 100)
    print("  DETAILS")
    print("=" * 100)
    for i, (_, row) in enumerate(results_df.iterrows()):
        syms = row["symbols"]
        weights = row["hedge_weights"]
        spread_formula = " + ".join(f"{w:.4f}*log({s})" for s, w in zip(syms, weights))
        print(f"\n  #{i + 1}  {row['name']}")
        print(f"       Symbols:      {syms}")
        print(f"       Sector:       {row['sector']}")
        print(f"       Spread:       {spread_formula}")
        print(
            f"       Coint p-val:  {row['coint_pvalue']:.4f}  "
            f"{'[STRONG]' if row['coint_pvalue'] <= 0.01 else '[OK]'}"
        )
        print(
            f"       Half-life:    {row['half_life_hours']:.1f} hours  "
            f"(~{row['half_life_hours'] / 7:.1f} trading days)"
        )
        print(
            f"       Z-window:     {row['z_score_window']} bars  (2 x half-life, max 60)"
        )
        print(f"       Min pairwise corr: {row['min_correlation']:.4f}")
        print(f"       Z abs mean:   {row['z_score_abs_mean']:.4f}  (tradeability)")
        print(f"       Current Z:    {row['current_z_score']:.3f}")
        print(f"       Overlap bars: {row['overlap_bars']}")

    # Upsert to DB
    basket_ids = upsert_baskets(results_df)

    print("\n" + "=" * 100)
    print(
        f"  SAVED {len(basket_ids)} baskets to strategy_engine.basket_registry (is_active=False)"
    )
    for basket_id, (_, row) in zip(basket_ids, results_df.iterrows()):
        print(f"    id={basket_id}  {row['name']}")
    print()
    print("  NEXT STEPS:")
    print(
        "    1. Review half-life and z_score_abs_mean - prefer short half-life, high z abs mean"
    )
    print("    2. Activate a basket: UPDATE strategy_engine.basket_registry")
    print("       SET is_active = TRUE WHERE id = <id>;")
    print("    3. The Prefect flow will start evaluating it on the next hourly cycle")

    return basket_ids


if __name__ == "__main__":
    main()
