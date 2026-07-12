"""Unit tests for factor-basket discovery logic (no DB)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.discover_factor_baskets import (  # noqa: E402
    build_candidate,
    rolling_zscore_abs_mean,
    zscore_window_for,
)
from src.services.strategy_engine.factor_stat_arb.proxy_mapper import ProxyMapper  # noqa: E402


def _mean_reverting_stock(b=0.99, n=2500, beta=0.8, seed=0):
    """Stock = beta*proxy + mean-reverting idiosyncratic returns.

    The residual LEVEL is AR(1) with coefficient b (half-life ln2/-ln b), so the
    OU screen sees a mean-reverting residual.
    """
    rng = np.random.default_rng(seed)
    proxy = rng.normal(0, 0.01, n)
    level = np.zeros(n)
    for t in range(1, n):
        level[t] = b * level[t - 1] + rng.normal(0, 0.003)
    resid_ret = np.diff(level, prepend=level[0])
    idx = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    proxies = pd.DataFrame({"SPY": proxy}, index=idx)
    stock = pd.Series(beta * proxy + resid_ret, index=idx, name="TEST")
    return proxies, stock


@pytest.mark.unit
class TestHelpers:
    def test_zscore_window_bounds(self):
        assert zscore_window_for(10) == 60  # floored
        assert zscore_window_for(1000) == 300  # capped
        assert zscore_window_for(150) == 150

    def test_rolling_zscore_abs_mean_positive(self):
        idx = pd.date_range("2026-01-01", periods=300, freq="h", tz="UTC")
        rng = np.random.default_rng(0)
        level = pd.Series(np.cumsum(rng.normal(0, 0.01, 300)), index=idx)
        z = rolling_zscore_abs_mean(level, 60)
        assert z > 0

    def test_rolling_zscore_flat_series_is_zero(self):
        idx = pd.date_range("2026-01-01", periods=100, freq="h", tz="UTC")
        flat = pd.Series(np.ones(100), index=idx)
        assert rolling_zscore_abs_mean(flat, 30) == 0.0


@pytest.mark.unit
class TestBuildCandidate:
    def _mapper_and_stock(self, **kw):
        proxies, stock = _mean_reverting_stock(**kw)
        return ProxyMapper(proxies), stock

    def test_returns_candidate_for_mean_reverting_stock(self):
        mapper, stock = self._mapper_and_stock(b=0.99)  # half-life ~69h, in band
        cand = build_candidate(
            "TEST",
            None,
            mapper,
            stock,
            min_proxy_r2=0.3,
            min_half_life=48,
            max_half_life=400,
            max_allocation_pct=0.05,
        )
        assert cand is not None
        assert cand["name"] == "FSA_TEST"
        assert 48 <= cand["half_life_hours"] <= 400
        assert cand["hedge_weights"]["TEST"] == 1.0
        assert cand["max_hold_hours"] == pytest.approx(
            cand["half_life_hours"] * 3, abs=0.1
        )

    def test_rejects_low_proxy_r2(self):
        # stock uncorrelated with proxy -> proxy_r2 ~ 0
        rng = np.random.default_rng(5)
        idx = pd.date_range("2026-01-01", periods=1500, freq="h", tz="UTC")
        proxies = pd.DataFrame({"SPY": rng.normal(0, 0.01, 1500)}, index=idx)
        stock = pd.Series(rng.normal(0, 0.01, 1500), index=idx, name="TEST")
        cand = build_candidate(
            "TEST",
            None,
            ProxyMapper(proxies),
            stock,
            min_proxy_r2=0.3,
            min_half_life=48,
            max_half_life=400,
            max_allocation_pct=0.05,
        )
        assert cand is None

    def test_rejects_too_fast_reversion(self):
        # b=0.5 -> residual half-life ~1 bar, below the 48h floor -> rejected
        mapper, stock = self._mapper_and_stock(b=0.5)
        cand = build_candidate(
            "TEST",
            None,
            mapper,
            stock,
            min_proxy_r2=0.3,
            min_half_life=48,
            max_half_life=400,
            max_allocation_pct=0.05,
        )
        assert cand is None
