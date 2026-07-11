"""
Tests for Technical Indicator Calculations

This module tests technical indicator calculations using pandas-ta library.
Tests verify that indicators (SMA, EMA, RSI, MACD, Bollinger Bands) are calculated
correctly and match industry-standard implementations.

Author: Trading System Team
"""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Add streamlit_ui to path to import calculation functions
streamlit_path = Path(__file__).parent.parent.parent / "streamlit_ui"
sys.path.insert(0, str(streamlit_path))

# Import directly from technical_indicators module to avoid importing utils package
# which would trigger plotly import (not available in test environment)

technical_indicators_path = streamlit_path / "utils" / "technical_indicators.py"
spec = importlib.util.spec_from_file_location("technical_indicators", technical_indicators_path)
technical_indicators_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(technical_indicators_module)

# Import functions from the module
calculate_bollinger_bands = technical_indicators_module.calculate_bollinger_bands
calculate_ema = technical_indicators_module.calculate_ema
calculate_macd = technical_indicators_module.calculate_macd
calculate_rsi = technical_indicators_module.calculate_rsi
calculate_sma = technical_indicators_module.calculate_sma


class TestSMA:
    """Test suite for Simple Moving Average (SMA) calculation"""

    def test_sma_basic_calculation(self):
        """Test basic SMA calculation with known values"""
        # Simple test case: 5 prices, period 3
        prices = [10.0, 20.0, 30.0, 40.0, 50.0]
        period = 3
        
        # Expected: mean of last 3 values = (30 + 40 + 50) / 3 = 40.0
        result = calculate_sma(prices, period)
        
        assert result is not None
        assert result == 40.0
        assert isinstance(result, (float, np.floating))

    def test_sma_manual_verification(self):
        """Test SMA with manual calculation verification"""
        # Test case with 10 prices, period 5
        prices = [100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0, 108.0, 107.0, 109.0]
        period = 5
        
        # Manual calculation: last 5 values = [105, 104, 106, 108, 107, 109]
        # Wait, that's 6 values. Last 5 should be: [105, 104, 106, 108, 107]
        # Actually, let's be precise: prices[-5:] = [105.0, 104.0, 106.0, 108.0, 107.0, 109.0]
        # No wait, let me count: indices 0-9, last 5 are indices 5-9: [104.0, 106.0, 108.0, 107.0, 109.0]
        expected = (104.0 + 106.0 + 108.0 + 107.0 + 109.0) / 5.0
        expected = 534.0 / 5.0  # = 106.8
        
        result = calculate_sma(prices, period)
        
        assert result is not None
        assert abs(result - expected) < 0.0001, f"Expected {expected}, got {result}"

    def test_sma_against_pandas_ta(self):
        """Test SMA calculation against pandas-ta (industry standard library)"""
        # Generate random price data
        np.random.seed(42)
        prices = (100 + np.random.randn(100).cumsum()).tolist()
        
        for period in [5, 10, 20, 50]:
            # Our implementation (uses pandas-ta internally)
            our_result = calculate_sma(prices, period)
            
            # Direct pandas-ta verification using pandas extension API
            df = pd.DataFrame({'close': prices})
            df.ta.sma(length=period, append=True)
            pandas_ta_result = df[f'SMA_{period}'].iloc[-1]
            
            assert our_result is not None
            assert pd.notna(pandas_ta_result)
            # Allow small floating point differences
            assert abs(our_result - pandas_ta_result) < 0.0001, \
                f"Period {period}: Our SMA ({our_result}) doesn't match pandas-ta ({pandas_ta_result})"

    def test_sma_different_periods(self):
        """Test SMA with different periods (20, 50, 200)"""
        # Generate enough data for 200-period SMA
        np.random.seed(42)
        prices = (100 + np.random.randn(250).cumsum()).tolist()
        
        periods = [20, 50, 200]
        for period in periods:
            result = calculate_sma(prices, period)
            
            assert result is not None, f"SMA {period} should not be None"
            
            # Verify it's the mean of the last 'period' values
            expected = np.mean(prices[-period:])
            assert abs(result - expected) < 0.0001, \
                f"Period {period}: Result ({result}) should equal mean of last {period} values ({expected})"

    def test_sma_insufficient_data(self):
        """Test SMA with insufficient data (should return None)"""
        prices = [10.0, 20.0, 30.0]  # Only 3 prices
        period = 5  # Need 5 prices
        
        result = calculate_sma(prices, period)
        
        assert result is None, "SMA should return None when insufficient data"

    def test_sma_exact_period_match(self):
        """Test SMA when data length exactly matches period"""
        prices = [10.0, 20.0, 30.0]  # Exactly 3 prices
        period = 3  # Period is 3
        
        result = calculate_sma(prices, period)
        expected = (10.0 + 20.0 + 30.0) / 3.0  # = 20.0
        
        assert result is not None
        assert result == expected

    def test_sma_single_value_period(self):
        """Test SMA with period of 1 (should return last value)"""
        prices = [10.0, 20.0, 30.0, 40.0, 50.0]
        period = 1
        
        result = calculate_sma(prices, period)
        expected = prices[-1]  # Should be 50.0
        
        assert result is not None
        assert result == expected

    def test_sma_empty_list(self):
        """Test SMA with empty price list"""
        prices = []
        period = 5
        
        result = calculate_sma(prices, period)
        
        assert result is None, "SMA should return None for empty list"

    def test_sma_constant_prices(self):
        """Test SMA with constant prices (should return the constant)"""
        prices = [100.0] * 20  # 20 identical prices
        period = 10
        
        result = calculate_sma(prices, period)
        
        assert result is not None
        assert result == 100.0, "SMA of constant prices should equal the constant"

    def test_sma_increasing_prices(self):
        """Test SMA with strictly increasing prices"""
        prices = list(range(1, 21))  # [1, 2, 3, ..., 20]
        period = 5
        
        result = calculate_sma(prices, period)
        # Last 5: [16, 17, 18, 19, 20]
        expected = (16 + 17 + 18 + 19 + 20) / 5.0  # = 90 / 5 = 18.0
        
        assert result is not None
        assert result == expected

    def test_sma_decreasing_prices(self):
        """Test SMA with strictly decreasing prices"""
        prices = list(range(20, 0, -1))  # [20, 19, 18, ..., 1]
        period = 5
        
        result = calculate_sma(prices, period)
        # Last 5: [5, 4, 3, 2, 1]
        expected = (5 + 4 + 3 + 2 + 1) / 5.0  # = 15 / 5 = 3.0
        
        assert result is not None
        assert result == expected

    def test_sma_float_precision(self):
        """Test SMA with floating point precision"""
        prices = [100.123456, 101.234567, 102.345678, 103.456789, 104.567890]
        period = 5
        
        result = calculate_sma(prices, period)
        expected = sum(prices) / len(prices)
        
        assert result is not None
        # Check precision (should handle floats correctly)
        assert abs(result - expected) < 0.000001

    def test_sma_real_world_scenario(self):
        """Test SMA with realistic stock price scenario"""
        # Simulate realistic stock prices (AAPL-like)
        prices = [
            150.25, 151.30, 150.80, 152.10, 151.50,
            152.75, 153.20, 152.90, 154.10, 153.80,
            155.00, 154.50, 156.20, 155.90, 157.10,
            156.80, 158.00, 157.50, 159.20, 158.90,
            160.10, 159.80, 161.00, 160.50, 162.20
        ]
        period = 20
        
        result = calculate_sma(prices, period)
        
        # Verify against pandas-ta using pandas extension API
        df = pd.DataFrame({'close': prices})
        df.ta.sma(length=period, append=True)
        pandas_ta_result = df[f'SMA_{period}'].iloc[-1]
        
        assert result is not None
        assert abs(result - pandas_ta_result) < 0.0001, \
            f"Real-world test: Our SMA ({result}) doesn't match pandas-ta ({pandas_ta_result})"

    def test_sma_large_dataset(self):
        """Test SMA with large dataset (performance and correctness)"""
        # Generate large dataset (1000 prices)
        np.random.seed(42)
        prices = (100 + np.random.randn(1000).cumsum()).tolist()
        period = 200
        
        result = calculate_sma(prices, period)
        
        # Verify against pandas-ta using pandas extension API
        df = pd.DataFrame({'close': prices})
        df.ta.sma(length=period, append=True)
        pandas_ta_result = df[f'SMA_{period}'].iloc[-1]
        
        assert result is not None
        assert abs(result - pandas_ta_result) < 0.0001, \
            f"Large dataset: Our SMA ({result}) doesn't match pandas-ta ({pandas_ta_result})"

    def test_sma_edge_case_zero_prices(self):
        """Test SMA behavior with zero prices (should handle gracefully)"""
        prices = [0.0, 0.0, 0.0, 0.0, 0.0]
        period = 5
        
        result = calculate_sma(prices, period)
        
        assert result is not None
        assert result == 0.0, "SMA of zeros should be zero"

    def test_sma_negative_prices(self):
        """Test SMA with negative prices (unusual but should work)"""
        prices = [-10.0, -20.0, -30.0, -40.0, -50.0]
        period = 5
        
        result = calculate_sma(prices, period)
        expected = sum(prices) / len(prices)  # = -30.0
        
        assert result is not None
        assert result == expected

    def test_sma_mixed_positive_negative(self):
        """Test SMA with mixed positive and negative prices"""
        prices = [-10.0, 20.0, -30.0, 40.0, -50.0, 60.0]
        period = 6
        
        result = calculate_sma(prices, period)
        expected = sum(prices) / len(prices)  # = (-10 + 20 - 30 + 40 - 50 + 60) / 6 = 30 / 6 = 5.0
        
        assert result is not None
        assert abs(result - expected) < 0.0001

    def test_sma_very_small_values(self):
        """Test SMA with very small price values"""
        prices = [0.0001, 0.0002, 0.0003, 0.0004, 0.0005]
        period = 5
        
        result = calculate_sma(prices, period)
        expected = sum(prices) / len(prices)  # = 0.0003
        
        assert result is not None
        assert abs(result - expected) < 0.0000001

    def test_sma_very_large_values(self):
        """Test SMA with very large price values"""
        prices = [1000000.0, 2000000.0, 3000000.0, 4000000.0, 5000000.0]
        period = 5
        
        result = calculate_sma(prices, period)
        expected = sum(prices) / len(prices)  # = 3000000.0
        
        assert result is not None
        assert abs(result - expected) < 0.01  # Allow small tolerance for large numbers

    def test_sma_returns_float_type(self):
        """Test that SMA returns appropriate numeric type"""
        prices = [10.0, 20.0, 30.0, 40.0, 50.0]
        period = 5
        
        result = calculate_sma(prices, period)
        
        assert result is not None
        # Should be a float or numpy float
        assert isinstance(result, (float, np.floating)), \
            f"Result should be float, got {type(result)}"

    def test_sma_consistency_multiple_calls(self):
        """Test that SMA returns consistent results on multiple calls"""
        prices = [100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0, 108.0, 107.0, 109.0]
        period = 5
        
        result1 = calculate_sma(prices, period)
        result2 = calculate_sma(prices, period)
        result3 = calculate_sma(prices, period)
        
        assert result1 == result2 == result3, \
            "SMA should return consistent results on multiple calls"


