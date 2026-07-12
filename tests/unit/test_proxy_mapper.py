"""Unit tests for the ETF proxy mapper (no DB)."""

import numpy as np
import pandas as pd
import pytest

from src.services.strategy_engine.factor_stat_arb.proxy_mapper import ProxyMapper


def _proxy_returns(n=500, seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame(
        {"SPY": rng.normal(0, 0.01, n), "XLF": rng.normal(0, 0.012, n)},
        index=idx,
    )


@pytest.mark.unit
class TestProxyMapper:
    def test_recovers_known_betas(self):
        proxies = _proxy_returns()
        rng = np.random.default_rng(1)
        # stock = 0.3*SPY + 0.9*XLF + small noise
        y = (
            0.3 * proxies["SPY"]
            + 0.9 * proxies["XLF"]
            + rng.normal(0, 1e-4, len(proxies))
        )
        y.name = "BANK"
        mapper = ProxyMapper(proxies)
        fit = mapper.fit_symbol(y, proxies=["SPY", "XLF"])
        assert fit.r2 > 0.99
        assert np.isclose(fit.betas["SPY"], 0.3, atol=0.02)
        assert np.isclose(fit.betas["XLF"], 0.9, atol=0.02)

    def test_basket_weights_sign(self):
        proxies = _proxy_returns()
        y = (0.5 * proxies["SPY"] + 0.5 * proxies["XLF"]).rename("X")
        fit = ProxyMapper(proxies).fit_symbol(y, proxies=["SPY", "XLF"])
        w = fit.basket_weights()
        assert w["X"] == 1.0
        assert w["SPY"] < 0 and w["XLF"] < 0  # proxies enter with negative weight

    def test_residual_is_small_for_linear_stock(self):
        proxies = _proxy_returns()
        y = (0.4 * proxies["SPY"] + 0.6 * proxies["XLF"]).rename("X")
        mapper = ProxyMapper(proxies)
        fit = mapper.fit_symbol(y, proxies=["SPY", "XLF"])
        resid = mapper.residual_series(y, fit)
        assert resid.abs().max() < 1e-6

    def test_residual_level_is_cumsum_and_drift_free(self):
        proxies = _proxy_returns()
        rng = np.random.default_rng(3)
        # stock has an alpha drift plus mean-zero idiosyncratic noise
        y = (0.5 * proxies["SPY"] + 5e-4 + rng.normal(0, 0.005, len(proxies))).rename(
            "X"
        )
        mapper = ProxyMapper(proxies)
        fit = mapper.fit_symbol(y, proxies=["SPY"])
        level = mapper.residual_level(y, fit)
        resid = mapper.residual_series(y, fit)
        # level is the cumulative sum of the residual series
        assert np.allclose(level.to_numpy(), resid.cumsum().to_numpy())
        # OLS residuals are mean-zero, so the level has no net drift (ends near 0)
        assert abs(level.iloc[-1]) < abs(level).max()

    def test_proxies_for_uses_broad_plus_sector(self):
        mapper = ProxyMapper(_proxy_returns())
        assert mapper._proxies_for("Financial Services") == ["SPY", "XLF"]

    def test_proxies_for_skips_missing_sector_etf(self):
        # proxy frame has no XLE, so an Energy stock falls back to SPY only
        mapper = ProxyMapper(_proxy_returns())
        assert mapper._proxies_for("Energy") == ["SPY"]

    def test_no_broad_when_disabled(self):
        mapper = ProxyMapper(_proxy_returns(), use_broad=False)
        assert mapper._proxies_for("Financial Services") == ["XLF"]

    def test_raises_without_proxies(self):
        mapper = ProxyMapper(_proxy_returns(), use_broad=False)
        y = pd.Series(np.zeros(500), name="X", index=_proxy_returns().index)
        with pytest.raises(ValueError):
            mapper.fit_symbol(y, sector="Nonexistent Sector")

    def test_raises_on_insufficient_overlap(self):
        proxies = _proxy_returns(n=3)
        y = pd.Series([0.01, 0.02, 0.03], index=proxies.index, name="X")
        with pytest.raises(ValueError):
            ProxyMapper(proxies).fit_symbol(y, proxies=["SPY", "XLF"])

    def test_fit_universe_skips_unfittable(self):
        proxies = _proxy_returns()
        stocks = pd.DataFrame(
            {"A": 0.5 * proxies["SPY"] + 0.5 * proxies["XLF"]},
            index=proxies.index,
        )
        fits = ProxyMapper(proxies).fit_universe(stocks, {"A": "Financial Services"})
        assert "A" in fits and fits["A"].r2 > 0.99
