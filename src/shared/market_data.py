"""
Market data access helper for the strategy engine.

get_price_series(symbol, limit) returns the last `limit` hourly close prices
for a symbol as a pd.Series indexed by UTC-aware timestamps.

Data source: data_ingestion.market_data, data_source='yahoo_adjusted'
These are hourly bars loaded by the Yahoo Finance flow (interval='1h',
auto_adjust=True).  The flow runs before each strategy cycle so the DB
always contains bars up to the most recent completed hour.
"""

import logging

import pandas as pd
from sqlalchemy import text

from src.shared.database.base import db_readonly_session

logger = logging.getLogger(__name__)

# Full-universe hourly, split/dividend-adjusted source: 1,038 symbols, ~2.5yr
# of history. The trading-system code had been switched to a newer
# 'yahoo_adjusted_1h' source that was only backfilled for ~19 symbols over a few
# months — too thin for PCA factor discovery. Reverted to the source the module
# docstring already describes. NOTE: whichever source the ongoing Yahoo refresh
# flow writes to (README step 4) must match this. See README setup TODOs.
_DATA_SOURCE = "yahoo_adjusted"


def get_price_series(symbol: str, limit: int = 500) -> pd.Series:
    """
    Return the last `limit` hourly adjusted close prices for `symbol`.

    Returns a pd.Series of float close prices indexed by UTC-aware
    timestamps, sorted oldest-first (same contract as AlpacaClient.get_bars).
    Returns an empty Series if no data exists.
    """
    sql = text(
        """
        SELECT timestamp, close
        FROM data_ingestion.market_data
        WHERE symbol     = :symbol
          AND data_source = :src
          AND close IS NOT NULL
        ORDER BY timestamp DESC
        LIMIT :lim
        """
    )
    try:
        with db_readonly_session() as session:
            rows = session.execute(
                sql,
                {"symbol": symbol, "src": _DATA_SOURCE, "lim": limit},
            ).fetchall()
    except Exception as exc:
        logger.error("DB error fetching price series for %s: %s", symbol, exc)
        return pd.Series(dtype=float, name=symbol)

    if not rows:
        logger.warning("No %s bars in DB for %s", _DATA_SOURCE, symbol)
        return pd.Series(dtype=float, name=symbol)

    # rows are newest-first; reverse so the Series is oldest-first
    timestamps = [r[0] for r in reversed(rows)]
    closes = [float(r[1]) for r in reversed(rows)]

    idx = pd.DatetimeIndex(pd.to_datetime(timestamps, utc=True), name="timestamp")
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    else:
        idx = idx.tz_convert("UTC")
    series = pd.Series(closes, index=idx, name=symbol, dtype=float)

    logger.debug(
        "get_price_series(%s): %d bars  %s -> %s  last_close=%.4f",
        symbol,
        len(series),
        series.index[0],
        series.index[-1],
        series.iloc[-1],
    )
    return series
