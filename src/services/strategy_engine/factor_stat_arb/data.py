"""Build aligned return matrices for factor decomposition.

Pulls hourly adjusted closes from data_ingestion.market_data in one query, pivots
to a wide (timestamp x symbol) frame, and derives log returns. Cleaning drops
sparse symbols and misaligned timestamps so PCA/regression get a dense matrix.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.config.database import get_engine

DEFAULT_SOURCE = "yahoo_adjusted"


def load_price_matrix(
    symbols: Optional[Sequence[str]] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    data_source: str = DEFAULT_SOURCE,
    engine: Optional[Engine] = None,
) -> pd.DataFrame:
    """Wide close-price matrix: index = UTC timestamp, columns = symbol.

    symbols=None loads every symbol available for the data source. start/end are
    inclusive bounds on the timestamp (UTC-aware or naive).
    """
    engine = engine or get_engine("trading")
    clauses = ["data_source = :src", "close IS NOT NULL"]
    params: dict = {"src": data_source}
    if symbols is not None:
        clauses.append("symbol = ANY(:symbols)")
        params["symbols"] = list(symbols)
    if start is not None:
        clauses.append("timestamp >= :start")
        params["start"] = start
    if end is not None:
        clauses.append("timestamp <= :end")
        params["end"] = end

    sql = text(
        "SELECT timestamp, symbol, close FROM data_ingestion.market_data "
        f"WHERE {' AND '.join(clauses)}"
    )
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn, params=params)

    if df.empty:
        return pd.DataFrame()

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    wide = df.pivot_table(index="timestamp", columns="symbol", values="close")
    return wide.sort_index()


def to_log_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Log returns from a price matrix (first row drops out)."""
    return np.log(prices.astype(float)).diff().iloc[1:]


def clean_returns(
    returns: pd.DataFrame,
    min_coverage: float = 0.95,
    max_abs_return: Optional[float] = 0.5,
) -> pd.DataFrame:
    """Drop sparse symbols, then misaligned timestamps, into a dense matrix.

    - Keep symbols with at least `min_coverage` of non-null observations.
    - Optionally null out absurd returns (|r| > max_abs_return, e.g. bad ticks)
      before the coverage check so they don't leak into PCA.
    - Drop any remaining rows that still contain NaNs.
    """
    r = returns.copy()
    if max_abs_return is not None:
        r = r.mask(r.abs() > max_abs_return)
    coverage = r.notna().mean(axis=0)
    keep = coverage[coverage >= min_coverage].index
    r = r[keep]
    r = r.dropna(axis=0, how="any")
    return r


def load_return_matrix(
    symbols: Optional[Sequence[str]] = None,
    lookback_bars: Optional[int] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    data_source: str = DEFAULT_SOURCE,
    min_coverage: float = 0.95,
    engine: Optional[Engine] = None,
) -> pd.DataFrame:
    """Convenience: prices -> log returns -> cleaned dense matrix.

    If lookback_bars is given, only the most recent that many rows are kept
    (applied after cleaning so the window is dense).
    """
    prices = load_price_matrix(symbols, start, end, data_source, engine)
    if prices.empty:
        return prices
    returns = clean_returns(to_log_returns(prices), min_coverage=min_coverage)
    if lookback_bars is not None and len(returns) > lookback_bars:
        returns = returns.iloc[-lookback_bars:]
        # re-drop symbols that became sparse within the shorter window
        returns = returns.dropna(axis=1, how="any")
    return returns
