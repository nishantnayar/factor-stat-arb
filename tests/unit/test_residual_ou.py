"""Unit tests for the residual OU / AR(1) fit (no DB)."""

import math

import numpy as np
import pandas as pd
import pytest

from src.services.strategy_engine.factor_stat_arb.residual_ou import (
    build_log_spread,
    fit_ou,
)


def _ar1_series(b: float, n: int = 4000, sigma: float = 0.02, mu: float = 0.0, seed=0):
    """AR(1): s_t = mu*(1-b) + b*s_{t-1} + eps, with known b (and half-life)."""
    rng = np.random.default_rng(seed)
    s = np.zeros(n)
    s[0] = mu
    c = mu * (1.0 - b)
    for t in range(1, n):
        s[t] = c + b * s[t - 1] + rng.normal(0, sigma)
    idx = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    return pd.Series(s, index=idx, name="spread")


@pytest.mark.unit
class TestFitOU:
    def test_recovers_half_life(self):
        b = 0.9  # half-life = ln2 / -ln(0.9) ~ 6.58 bars
        expected = math.log(2) / -math.log(b)
        ou = fit_ou(_ar1_series(b))
        assert ou.mean_reverting
        assert np.isclose(ou.b, b, atol=0.03)
        assert np.isclose(ou.half_life, expected, rtol=0.15)

    def test_recovers_long_run_mean(self):
        ou = fit_ou(_ar1_series(0.8, mu=1.5))
        assert np.isclose(ou.mu, 1.5, atol=0.1)

    def test_explosive_not_mean_reverting(self):
        # b > 1 (explosive) reliably estimates b_hat > 1 -> not mean-reverting.
        ou = fit_ou(_ar1_series(1.02, n=1000))
        assert not ou.mean_reverting
        assert ou.half_life == math.inf

    def test_random_walk_fails_screen(self):
        # A random walk (b ~ 1) may estimate b_hat slightly < 1 (Dickey-Fuller
        # bias), but its half-life is enormous, so it fails the screen.
        ou = fit_ou(_ar1_series(1.0))
        assert not ou.passes(min_half_life=5, max_half_life=72)

    def test_faster_reversion_shorter_half_life(self):
        fast = fit_ou(_ar1_series(0.5))
        slow = fit_ou(_ar1_series(0.95))
        assert fast.half_life < slow.half_life

    def test_passes_screen_in_bounds(self):
        # b=0.9 -> ~6.6 bars, within 5-72
        ou = fit_ou(_ar1_series(0.9))
        assert ou.passes(min_half_life=5, max_half_life=72, min_r2=0.0)

    def test_fails_screen_when_too_slow(self):
        ou = fit_ou(_ar1_series(0.999))  # very long half-life
        assert not ou.passes(min_half_life=5, max_half_life=72)

    def test_fails_screen_when_not_mean_reverting(self):
        ou = fit_ou(_ar1_series(1.0))
        assert not ou.passes()

    def test_insufficient_obs_raises(self):
        s = pd.Series(np.arange(10.0))
        with pytest.raises(ValueError):
            fit_ou(s, min_obs=30)


@pytest.mark.unit
class TestBuildLogSpread:
    def test_weighted_log_spread(self):
        idx = pd.date_range("2026-01-01", periods=3, freq="h", tz="UTC")
        prices = pd.DataFrame(
            {"AAA": [100.0, 110.0, 121.0], "SPY": [50.0, 55.0, 60.5]}, index=idx
        )
        # spread = 1*log(AAA) - 1*log(SPY)
        spread = build_log_spread(prices, {"AAA": 1.0, "SPY": -1.0})
        expected0 = math.log(100.0) - math.log(50.0)
        assert np.isclose(spread.iloc[0], expected0)
        # AAA and SPY move together here -> spread ~ constant
        assert spread.std() < 1e-9

    def test_ignores_missing_columns(self):
        idx = pd.date_range("2026-01-01", periods=2, freq="h", tz="UTC")
        prices = pd.DataFrame({"AAA": [100.0, 101.0]}, index=idx)
        spread = build_log_spread(prices, {"AAA": 1.0, "MISSING": -0.5})
        assert np.isclose(spread.iloc[0], math.log(100.0))

    def test_raises_when_no_columns_present(self):
        prices = pd.DataFrame({"AAA": [100.0, 101.0]})
        with pytest.raises(ValueError):
            build_log_spread(prices, {"ZZZ": 1.0})
