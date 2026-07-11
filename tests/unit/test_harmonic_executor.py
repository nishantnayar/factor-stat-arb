"""Unit tests for HarmonicExecutor - no DB or network required."""

from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.strategy_engine.harmonic.gartley_detector import (
    GartleyPattern,
    SwingPoint,
)
from src.services.strategy_engine.harmonic.harmonic_executor import (
    HarmonicExecutor,
    _compute_pnl,
    compute_qty,
)
from src.shared.database.models.strategy_models import HarmonicTrade

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _sw(index: int, price: float) -> SwingPoint:
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return SwingPoint(index=index, price=price, timestamp=ts)


def _make_pattern(direction: str = "bullish", symbol: str = "AAPL") -> GartleyPattern:
    p = GartleyPattern(
        direction=direction,
        X=_sw(0, 100.0),
        A=_sw(1, 150.0),
        B=_sw(2, 119.1),
        C=_sw(3, 138.2),
        D=_sw(4, 110.7),
        stop_loss=108.0,
        targets=[118.0, 128.0],
        symbol=symbol,
    )
    return p


def _make_open_trade(
    side: str = "buy",
    entry_price: float = 110.0,
    qty: int = 10,
    stop_loss: float = 108.0,
    target_1: float = 118.0,
    target_2: float = 128.0,
) -> HarmonicTrade:
    t = HarmonicTrade(
        id=1,
        symbol="AAPL",
        pattern="gartley",
        direction="bullish",
        side=side,
        x_price=100.0,
        a_price=150.0,
        b_price=119.1,
        c_price=138.2,
        d_price=110.7,
        qty=qty,
        entry_price=entry_price,
        entry_time=datetime.now(timezone.utc),
        stop_loss=stop_loss,
        target_1=target_1,
        target_2=target_2,
        status="OPEN",
    )
    return t


def _mock_alpaca(order_id: str = "ord-123") -> MagicMock:
    alpaca = MagicMock()
    alpaca.place_order = AsyncMock(return_value={"id": order_id})
    alpaca.close_position = AsyncMock(return_value={})
    return alpaca


# ---------------------------------------------------------------------------
# compute_qty
# ---------------------------------------------------------------------------
class TestComputeQty:
    def test_normal(self):
        # 2% of 100_000 at $100 = $2000 / $100 = 20 shares
        assert compute_qty(100_000, 100.0) == 20

    def test_zero_price(self):
        assert compute_qty(100_000, 0.0) == 0

    def test_zero_equity(self):
        assert compute_qty(0, 100.0) == 0

    def test_caps_at_max_fraction(self):
        # fraction=0.5 but max is 10% -> 10% of 100_000 at $100 = 100 shares
        qty = compute_qty(100_000, 100.0, fraction=0.5)
        assert qty == 100

    def test_rounds_down(self):
        # 2% of 1000 = $20 at $11 -> 1 share
        assert compute_qty(1_000, 11.0) == 1


# ---------------------------------------------------------------------------
# _compute_pnl
# ---------------------------------------------------------------------------
class TestComputePnl:
    def test_long_profit(self):
        trade = _make_open_trade(side="buy", entry_price=100.0, qty=10)
        pnl, pct = _compute_pnl(trade, exit_price=110.0)
        assert pnl == pytest.approx(100.0)
        assert pct == pytest.approx(10.0)

    def test_short_profit(self):
        trade = _make_open_trade(side="sell", entry_price=100.0, qty=10)
        pnl, pct = _compute_pnl(trade, exit_price=90.0)
        assert pnl == pytest.approx(100.0)
        assert pct == pytest.approx(10.0)

    def test_long_loss(self):
        trade = _make_open_trade(side="buy", entry_price=100.0, qty=10)
        pnl, pct = _compute_pnl(trade, exit_price=95.0)
        assert pnl == pytest.approx(-50.0)

    def test_missing_entry_price(self):
        trade = _make_open_trade()
        trade.entry_price = None
        pnl, pct = _compute_pnl(trade, exit_price=115.0)
        assert pnl is None
        assert pct is None

    def test_missing_exit_price(self):
        trade = _make_open_trade()
        pnl, pct = _compute_pnl(trade, exit_price=None)
        assert pnl is None


