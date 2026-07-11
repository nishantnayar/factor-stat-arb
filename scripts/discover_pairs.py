"""
Pair Discovery Script

Finds statistically validated pairs for intraday pairs trading from actual DB data.
Runs Engle-Granger cointegration tests on 252 days of hourly close prices,
computes OLS hedge ratios and mean-reversion half-lives, and outputs a ranked
table of the best candidates.

Usage:
    python scripts/discover_pairs.py
    python scripts/discover_pairs.py --min-correlation 0.75 --max-pvalue 0.05
    python scripts/discover_pairs.py --sector Technology
    python scripts/discover_pairs.py --top 10
"""

import asyncio
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, cast

import click
import numpy as np
import pandas as pd
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datetime import timezone

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.shared.database.base import db_readonly_session, db_transaction
from src.shared.database.models.market_data import MarketData
from src.shared.database.models.strategy_models import PairRegistry
from src.shared.database.models.symbols import Symbol

# ---------------------------------------------------------------------------
# Data loading
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
    Only rows where at least 2 symbols have data are kept.
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

    # Pivot: rows = timestamp, columns = symbol
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


def compute_log_returns(prices: pd.Series) -> pd.Series:
    """Compute log returns from a price series."""
    return cast(pd.Series, np.log(prices).diff().dropna())


def pearson_correlation(s1: pd.Series, s2: pd.Series) -> float:
    """Pearson correlation of log returns on the aligned series."""
    r1 = compute_log_returns(s1)
    r2 = compute_log_returns(s2)
    aligned = pd.concat([r1, r2], axis=1).dropna()
    if len(aligned) < 30:
        return 0.0
    return float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1]))


def engle_granger_cointegration(s1: pd.Series, s2: pd.Series) -> Tuple[float, float]:
    """
    Run Engle-Granger cointegration test on log prices.
    Returns (p_value, hedge_ratio).
    hedge_ratio is the OLS beta from regressing log(s1) on log(s2).
    """
    from statsmodels.regression.linear_model import OLS
    from statsmodels.tools import add_constant
    from statsmodels.tsa.stattools import coint

    log_s1 = np.log(s1)
    log_s2 = np.log(s2)
    aligned = pd.concat([log_s1, log_s2], axis=1).dropna()
    if len(aligned) < 60:
        return 1.0, 1.0

    y = aligned.iloc[:, 0].values
    x = aligned.iloc[:, 1].values

    # OLS hedge ratio
    x_const = add_constant(x)
    model = OLS(y, x_const).fit()
    hedge_ratio = float(model.params[1])

    # Engle-Granger test (tests residuals for stationarity)
    _, p_value, _ = coint(y, x)

    return float(p_value), hedge_ratio


def compute_half_life(spread: pd.Series) -> float:
    """
    Compute mean-reversion half-life via AR(1) on delta-spread.
    half_life = -log(2) / log(1 + beta_ar1)  in same units as the series index.
    Returns inf if the series is not mean-reverting.
    """
    from statsmodels.regression.linear_model import OLS
    from statsmodels.tools import add_constant

    spread = spread.dropna()
    if len(spread) < 30:
        return float("inf")

    delta = spread.diff().dropna()
    lagged = spread.shift(1).dropna()

    # Align
    aligned = pd.concat([delta, lagged], axis=1).dropna()
    if len(aligned) < 20:
        return float("inf")

    y = aligned.iloc[:, 0].values
    x = add_constant(aligned.iloc[:, 1].values)
    model = OLS(y, x).fit()
    beta = float(model.params[1])

    if beta >= 0:
        # Not mean-reverting
        return float("inf")

    half_life = -np.log(2) / np.log(1 + beta)
    return float(half_life)


def compute_spread_stats(
    s1: pd.Series,
    s2: pd.Series,
    hedge_ratio: float,
    z_window: int,
) -> Dict:
    """
    Compute spread, z-score stats and current z-score.
    spread = log(P1) - hedge_ratio * log(P2)
    """
    log_s1 = np.log(s1)
    log_s2 = np.log(s2)
    aligned = pd.concat([log_s1, log_s2], axis=1).dropna()
    aligned.columns = ["s1", "s2"]

    spread = aligned["s1"] - hedge_ratio * aligned["s2"]
    roll_mean = spread.rolling(z_window).mean()
    roll_std = spread.rolling(z_window).std()
    z_score = (spread - roll_mean) / roll_std

    return {
        "spread_mean": float(spread.mean()),
        "spread_std": float(spread.std()),
        "current_z_score": float(z_score.iloc[-1]) if not z_score.empty else 0.0,
        "z_score_abs_mean": float(z_score.abs().mean()) if not z_score.empty else 0.0,
    }


