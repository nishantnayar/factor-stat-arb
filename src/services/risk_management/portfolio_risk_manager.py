"""
Portfolio Risk Manager

Three controls applied before every new trade entry:

    A. Correlation Guard
       Blocks a new pair entry if any leg of the candidate pair has Pearson |r| >
       threshold with any leg of an already-open pair (using recent price series).

    B. Portfolio Drawdown Circuit Breaker
       Tracks peak portfolio equity in DB.  If current total equity drops more than
       drawdown_threshold below peak, marks circuit_breaker_active = True and blocks
       all new entries until manually reset via the API.

    C. Per-pair Allocation Cap
       Applied inside KellySizer via pair.max_allocation_pct - not implemented here.
       This class exposes helper methods used by the strategy and the API.

Usage (inside PairsStrategy.run_cycle):
    risk_mgr = PortfolioRiskManager()
    circuit_open = risk_mgr.update_and_check_drawdown(total_equity)
    allowed, reason = risk_mgr.check_correlation_guard(
        candidate, prices_cache, active_open_pairs
    )
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from loguru import logger

from src.shared.database.base import db_transaction
from src.shared.database.models.strategy_models import PairRegistry, PortfolioRiskState

# Minimum bars required to trust a Pearson correlation estimate
_MIN_CORRELATION_BARS = 30
# Default cross-pair correlation threshold above which an entry is blocked
DEFAULT_CORRELATION_THRESHOLD = 0.85


class PortfolioRiskManager:
    """
    Stateless helper - all state is persisted in portfolio_risk_state (single DB row).

    Instantiate once per Prefect flow cycle; methods read/write the DB row directly.
    """

    # ------------------------------------------------------------------
    # A. Correlation Guard
    # ------------------------------------------------------------------

    def check_correlation_guard(
        self,
        candidate: PairRegistry,
        prices_cache: Dict[str, pd.Series],
        active_open_pairs: List[PairRegistry],
        threshold: float = DEFAULT_CORRELATION_THRESHOLD,
    ) -> Tuple[bool, str]:
        """
        Check whether the candidate pair is too correlated with any already-open pair.

        Compares all four leg combinations:
            (candidate.sym1, active.sym1), (candidate.sym1, active.sym2),
            (candidate.sym2, active.sym1), (candidate.sym2, active.sym2)

        Returns:
            (True, "")            - safe to enter
            (False, reason_str)   - blocked; reason_str explains which pair/leg
                                    caused it
        """
        if not active_open_pairs:
            return True, ""

        c1 = candidate.symbol1
        c2 = candidate.symbol2

        for active in active_open_pairs:
            # Skip self-comparison (shouldn't happen but be safe)
            if active.id == candidate.id:
                continue

            for c_sym in (c1, c2):
                for a_sym in (active.symbol1, active.symbol2):
                    corr = self._pearson(
                        prices_cache.get(c_sym), prices_cache.get(a_sym)
                    )
                    if corr is None:
                        # Insufficient data - fail open (allow trade)
                        logger.debug(
                            f"Correlation guard: insufficient data for "
                            f"{c_sym}/{a_sym}, allowing entry"
                        )
                        continue
                    if abs(corr) > threshold:
                        reason = (
                            f"{c_sym} vs {a_sym} "
                            f"(pair {active.symbol1}/{active.symbol2})"
                            f" r={corr:.3f} > threshold {threshold:.2f}"
                        )
                        logger.warning(f"Correlation guard blocked {c1}/{c2}: {reason}")
                        return False, reason

        return True, ""

    @staticmethod
    def _pearson(s1: Optional[pd.Series], s2: Optional[pd.Series]) -> Optional[float]:
        """
        Compute Pearson correlation on the aligned tail of two price series.
        Returns None if either series is missing or has too few overlapping bars.
        """
        if s1 is None or s2 is None or s1.empty or s2.empty:
            return None

        aligned = pd.concat([s1.rename("a"), s2.rename("b")], axis=1).dropna()
        if len(aligned) < _MIN_CORRELATION_BARS:
            return None

        a = np.asarray(aligned["a"].to_numpy(), dtype=np.float64)
        b = np.asarray(aligned["b"].to_numpy(), dtype=np.float64)
        corr_matrix = np.corrcoef(a, b)
        return float(corr_matrix[0, 1])

    # ------------------------------------------------------------------
    # B. Portfolio Drawdown Circuit Breaker
    # ------------------------------------------------------------------

    def update_and_check_drawdown(self, current_equity: float) -> bool:
        """
        Update peak equity and check whether the circuit breaker should fire.

        - If current_equity > peak -> update peak, ensure circuit breaker is OFF.
        - If current_equity < peak x (1 - threshold) -> activate circuit breaker.
        - If circuit breaker is already active -> keep it active (manual reset
          required).

        Returns True if new entries should be blocked (circuit breaker active).
        """
        with db_transaction() as session:
            state = session.query(PortfolioRiskState).filter_by(id=1).first()
            if state is None:
                # Seed row if migration hasn't been applied yet
                state = PortfolioRiskState(
                    id=1,
                    peak_equity=current_equity,
                    circuit_breaker_active=False,
                    drawdown_threshold=0.05,
                )
                session.add(state)
                return False

            peak = float(state.peak_equity)
            threshold = float(state.drawdown_threshold)

            if current_equity > peak:
                state.peak_equity = current_equity
                state.circuit_breaker_active = False
                state.updated_at = datetime.now(timezone.utc)
                logger.debug(f"Portfolio peak updated: ${current_equity:,.2f}")
                return False

            if state.circuit_breaker_active:
                logger.warning(
                    f"Circuit breaker ACTIVE - blocking new entries "
                    f"(equity ${current_equity:,.2f}, peak ${peak:,.2f})"
                )
                return True

            drawdown = (peak - current_equity) / peak if peak > 0 else 0.0
            if drawdown > threshold:
                state.circuit_breaker_active = True
                state.circuit_breaker_triggered_at = datetime.now(timezone.utc)
                state.updated_at = datetime.now(timezone.utc)
                logger.error(
                    f"Circuit breaker TRIGGERED - drawdown {drawdown:.1%} "
                    f"exceeds threshold {threshold:.1%} "
                    f"(equity ${current_equity:,.2f}, peak ${peak:,.2f})"
                )
                return True

            state.updated_at = datetime.now(timezone.utc)
            return False

    def reset_circuit_breaker(self) -> None:
        """Manually reset the circuit breaker (called from API endpoint)."""
        with db_transaction() as session:
            state = session.query(PortfolioRiskState).filter_by(id=1).first()
            if state:
                state.circuit_breaker_active = False
                state.circuit_breaker_triggered_at = None
                state.updated_at = datetime.now(timezone.utc)
                logger.info("Circuit breaker manually reset")

    def update_drawdown_threshold(self, threshold: float) -> None:
        """Update the drawdown threshold (0 < threshold < 1)."""
        if not 0 < threshold < 1:
            raise ValueError(f"drawdown_threshold must be in (0, 1), got {threshold}")
        with db_transaction() as session:
            state = session.query(PortfolioRiskState).filter_by(id=1).first()
            if state:
                state.drawdown_threshold = threshold
                state.updated_at = datetime.now(timezone.utc)

    def get_state(self) -> Optional[dict]:
        """Return current risk state as a dict (for API/UI)."""
        from src.shared.database.base import db_readonly_session

        with db_readonly_session() as session:
            state = session.query(PortfolioRiskState).filter_by(id=1).first()
            return state.to_dict() if state else None

    # ------------------------------------------------------------------
    # Portfolio P&L helper (used by strategy to compute total equity)
    # ------------------------------------------------------------------

    @staticmethod
    def compute_unrealized_pnl(
        open_trades: list,
        prices_cache: Dict[str, pd.Series],
        pair_lookup: Optional[Dict[int, PairRegistry]] = None,
    ) -> float:
        """
        Sum unrealized P&L across all open trades using current prices from the cache.

        open_trades: list of PairTrade ORM objects with status='OPEN'
        prices_cache: {symbol: pd.Series of recent close prices}

        Returns total unrealized P&L in dollars.
        """
        total = 0.0
        for trade in open_trades:
            # open_trades are detached ORM instances in live flow runs.
            # Avoid lazy-loading trade.pair on detached objects.
            pair = pair_lookup.get(trade.pair_id) if pair_lookup else getattr(trade, "pair", None)
            if pair is None:
                logger.debug(
                    "compute_unrealized_pnl: missing pair metadata for pair_id=%s",
                    getattr(trade, "pair_id", "unknown"),
                )
                continue
            p1_series = prices_cache.get(pair.symbol1)
            p2_series = prices_cache.get(pair.symbol2)
            if p1_series is None or p1_series.empty:
                continue
            if p2_series is None or p2_series.empty:
                continue

            current_p1 = float(p1_series.iloc[-1])
            current_p2 = float(p2_series.iloc[-1])
            entry_p1 = float(trade.entry_price1) if trade.entry_price1 else 0.0
            entry_p2 = float(trade.entry_price2) if trade.entry_price2 else 0.0
            qty1 = float(trade.qty1)
            qty2 = float(trade.qty2)

            d1 = current_p1 - entry_p1
            d2 = current_p2 - entry_p2

            if trade.side == "LONG_SPREAD":
                pnl = qty1 * d1 - qty2 * d2
            else:  # SHORT_SPREAD
                pnl = -qty1 * d1 + qty2 * d2

            total += pnl

        return total