# ---------------------------------------------------------------------------
# HarmonicExecutor.check_exit
# ---------------------------------------------------------------------------
class TestCheckExit:
    def test_long_target1(self):
        trade = _make_open_trade(
            side="buy", target_1=118.0, target_2=128.0, stop_loss=108.0
        )
        assert HarmonicExecutor.check_exit(trade, 119.0) == "TARGET_1"

    def test_long_target2(self):
        trade = _make_open_trade(
            side="buy", target_1=118.0, target_2=128.0, stop_loss=108.0
        )
        assert HarmonicExecutor.check_exit(trade, 130.0) == "TARGET_2"

    def test_long_stop(self):
        trade = _make_open_trade(
            side="buy", target_1=118.0, target_2=128.0, stop_loss=108.0
        )
        assert HarmonicExecutor.check_exit(trade, 107.0) == "STOP_LOSS"

    def test_long_no_signal(self):
        trade = _make_open_trade(
            side="buy", target_1=118.0, target_2=128.0, stop_loss=108.0
        )
        assert HarmonicExecutor.check_exit(trade, 113.0) is None

    def test_short_target1(self):
        trade = _make_open_trade(
            side="sell",
            entry_price=150.0,
            target_1=140.0,
            target_2=130.0,
            stop_loss=158.0,
        )
        assert HarmonicExecutor.check_exit(trade, 139.0) == "TARGET_1"

    def test_short_stop(self):
        trade = _make_open_trade(
            side="sell",
            entry_price=150.0,
            target_1=140.0,
            target_2=130.0,
            stop_loss=158.0,
        )
        assert HarmonicExecutor.check_exit(trade, 159.0) == "STOP_LOSS"


# ---------------------------------------------------------------------------
# HarmonicExecutor.open_trade
# ---------------------------------------------------------------------------
class TestOpenTrade:
    @pytest.mark.asyncio
    async def test_open_bullish_places_buy(self):
        alpaca = _mock_alpaca("ord-abc")
        executor = HarmonicExecutor(alpaca)
        pattern = _make_pattern("bullish", "AAPL")

        with patch(
            "src.services.strategy_engine.harmonic.harmonic_executor.db_transaction"
        ) as mock_tx:
            mock_session = MagicMock()
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)

            trade = await executor.open_trade(pattern, qty=10, current_price=110.5)

        alpaca.place_order.assert_awaited_once_with(
            symbol="AAPL", qty=10, side="buy", order_type="market", time_in_force="day"
        )
        assert trade is not None
        assert trade.side == "buy"
        assert trade.symbol == "AAPL"
        assert trade.order_id == "ord-abc"

    @pytest.mark.asyncio
    async def test_open_bearish_places_sell(self):
        alpaca = _mock_alpaca()
        executor = HarmonicExecutor(alpaca)
        pattern = _make_pattern("bearish", "TSLA")

        with patch(
            "src.services.strategy_engine.harmonic.harmonic_executor.db_transaction"
        ) as mock_tx:
            mock_session = MagicMock()
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)

            trade = await executor.open_trade(pattern, qty=5)

        alpaca.place_order.assert_awaited_once()
        call_kwargs = alpaca.place_order.call_args.kwargs
        assert call_kwargs["side"] == "sell"

    @pytest.mark.asyncio
    async def test_zero_qty_skipped(self):
        alpaca = _mock_alpaca()
        executor = HarmonicExecutor(alpaca)
        pattern = _make_pattern()

        trade = await executor.open_trade(pattern, qty=0)

        alpaca.place_order.assert_not_awaited()
        assert trade is None

    @pytest.mark.asyncio
    async def test_alpaca_error_returns_none(self):
        alpaca = MagicMock()
        alpaca.place_order = AsyncMock(side_effect=RuntimeError("API down"))
        executor = HarmonicExecutor(alpaca)
        pattern = _make_pattern()

        trade = await executor.open_trade(pattern, qty=10)

        assert trade is None

    @pytest.mark.asyncio
    async def test_missing_symbol_raises(self):
        alpaca = _mock_alpaca()
        executor = HarmonicExecutor(alpaca)
        pattern = _make_pattern()
        pattern.symbol = ""

        with pytest.raises(ValueError, match="symbol"):
            await executor.open_trade(pattern, qty=10)


