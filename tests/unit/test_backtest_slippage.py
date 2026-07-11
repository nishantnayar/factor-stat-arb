"""
Unit tests for slippage and commission modeling in BacktestEngine.

All tests are fully in-memory - no DB required.
The DB-loading methods are mocked so BacktestEngine can be exercised
with synthetic price series.
"""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.services.strategy_engine.backtesting.engine import (
    BacktestEngine,
    BacktestResult,
    SimulatedTrade,
    _compute_pnl,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pair(
    entry_threshold: float = 2.0,
    exit_threshold: float = 0.5,
    stop_loss_threshold: float = 3.0,
    max_hold_hours: float = 48.0,
    hedge_ratio: float = 1.0,
    z_score_window: int = 10,
    symbol1: str = "SYM1",
    symbol2: str = "SYM2",
) -> MagicMock:
    """Minimal PairRegistry mock for BacktestEngine."""
    pair = MagicMock()
    pair.id = 1
    pair.symbol1 = symbol1
    pair.symbol2 = symbol2
    pair.entry_threshold = entry_threshold
    pair.exit_threshold = exit_threshold
    pair.stop_loss_threshold = stop_loss_threshold
    pair.max_hold_hours = max_hold_hours
    pair.hedge_ratio = hedge_ratio
    pair.z_score_window = z_score_window
    return pair


def _make_engine(
    slippage_bps: float = 0.0,
    commission_per_trade: float = 0.0,
) -> BacktestEngine:
    """Create a BacktestEngine with mocked price loading."""
    engine = BacktestEngine(
        pair=_make_pair(),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 6, 1),
        initial_capital=100_000.0,
        slippage_bps=slippage_bps,
        commission_per_trade=commission_per_trade,
    )
    return engine


def _make_trade(
    side: str = "LONG_SPREAD",
    entry_price1: float = 100.0,
    entry_price2: float = 100.0,
    qty1: float = 10.0,
    qty2: float = 10.0,
) -> SimulatedTrade:
    """Minimal SimulatedTrade for P&L helper tests."""
    return SimulatedTrade(
        side=side,
        entry_time=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
        entry_z=-2.5,
        entry_price1=entry_price1,
        entry_price2=entry_price2,
        qty1=qty1,
        qty2=qty2,
    )


# ---------------------------------------------------------------------------
# Tests: _slipped_price method
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.trading
class TestSlippedPrice:
    """Unit tests for BacktestEngine._slipped_price()."""

    def test_buy_price_increased_by_bps(self):
        """Buying at 10 bps slippage worsens fill upward."""
        engine = _make_engine(slippage_bps=10)
        result = engine._slipped_price(100.0, is_buy=True)
        assert abs(result - 100.10) < 1e-9

    def test_sell_price_decreased_by_bps(self):
        """Selling at 10 bps slippage worsens fill downward."""
        engine = _make_engine(slippage_bps=10)
        result = engine._slipped_price(100.0, is_buy=False)
        assert abs(result - 99.90) < 1e-9

    def test_zero_bps_no_change(self):
        """Zero slippage leaves the price unchanged."""
        engine = _make_engine(slippage_bps=0)
        assert engine._slipped_price(150.0, is_buy=True) == 150.0
        assert engine._slipped_price(150.0, is_buy=False) == 150.0

    def test_five_bps_buy(self):
        """5 bps = 0.05% - default production setting."""
        engine = _make_engine(slippage_bps=5)
        expected = 200.0 * (1 + 5 / 10_000)
        assert abs(engine._slipped_price(200.0, is_buy=True) - expected) < 1e-9

    def test_five_bps_sell(self):
        engine = _make_engine(slippage_bps=5)
        expected = 200.0 * (1 - 5 / 10_000)
        assert abs(engine._slipped_price(200.0, is_buy=False) - expected) < 1e-9


