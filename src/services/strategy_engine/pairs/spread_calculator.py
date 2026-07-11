"""
Spread Calculator

Computes log spread and rolling z-score for a pair of price series.

Spread formula:  spread = log(P1) - hedge_ratio * log(P2)
Z-score:         z = (spread - rolling_mean) / rolling_std

The z-score window is typically 2x the half-life of mean reversion (in hours).
"""

from datetime import datetime
from typing import Optional, Tuple

import numpy as np
import pandas as pd
from loguru import logger


class SpreadCalculator:
    """
    Calculates log spread and rolling z-score for a pair.

    Usage (live cycle):
        calc = SpreadCalculator(hedge_ratio=0.85, z_score_window=40)
        spread_series, z_series, current_z = calc.calculate(prices1, prices2)

    Usage (backtest - in-memory, no DB writes):
        result = calc.calculate(prices1, prices2)
    """

    def __init__(self, hedge_ratio: float, z_score_window: int):
        """
        Args:
            hedge_ratio:    OLS beta - log(P1) - hedge_ratio * log(P2)
            z_score_window: Rolling window size in bars (typically 2x half-life)
        """
        self.hedge_ratio = hedge_ratio
        self.z_score_window = z_score_window

    def calculate(
        self,
        prices1: pd.Series,
        prices2: pd.Series,
    ) -> Tuple[pd.Series, pd.Series, Optional[float]]:
        """
        Compute spread and z-score series from price series.

        Args:
            prices1: Price series for symbol1 (indexed by timestamp)
            prices2: Price series for symbol2 (indexed by timestamp)

        Returns:
            Tuple of (spread_series, z_score_series, current_z_score)
            current_z_score is None if insufficient data for rolling window.
        """
        if prices1.empty or prices2.empty:
            logger.warning("Empty price series passed to SpreadCalculator")
            return pd.Series(dtype=float), pd.Series(dtype=float), None

        # Align on common timestamps
        aligned = pd.concat(
            [prices1.rename("p1"), prices2.rename("p2")], axis=1
        ).dropna()

        if len(aligned) < self.z_score_window:
            logger.warning(
                f"Insufficient data: {len(aligned)} bars < window {self.z_score_window}"
            )
            return pd.Series(dtype=float), pd.Series(dtype=float), None

        log_p1 = np.log(aligned["p1"])
        log_p2 = np.log(aligned["p2"])
        spread = log_p1 - self.hedge_ratio * log_p2

        roll_mean = spread.rolling(window=self.z_score_window, min_periods=self.z_score_window).mean()
        roll_std = spread.rolling(window=self.z_score_window, min_periods=self.z_score_window).std()

        # Avoid division by zero
        z_score = (spread - roll_mean) / roll_std.replace(0, np.nan)

        current_z: Optional[float] = None
        if not z_score.empty and not np.isnan(z_score.iloc[-1]):
            current_z = float(z_score.iloc[-1])

        return spread, z_score, current_z

    def current_prices(
        self,
        prices1: pd.Series,
        prices2: pd.Series,
    ) -> Tuple[Optional[float], Optional[float]]:
        """Return the most recent price for each symbol."""
        p1 = float(prices1.iloc[-1]) if not prices1.empty else None
        p2 = float(prices2.iloc[-1]) if not prices2.empty else None
        return p1, p2

    def spread_at(self, price1: float, price2: float) -> float:
        """Compute instantaneous spread for a single price pair."""
        return float(np.log(price1) - self.hedge_ratio * np.log(price2))
