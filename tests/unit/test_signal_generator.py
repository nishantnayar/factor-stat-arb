"""
Unit tests for BacktestSignalGenerator.

Uses the stateless BacktestSignalGenerator - no DB access required.
A mock PairRegistry is injected with the required threshold attributes.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.services.strategy_engine.pairs.signal_generator import BacktestSignalGenerator


def _make_pair(
    entry_threshold: float = 2.0,
    exit_threshold: float = 0.5,
    stop_loss_threshold: float = 3.0,
    max_hold_hours: float = 24.0,
    symbol1: str = "SYM1",
    symbol2: str = "SYM2",
) -> MagicMock:
    """Build a minimal PairRegistry mock."""
    pair = MagicMock()
    pair.entry_threshold = entry_threshold
    pair.exit_threshold = exit_threshold
    pair.stop_loss_threshold = stop_loss_threshold
    pair.max_hold_hours = max_hold_hours
    pair.symbol1 = symbol1
    pair.symbol2 = symbol2
    return pair


_NOW = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
_ENTRY_TIME = _NOW - timedelta(hours=1)  # 1h ago - well within max_hold_hours


@pytest.mark.unit
@pytest.mark.trading
class TestBacktestSignalGenerator:
    """Tests for BacktestSignalGenerator (stateless, no DB)."""

    def test_long_spread_entry(self):
        """z below -entry_threshold with no open trade -> LONG_SPREAD."""
        gen = BacktestSignalGenerator(_make_pair(entry_threshold=2.0))
        signal, reason = gen.evaluate(
            z=-2.5, open_trade_entry_time=None, current_time=_NOW
        )
        assert signal == "LONG_SPREAD"
        assert reason is not None

    def test_short_spread_entry(self):
        """z above +entry_threshold with no open trade -> SHORT_SPREAD."""
        gen = BacktestSignalGenerator(_make_pair(entry_threshold=2.0))
        signal, reason = gen.evaluate(
            z=2.5, open_trade_entry_time=None, current_time=_NOW
        )
        assert signal == "SHORT_SPREAD"
        assert reason is not None

    def test_no_signal_in_dead_zone_no_trade(self):
        """z within +/-entry_threshold, no open trade -> no signal."""
        gen = BacktestSignalGenerator(_make_pair(entry_threshold=2.0))
        signal, reason = gen.evaluate(
            z=1.0, open_trade_entry_time=None, current_time=_NOW
        )
        assert signal is None
        assert reason is None

    def test_no_entry_when_trade_open(self):
        """z would trigger entry, but open trade exists -> no entry signal."""
        gen = BacktestSignalGenerator(_make_pair(entry_threshold=2.0))
        # z=-2.5 would trigger LONG_SPREAD, but a trade is open
        signal, _ = gen.evaluate(
            z=-2.5, open_trade_entry_time=_ENTRY_TIME, current_time=_NOW
        )
        assert signal != "LONG_SPREAD"

    def test_exit_signal(self):
        """|z| below exit_threshold with open trade -> EXIT."""
        gen = BacktestSignalGenerator(_make_pair(exit_threshold=0.5))
        signal, reason = gen.evaluate(
            z=0.2, open_trade_entry_time=_ENTRY_TIME, current_time=_NOW
        )
        assert signal == "EXIT"
        assert reason is not None

    def test_stop_loss_signal(self):
        """|z| above stop_loss_threshold with open trade -> STOP_LOSS."""
        gen = BacktestSignalGenerator(_make_pair(stop_loss_threshold=3.0))
        signal, reason = gen.evaluate(
            z=3.5, open_trade_entry_time=_ENTRY_TIME, current_time=_NOW
        )
        assert signal == "STOP_LOSS"
        assert reason is not None

    def test_stop_loss_negative_z(self):
        """Negative z beyond stop_loss_threshold -> STOP_LOSS."""
        gen = BacktestSignalGenerator(_make_pair(stop_loss_threshold=3.0))
        signal, _ = gen.evaluate(
            z=-3.5, open_trade_entry_time=_ENTRY_TIME, current_time=_NOW
        )
        assert signal == "STOP_LOSS"

    def test_expire_signal(self):
        """Hold time >= max_hold_hours with no exit/stop trigger -> EXPIRE."""
        gen = BacktestSignalGenerator(
            _make_pair(
                exit_threshold=0.5,
                stop_loss_threshold=3.0,
                max_hold_hours=10.0,
            )
        )
        old_entry = _NOW - timedelta(hours=11)  # held 11h, max is 10h
        signal, reason = gen.evaluate(
            z=1.0, open_trade_entry_time=old_entry, current_time=_NOW
        )
        assert signal == "EXPIRE"
        assert reason is not None

    def test_stop_loss_takes_priority_over_expire(self):
        """If stop_loss threshold exceeded, STOP_LOSS returned before EXPIRE."""
        gen = BacktestSignalGenerator(
            _make_pair(
                stop_loss_threshold=3.0,
                max_hold_hours=1.0,
            )
        )
        old_entry = _NOW - timedelta(hours=2)  # expired AND stop-loss
        signal, _ = gen.evaluate(
            z=3.5, open_trade_entry_time=old_entry, current_time=_NOW
        )
        assert signal == "STOP_LOSS"

    def test_hold_within_limit_no_expire(self):
        """Hold time < max_hold_hours and z in dead zone -> no signal."""
        gen = BacktestSignalGenerator(
            _make_pair(
                exit_threshold=0.5,
                stop_loss_threshold=3.0,
                max_hold_hours=24.0,
            )
        )
        signal, _ = gen.evaluate(
            z=1.0, open_trade_entry_time=_ENTRY_TIME, current_time=_NOW
        )
        assert signal is None

    def test_max_hold_hours_none_no_expire(self):
        """max_hold_hours=None means no expiry logic - long hold never expires."""
        gen = BacktestSignalGenerator(
            _make_pair(
                exit_threshold=0.5,
                stop_loss_threshold=3.0,
                max_hold_hours=None,
            )
        )
        old_entry = _NOW - timedelta(hours=1000)
        signal, _ = gen.evaluate(
            z=1.0, open_trade_entry_time=old_entry, current_time=_NOW
        )
        assert signal is None

    def test_z_exactly_at_entry_threshold_no_signal(self):
        """z == entry_threshold exactly (not >) -> no entry signal."""
        gen = BacktestSignalGenerator(_make_pair(entry_threshold=2.0))
        signal, _ = gen.evaluate(z=2.0, open_trade_entry_time=None, current_time=_NOW)
        assert signal is None

    def test_z_exactly_at_exit_threshold_no_exit(self):
        """z == exit_threshold exactly (not <) -> no EXIT signal."""
        gen = BacktestSignalGenerator(_make_pair(exit_threshold=0.5))
        signal, _ = gen.evaluate(
            z=0.5, open_trade_entry_time=_ENTRY_TIME, current_time=_NOW
        )
        assert signal is None
