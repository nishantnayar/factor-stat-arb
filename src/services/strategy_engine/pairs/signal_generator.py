"""
Signal Generator

Generates trading signals for a pair based on z-score thresholds.

Signal types:
    LONG_SPREAD:  z_score < -entry_threshold  -> long symbol1, short symbol2
    SHORT_SPREAD: z_score > +entry_threshold  -> short symbol1, long symbol2
    EXIT:         |z_score| < exit_threshold  (from open position)
    STOP_LOSS:    |z_score| > stop_loss_threshold
    EXPIRE:       position held > max_hold_hours (3x half-life)

Rules:
    - No new entry signal if an OPEN trade already exists for the pair
    - EXIT / STOP_LOSS / EXPIRE only generated when a trade is OPEN
    - All signals written to PairSignal table
"""

from datetime import datetime, timezone
from typing import Any, Optional, Tuple

from loguru import logger

from src.shared.database.base import db_readonly_session, db_transaction
from src.shared.database.models.strategy_models import (
    PairRegistry,
    PairSignal,
    PairTrade,
)


class SignalGenerator:
    """
    Generates entry, exit, stop-loss, and expiry signals for a pair.

    Usage:
        gen = SignalGenerator(pair)
        signal = gen.generate(current_z, current_time)
        # signal is a PairSignal ORM object (already persisted) or None
    """

    def __init__(self, pair: Any):  # Any allows SimpleNamespace shim for baskets
        """
        Args:
            pair: PairRegistry row for the pair being evaluated
        """
        self.pair = pair

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        current_z: float,
        current_time: Optional[datetime] = None,
        persist: bool = True,
        open_trade: Optional[Any] = None,
    ) -> Optional[PairSignal]:
        """
        Evaluate z-score and produce a signal if thresholds are crossed.

        Args:
            current_z:    Latest z-score value
            current_time: Timestamp for the signal (default: now UTC)
            persist:      Write signal to DB (set False for backtesting)
            open_trade:   Pre-fetched open trade to evaluate against (only
                          entry_time is read). When None, looked up from
                          PairTrade via self.pair.id. Callers with their own
                          trade table (e.g. baskets/BasketTrade) should pass
                          it explicitly instead of relying on the PairTrade
                          lookup, since self.pair.id may not be a real
                          pair_registry id.

        Returns:
            PairSignal instance if a signal was generated, else None.
            When persist=False, returns an unsaved PairSignal (or None).
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        if open_trade is None:
            open_trade = self._get_open_trade()

        signal_type, reason = self._evaluate(current_z, open_trade, current_time)

        if signal_type is None:
            return None

        sig = PairSignal(
            pair_id=self.pair.id,
            timestamp=current_time,
            signal_type=signal_type,
            z_score=current_z,
            reason=reason,
            acted_on=False,
        )

        if persist:
            with db_transaction() as session:
                session.add(sig)
                session.flush()
                session.refresh(sig)
                # Detach before transaction commit/close so attributes
                # remain usable by callers outside this session.
                session.expunge(sig)
            logger.info(
                f"Signal [{signal_type}] for pair {self.pair.symbol1}/{self.pair.symbol2} "
                f"z={current_z:.3f} - {reason}"
            )

        return sig

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _evaluate(
        self,
        z: float,
        open_trade: Optional[PairTrade],
        current_time: datetime,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Core signal logic.

        Returns:
            (signal_type, reason) or (None, None)
        """
        entry_thr = float(self.pair.entry_threshold)
        exit_thr = float(self.pair.exit_threshold)
        stop_thr = float(self.pair.stop_loss_threshold)
        max_hold = self.pair.max_hold_hours  # 3x half-life

        # ---- Exit conditions (only when a trade is open) ----
        if open_trade is not None:
            hold_hours = _hours_since(open_trade.entry_time, current_time)

            if abs(z) > stop_thr:
                return (
                    "STOP_LOSS",
                    f"|z|={abs(z):.3f} exceeded stop threshold {stop_thr}",
                )

            if max_hold is not None and hold_hours >= max_hold:
                return (
                    "EXPIRE",
                    f"Max hold time {max_hold}h exceeded (held {hold_hours:.1f}h)",
                )

            if abs(z) < exit_thr:
                return (
                    "EXIT",
                    f"|z|={abs(z):.3f} crossed below exit threshold {exit_thr}",
                )

            # No exit trigger - hold position
            return None, None

        # ---- Entry conditions (only when no open trade) ----
        if z < -entry_thr:
            return (
                "LONG_SPREAD",
                f"z={z:.3f} below -{entry_thr} -> "
                f"long {self.pair.symbol1}, short {self.pair.symbol2}",
            )

        if z > entry_thr:
            return (
                "SHORT_SPREAD",
                f"z={z:.3f} above +{entry_thr} -> "
                f"short {self.pair.symbol1}, long {self.pair.symbol2}",
            )

        return None, None

    def _get_open_trade(self) -> Optional[PairTrade]:
        """Return the single open trade for this pair, or None."""
        with db_readonly_session() as session:
            trade = (
                session.query(PairTrade)
                .filter(
                    PairTrade.pair_id == self.pair.id,
                    PairTrade.status == "OPEN",
                )
                .order_by(PairTrade.entry_time.desc())
                .first()
            )
            if trade is not None:
                # Detach from session before returning
                session.expunge(trade)
            return trade


# ------------------------------------------------------------------
# Stateless backtest helper (no DB access)
# ------------------------------------------------------------------


class BacktestSignalGenerator:
    """
    Stateless signal evaluator for backtesting - no DB reads or writes.

    The backtest engine passes the current open-trade state explicitly
    rather than querying the DB, keeping the engine fast and deterministic.

    Usage:
        gen = BacktestSignalGenerator(pair)
        signal_type, reason = gen.evaluate(z, open_trade_entry_time, current_time)
    """

    def __init__(self, pair: PairRegistry):
        self.pair = pair

    def evaluate(
        self,
        z: float,
        open_trade_entry_time: Optional[datetime],
        current_time: datetime,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Args:
            z:                     Current z-score
            open_trade_entry_time: entry_time of open trade (None if no open trade)
            current_time:          Bar timestamp

        Returns:
            (signal_type, reason) or (None, None)
        """
        entry_thr = float(self.pair.entry_threshold)
        exit_thr = float(self.pair.exit_threshold)
        stop_thr = float(self.pair.stop_loss_threshold)
        max_hold = self.pair.max_hold_hours

        if open_trade_entry_time is not None:
            hold_hours = _hours_since(open_trade_entry_time, current_time)

            if abs(z) > stop_thr:
                return "STOP_LOSS", f"|z|={abs(z):.3f} > {stop_thr}"

            if max_hold is not None and hold_hours >= max_hold:
                return "EXPIRE", f"Held {hold_hours:.1f}h >= max {max_hold}h"

            if abs(z) < exit_thr:
                return "EXIT", f"|z|={abs(z):.3f} < {exit_thr}"

            return None, None

        # Entry
        if z < -entry_thr:
            return "LONG_SPREAD", f"z={z:.3f} < -{entry_thr}"
        if z > entry_thr:
            return "SHORT_SPREAD", f"z={z:.3f} > +{entry_thr}"

        return None, None


# ------------------------------------------------------------------
# Utility
# ------------------------------------------------------------------


def _hours_since(entry_time: datetime, current_time: datetime) -> float:
    """Return elapsed hours between two datetimes (timezone-aware safe)."""
    if entry_time.tzinfo is None:
        entry_time = entry_time.replace(tzinfo=timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    delta = current_time - entry_time
    return delta.total_seconds() / 3600
