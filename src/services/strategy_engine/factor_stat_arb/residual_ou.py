"""Fit an Ornstein-Uhlenbeck / AR(1) process to a residual spread.

The residual spread is the log-price spread of a stock against its ETF proxies:
    spread_t = log(P_stock,t) - sum(beta_i * log(P_proxy_i,t)).
Discretized, an OU process is an AR(1): s_t = a + b * s_{t-1} + eps. From the
fitted b we get the mean-reversion speed and half-life; a mean-reverting spread
(0 < b < 1) with a half-life inside the screening bounds is a tradable candidate.
This replaces the Engle-Granger p-value gate used for pairs with an OU fit-quality
gate (half-life bounds + AR(1) R2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd

# Match the pairs discovery convention (hourly bars).
DEFAULT_MIN_HALF_LIFE = 5.0
DEFAULT_MAX_HALF_LIFE = 72.0
DEFAULT_MIN_R2 = 0.60


def build_log_spread(prices: pd.DataFrame, weights: Mapping[str, float]) -> pd.Series:
    """Log-price spread sum(w_i * log(P_i)) for the basket weights.

    weights is typically ProxyFit.basket_weights(): +1 on the stock, -beta on each
    proxy. Columns missing from `prices` are ignored.
    """
    cols = [c for c in weights if c in prices.columns]
    if not cols:
        raise ValueError("none of the weighted symbols are in the price frame")
    log_p = np.log(prices[cols].astype(float))
    w = np.array([weights[c] for c in cols])
    return (log_p * w).sum(axis=1).dropna()


@dataclass
class OUFit:
    """Fitted OU/AR(1) parameters for a spread series (time unit = one bar)."""

    b: float  # AR(1) coefficient
    mu: float  # long-run mean
    theta: float  # mean-reversion speed per bar (-ln b)
    half_life: float  # ln(2) / theta, in bars (inf if not mean-reverting)
    sigma: float  # innovation (residual) std
    sigma_eq: float  # equilibrium std of the spread
    r2: float  # AR(1) fit R2 on the level series
    n_obs: int
    mean_reverting: bool

    def passes(
        self,
        min_half_life: float = DEFAULT_MIN_HALF_LIFE,
        max_half_life: float = DEFAULT_MAX_HALF_LIFE,
        min_r2: float = DEFAULT_MIN_R2,
    ) -> bool:
        """Screen: mean-reverting, half-life in bounds, and AR(1) fit good enough."""
        return (
            self.mean_reverting
            and min_half_life <= self.half_life <= max_half_life
            and self.r2 >= min_r2
        )


def fit_ou(spread: pd.Series, min_obs: int = 30) -> OUFit:
    """Fit AR(1) s_t = a + b*s_{t-1} + eps to the spread and derive OU parameters."""
    s = spread.dropna().to_numpy(dtype=float)
    if len(s) < min_obs:
        raise ValueError(f"need at least {min_obs} observations, got {len(s)}")

    s_lag, s_now = s[:-1], s[1:]
    X = np.column_stack([np.ones(len(s_lag)), s_lag])
    coef, _, _, _ = np.linalg.lstsq(X, s_now, rcond=None)
    a, b = float(coef[0]), float(coef[1])

    resid = s_now - X @ coef
    sigma = float(np.std(resid, ddof=2))
    ss_res = float(np.sum(resid**2))
    ss_tot = float(np.sum((s_now - s_now.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    mean_reverting = 0.0 < b < 1.0
    if mean_reverting:
        theta = -math.log(b)
        half_life = math.log(2) / theta
        sigma_eq = sigma / math.sqrt(1.0 - b * b)
    else:
        theta = 0.0
        half_life = math.inf
        sigma_eq = math.nan
    mu = a / (1.0 - b) if b != 1.0 else math.nan

    return OUFit(
        b=b,
        mu=mu,
        theta=theta,
        half_life=half_life,
        sigma=sigma,
        sigma_eq=sigma_eq,
        r2=r2,
        n_obs=len(s),
        mean_reverting=mean_reverting,
    )
