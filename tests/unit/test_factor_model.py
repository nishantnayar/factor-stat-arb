"""Unit tests for the PCA factor model and return-matrix cleaning (no DB)."""

import numpy as np
import pandas as pd
import pytest

from src.services.strategy_engine.factor_stat_arb.data import (
    clean_returns,
    to_log_returns,
)
from src.services.strategy_engine.factor_stat_arb.factor_model import FactorModel


def _synthetic_returns(n_obs=400, n_symbols=30, n_factors=3, seed=0) -> pd.DataFrame:
    """Returns generated from a few common factors plus idiosyncratic noise."""
    rng = np.random.default_rng(seed)
    factors = rng.normal(0, 1.0, size=(n_obs, n_factors))
    loadings = rng.normal(0, 1.0, size=(n_factors, n_symbols))
    noise = rng.normal(0, 0.3, size=(n_obs, n_symbols))
    data = factors @ loadings + noise
    idx = pd.date_range("2026-01-01", periods=n_obs, freq="h", tz="UTC")
    cols = [f"S{i:02d}" for i in range(n_symbols)]
    return pd.DataFrame(data, index=idx, columns=cols)


@pytest.mark.unit
class TestFactorModel:
    def test_reconstruction_identity(self):
        R = _synthetic_returns()
        fm = FactorModel(n_components=5).fit(R)
        recon = fm.reconstruct(R)
        resid = fm.residuals(R)
        # returns == reconstruction + residuals (exactly, up to float error)
        err = (R[fm.symbols_] - (recon + resid)).abs().to_numpy().max()
        assert err < 1e-9

    def test_var_threshold_picks_few_components_for_low_rank_data(self):
        # 3 true factors -> most variance captured by ~3 components
        R = _synthetic_returns(n_factors=3)
        fm = FactorModel(var_threshold=0.6).fit(R)
        assert 1 <= fm.k_ <= 10
        assert fm.total_variance_explained() >= 0.6

    def test_fixed_n_components(self):
        R = _synthetic_returns()
        fm = FactorModel(n_components=4).fit(R)
        assert fm.k_ == 4
        assert fm.loadings_.shape == (R.shape[1], 4)

    def test_factor_returns_shape(self):
        R = _synthetic_returns()
        fm = FactorModel(n_components=3).fit(R)
        f = fm.factor_returns(R)
        assert f.shape == (R.shape[0], 3)
        assert list(f.columns) == ["PC1", "PC2", "PC3"]

    def test_residuals_have_less_variance_than_raw(self):
        R = _synthetic_returns(n_factors=3)
        fm = FactorModel(var_threshold=0.7).fit(R)
        resid = fm.residuals(R)
        ratio = (resid.std() / R[fm.symbols_].std()).mean()
        assert ratio < 1.0  # common structure removed

    def test_rejects_nan_matrix(self):
        R = _synthetic_returns()
        R.iloc[0, 0] = np.nan
        with pytest.raises(ValueError):
            FactorModel().fit(R)

    def test_rejects_single_symbol(self):
        R = _synthetic_returns(n_symbols=1)
        with pytest.raises(ValueError):
            FactorModel().fit(R)

    def test_unfitted_raises(self):
        with pytest.raises(RuntimeError):
            FactorModel().residuals(_synthetic_returns())


@pytest.mark.unit
class TestReturnCleaning:
    def test_log_returns_drop_first_row(self):
        prices = pd.DataFrame(
            {"A": [100.0, 101.0, 102.0], "B": [50.0, 49.0, 50.0]},
            index=pd.date_range("2026-01-01", periods=3, freq="h", tz="UTC"),
        )
        r = to_log_returns(prices)
        assert len(r) == 2
        assert np.isclose(r["A"].iloc[0], np.log(101 / 100))

    def test_clean_drops_sparse_symbol(self):
        idx = pd.date_range("2026-01-01", periods=10, freq="h", tz="UTC")
        df = pd.DataFrame(
            {
                "good": np.linspace(0.01, 0.02, 10),
                "sparse": [np.nan] * 8 + [0.01, 0.02],
            },
            index=idx,
        )
        cleaned = clean_returns(df, min_coverage=0.9)
        assert "good" in cleaned.columns
        assert "sparse" not in cleaned.columns

    def test_clean_masks_absurd_returns(self):
        idx = pd.date_range("2026-01-01", periods=5, freq="h", tz="UTC")
        df = pd.DataFrame({"A": [0.01, 0.02, 5.0, 0.01, 0.02]}, index=idx)
        cleaned = clean_returns(df, min_coverage=0.5, max_abs_return=0.5)
        # the 5.0 tick row is dropped (NaN -> dropna)
        assert (cleaned["A"].abs() <= 0.5).all()