# ---------------------------------------------------------------------------
# Pair discovery
# ---------------------------------------------------------------------------


def discover_pairs(
    price_df: pd.DataFrame,
    symbols_meta: Dict[str, Dict],
    min_correlation: float = 0.70,
    max_pvalue: float = 0.05,
    min_half_life_hours: float = 5.0,
    max_half_life_hours: float = 72.0,
    min_overlap_days: int = 60,
    top_n: int = 5,
    sector_filter: Optional[str] = None,
) -> pd.DataFrame:
    """
    Run the full pair discovery pipeline and return a ranked DataFrame.
    """
    symbols = list(price_df.columns)
    results: List[Dict] = []

    # Group by sector if requested
    if sector_filter:
        symbols = [
            s for s in symbols if symbols_meta.get(s, {}).get("sector") == sector_filter
        ]
        logger.info(f"Filtered to {len(symbols)} symbols in sector: {sector_filter}")

    total_pairs = len(symbols) * (len(symbols) - 1) // 2
    logger.info(f"Testing {total_pairs} pairs from {len(symbols)} symbols...")

    checked = 0
    for i, sym1 in enumerate(symbols):
        for sym2 in symbols[i + 1 :]:
            checked += 1
            if checked % 50 == 0:
                logger.info(
                    f"  Progress: {checked}/{total_pairs} pairs checked, {len(results)} candidates so far"
                )

            s1 = price_df[sym1].dropna()
            s2 = price_df[sym2].dropna()

            # Need sufficient overlapping data
            overlap = s1.index.intersection(s2.index)
            overlap_days = len(overlap) / 7  # ~7 hourly bars per trading day
            if overlap_days < min_overlap_days:
                continue

            s1_aligned = s1.loc[overlap]
            s2_aligned = s2.loc[overlap]

            # Step 1: Pearson correlation on log returns
            corr = pearson_correlation(s1_aligned, s2_aligned)
            if abs(corr) < min_correlation:
                continue

            # Step 2: Engle-Granger cointegration
            p_value, hedge_ratio = engle_granger_cointegration(s1_aligned, s2_aligned)
            if p_value > max_pvalue:
                continue

            # Step 3: Compute spread and half-life
            log_s1 = np.log(s1_aligned)
            log_s2 = np.log(s2_aligned)
            spread = log_s1 - hedge_ratio * log_s2
            half_life = compute_half_life(spread)

            if half_life < min_half_life_hours or half_life > max_half_life_hours:
                continue

            # Step 4: Z-score window = 2x half-life, capped at 60 bars to avoid
            # over-smoothing long half-life pairs (which compresses z-scores)
            z_window = min(max(10, int(2 * half_life)), 60)
            spread_stats = compute_spread_stats(
                s1_aligned, s2_aligned, hedge_ratio, z_window
            )

            # Step 5: Composite rank score = cointegration strength x correlation x z volatility
            # z_score_abs_mean measures how far the spread actually moves - pairs with low
            # values are cointegrated but never cross entry thresholds, so they never trade.
            coint_strength = 1 - p_value  # higher is better
            z_abs_mean = spread_stats["z_score_abs_mean"]
            rank_score = coint_strength * abs(corr) * z_abs_mean

            results.append(
                {
                    "symbol1": sym1,
                    "symbol2": sym2,
                    "sector": symbols_meta.get(sym1, {}).get("sector", "Unknown"),
                    "correlation": round(corr, 4),
                    "coint_pvalue": round(p_value, 4),
                    "hedge_ratio": round(hedge_ratio, 4),
                    "half_life_hours": round(half_life, 1),
                    "z_score_window": z_window,
                    "current_z_score": round(spread_stats["current_z_score"], 3),
                    "overlap_days": round(overlap_days, 0),
                    "z_score_abs_mean": round(z_abs_mean, 4),
                    "rank_score": round(rank_score, 4),
                    "name1": symbols_meta.get(sym1, {}).get("name", ""),
                    "name2": symbols_meta.get(sym2, {}).get("name", ""),
                }
            )

    if not results:
        logger.warning("No pairs passed all filters.")
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df.sort_values("rank_score", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)

    ranked = df.head(top_n)
    if not isinstance(ranked, pd.DataFrame):
        raise TypeError("internal: DataFrame.head must return DataFrame")
    return ranked


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.option(
    "--min-correlation",
    default=0.70,
    type=float,
    show_default=True,
    help="Minimum Pearson correlation on log returns",
)
@click.option(
    "--max-pvalue",
    default=0.05,
    type=float,
    show_default=True,
    help="Maximum Engle-Granger cointegration p-value",
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
    "--sector",
    default=None,
    type=str,
    help="Filter to a specific sector (e.g. Technology)",
)
@click.option(
    "--top",
    "top_n",
    default=5,
    type=int,
    show_default=True,
    help="Number of top pairs to display",
)
@click.option(
    "--days-back",
    default=252,
    type=int,
    show_default=True,
    help="Days of hourly history to pull (default: 252 = 1 trading year)",
)
@click.option(
    "--data-source",
    default="yahoo_adjusted",
    show_default=True,
    help="Data source in market_data table",
)
def main(
    min_correlation: float,
    max_pvalue: float,
    min_half_life: float,
    max_half_life: float,
    sector: Optional[str],
    top_n: int,
    days_back: int,
    data_source: str,
) -> None:
    """
    Discover statistically validated pairs for intraday pairs trading.

    Pulls hourly close prices from the DB, filters by correlation and
    Engle-Granger cointegration, computes OLS hedge ratios and mean-reversion
    half-lives, and prints a ranked table of the best candidates.

    After reviewing the results, update config/pairs.yaml with the pair(s) you
    want to trade.

    Examples:

        # Run with defaults (top 5 pairs, 252 days)
        python scripts/discover_pairs.py

        # Technology sector only, stricter correlation
        python scripts/discover_pairs.py --sector Technology --min-correlation 0.80

        # Show top 10 pairs
        python scripts/discover_pairs.py --top 10
    """
    # Configure logging
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
    )

    asyncio.run(
        run_discovery(
            min_correlation=min_correlation,
            max_pvalue=max_pvalue,
            min_half_life=min_half_life,
            max_half_life=max_half_life,
            sector_filter=sector,
            top_n=top_n,
            days_back=days_back,
            data_source=data_source,
        )
    )


