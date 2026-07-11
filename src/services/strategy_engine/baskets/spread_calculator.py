"""
Basket Spread Calculator

Computes log spread and rolling z-score for an N-stock basket using
Johansen cointegrating weights.

Spread formula:  spread = sum(w_i * log(P_i)) for i in 1..N
Z-score:         z = (spread - rolling_mean) / rolling_std
"""

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from loguru import logger


class BasketSpreadCalculator:
    """
    Calculates basket spread and rolling z-score for N assets.

    Usage:
        calc = BasketSpreadCalculator(
            symbols=["EWBC", "FNB", "COLB"],
            hedge_weights=[1.0, -0.82, -0.43],
            z_score_window=30,
        )
        spread_series, z_series, current_z = calc.calculate(prices)
    """

    def __init__(
        self,
        symbols: List[str],
        hedge_weights: List[float],
        z_score_window: int,
    ):
        """
        Args:
            symbols:        Ordered list of ticker symbols matching hedge_weights.
            hedge_weights:  Johansen cointegrating vector normalized so weights[0]=1.
            z_score_window: Rolling window in bars (typically 2x half-life, max 60).
        """
        if len(symbols) != len(hedge_weights):
            raise ValueError("symbols and hedge_weights must have the same length")
        self.symbols = symbols
        self.hedge_weights = np.array(hedge_weights, dtype=float)
        self.z_score_window = z_score_window

    def calculate(
        self,
        prices: Dict[str, pd.Series],
    ) -> Tuple[pd.Series, pd.Series, Optional[float]]:
        """
        Compute basket spread and z-score series.

        Args:
            prices: Dict mapping symbol -> price Series (indexed by timestamp).

        Returns:
            (spread_series, z_score_series, current_z_score)
            current_z_score is None if insufficient data for the rolling window.
        """
        # Align all series on common timestamps
        frames = {}
        for sym in self.symbols:
            if sym not in prices or prices[sym].empty:
                logger.warning(f"Missing price series for {sym} in basket")
                return pd.Series(dtype=float), pd.Series(dtype=float), None
            frames[sym] = prices[sym]

        aligned = pd.concat(frames, axis=1).dropna()
        aligned.columns = pd.Index(self.symbols)

        if len(aligned) < self.z_score_window:
            logger.warning(
                f"Insufficient data for basket: {len(aligned)} bars < window {self.z_score_window}"
            )
            return pd.Series(dtype=float), pd.Series(dtype=float), None

        log_prices = np.log(aligned.values)
        spread_vals = log_prices @ self.hedge_weights
        spread = pd.Series(spread_vals, index=aligned.index, name="spread")

        roll_mean = spread.rolling(
            window=self.z_score_window, min_periods=self.z_score_window
        ).mean()
        roll_std = spread.rolling(
            window=self.z_score_window, min_periods=self.z_score_window
        ).std()

        z_score = (spread - roll_mean) / roll_std.replace(0, np.nan)

        current_z: Optional[float] = None
        if not z_score.empty and not np.isnan(z_score.iloc[-1]):
            current_z = float(z_score.iloc[-1])

        return spread, z_score, current_z

    def current_prices(
        self, prices: Dict[str, pd.Series]
    ) -> Dict[str, Optional[float]]:
        """Return the most recent price for each symbol in the basket."""
        return {
            sym: (
                float(prices[sym].iloc[-1])
                if sym in prices and not prices[sym].empty
                else None
            )
            for sym in self.symbols
        }

    def spread_at(self, price_snapshot: Dict[str, float]) -> float:
        """Compute instantaneous spread for a single price snapshot."""
        log_vals = np.array([np.log(price_snapshot[s]) for s in self.symbols])
        return float(log_vals @ self.hedge_weights)
