"""PCA factor decomposition of the equity-return universe.

Standardizes each symbol's return series, fits PCA on the cross-section, and keeps
the smallest number of components explaining a target share of variance. Exposes
factor loadings (symbol x component), factor returns (time x component), and the
residual returns left after removing the common factor structure - the object the
proxy mapper and residual-OU steps build on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA


@dataclass
class FactorModel:
    """Fitted PCA factor model over a return matrix (index=time, columns=symbol).

    Parameters
    ----------
    n_components:
        Fixed number of components. If None, chosen as the smallest k whose
        cumulative explained variance reaches `var_threshold`.
    var_threshold:
        Target cumulative explained-variance ratio when n_components is None.
    """

    n_components: Optional[int] = None
    var_threshold: float = 0.6

    # populated by fit()
    symbols_: Optional[pd.Index] = None
    mean_: Optional[pd.Series] = None
    std_: Optional[pd.Series] = None
    loadings_: Optional[pd.DataFrame] = None
    explained_variance_ratio_: Optional[np.ndarray] = None
    k_: Optional[int] = None

    def fit(self, returns: pd.DataFrame) -> "FactorModel":
        if returns.isna().any().any():
            raise ValueError("returns must be a dense matrix (no NaNs); clean it first")
        if returns.shape[1] < 2:
            raise ValueError("need at least 2 symbols to fit a factor model")

        self.symbols_ = returns.columns
        self.mean_ = returns.mean(axis=0)
        std = returns.std(axis=0, ddof=0)
        # Guard against zero-variance columns (a flat series) -> avoid div by zero.
        self.std_ = std.replace(0.0, np.nan)
        z = (returns - self.mean_) / self.std_
        z = z.dropna(axis=1, how="any")  # drop any flat symbols
        self.symbols_ = z.columns

        max_k = min(z.shape[0], z.shape[1])
        pca = PCA(n_components=max_k)
        pca.fit(z.values)
        evr = pca.explained_variance_ratio_

        if self.n_components is not None:
            k = min(self.n_components, max_k)
        else:
            cum = np.cumsum(evr)
            k = int(np.searchsorted(cum, self.var_threshold) + 1)
            k = max(1, min(k, max_k))

        self.k_ = k
        self.explained_variance_ratio_ = evr[:k]
        # components_: (k x symbols) -> loadings (symbols x k)
        self.loadings_ = pd.DataFrame(
            pca.components_[:k].T,
            index=self.symbols_,
            columns=[f"PC{i + 1}" for i in range(k)],
        )
        self._pca = pca  # retained for transform
        return self

    def _standardize(self, returns: pd.DataFrame) -> pd.DataFrame:
        assert self.symbols_ is not None
        assert self.mean_ is not None and self.std_ is not None
        cols = self.symbols_
        z = (returns[cols] - self.mean_[cols]) / self.std_[cols]
        return z

    def factor_returns(self, returns: pd.DataFrame) -> pd.DataFrame:
        """Project returns onto the factors -> time x component factor returns."""
        self._check_fitted()
        assert self.loadings_ is not None
        z = self._standardize(returns)
        scores = z.values @ self.loadings_.values
        return pd.DataFrame(scores, index=returns.index, columns=self.loadings_.columns)

    def reconstruct(self, returns: pd.DataFrame) -> pd.DataFrame:
        """Common-factor part of the standardized returns, back in return units."""
        self._check_fitted()
        assert self.loadings_ is not None and self.symbols_ is not None
        assert self.mean_ is not None and self.std_ is not None
        f = self.factor_returns(returns)
        z_hat = f.values @ self.loadings_.values.T
        cols = self.symbols_
        return (
            pd.DataFrame(z_hat, index=returns.index, columns=cols) * self.std_[cols]
            + self.mean_[cols]
        )

    def residuals(self, returns: pd.DataFrame) -> pd.DataFrame:
        """Idiosyncratic returns: what remains after removing the common factors."""
        self._check_fitted()
        assert self.symbols_ is not None
        cols = self.symbols_
        return returns[cols] - self.reconstruct(returns)

    def total_variance_explained(self) -> float:
        self._check_fitted()
        assert self.explained_variance_ratio_ is not None
        return float(np.sum(self.explained_variance_ratio_))

    def _check_fitted(self) -> None:
        if self.loadings_ is None:
            raise RuntimeError("FactorModel is not fitted; call fit() first")
