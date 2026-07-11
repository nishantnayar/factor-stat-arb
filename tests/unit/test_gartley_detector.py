"""Unit tests for GartleyDetector - no DB or network required."""

import numpy as np
import pandas as pd
import pytest

from src.services.strategy_engine.harmonic.gartley_detector import (
    GartleyDetector,
    GartleyPattern,
    SwingPoint,
    _direction_valid,
    _ratio,
    _validate_gartley,
    find_swing_points,
    scan_universe,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_series(prices: list, freq: str = "1h") -> pd.Series:
    idx = pd.date_range("2024-01-01", periods=len(prices), freq=freq, tz="UTC")
    return pd.Series(prices, index=idx, dtype=float)


def _sw(index: int, price: float) -> SwingPoint:
    ts = pd.Timestamp("2024-01-01", tz="UTC") + pd.Timedelta(hours=index)
    return SwingPoint(index=index, price=price, timestamp=ts)


# ---------------------------------------------------------------------------
# _ratio
# ---------------------------------------------------------------------------
class TestRatio:
    def test_basic(self):
        assert abs(_ratio(0.618, 1.0) - 0.618) < 1e-9

    def test_zero_denominator(self):
        assert _ratio(1.0, 0.0) == float("inf")

    def test_abs_legs(self):
        assert abs(_ratio(-0.5, 1.0) - 0.5) < 1e-9


# ---------------------------------------------------------------------------
# _direction_valid
# ---------------------------------------------------------------------------
class TestDirectionValid:
    def _make(self, prices):
        return [_sw(i, p) for i, p in enumerate(prices)]

    def test_bullish(self):
        pts = self._make([10, 20, 13, 17, 11])  # X low A high B low C high D low
        assert _direction_valid(*pts) == "bullish"

    def test_bearish(self):
        pts = self._make([20, 10, 17, 13, 19])  # X high A low B high C low D high
        assert _direction_valid(*pts) == "bearish"

    def test_invalid(self):
        # All rising: X<A<B<C<D - not alternating, so neither bullish nor bearish
        pts = self._make([10, 11, 12, 13, 14])
        assert _direction_valid(*pts) is None


# ---------------------------------------------------------------------------
# _validate_gartley with synthetic perfect-ratio points
# ---------------------------------------------------------------------------
class TestValidateGartley:
    def _bullish_xabcd(self):
        """Build a perfect bullish Gartley from first principles.

        Constraints:
          AB/XA = 0.618, BC/AB in [0.382, 0.886], CD/BC in [1.272, 1.618],
          XD/XA = 0.786 (the Gartley signature).

        We fix X, A, B, C and derive D from the XD requirement so all checks
        pass simultaneously.
        """
        # XD/XA is measured as AD/XA = 0.786 (D is 78.6% of XA below A).
        # D = A - 0.786*XA = 150 - 39.3 = 110.7
        # AB/XA = 0.618, BC/AB = 0.618 (in range), CD/BC must be in [1.272, 1.618].
        # C = 138.19, D = 110.7 -> CD = 27.49, BC = 19.09, CD/BC = 1.440 (ok)
        X = _sw(0, 100.0)
        A = _sw(1, 150.0)  # XA = +50 upward
        B = _sw(2, 119.1)  # AB/XA = 30.9/50 = 0.618 (down)
        C = _sw(3, 138.1962)  # BC/AB = 19.0962/30.9 = 0.618 (up, in range)
        D = _sw(4, 110.7)  # AD/XA = 39.3/50 = 0.786; CD/BC = 27.49/19.09 = 1.440
        return X, A, B, C, D

    def test_perfect_bullish_passes(self):
        X, A, B, C, D = self._bullish_xabcd()
        assert _validate_gartley(X, A, B, C, D) is True

    def test_wrong_ab_ratio_fails(self):
        X, A, B, C, D = self._bullish_xabcd()
        # Move B to make AB/XA = 0.9 (too high)
        bad_B = _sw(2, A.price - (A.price - X.price) * 0.9)
        assert _validate_gartley(X, A, bad_B, C, D) is False


# ---------------------------------------------------------------------------
# find_swing_points
# ---------------------------------------------------------------------------
class TestFindSwingPoints:
    def test_detects_obvious_swings(self):
        # Zigzag: lo-hi-lo-hi-lo
        prices = [10, 20, 10, 20, 10, 20, 10, 20, 10, 20, 10, 20, 10]
        series = _make_series(prices)
        highs, lows = find_swing_points(series, order=1)
        assert len(highs) > 0
        assert len(lows) > 0

    def test_no_swings_flat(self):
        series = _make_series([10] * 20)
        highs, lows = find_swing_points(series, order=3)
        # Flat series - all points tie for max/min, many detected
        # Just ensure it doesn't crash
        assert isinstance(highs, list)
        assert isinstance(lows, list)


# ---------------------------------------------------------------------------
# GartleyDetector - constructor validation
# ---------------------------------------------------------------------------
class TestGartleyDetectorInit:
    def test_too_few_bars_raises(self):
        with pytest.raises(ValueError, match="at least"):
            GartleyDetector(_make_series([1, 2, 3]), swing_order=5)

    def test_sufficient_bars_ok(self):
        series = _make_series(list(range(50)))
        det = GartleyDetector(series, swing_order=3)
        assert det is not None


# ---------------------------------------------------------------------------
# GartleyDetector.find_patterns - flat / random data returns no crash
# ---------------------------------------------------------------------------
class TestGartleyDetectorFindPatterns:
    def test_random_data_no_crash(self):
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(200))
        series = _make_series(prices.tolist())
        det = GartleyDetector(series, swing_order=5)
        result = det.find_patterns()
        assert isinstance(result, list)

    def test_returns_gartley_pattern_objects(self):
        np.random.seed(0)
        prices = 100 + np.cumsum(np.random.randn(300))
        series = _make_series(prices.tolist())
        det = GartleyDetector(series, swing_order=3)
        result = det.find_patterns()
        for p in result:
            assert isinstance(p, GartleyPattern)
            assert p.direction in ("bullish", "bearish")
            assert len(p.targets) == 2

    def test_most_recent_first(self):
        np.random.seed(7)
        prices = 100 + np.cumsum(np.random.randn(300))
        series = _make_series(prices.tolist())
        det = GartleyDetector(series, swing_order=3)
        result = det.find_patterns()
        if len(result) > 1:
            for i in range(len(result) - 1):
                assert result[i].D.index >= result[i + 1].D.index