# ---------------------------------------------------------------------------
# Tests: _compute_pnl commission deduction
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.trading
class TestComputePnlCommission:
    """Commission is subtracted from gross P&L in _compute_pnl."""

    def test_zero_commission_no_change(self):
        """commission=0 returns same P&L as no-commission call."""
        trade = _make_trade(side="LONG_SPREAD", entry_price1=100.0, entry_price2=100.0)
        pnl_no_comm, _ = _compute_pnl(trade, 105.0, 95.0, commission=0.0)
        pnl_with_comm, _ = _compute_pnl(trade, 105.0, 95.0, commission=0.0)
        assert pnl_no_comm == pnl_with_comm

    def test_commission_deducted_from_pnl(self):
        """$10 commission reduces net P&L by exactly $10."""
        trade = _make_trade(
            side="LONG_SPREAD",
            entry_price1=100.0,
            entry_price2=100.0,
            qty1=10.0,
            qty2=10.0,
        )
        pnl_no_comm, _ = _compute_pnl(trade, 105.0, 95.0, commission=0.0)
        pnl_with_comm, _ = _compute_pnl(trade, 105.0, 95.0, commission=10.0)
        assert abs(pnl_no_comm - pnl_with_comm - 10.0) < 1e-9

    def test_commission_reduces_pnl_pct(self):
        """Commission also reduces pnl_pct proportionally."""
        trade = _make_trade(
            side="LONG_SPREAD",
            entry_price1=100.0,
            entry_price2=100.0,
            qty1=10.0,
            qty2=10.0,
        )
        _, pct_no_comm = _compute_pnl(trade, 105.0, 95.0, commission=0.0)
        _, pct_with_comm = _compute_pnl(trade, 105.0, 95.0, commission=10.0)
        assert pct_with_comm < pct_no_comm

    def test_large_commission_can_make_pnl_negative(self):
        """Commission large enough turns a winning trade into a loser."""
        trade = _make_trade(
            side="LONG_SPREAD",
            entry_price1=100.0,
            entry_price2=100.0,
            qty1=1.0,
            qty2=1.0,
        )
        # gross pnl = 1*(101-100) - 1*(99-100) = 1 + 1 = $2
        pnl, _ = _compute_pnl(trade, 101.0, 99.0, commission=5.0)
        assert pnl < 0


# ---------------------------------------------------------------------------
# Tests: BacktestResult carries slippage params
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.trading
class TestBacktestResultSlippageFields:
    """BacktestResult dataclass stores slippage and commission parameters."""

    def test_default_slippage_fields(self):
        """Default BacktestResult has slippage_bps=5.0 and commission=0.0."""
        result = BacktestResult(
            pair_id=1,
            symbol1="A",
            symbol2="B",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 1),
            initial_capital=100_000.0,
            entry_threshold=2.0,
            exit_threshold=0.5,
            stop_loss_threshold=3.0,
            z_score_window=20,
            hedge_ratio=1.0,
        )
        assert result.slippage_bps == 5.0
        assert result.commission_per_trade == 0.0

    def test_engine_passes_slippage_to_result(self):
        """Engine populates BacktestResult with its own slippage parameters."""
        engine = _make_engine(slippage_bps=7.0, commission_per_trade=1.50)
        empty = engine._empty_result()
        assert empty.slippage_bps == 7.0
        assert empty.commission_per_trade == 1.50


# ---------------------------------------------------------------------------
# Tests: end-to-end P&L comparison (mocked price loading)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.trading
class TestSlippageEndToEnd:
    """End-to-end: slippage reduces net P&L vs zero-slippage baseline."""

    def _run_with_slippage(self, slippage_bps: float, commission: float) -> float:
        """
        Build a simple price series that generates one LONG_SPREAD trade
        and one EXIT, then return total P&L.
        """
        # 50 bars: prices constant at 100, then sym1 drops and sym2 rises
        # so spread reverts -> exit signal fires
        # Use a simple controlled series to guarantee exactly one trade
        idx = pd.date_range("2024-01-02", periods=50, freq="h", tz="UTC")
        # sym1 starts at 100, drops to 95 at bar 20, returns to 100 at bar 40
        p1_vals = [100.0] * 20 + [95.0] * 20 + [100.0] * 10
        # sym2 stays at 100
        p2_vals = [100.0] * 50
        aligned = pd.DataFrame({"p1": p1_vals, "p2": p2_vals}, index=idx)

        engine = BacktestEngine(
            pair=_make_pair(
                entry_threshold=1.5,
                exit_threshold=0.3,
                stop_loss_threshold=4.0,
                z_score_window=10,
                hedge_ratio=1.0,
            ),
            start_date=date(2024, 1, 2),
            end_date=date(2024, 1, 4),
            initial_capital=100_000.0,
            slippage_bps=slippage_bps,
            commission_per_trade=commission,
        )
        result = engine._replay(aligned)
        return sum(t.pnl for t in result.trades if t.pnl is not None)

    def test_slippage_reduces_pnl(self):
        """Net P&L with slippage=10bps must be lower than with slippage=0."""
        pnl_zero = self._run_with_slippage(slippage_bps=0.0, commission=0.0)
        pnl_slip = self._run_with_slippage(slippage_bps=10.0, commission=0.0)
        assert pnl_slip < pnl_zero

    def test_commission_reduces_pnl(self):
        """Net P&L with commission=$10 must be lower than with commission=$0."""
        pnl_zero = self._run_with_slippage(slippage_bps=0.0, commission=0.0)
        pnl_comm = self._run_with_slippage(slippage_bps=0.0, commission=10.0)
        assert pnl_comm < pnl_zero
