"""
Tests for Indicator Calculation Service

This module tests the IndicatorCalculationService, including:
- Data frequency detection
- Hourly to daily resampling
- Indicator calculation with resampling
"""

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.services.analytics.indicator_calculator import IndicatorCalculationService


class TestDataFrequencyDetection:
    """Test suite for data frequency detection"""

    def test_detect_hourly_data(self):
        """Test detection of hourly data"""
        service = IndicatorCalculationService()
        
        # Create hourly data (1 hour intervals)
        base_time = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        hourly_data = []
        for i in range(10):
            timestamp = base_time + timedelta(hours=i)
            hourly_data.append({
                'symbol': 'AAPL',
                'timestamp': timestamp,
                'open': 150.0 + i * 0.1,
                'high': 151.0 + i * 0.1,
                'low': 149.0 + i * 0.1,
                'close': 150.5 + i * 0.1,
                'volume': 1000000,
            })
        
        frequency = service._detect_data_frequency(hourly_data)
        assert frequency == 'hourly'

    def test_detect_daily_data(self):
        """Test detection of daily data"""
        service = IndicatorCalculationService()
        
        # Create daily data (24 hour intervals)
        base_time = datetime(2024, 1, 1, 16, 0, 0, tzinfo=timezone.utc)
        daily_data = []
        for i in range(10):
            timestamp = base_time + timedelta(days=i)
            daily_data.append({
                'symbol': 'AAPL',
                'timestamp': timestamp,
                'open': 150.0 + i * 0.5,
                'high': 151.0 + i * 0.5,
                'low': 149.0 + i * 0.5,
                'close': 150.5 + i * 0.5,
                'volume': 10000000,
            })
        
        frequency = service._detect_data_frequency(daily_data)
        assert frequency == 'daily'

    def test_detect_unknown_frequency(self):
        """Test detection of unknown frequency"""
        service = IndicatorCalculationService()
        
        # Create data with irregular intervals
        base_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        irregular_data = []
        intervals = [2, 5, 10, 15, 30]  # Mixed intervals in hours
        for i, interval in enumerate(intervals):
            timestamp = base_time + timedelta(hours=sum(intervals[:i+1]))
            irregular_data.append({
                'symbol': 'AAPL',
                'timestamp': timestamp,
                'open': 150.0,
                'high': 151.0,
                'low': 149.0,
                'close': 150.5,
                'volume': 1000000,
            })
        
        frequency = service._detect_data_frequency(irregular_data)
        assert frequency == 'unknown'

    def test_detect_frequency_insufficient_data(self):
        """Test frequency detection with insufficient data"""
        service = IndicatorCalculationService()
        
        # Single data point
        single_data = [{
            'symbol': 'AAPL',
            'timestamp': datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc),
            'open': 150.0,
            'high': 151.0,
            'low': 149.0,
            'close': 150.5,
            'volume': 1000000,
        }]
        
        frequency = service._detect_data_frequency(single_data)
        assert frequency == 'unknown'

    def test_detect_frequency_empty_data(self):
        """Test frequency detection with empty data"""
        service = IndicatorCalculationService()
        
        frequency = service._detect_data_frequency([])
        assert frequency == 'unknown'


