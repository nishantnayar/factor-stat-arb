"""
Unit tests for KellySizer (position_sizer.py).

DB access is mocked via unittest.mock.patch on _load_closed_trades,
so these tests require no database connection.
"""

import math
from unittest.mock import MagicMock, patch

import pytest

from src.services.strategy_engine.pairs.position_sizer import (
    BOOTSTRAP_FRACTION,
    BOOTSTRAP_TRADES,
    MAX_LEG_FRACTION,
    KellySizer,
)


def _make_pair(symbol1: str = "SYM1", symbol2: str = "SYM2") -> MagicMock:
    """Minimal PairRegistry mock."""
    pair = MagicMock()
    pair.id = 1
    pair.symbol1 = symbol1
    pair.symbol2 = symbol2
    return pair


def _make_trade(pnl_pct: float) -> MagicMock:
    """Minimal closed PairTrade mock."""
    t = MagicMock()
    t.pnl_pct = pnl_pct
    return t


def _make_trades(win_pcts: list, loss_pcts: list) -> list:
    """Build a list of trade mocks given winning and losing pnl_pct values."""
    return [_make_trade(p) for p in win_pcts + loss_pcts]


@pytest.mark.unit
@pytest.mark.trading
class TestKellySizer:
    """Unit tests for KellySizer position sizing logic."""

    def test_bootstrap_mode_under_20_trades(self):
        """Fewer than BOOTSTRAP_TRADES closed trades -> 2% fixed fraction per leg."""
        sizer = KellySizer(_make_pair())
        trades = _make_trades([2.0] * 5, [-1.0] * 4)  # 9 trades < 20
        with patch.object(sizer, "_load_closed_trades", return_value=trades):
            fraction = sizer._compute_fraction()
        assert fraction == BOOTSTRAP_FRACTION

    def test_bootstrap_mode_zero_trades(self):
        """Zero trades -> bootstrap fraction."""
        sizer = KellySizer(_make_pair())
        with patch.object(sizer, "_load_closed_trades", return_value=[]):
            fraction = sizer._compute_fraction()
        assert fraction == BOOTSTRAP_FRACTION

    def test_full_kelly_over_20_trades(self):
        """At least 20 trades with positive expectancy -> Kelly fraction > bootstrap."""
        # 15 wins at +3%, 10 losses at -1%
        trades = _make_trades([3.0] * 15, [-1.0] * 10)
        sizer = KellySizer(_make_pair())
        with patch.object(sizer, "_load_closed_trades", return_value=trades):
            fraction = sizer._compute_fraction()
        # win_rate=15/25=0.6, avg_win=3, avg_loss=1
        # kelly = 0.6 - 0.4/3 = 0.6 - 0.133 = 0.467; half_kelly = 0.233
        assert fraction > BOOTSTRAP_FRACTION
        assert fraction <= MAX_LEG_FRACTION * 2

    def test_max_leg_fraction_cap(self):
        """Very high Kelly fraction -> capped at MAX_LEG_FRACTION * 2."""
        # 24 wins at +10%, 1 loss at -0.1% -> kelly would be enormous
        trades = _make_trades([10.0] * 24, [-0.1] * 1)
        sizer = KellySizer(_make_pair())
        with patch.object(sizer, "_load_closed_trades", return_value=trades):
            fraction = sizer._compute_fraction()
        assert fraction == MAX_LEG_FRACTION * 2

    def test_kelly_negative_clamps_to_minimum(self):
        """Negative Kelly (losing edge) -> clamped to 0.01 minimum."""
        # 5 wins at +0.5%, 20 losses at -3% -> very negative Kelly
        trades = _make_trades([0.5] * 5, [-3.0] * 20)
        sizer = KellySizer(_make_pair())
        with patch.object(sizer, "_load_closed_trades", return_value=trades):
            fraction = sizer._compute_fraction()
        assert fraction == 0.01

    def test_all_wins_falls_back_to_bootstrap(self):
        """All winning trades (no losses) -> bootstrap fraction (guard path)."""
        trades = _make_trades([2.0] * 25, [])
        sizer = KellySizer(_make_pair())
        with patch.object(sizer, "_load_closed_trades", return_value=trades):
            fraction = sizer._compute_fraction()
        assert fraction == BOOTSTRAP_FRACTION

    def test_min_qty_one_share(self):
        """Very high price -> at least 1 share per leg returned."""
        sizer = KellySizer(_make_pair())
        with patch.object(sizer, "_load_closed_trades", return_value=[]):
            qty1, qty2 = sizer.calculate_size(
                portfolio_equity=100.0,  # tiny equity
                price1=10_000.0,  # very expensive stock
                price2=10_000.0,
            )
        assert qty1 >= 1
        assert qty2 >= 1

    def test_max_leg_cap_applied_in_calculate_size(self):
        """Quantities must not exceed MAX_LEG_FRACTION * equity / price."""
        equity = 100_000.0
        price = 10.0  # cheap stock -> uncapped qty would be huge
        sizer = KellySizer(_make_pair())
        # Force a very high fraction
        with patch.object(sizer, "_compute_fraction", return_value=1.0):
            qty1, qty2 = sizer.calculate_size(equity, price, price)
        max_qty = math.floor(MAX_LEG_FRACTION * equity / price)
        assert qty1 <= max_qty
        assert qty2 <= max_qty

    def test_qty_proportional_to_equity(self):
        """Doubling portfolio equity should approximately double share quantities."""
        sizer = KellySizer(_make_pair())
        with patch.object(sizer, "_load_closed_trades", return_value=[]):
            qty1_base, qty2_base = sizer.calculate_size(100_000, 50.0, 50.0)
            qty1_double, qty2_double = sizer.calculate_size(200_000, 50.0, 50.0)
        # Allow +/-1 share rounding tolerance
        assert abs(qty1_double - 2 * qty1_base) <= 1
        assert abs(qty2_double - 2 * qty2_base) <= 1

    def test_different_prices_different_quantities(self):
        """Higher-priced symbol gets fewer shares than lower-priced symbol."""
        sizer = KellySizer(_make_pair())
        with patch.object(sizer, "_load_closed_trades", return_value=[]):
            qty1, qty2 = sizer.calculate_size(100_000, price1=200.0, price2=50.0)
        # price1 > price2 so qty1 < qty2
        assert qty1 < qty2
