"""
Unit tests for PortfolioRiskManager.

All DB access is mocked - no database connection required.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.services.risk_management.portfolio_risk_manager import PortfolioRiskManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pair(id: int, sym1: str, sym2: str) -> MagicMock:
    p = MagicMock()
    p.id = id
    p.symbol1 = sym1
    p.symbol2 = sym2
    return p


def _price_series(n: int = 60, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(100 + rng.standard_normal(n).cumsum())


def _correlated_series(base: pd.Series, r: float) -> pd.Series:
    """Return a series with Pearson correlation ~r to base."""
    noise = pd.Series(np.random.default_rng(42).standard_normal(len(base)))
    beta = r / (1 - r**2) ** 0.5 if abs(r) < 1 else float("inf")
    combined = beta * (base - base.mean()) / base.std() + noise
    return combined


def _make_risk_state(
    peak: float = 100_000.0,
    cb_active: bool = False,
    threshold: float = 0.05,
    cb_triggered_at: datetime | None = None,
) -> MagicMock:
    state = MagicMock()
    state.peak_equity = peak
    state.circuit_breaker_active = cb_active
    state.drawdown_threshold = threshold
    state.circuit_breaker_triggered_at = cb_triggered_at
    state.updated_at = datetime.now(timezone.utc)
    return state


@contextmanager
def _mock_db_transaction(state):
    """Context manager yielding a session whose query().filter_by().first() returns state."""
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = state
    yield session


# ---------------------------------------------------------------------------
# A. Correlation Guard
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCorrelationGuard:
    def setup_method(self):
        self.mgr = PortfolioRiskManager()

    def test_no_active_pairs_always_allowed(self):
        candidate = _make_pair(1, "AAPL", "MSFT")
        allowed, reason = self.mgr.check_correlation_guard(candidate, {}, [])
        assert allowed is True
        assert reason == ""

    def test_blocks_when_correlation_exceeds_threshold(self):
        base = _price_series(60, seed=1)
        # near-perfect correlation
        correlated = base * 0.99 + 0.01

        candidate = _make_pair(1, "A", "B")
        active = _make_pair(2, "C", "D")
        prices_cache = {
            "A": base,
            "B": _price_series(60, seed=99),
            "C": correlated,
            "D": _price_series(60, seed=88),
        }

        allowed, reason = self.mgr.check_correlation_guard(
            candidate, prices_cache, [active]
        )
        assert allowed is False
        assert "A" in reason or "C" in reason

    def test_allows_when_correlation_below_threshold(self):
        rng = np.random.default_rng(0)
        # Four fully independent series - all pairwise correlations will be near 0
        s1 = pd.Series(rng.standard_normal(60))
        s2 = pd.Series(rng.standard_normal(60))
        s3 = pd.Series(rng.standard_normal(60))
        s4 = pd.Series(rng.standard_normal(60))

        candidate = _make_pair(1, "A", "B")
        active = _make_pair(2, "C", "D")
        prices_cache = {"A": s1, "B": s2, "C": s3, "D": s4}

        allowed, _ = self.mgr.check_correlation_guard(
            candidate, prices_cache, [active]
        )
        assert allowed is True

    def test_fail_open_when_insufficient_bars(self):
        # Only 10 bars - below _MIN_CORRELATION_BARS
        short = pd.Series(range(10), dtype=float)
        candidate = _make_pair(1, "A", "B")
        active = _make_pair(2, "C", "D")
        prices_cache = {"A": short, "B": short, "C": short, "D": short}

        allowed, reason = self.mgr.check_correlation_guard(
            candidate, prices_cache, [active]
        )
        assert allowed is True

    def test_skips_self_comparison(self):
        base = _price_series(60, seed=5)
        candidate = _make_pair(7, "X", "Y")
        same = _make_pair(7, "X", "Y")  # same id
        prices_cache = {"X": base, "Y": base}  # would block if checked

        allowed, _ = self.mgr.check_correlation_guard(candidate, prices_cache, [same])
        assert allowed is True

    def test_missing_price_series_fails_open(self):
        candidate = _make_pair(1, "A", "B")
        active = _make_pair(2, "C", "D")
        # prices_cache has nothing
        allowed, _ = self.mgr.check_correlation_guard(candidate, {}, [active])
        assert allowed is True


# ---------------------------------------------------------------------------
# B. Portfolio Drawdown Circuit Breaker
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCircuitBreaker:
    def setup_method(self):
        self.mgr = PortfolioRiskManager()

    def _patch_tx(self, state):
        return patch(
            "src.services.risk_management.portfolio_risk_manager.db_transaction",
            side_effect=lambda: _mock_db_transaction(state),
        )

    def test_seeds_row_when_missing_returns_false(self):
        with patch(
            "src.services.risk_management.portfolio_risk_manager.db_transaction",
            side_effect=lambda: _mock_db_transaction(None),
        ):
            result = self.mgr.update_and_check_drawdown(100_000.0)
        assert result is False

    def test_updates_peak_when_equity_higher(self):
        state = _make_risk_state(peak=90_000.0, cb_active=False)
        with self._patch_tx(state):
            result = self.mgr.update_and_check_drawdown(100_000.0)
        assert result is False
        assert float(state.peak_equity) == 100_000.0
        assert state.circuit_breaker_active is False

    def test_returns_false_within_threshold(self):
        # 2% drawdown, threshold 5% -> no trigger
        state = _make_risk_state(peak=100_000.0, threshold=0.05)
        with self._patch_tx(state):
            result = self.mgr.update_and_check_drawdown(98_000.0)
        assert result is False

    def test_fires_when_drawdown_exceeds_threshold(self):
        # 6% drawdown, threshold 5% -> trigger
        state = _make_risk_state(peak=100_000.0, cb_active=False, threshold=0.05)
        with self._patch_tx(state):
            result = self.mgr.update_and_check_drawdown(94_000.0)
        assert result is True
        assert state.circuit_breaker_active is True

    def test_stays_active_once_triggered(self):
        # Even if equity is only slightly below peak (within threshold),
        # once active the breaker stays on until manually reset.
        state = _make_risk_state(peak=100_000.0, cb_active=True, threshold=0.05)
        with self._patch_tx(state):
            result = self.mgr.update_and_check_drawdown(96_000.0)
        assert result is True

    def test_reset_clears_circuit_breaker(self):
        state = _make_risk_state(cb_active=True)
        with patch(
            "src.services.risk_management.portfolio_risk_manager.db_transaction",
            side_effect=lambda: _mock_db_transaction(state),
        ):
            self.mgr.reset_circuit_breaker()
        assert state.circuit_breaker_active is False
        assert state.circuit_breaker_triggered_at is None

    def test_update_drawdown_threshold_valid(self):
        state = _make_risk_state()
        with patch(
            "src.services.risk_management.portfolio_risk_manager.db_transaction",
            side_effect=lambda: _mock_db_transaction(state),
        ):
            self.mgr.update_drawdown_threshold(0.10)
        assert float(state.drawdown_threshold) == 0.10

    def test_update_drawdown_threshold_invalid_raises(self):
        with pytest.raises(ValueError):
            self.mgr.update_drawdown_threshold(0.0)
        with pytest.raises(ValueError):
            self.mgr.update_drawdown_threshold(1.0)
        with pytest.raises(ValueError):
            self.mgr.update_drawdown_threshold(-0.1)


# ---------------------------------------------------------------------------
# Unrealized P&L helper
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestUnrealizedPnl:
    def _make_trade(self, side, ep1, ep2, qty1, qty2, sym1="A", sym2="B"):
        pair = MagicMock()
        pair.symbol1 = sym1
        pair.symbol2 = sym2
        t = MagicMock()
        t.pair = pair
        t.side = side
        t.entry_price1 = ep1
        t.entry_price2 = ep2
        t.qty1 = qty1
        t.qty2 = qty2
        return t

    def test_long_spread_profit(self):
        trade = self._make_trade("LONG_SPREAD", ep1=100.0, ep2=50.0, qty1=10, qty2=5)
        prices = {"A": pd.Series([110.0]), "B": pd.Series([55.0])}
        # long A: +10*(110-100) = +100, short B: -5*(55-50) = -25 -> net +75
        pnl = PortfolioRiskManager.compute_unrealized_pnl([trade], prices)
        assert abs(pnl - 75.0) < 1e-6

    def test_short_spread_profit(self):
        trade = self._make_trade("SHORT_SPREAD", ep1=100.0, ep2=50.0, qty1=10, qty2=5)
        prices = {"A": pd.Series([95.0]), "B": pd.Series([48.0])}
        # short A: -10*(95-100) = +50, long B: +5*(48-50) = -10 -> net +40
        pnl = PortfolioRiskManager.compute_unrealized_pnl([trade], prices)
        assert abs(pnl - 40.0) < 1e-6

    def test_skips_trade_with_missing_price_series(self):
        trade = self._make_trade("LONG_SPREAD", 100.0, 50.0, 10, 5, sym1="X", sym2="Y")
        prices = {}  # missing X and Y
        pnl = PortfolioRiskManager.compute_unrealized_pnl([trade], prices)
        assert pnl == 0.0

    def test_multiple_trades_summed(self):
        t1 = self._make_trade("LONG_SPREAD", 100.0, 50.0, 10, 5, sym1="A", sym2="B")
        t2 = self._make_trade("SHORT_SPREAD", 200.0, 100.0, 3, 6, sym1="C", sym2="D")
        prices = {
            "A": pd.Series([110.0]),  # +100 on long leg
            "B": pd.Series([55.0]),   # -25 on short leg -> +75
            "C": pd.Series([195.0]),  # -3*(-5) = +15 on short side
            "D": pd.Series([98.0]),   # +6*(-2) = -12 on long side -> +3
        }
        pnl = PortfolioRiskManager.compute_unrealized_pnl([t1, t2], prices)
        assert abs(pnl - 78.0) < 1e-6
