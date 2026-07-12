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
from typing import Optional, Sequence

import numpy as np
import pandas as pd

from src.services.strategy_engine.factor_stat_arb.proxies import BROAD_ETF, sector_etf


@dataclass
class ProxyFit:
    """Result of regressing one stock on its ETF proxies."""

    symbol: str
    proxies: list[str]
    betas: dict[str, float]  # proxy ticker -> hedge weight
    alpha: float
    r2: float
    n_obs: int

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

        return ProxyFit(symbol, cols, betas, alpha, r2, len(df))

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