# ---------------------------------------------------------------------------
# GartleyPattern.to_dict
# ---------------------------------------------------------------------------
class TestGartleyPatternToDict:
    def test_to_dict_keys(self):
        pts = [_sw(i, float(p)) for i, p in enumerate([100, 150, 119, 135, 105])]
        p = GartleyPattern(
            direction="bullish",
            X=pts[0],
            A=pts[1],
            B=pts[2],
            C=pts[3],
            D=pts[4],
            stop_loss=98.0,
            targets=[115.0, 125.0],
        )
        d = p.to_dict()
        expected_keys = {
            "direction",
            "X_price",
            "A_price",
            "B_price",
            "C_price",
            "D_price",
            "D_timestamp",
            "stop_loss",
            "target_1",
            "target_2",
            "quality_score",
        }
        assert expected_keys == set(d.keys())
        assert d["direction"] == "bullish"
        assert d["stop_loss"] == 98.0


# ---------------------------------------------------------------------------
# scan_universe
# ---------------------------------------------------------------------------
class TestScanUniverse:
    def test_empty_input(self):
        assert scan_universe({}) == {}

    def test_too_short_series_skipped(self):
        result = scan_universe({"AAPL": _make_series([100, 101, 99])})
        assert "AAPL" not in result

    def test_returns_dict(self):
        np.random.seed(1)
        prices = 100 + np.cumsum(np.random.randn(200))
        result = scan_universe({"TEST": _make_series(prices.tolist())})
        assert isinstance(result, dict)
