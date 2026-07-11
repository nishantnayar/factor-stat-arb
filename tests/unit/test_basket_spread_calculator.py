"""
Unit tests for BasketSpreadCalculator.

Tests spread formula (dot product of weights and log prices), z-score
normalization, edge cases (missing symbol, insufficient window, zero std,
weight/symbol mismatch).
"""

import math

import numpy as np
import pandas as pd
import pytest

from src.services.strategy_engine.baskets.spread_calculator import (
    BasketSpreadCalculator,
)


def _make_prices(values: list, start: str = "2024-01-01") -> pd.Series:
    """Helper: build a price Series with hourly DatetimeIndex."""
    idx = pd.date_range(start, periods=len(values), freq="h")
    return pd.Series(values, index=idx, dtype=float)


def _make_prices_dict(
    syms: list,
    values_per_sym: list,
    start: str = "2024-01-01",
) -> dict:
    """Helper: build {symbol: Series} dict with a shared DatetimeIndex."""
    return {s: _make_prices(v, start) for s, v in zip(syms, values_per_sym)}


@pytest.mark.unit
@pytest.mark.trading
class TestBasketSpreadCalculator:
    """Unit tests for BasketSpreadCalculator."""

    def test_basic_spread_two_assets(self):
        """2-asset basket with weights [1, -1] == log(P1) - log(P2)."""
        prices = _make_prices_dict(
            ["A", "B"],
            [[100.0] * 50, [50.0] * 50],
        )
        calc = BasketSpreadCalculator(["A", "B"], [1.0, -1.0], z_score_window=10)
        spread, _, _ = calc.calculate(prices)

        expected = math.log(100.0) - math.log(50.0)
        assert not spread.empty
        assert all(abs(v - expected) < 1e-10 for v in spread)

    def test_three_asset_spread(self):
        """3-asset basket: spread = w0*log(P0) + w1*log(P1) + w2*log(P2)."""
        p0, p1, p2 = math.e, math.e**2, math.e**3  # logs = 1, 2, 3
        prices = _make_prices_dict(
            ["A", "B", "C"],
            [[p0] * 50, [p1] * 50, [p2] * 50],
        )
        weights = [1.0, -0.5, 0.25]
        calc = BasketSpreadCalculator(["A", "B", "C"], weights, z_score_window=10)
        spread, _, _ = calc.calculate(prices)

        expected = 1.0 * 1 + (-0.5) * 2 + 0.25 * 3  # = 0.75
        assert not spread.empty
        assert all(abs(v - expected) < 1e-10 for v in spread)

    def test_z_score_normalization(self):
        """current_z is a finite float when the spread has variance."""
        np.random.seed(7)
        p0 = list(100 + np.random.randn(100) * 0.5)
        p1 = list(50.0 + np.random.randn(100) * 0.3)
        prices = _make_prices_dict(["A", "B"], [p0, p1])
        calc = BasketSpreadCalculator(["A", "B"], [1.0, -1.0], z_score_window=20)
        _, _, current_z = calc.calculate(prices)

        assert current_z is not None
        assert isinstance(current_z, float)
        assert not math.isnan(current_z)

    def test_insufficient_data_returns_none(self):
        """Fewer bars than z_score_window -> (empty, empty, None)."""
        prices = _make_prices_dict(["A", "B"], [[100.0] * 5, [50.0] * 5])
        calc = BasketSpreadCalculator(["A", "B"], [1.0, -1.0], z_score_window=10)
        spread, z, current_z = calc.calculate(prices)

        assert spread.empty
        assert z.empty
        assert current_z is None

    def test_missing_symbol_returns_none(self):
        """Symbol in calculator not present in prices dict -> (empty, empty, None)."""
        prices = {"A": _make_prices([100.0] * 50)}  # "B" missing
        calc = BasketSpreadCalculator(["A", "B"], [1.0, -1.0], z_score_window=10)
        spread, z, current_z = calc.calculate(prices)

        assert spread.empty
        assert z.empty
        assert current_z is None

    def test_empty_series_returns_none(self):
        """Empty Series for a symbol -> (empty, empty, None)."""
        prices = {
            "A": _make_prices([100.0] * 50),
            "B": pd.Series(dtype=float),
        }
        calc = BasketSpreadCalculator(["A", "B"], [1.0, -1.0], z_score_window=10)
        spread, z, current_z = calc.calculate(prices)

        assert spread.empty
        assert z.empty
        assert current_z is None

    def test_zero_std_returns_none(self):
        """Constant spread (zero rolling std) -> current_z is None, no ZeroDivisionError."""
        prices = _make_prices_dict(["A", "B"], [[100.0] * 50, [100.0] * 50])
        calc = BasketSpreadCalculator(["A", "B"], [1.0, -1.0], z_score_window=20)
        _, _, current_z = calc.calculate(prices)

        assert current_z is None

    def test_current_prices_returns_last(self):
        """current_prices() returns the last value per symbol."""
        prices = _make_prices_dict(
            ["A", "B", "C"],
            [[10.0, 11.0, 12.0], [20.0, 21.0, 22.0], [30.0, 31.0, 32.0]],
        )
        calc = BasketSpreadCalculator(
            ["A", "B", "C"], [1.0, -0.5, 0.25], z_score_window=2
        )
        result = calc.current_prices(prices)

        assert result["A"] == 12.0
        assert result["B"] == 22.0
        assert result["C"] == 32.0

    def test_current_prices_missing_symbol_returns_none(self):
        """current_prices() returns None for a symbol not in prices dict."""
        prices = {"A": _make_prices([100.0, 101.0])}
        calc = BasketSpreadCalculator(["A", "B"], [1.0, -1.0], z_score_window=2)
        result = calc.current_prices(prices)

        assert result["A"] == 101.0
        assert result["B"] is None

    def test_spread_at_snapshot(self):
        """spread_at() = dot(weights, log(prices)) for a single snapshot."""
        weights = [1.0, -0.8, 0.3]
        calc = BasketSpreadCalculator(["A", "B", "C"], weights, z_score_window=10)
        snapshot = {"A": 200.0, "B": 150.0, "C": 100.0}
        result = calc.spread_at(snapshot)

        expected = (
            1.0 * math.log(200.0) + (-0.8) * math.log(150.0) + 0.3 * math.log(100.0)
        )
        assert abs(result - expected) < 1e-10

    def test_symbol_weight_mismatch_raises(self):
        """len(symbols) != len(weights) raises ValueError at construction."""
        with pytest.raises(ValueError):
            BasketSpreadCalculator(["A", "B", "C"], [1.0, -1.0], z_score_window=10)
