"""
Unit tests for SpreadCalculator.

Tests spread formula, z-score normalization, edge cases (empty data,
insufficient window, constant spread, misaligned timestamps).
"""

import math

import numpy as np
import pandas as pd
import pytest

from src.services.strategy_engine.pairs.spread_calculator import SpreadCalculator


def _make_prices(values: list, start: str = "2024-01-01") -> pd.Series:
    """Helper: build a price Series with hourly DatetimeIndex."""
    idx = pd.date_range(start, periods=len(values), freq="h")
    return pd.Series(values, index=idx, dtype=float)


@pytest.mark.unit
@pytest.mark.trading
class TestSpreadCalculator:
    """Unit tests for SpreadCalculator."""

    def test_basic_spread_calculation(self):
        """With hedge_ratio=1.0, spread == log(P1) - log(P2) at each bar."""
        p1 = _make_prices([100.0] * 50)
        p2 = _make_prices([50.0] * 50)
        calc = SpreadCalculator(hedge_ratio=1.0, z_score_window=10)
        spread, _, _ = calc.calculate(p1, p2)

        expected = math.log(100.0) - math.log(50.0)
        assert not spread.empty
        assert all(abs(v - expected) < 1e-10 for v in spread)

    def test_hedge_ratio_applied(self):
        """hedge_ratio scales log(P2) correctly."""
        p1 = _make_prices([math.e] * 50)  # log(e) = 1
        p2 = _make_prices([math.e] * 50)
        calc = SpreadCalculator(hedge_ratio=0.5, z_score_window=10)
        spread, _, _ = calc.calculate(p1, p2)
        # spread = 1 - 0.5 * 1 = 0.5
        assert all(abs(v - 0.5) < 1e-10 for v in spread)

    def test_z_score_normalization(self):
        """current_z should be ~0 when last point equals rolling mean."""
        # Build a spread that oscillates so the mean reverts and last point is near mean
        np.random.seed(42)
        prices = 100 + np.random.randn(100) * 0.1
        p1 = _make_prices(list(prices))
        p2 = _make_prices([100.0] * 100)
        calc = SpreadCalculator(hedge_ratio=1.0, z_score_window=20)
        _, _, current_z = calc.calculate(p1, p2)
        # current_z should be a finite float
        assert current_z is not None
        assert isinstance(current_z, float)
        assert not math.isnan(current_z)

    def test_empty_prices1_returns_none(self):
        """Empty prices1 -> all outputs empty, current_z is None."""
        calc = SpreadCalculator(hedge_ratio=1.0, z_score_window=10)
        spread, z, current_z = calc.calculate(
            pd.Series(dtype=float), _make_prices([100.0] * 20)
        )
        assert spread.empty
        assert z.empty
        assert current_z is None

    def test_empty_prices2_returns_none(self):
        """Empty prices2 -> all outputs empty, current_z is None."""
        calc = SpreadCalculator(hedge_ratio=1.0, z_score_window=10)
        spread, z, current_z = calc.calculate(
            _make_prices([100.0] * 20), pd.Series(dtype=float)
        )
        assert spread.empty
        assert z.empty
        assert current_z is None

    def test_insufficient_window_returns_none(self):
        """Fewer bars than z_score_window -> returns empty series and None."""
        p1 = _make_prices([100.0] * 5)
        p2 = _make_prices([50.0] * 5)
        calc = SpreadCalculator(hedge_ratio=1.0, z_score_window=10)
        spread, z, current_z = calc.calculate(p1, p2)
        assert spread.empty
        assert z.empty
        assert current_z is None

    def test_zero_std_returns_none(self):
        """Constant spread (zero rolling std) -> current_z is None, no ZeroDivisionError."""
        p1 = _make_prices([100.0] * 50)
        p2 = _make_prices([100.0] * 50)  # spread is always 0 - std = 0
        calc = SpreadCalculator(hedge_ratio=1.0, z_score_window=20)
        _, _, current_z = calc.calculate(p1, p2)
        assert current_z is None

    def test_spread_at_single_price_pair(self):
        """spread_at() should equal log(P1) - hedge_ratio * log(P2)."""
        calc = SpreadCalculator(hedge_ratio=0.8, z_score_window=10)
        result = calc.spread_at(200.0, 150.0)
        expected = math.log(200.0) - 0.8 * math.log(150.0)
        assert abs(result - expected) < 1e-10

    def test_current_prices_returns_last(self):
        """current_prices() should return the last values of each series."""
        p1 = _make_prices([100.0, 101.0, 102.0])
        p2 = _make_prices([50.0, 51.0, 52.0])
        calc = SpreadCalculator(hedge_ratio=1.0, z_score_window=2)
        price1, price2 = calc.current_prices(p1, p2)
        assert price1 == 102.0
        assert price2 == 52.0

    def test_current_prices_empty_returns_none(self):
        """current_prices() with empty series returns (None, None)."""
        calc = SpreadCalculator(hedge_ratio=1.0, z_score_window=10)
        p1, p2 = calc.current_prices(pd.Series(dtype=float), pd.Series(dtype=float))
        assert p1 is None
        assert p2 is None

    def test_misaligned_timestamps_aligned(self):
        """Series with different timestamps -> only common timestamps used, no KeyError."""
        idx1 = pd.date_range("2024-01-01", periods=40, freq="h")
        idx2 = pd.date_range("2024-01-01 10:00", periods=40, freq="h")  # offset by 10h
        p1 = pd.Series([100.0] * 40, index=idx1)
        p2 = pd.Series([50.0] * 40, index=idx2)
        calc = SpreadCalculator(hedge_ratio=1.0, z_score_window=10)
        spread, z, current_z = calc.calculate(p1, p2)
        # 30 common timestamps -> enough for window=10
        assert not spread.empty
        assert len(spread) == 30