# ---------------------------------------------------------------------------
# HarmonicExecutor.close_trade
# ---------------------------------------------------------------------------
class TestCloseTrade:
    @pytest.mark.asyncio
    async def test_close_updates_db(self):
        alpaca = _mock_alpaca()
        executor = HarmonicExecutor(alpaca)
        trade = _make_open_trade(entry_price=110.0, qty=10)

        mock_db_trade = _make_open_trade(entry_price=110.0, qty=10)

        with patch(
            "src.services.strategy_engine.harmonic.harmonic_executor.db_transaction"
        ) as mock_tx:
            mock_session = MagicMock()
            mock_session.query.return_value.filter_by.return_value.first.return_value = (
                mock_db_trade
            )
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)

            result = await executor.close_trade(
                trade, exit_price=118.0, exit_reason="TARGET_1"
            )

        assert result is True
        alpaca.close_position.assert_awaited_once_with("AAPL")
        assert mock_db_trade.exit_reason == "TARGET_1"
        assert mock_db_trade.status == "CLOSED"

    @pytest.mark.asyncio
    async def test_stop_loss_sets_stopped_status(self):
        alpaca = _mock_alpaca()
        executor = HarmonicExecutor(alpaca)
        trade = _make_open_trade()
        mock_db_trade = _make_open_trade()

        with patch(
            "src.services.strategy_engine.harmonic.harmonic_executor.db_transaction"
        ) as mock_tx:
            mock_session = MagicMock()
            mock_session.query.return_value.filter_by.return_value.first.return_value = (
                mock_db_trade
            )
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)

            await executor.close_trade(trade, exit_price=107.0, exit_reason="STOP_LOSS")

        assert mock_db_trade.status == "STOPPED"

    @pytest.mark.asyncio
    async def test_alpaca_error_returns_false(self):
        alpaca = MagicMock()
        alpaca.close_position = AsyncMock(side_effect=RuntimeError("network"))
        executor = HarmonicExecutor(alpaca)
        trade = _make_open_trade()

        result = await executor.close_trade(trade, exit_price=115.0)

        assert result is False


# ---------------------------------------------------------------------------
# HarmonicExecutor.emergency_stop
# ---------------------------------------------------------------------------
class TestEmergencyStop:
    @pytest.mark.asyncio
    async def test_marks_trade_stopped(self):
        alpaca = _mock_alpaca()
        executor = HarmonicExecutor(alpaca)
        trade = _make_open_trade()
        mock_db_trade = _make_open_trade()

        with patch(
            "src.services.strategy_engine.harmonic.harmonic_executor.db_transaction"
        ) as mock_tx:
            mock_session = MagicMock()
            mock_session.query.return_value.filter_by.return_value.first.return_value = (
                mock_db_trade
            )
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)

            await executor.emergency_stop(trade)

        assert mock_db_trade.status == "STOPPED"
        assert mock_db_trade.exit_reason == "EMERGENCY_STOP"

    @pytest.mark.asyncio
    async def test_alpaca_error_does_not_raise(self):
        alpaca = MagicMock()
        alpaca.close_position = AsyncMock(side_effect=RuntimeError("already flat"))
        executor = HarmonicExecutor(alpaca)
        trade = _make_open_trade()

        with patch(
            "src.services.strategy_engine.harmonic.harmonic_executor.db_transaction"
        ) as mock_tx:
            mock_session = MagicMock()
            mock_session.query.return_value.filter_by.return_value.first.return_value = (
                _make_open_trade()
            )
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)

            # must not raise
            await executor.emergency_stop(trade)