class TestResampleToDaily:
    """Test suite for hourly to daily resampling"""

    def test_resample_hourly_to_daily(self):
        """Test resampling hourly data to daily bars"""
        service = IndicatorCalculationService()
        
        # Create hourly data for one day (9 AM to 4 PM, 8 hours)
        base_time = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        hourly_data = []
        for i in range(8):
            timestamp = base_time + timedelta(hours=i)
            hourly_data.append({
                'symbol': 'AAPL',
                'timestamp': timestamp,
                'open': 150.0 + i * 0.1,
                'high': 151.0 + i * 0.1,
                'low': 149.0 + i * 0.1,
                'close': 150.5 + i * 0.1,
                'volume': 1000000,
            })
        
        daily_data = service._resample_to_daily(hourly_data)
        
        assert len(daily_data) == 1
        assert daily_data[0]['symbol'] == 'AAPL'
        assert daily_data[0]['open'] == 150.0  # First open
        assert daily_data[0]['high'] == pytest.approx(151.7, abs=0.1)  # Max high
        assert daily_data[0]['low'] == pytest.approx(149.0, abs=0.1)  # Min low
        assert daily_data[0]['close'] == pytest.approx(150.5 + 7 * 0.1, abs=0.1)  # Last close
        assert daily_data[0]['volume'] == 8000000  # Sum of volumes

    def test_resample_multiple_days(self):
        """Test resampling hourly data across multiple days"""
        service = IndicatorCalculationService()
        
        # Create hourly data for 2 days
        base_time = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        hourly_data = []
        
        # Day 1: 8 hours
        for i in range(8):
            timestamp = base_time + timedelta(hours=i)
            hourly_data.append({
                'symbol': 'AAPL',
                'timestamp': timestamp,
                'open': 150.0 + i * 0.1,
                'high': 151.0 + i * 0.1,
                'low': 149.0 + i * 0.1,
                'close': 150.5 + i * 0.1,
                'volume': 1000000,
            })
        
        # Day 2: 8 hours (skip to next day)
        base_time_day2 = datetime(2024, 1, 16, 9, 0, 0, tzinfo=timezone.utc)
        for i in range(8):
            timestamp = base_time_day2 + timedelta(hours=i)
            hourly_data.append({
                'symbol': 'AAPL',
                'timestamp': timestamp,
                'open': 151.0 + i * 0.1,
                'high': 152.0 + i * 0.1,
                'low': 150.0 + i * 0.1,
                'close': 151.5 + i * 0.1,
                'volume': 1200000,
            })
        
        daily_data = service._resample_to_daily(hourly_data)
        
        assert len(daily_data) == 2
        assert daily_data[0]['open'] == 150.0  # First day's first open
        assert daily_data[1]['open'] == 151.0  # Second day's first open

    def test_resample_removes_weekends(self):
        """Test that resampling removes weekends (days with no data)"""
        service = IndicatorCalculationService()
        
        # Create data for Friday, skip weekend, then Monday
        friday = datetime(2024, 1, 12, 16, 0, 0, tzinfo=timezone.utc)  # Friday
        monday = datetime(2024, 1, 15, 16, 0, 0, tzinfo=timezone.utc)  # Monday
        
        hourly_data = [
            {
                'symbol': 'AAPL',
                'timestamp': friday,
                'open': 150.0,
                'high': 151.0,
                'low': 149.0,
                'close': 150.5,
                'volume': 1000000,
            },
            {
                'symbol': 'AAPL',
                'timestamp': monday,
                'open': 151.0,
                'high': 152.0,
                'low': 150.0,
                'close': 151.5,
                'volume': 1200000,
            },
        ]
        
        daily_data = service._resample_to_daily(hourly_data)
        
        # Should have 2 days (Friday and Monday, weekend skipped)
        assert len(daily_data) == 2

    def test_resample_empty_data(self):
        """Test resampling with empty data"""
        service = IndicatorCalculationService()
        
        daily_data = service._resample_to_daily([])
        assert daily_data == []

    def test_resample_preserves_ohlc_relationships(self):
        """Test that resampled data preserves OHLC relationships"""
        service = IndicatorCalculationService()
        
        # Create hourly data
        base_time = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        hourly_data = []
        for i in range(8):
            timestamp = base_time + timedelta(hours=i)
            hourly_data.append({
                'symbol': 'AAPL',
                'timestamp': timestamp,
                'open': 150.0 + i * 0.1,
                'high': 151.0 + i * 0.1,
                'low': 149.0 + i * 0.1,
                'close': 150.5 + i * 0.1,
                'volume': 1000000,
            })
        
        daily_data = service._resample_to_daily(hourly_data)
        
        assert len(daily_data) > 0
        for bar in daily_data:
            # High should be >= Open, Close
            assert bar['high'] >= bar['open']
            assert bar['high'] >= bar['close']
            # Low should be <= Open, Close
            assert bar['low'] <= bar['open']
            assert bar['low'] <= bar['close']
            # Volume should be positive
            assert bar['volume'] > 0


