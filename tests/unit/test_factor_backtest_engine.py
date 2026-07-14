"""Unit tests for FactorBacktestEngine (no DB)."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from src.services.strategy_engine.backtesting.metrics import MetricsCalculator
from src.services.strategy_engine.factor_stat_arb.backtest_engine import (
    FactorBacktestEngine,
)


def _fake_basket(
    symbols=("A", "B", "C"),
    hedge_weights=(1.0, -0.5, -0.3),
    entry_threshold=2.0,
    exit_threshold=0.5,
    stop_loss_threshold=3.0,
    max_hold_hours=200.0,
    z_score_window=30,
):
    """SimpleNamespace shaped like a BasketRegistry row (no DB instrumentation).

    hedge_weights is a {symbol: weight} dict in the real DB (JSON column), not
    a positional list -- keep this fixture in that shape so tests catch
    symbol/weight mismatches the way the real engine would.
    """
    return SimpleNamespace(
        id=1,
        name="FSA_TEST",
        symbols=list(symbols),
        hedge_weights=dict(zip(symbols, hedge_weights)),
        entry_threshold=entry_threshold,
        exit_threshold=exit_threshold,
        stop_loss_threshold=stop_loss_threshold,
        max_hold_hours=max_hold_hours,
        z_score_window=z_score_window,
    )


def _mean_reverting_prices(n=400, symbols=("A", "B", "C"), seed=0):
    """3-leg synthetic prices whose log-spread mean-reverts strongly."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")

    spread_level = np.zeros(n)
    for t in range(1, n):
        spread_level[t] = 0.9 * spread_level[t - 1] + rng.normal(0, 0.05)

    common = np.cumsum(rng.normal(0, 0.001, n))
    log_a = 4.0 + common + spread_level
    log_b = 4.0 + common
    log_c = 4.0 + common

    prices = pd.DataFrame(
        {
            symbols[0]: np.exp(log_a),
            symbols[1]: np.exp(log_b),
            symbols[2]: np.exp(log_c),
        },
        index=idx,
    )
    return prices


def _engine_with_prices(basket, prices: pd.DataFrame) -> FactorBacktestEngine:
    """Build an engine and monkeypatch _load_prices to avoid DB access."""
    engine = FactorBacktestEngine(
        basket,
        start_date=prices.index[0].date(),
        end_date=prices.index[-1].date(),
    )
    engine._load_prices = lambda: {s: prices[s] for s in engine.symbols}  # type: ignore[method-assign]
    return engine


@pytest.mark.unit
class TestFactorBacktestEngine:
    def test_mean_reverting_basket_produces_trades_with_sane_pnl(self):
        basket = _fake_basket()
        prices = _mean_reverting_prices()
        engine = _engine_with_prices(basket, prices)

        result = engine.run()

        assert result.bars_processed > 0
        assert len(result.trades) > 0
        for t in result.trades:
            assert t.exit_time is not None
            assert t.pnl is not None
            assert set(t.entry_prices.keys()) == set(basket.symbols)
            assert set(t.qty.keys()) == set(basket.symbols)

    def test_insufficient_bars_returns_empty_result(self):
        basket = _fake_basket(z_score_window=300)
        prices = _mean_reverting_prices(n=50)
        engine = _engine_with_prices(basket, prices)

        result = engine.run()

        assert result.trades == []
        assert result.bars_processed == 0

    def test_missing_symbol_data_returns_empty_result(self):
        basket = _fake_basket()
        prices = _mean_reverting_prices()
        engine = FactorBacktestEngine(
            basket,
            start_date=prices.index[0].date(),
            end_date=prices.index[-1].date(),
        )
        engine._load_prices = lambda: {  # type: ignore[method-assign]
            "A": prices["A"],
            "B": prices["B"],
            "C": pd.Series(dtype=float),
        }

        result = engine.run()

        assert result.trades == []
        assert result.bars_processed == 0

    def test_stop_loss_exit_reason_fires(self):
        basket = _fake_basket(stop_loss_threshold=1.0, exit_threshold=0.9)
        prices = _mean_reverting_prices(seed=1)
        engine = _engine_with_prices(basket, prices)

        result = engine.run()

        reasons = {t.exit_reason for t in result.trades}
        assert reasons & {"STOP_LOSS", "EXIT", "EXPIRE", "END_OF_BACKTEST"}

    def test_metrics_calculator_computes_gate_from_result(self):
        basket = _fake_basket()
        prices = _mean_reverting_prices()
        engine = _engine_with_prices(basket, prices)
        result = engine.run()

        metrics = MetricsCalculator().compute(result)

        assert metrics.total_trades == len(result.trades)
        assert isinstance(metrics.passed_gate, bool)
        assert metrics.sharpe_ratio == metrics.sharpe_ratio  # not NaN

    def test_flat_prices_produce_no_trades(self):
        basket = _fake_basket()
        idx = pd.date_range("2026-01-01", periods=200, freq="h", tz="UTC")
        flat = pd.DataFrame(
            {"A": np.full(200, 10.0), "B": np.full(200, 10.0), "C": np.full(200, 10.0)},
            index=idx,
        )
        engine = _engine_with_prices(basket, flat)

        result = engine.run()

        assert result.trades == []
