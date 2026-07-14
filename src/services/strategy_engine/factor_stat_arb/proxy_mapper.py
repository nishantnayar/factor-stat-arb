"""Map each stock to a small basket of tradable ETF proxies via OLS.

For a stock, regress its returns on a broad-market ETF (SPY) plus its sector ETF.
The fitted betas are the hedge weights that make the residual spread tradable and
interpretable ("this name trades like 0.7 XLF + 0.3 SPY"). The residual series is
what the OU/mean-reversion step and BasketSpreadCalculator operate on.

Regressing returns is equivalent to regressing log-price changes, so the betas are
exactly the proxy weights for a log-price spread:
    spread = log(P_stock) - sum(beta_i * log(P_proxy_i)).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from src.services.strategy_engine.factor_stat_arb.proxies import (
    BROAD_ETF,
    SECTOR_ETFS,
    sector_etf,
)


@dataclass
class ProxyFit:
    """Result of regressing one stock on its ETF proxies."""

    symbol: str
    proxies: list[str]
    betas: dict[str, float]  # proxy ticker -> hedge weight
    alpha: float
    r2: float
    adj_r2: float
    n_obs: int
    extended: bool = False  # True if a best-second-sector-ETF proxy was added

    def basket_weights(self) -> dict[str, float]:
        """Weights for a log-price spread basket: +1 stock, -beta on each proxy."""
        weights = {self.symbol: 1.0}
        for etf, beta in self.betas.items():
            weights[etf] = -beta
        return weights


class ProxyMapper:
    """Regress stock returns onto ETF proxy returns."""

    def __init__(self, proxy_returns: pd.DataFrame, use_broad: bool = True):
        """proxy_returns: time x ETF-ticker matrix of aligned returns."""
        self.proxy_returns = proxy_returns
        self.use_broad = use_broad

    def _proxies_for(
        self, sector: Optional[str], extra: Sequence[str] = ()
    ) -> list[str]:
        proxies: list[str] = []
        if self.use_broad and BROAD_ETF in self.proxy_returns.columns:
            proxies.append(BROAD_ETF)
        etf = sector_etf(sector)
        if etf and etf in self.proxy_returns.columns and etf not in proxies:
            proxies.append(etf)
        for e in extra:
            if e in self.proxy_returns.columns and e not in proxies:
                proxies.append(e)
        return proxies

    def fit_symbol(
        self,
        stock_returns: pd.Series,
        sector: Optional[str] = None,
        proxies: Optional[Sequence[str]] = None,
    ) -> ProxyFit:
        """OLS of a stock's returns on its proxies (with intercept)."""
        symbol = str(stock_returns.name)
        cols = list(proxies) if proxies is not None else self._proxies_for(sector)
        if not cols:
            raise ValueError(f"no usable proxies for {symbol}")

        df = pd.concat(
            [stock_returns.rename("y"), self.proxy_returns[cols]], axis=1
        ).dropna()
        if len(df) < len(cols) + 2:
            raise ValueError(f"not enough overlapping observations for {symbol}")

        y = df["y"].to_numpy()
        X = df[cols].to_numpy()
        X_design = np.column_stack([np.ones(len(X)), X])
        coef, _, _, _ = np.linalg.lstsq(X_design, y, rcond=None)
        alpha = float(coef[0])
        betas = {c: float(b) for c, b in zip(cols, coef[1:])}

        resid = y - X_design @ coef
        ss_res = float(np.sum(resid**2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

        n = len(df)
        p = len(cols)
        dof = n - p - 1
        adj_r2 = 1.0 - (1.0 - r2) * (n - 1) / dof if dof > 0 else r2

        return ProxyFit(symbol, cols, betas, alpha, r2, adj_r2, n)

    def residual_series(self, stock_returns: pd.Series, fit: ProxyFit) -> pd.Series:
        """Idiosyncratic return series: stock return minus the fitted proxy return."""
        cols = fit.proxies
        df = pd.concat(
            [stock_returns.rename("y"), self.proxy_returns[cols]], axis=1
        ).dropna()
        pred = fit.alpha + df[cols].to_numpy() @ np.array([fit.betas[c] for c in cols])
        return pd.Series(df["y"].to_numpy() - pred, index=df.index, name=fit.symbol)

    def residual_level(self, stock_returns: pd.Series, fit: ProxyFit) -> pd.Series:
        """Cumulative residual series - the drift-free target for the OU fit.

        This is the Avellaneda-Lee residual process X_t = sum of idiosyncratic
        returns. Because the regression alpha is subtracted, it has no linear
        drift, so its OU half-life measures true idiosyncratic mean reversion.
        (The raw log-price spread log P_stock - sum beta*log P_proxy still carries
        the alpha drift and is only appropriate as the traded spread, where a
        rolling z-score absorbs the drift.)
        """
        return self.residual_series(stock_returns, fit).cumsum()

    def fit_universe(
        self,
        stock_returns: pd.DataFrame,
        sectors: dict[str, str],
    ) -> dict[str, ProxyFit]:
        """Fit every column of stock_returns against its sector proxies."""
        fits: dict[str, ProxyFit] = {}
        for symbol in stock_returns.columns:
            try:
                fits[symbol] = self.fit_symbol(
                    stock_returns[symbol], sectors.get(symbol)
                )
            except ValueError:
                continue
        return fits

    def best_second_sector_etf(
        self, stock_returns: pd.Series, exclude: set[str]
    ) -> Optional[str]:
        """Sector ETF (excluding `exclude`) with the highest |correlation| to the
        stock's returns -- the single strongest candidate for a missed second
        sector exposure. See compare_proxy_sets for why an "all ETFs" set is not
        a fair comparison; the same reasoning is why discovery adds at most one
        extra proxy rather than the whole sector-ETF list."""
        candidates = [
            e
            for e in sorted(set(SECTOR_ETFS.values()))
            if e not in exclude and e in self.proxy_returns.columns
        ]
        if not candidates:
            return None
        corr = (
            self.proxy_returns[candidates]
            .corrwith(stock_returns)
            .abs()
            .dropna()
            .sort_values(ascending=False)
        )
        return str(corr.index[0]) if not corr.empty else None

    def fit_symbol_auto(
        self,
        stock_returns: pd.Series,
        sector: Optional[str] = None,
        min_adj_r2_gain: float = 0.02,
    ) -> ProxyFit:
        """Fit SPY + sector ETF, then extend with the single best-correlated
        extra sector ETF only if it improves adj_r2 by at least
        `min_adj_r2_gain`. Keeps the hedge to at most 3 proxies (tradable,
        interpretable) while catching stocks whose sector label misses a real
        second exposure. Sets ProxyFit.extended=True when the extra proxy was
        used, so callers can flag it for human review.
        """
        base = self.fit_symbol(stock_returns, sector=sector)
        second = self.best_second_sector_etf(stock_returns, set(base.proxies))
        if second is None:
            return base
        try:
            extended = self.fit_symbol(stock_returns, proxies=[*base.proxies, second])
        except ValueError:
            return base
        if extended.adj_r2 - base.adj_r2 >= min_adj_r2_gain:
            extended.extended = True
            return extended
        return base

    def compare_proxy_sets(
        self,
        stock_returns: pd.Series,
        candidate_sets: Mapping[str, Sequence[str]],
    ) -> dict[str, ProxyFit]:
        """Fit a stock against several named proxy sets, e.g. to check whether
        SPY+sector beats a single ETF or a wider multi-ETF set.

        candidate_sets: name -> list of proxy tickers, e.g.
            {"broad_only": ["SPY"], "sector_only": ["XLF"],
             "broad_plus_sector": ["SPY", "XLF"]}

        Sets referencing a proxy not present in proxy_returns are skipped.
        Compare with adj_r2, not r2, since candidate sets differ in size and
        raw r2 never decreases as proxies are added.
        """
        fits: dict[str, ProxyFit] = {}
        for name, cols in candidate_sets.items():
            usable = [c for c in cols if c in self.proxy_returns.columns]
            if not usable:
                continue
            try:
                fits[name] = self.fit_symbol(stock_returns, proxies=usable)
            except ValueError:
                continue
        return fits