class TestOtherIndicators:
    """Test suite for other technical indicators (EMA, RSI, MACD, Bollinger Bands)"""

    def test_ema_basic(self):
        """Test EMA calculation"""
        prices = [100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0, 108.0, 107.0, 109.0] * 25
        period = 12
        
        result = calculate_ema(prices, period)
        
        assert result is not None
        assert isinstance(result, (float, np.floating))
        
        # Verify against pandas-ta using pandas extension API
        df = pd.DataFrame({'close': prices})
        df.ta.ema(length=period, append=True)
        expected = df[f'EMA_{period}'].iloc[-1]
        assert abs(result - expected) < 0.0001

    def test_rsi_basic(self):
        """Test RSI calculation"""
        prices = [100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0, 108.0, 107.0, 109.0] * 25
        period = 14
        
        result = calculate_rsi(prices, period)
        
        assert result is not None
        assert 0 <= result <= 100, "RSI should be between 0 and 100"
        
        # Verify against pandas-ta using pandas extension API
        df = pd.DataFrame({'close': prices})
        df.ta.rsi(length=period, append=True)
        expected = df[f'RSI_{period}'].iloc[-1]
        assert abs(result - expected) < 0.0001

    def test_macd_basic(self):
        """Test MACD calculation"""
        prices = [100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0, 108.0, 107.0, 109.0] * 25
        
        result = calculate_macd(prices, fast_period=12, slow_period=26, signal_period=9)
        
        assert result is not None
        assert 'macd' in result
        assert 'signal' in result
        assert 'histogram' in result
        assert all(isinstance(v, (float, np.floating)) for v in result.values())
        
        # Verify against pandas-ta using pandas extension API
        df = pd.DataFrame({'close': prices})
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        expected_macd = df['MACD_12_26_9'].iloc[-1]
        expected_signal = df['MACDs_12_26_9'].iloc[-1]
        expected_hist = df['MACDh_12_26_9'].iloc[-1]
        
        assert abs(result['macd'] - expected_macd) < 0.0001
        assert abs(result['signal'] - expected_signal) < 0.0001
        assert abs(result['histogram'] - expected_hist) < 0.0001

    def test_bollinger_bands_basic(self):
        """Test Bollinger Bands calculation"""
        prices = [100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0, 108.0, 107.0, 109.0] * 25
        period = 20
        std_dev = 2.0
        
        result = calculate_bollinger_bands(prices, period=period, std_dev=std_dev)
        
        assert result is not None
        assert 'upper' in result
        assert 'middle' in result
        assert 'lower' in result
        assert result['upper'] > result['middle'] > result['lower']
        
        # Verify against pandas-ta using pandas extension API
        df = pd.DataFrame({'close': prices})
        df.ta.bbands(length=period, std=std_dev, append=True)
        
        # Find columns dynamically
        upper_cols = [col for col in df.columns if col.startswith('BBU_')]
        middle_cols = [col for col in df.columns if col.startswith('BBM_')]
        lower_cols = [col for col in df.columns if col.startswith('BBL_')]
        
        expected_upper = df[upper_cols[0]].iloc[-1]
        expected_middle = df[middle_cols[0]].iloc[-1]
        expected_lower = df[lower_cols[0]].iloc[-1]
        
        assert abs(result['upper'] - expected_upper) < 0.0001
        assert abs(result['middle'] - expected_middle) < 0.0001
        assert abs(result['lower'] - expected_lower) < 0.0001

    def test_indicators_insufficient_data(self):
        """Test that all indicators return None with insufficient data"""
        prices = [100.0, 102.0, 101.0]  # Only 3 prices
        
        assert calculate_sma(prices, 20) is None
        assert calculate_ema(prices, 20) is None
        assert calculate_rsi(prices, 14) is None
        assert calculate_macd(prices) is None
        assert calculate_bollinger_bands(prices, period=20) is None