async def run_discovery(
    min_correlation: float,
    max_pvalue: float,
    min_half_life: float,
    max_half_life: float,
    sector_filter: Optional[str],
    top_n: int,
    days_back: int,
    data_source: str,
) -> List[Tuple[int, str, str]]:
    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)

    logger.info(f"Pair Discovery - {start_date} to {end_date} ({days_back} days)")
    logger.info(
        f"Filters: correlation >= {min_correlation}, p-value <= {max_pvalue}, "
        f"half-life {min_half_life}-{max_half_life}h"
    )

    # Load symbols
    logger.info("Loading active symbols...")
    symbols_list = get_active_symbols()
    if not symbols_list:
        logger.error("No active symbols found in DB.")
        return []

    symbols = [s["symbol"] for s in symbols_list]
    symbols_meta = {s["symbol"]: s for s in symbols_list}
    logger.info(f"Found {len(symbols)} active symbols")

    # Filter by sector early to reduce DB load
    if sector_filter:
        symbols = [s for s in symbols if symbols_meta[s].get("sector") == sector_filter]
        logger.info(f"Sector filter '{sector_filter}': {len(symbols)} symbols")
        if len(symbols) < 2:
            logger.error("Need at least 2 symbols in sector to find pairs.")
            return []

    # Load prices
    logger.info(f"Loading hourly close prices for {len(symbols)} symbols...")
    price_df = get_hourly_closes(symbols, start_date, end_date, data_source)

    if price_df.empty:
        logger.error(
            f"No price data found for data_source='{data_source}' in date range."
        )
        logger.info(
            "Tip: Check that yahoo_flows.py has run and populated data_ingestion.market_data"
        )
        return []

    # Drop symbols with too little data (< 30 days worth of bars)
    min_bars = 30 * 7
    coverage = price_df.count()
    symbols_with_data = coverage[coverage >= min_bars].index.tolist()
    price_df = price_df[symbols_with_data]

    logger.info(f"Symbols with sufficient data (>= 30 days): {len(symbols_with_data)}")

    if len(symbols_with_data) < 2:
        logger.error("Need at least 2 symbols with sufficient data.")
        return []

    # Run discovery
    results_df = discover_pairs(
        price_df=price_df,
        symbols_meta=symbols_meta,
        min_correlation=min_correlation,
        max_pvalue=max_pvalue,
        min_half_life_hours=min_half_life,
        max_half_life_hours=max_half_life,
        min_overlap_days=60,
        top_n=top_n,
        sector_filter=None,  # already filtered above
    )

    if results_df.empty:
        logger.warning("\nNo pairs found matching all criteria.")
        logger.info(
            "Try relaxing filters: --min-correlation 0.60 --max-pvalue 0.10 --max-half-life 120"
        )
        return []

    # Print results table
    print("\n" + "=" * 90)
    print(
        f"  TOP {len(results_df)} PAIRS - Ranked by cointegration strength x correlation"
    )
    print("=" * 90)

    display_cols = [
        "symbol1",
        "symbol2",
        "sector",
        "correlation",
        "coint_pvalue",
        "hedge_ratio",
        "half_life_hours",
        "z_score_window",
        "z_score_abs_mean",
        "current_z_score",
        "overlap_days",
        "rank_score",
    ]

    pd.set_option("display.float_format", "{:.4f}".format)
    pd.set_option("display.max_columns", 20)
    pd.set_option("display.width", 200)

    print(results_df[display_cols].to_string(index=True))

    print("\n" + "=" * 90)
    print("  DETAILS")
    print("=" * 90)
    for i, (_, row) in enumerate(results_df.iterrows()):
        print(f"\n  #{i + 1}  {row['symbol1']} / {row['symbol2']}")
        print(f"       {row['name1']} / {row['name2']}")
        print(f"       Sector:       {row['sector']}")
        print(f"       Correlation:  {row['correlation']:.4f}")
        print(
            f"       Coint p-val:  {row['coint_pvalue']:.4f}  "
            f"{'[STRONG]' if row['coint_pvalue'] < 0.01 else '[OK]'}"
        )
        print(
            f"       Hedge ratio:  {row['hedge_ratio']:.4f}  "
            f"(spread = log({row['symbol1']}) - {row['hedge_ratio']:.4f} x log({row['symbol2']}))"
        )
        print(
            f"       Half-life:    {row['half_life_hours']:.1f} hours  (~{row['half_life_hours']/7:.1f} trading days)"
        )
        print(
            f"       Z-window:     {row['z_score_window']} bars  (2 x half-life, max 60)"
        )
        print(
            f"       Z abs mean:   {row['z_score_abs_mean']:.4f}  (tradeability signal)"
        )
        print(f"       Current Z:    {row['current_z_score']:.3f}")
        print(f"       Data overlap: {int(row['overlap_days'])} days")

    # ---- Upsert into pair_registry (is_active=False - activate from UI after backtest) ----
    upserted = []
    now = datetime.now(tz=timezone.utc)
    with db_transaction() as session:
        for _, row in results_df.iterrows():
            stmt = (
                pg_insert(PairRegistry)
                .values(
                    symbol1=row["symbol1"],
                    symbol2=row["symbol2"],
                    sector=row.get("sector"),
                    name=f"{row['symbol1']}/{row['symbol2']}",
                    hedge_ratio=float(row["hedge_ratio"]),
                    half_life_hours=float(row["half_life_hours"]),
                    correlation=float(row["correlation"]),
                    coint_pvalue=float(row["coint_pvalue"]),
                    z_score_window=int(row["z_score_window"]),
                    z_score_abs_mean=float(row["z_score_abs_mean"]),
                    rank_score=float(row["rank_score"]),
                    is_active=False,
                    last_validated=now,
                )
                .on_conflict_do_update(
                    constraint="uq_pair_registry_symbols",
                    set_={
                        "hedge_ratio": float(row["hedge_ratio"]),
                        "half_life_hours": float(row["half_life_hours"]),
                        "correlation": float(row["correlation"]),
                        "coint_pvalue": float(row["coint_pvalue"]),
                        "z_score_window": int(row["z_score_window"]),
                        "z_score_abs_mean": float(row["z_score_abs_mean"]),
                        "rank_score": float(row["rank_score"]),
                        "last_validated": now,
                        "updated_at": now,
                    },
                )
                .returning(PairRegistry.id)
            )
            result = session.execute(stmt)
            pair_id = result.scalar_one()
            upserted.append((pair_id, row["symbol1"], row["symbol2"]))

    print("\n" + "=" * 90)
    print(
        f"  SAVED {len(upserted)} pairs to strategy_engine.pair_registry (is_active=False)"
    )
    for pair_id, s1, s2 in upserted:
        print(f"    id={pair_id}  {s1}/{s2}")
    print()
    print("  NEXT STEP:")
    print("    1. Open the Backtest Review page in Streamlit")
    print("    2. Run a backtest for each pair - look for Sharpe > 0.5, drawdown < 15%")
    print("    3. Use the 'Activate' toggle on passing pairs to enable live trading")
    print("=" * 90 + "\n")

    return upserted


if __name__ == "__main__":
    main()