class TestIndicatorCalculationWithResampling:
    """Test suite for indicator calculation with resampling"""

    @pytest.mark.asyncio
    async def test_calculate_indicators_with_hourly_data(self):
        """Test that indicators are calculated correctly with hourly data"""
        service = IndicatorCalculationService()
        
        # Create hourly data for sufficient days (need at least 20 days for SMA_20)
        base_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        hourly_data = []
        
        # Create 25 days of hourly data (8 hours per day = 200 hourly bars)
        for day in range(25):
            day_start = base_time + timedelta(days=day)
            for hour in range(8):  # 8 trading hours per day
                timestamp = day_start + timedelta(hours=hour)
                price_base = 150.0 + day * 0.5
                hourly_data.append({
                    'symbol': 'AAPL',
                    'timestamp': timestamp,
                    'open': price_base + hour * 0.1,
                    'high': price_base + hour * 0.1 + 0.5,
                    'low': price_base + hour * 0.1 - 0.5,
                    'close': price_base + hour * 0.1 + 0.2,
                    'volume': 1000000,
                })
        
        # Calculate indicators
        indicators = service.calculate_all_indicators(hourly_data)
        
        # Should have calculated indicators
        assert indicators is not None
        assert indicators['symbol'] == 'AAPL'
        
        # Should have SMA_20 (calculated on daily bars, not hourly)
        assert indicators['sma_20'] is not None
        assert isinstance(indicators['sma_20'], (float, int))
        
        # Should have RSI_14 (calculated on daily bars)
        assert indicators['rsi_14'] is not None
        assert 0 <= indicators['rsi_14'] <= 100

    @pytest.mark.asyncio
    async def test_calculate_indicators_with_daily_data(self):
        """Test that daily data passes through without resampling"""
        service = IndicatorCalculationService()
        
        # Create daily data
        base_time = datetime(2024, 1, 1, 16, 0, 0, tzinfo=timezone.utc)
        daily_data = []
        
        for day in range(25):
            timestamp = base_time + timedelta(days=day)
            price = 150.0 + day * 0.5
            daily_data.append({
                'symbol': 'AAPL',
                'timestamp': timestamp,
                'open': price,
                'high': price + 1.0,
                'low': price - 1.0,
                'close': price + 0.5,
                'volume': 10000000,
            })
        
        # Calculate indicators
        indicators = service.calculate_all_indicators(daily_data)
        
        # Should have calculated indicators
        assert indicators is not None
        assert indicators['symbol'] == 'AAPL'
        assert indicators['sma_20'] is not None

    def test_resampling_does_not_modify_original_data(self):
        """Test that resampling doesn't modify the original data list"""
        service = IndicatorCalculationService()
        
        # Create hourly data
        base_time = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        original_data = []
        for i in range(8):
            timestamp = base_time + timedelta(hours=i)
            original_data.append({
                'symbol': 'AAPL',
                'timestamp': timestamp,
                'open': 150.0 + i * 0.1,
                'high': 151.0 + i * 0.1,
                'low': 149.0 + i * 0.1,
                'close': 150.5 + i * 0.1,
                'volume': 1000000,
            })
        
        # Make a copy to compare
        original_copy = [dict(d) for d in original_data]
        
        # Resample
        daily_data = service._resample_to_daily(original_data)
        
        # Original data should be unchanged
        assert len(original_data) == len(original_copy)
        for orig, copy in zip(original_data, original_copy):
            assert orig['timestamp'] == copy['timestamp']
            assert orig['close'] == copy['close']
        
        # Daily data should be different (resampled)
        assert len(daily_data) < len(original_data)

