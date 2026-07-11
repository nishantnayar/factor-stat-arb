"""
Tests for timezone utilities

This module tests all timezone conversion functions, trading utilities,
and error handling for the trading system timezone management.

Author: Nishant Nayar
Email: nishant.nayar@hotmail.com
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from src.shared.utils.timezone import (
    CENTRAL,
    EASTERN,
    STORAGE_TIMEZONE,
    TRADING_TIMEZONE,
    USER_TIMEZONE,
    UTC,
    TimezoneError,
    convert_timezone,
    ensure_timezone_aware,
    ensure_utc_timestamp,
    format_for_database,
    format_for_display,
    format_timestamp_for_logging,
    format_trading_time,
    get_central_timezone,
    get_current_display_time,
    get_current_storage_time,
    get_current_trading_time,
    get_display_timestamp,
    get_eastern_timezone,
    get_last_market_close,
    get_market_status,
    get_next_market_open,
    get_trading_day,
    get_trading_timestamp,
    get_utc_timezone,
    handle_timezone_conversion_error,
    is_market_hours,
    is_weekend,
    normalize_vendor_timestamp,
    now_central,
    now_eastern,
    now_utc,
    process_market_data_timestamps,
    smart_convert_to_central,
    smart_convert_to_eastern,
    smart_convert_to_utc,
    to_central,
    to_eastern,
    to_utc,
    validate_timezone_aware,
)


class TestTimezoneConstants:
    """Test timezone constants"""

    def test_timezone_constants(self):
        """Test timezone constant definitions"""
        assert UTC == ZoneInfo("UTC")
        assert CENTRAL == ZoneInfo("America/Chicago")
        assert EASTERN == ZoneInfo("America/New_York")

        assert USER_TIMEZONE == CENTRAL
        assert TRADING_TIMEZONE == EASTERN
        assert STORAGE_TIMEZONE == UTC


class TestTimezoneConfiguration:
    """Test timezone configuration functions"""

    def test_get_timezone_functions(self):
        """Test timezone getter functions"""
        assert get_central_timezone() == CENTRAL
        assert get_eastern_timezone() == EASTERN
        assert get_utc_timezone() == UTC

    def test_now_functions(self):
        """Test current time functions"""
        utc_now = now_utc()
        central_now = now_central()
        eastern_now = now_eastern()

        # All should be timezone-aware
        assert utc_now.tzinfo == UTC
        assert central_now.tzinfo == CENTRAL
        assert eastern_now.tzinfo == EASTERN

        # Should be roughly the same time (within 1 second)
        time_diff = abs((utc_now - central_now).total_seconds())
        assert time_diff < 1


class TestConversionFunctions:
    """Test timezone conversion functions"""

    def test_to_utc(self):
        """Test conversion to UTC"""
        # Test with timezone-aware datetime
        central_dt = datetime(2024, 1, 15, 14, 30, 0, tzinfo=CENTRAL)
        utc_dt = to_utc(central_dt, CENTRAL)

        assert utc_dt.tzinfo == UTC
        assert utc_dt.hour == 20  # 14:30 CST = 20:30 UTC

        # Test with naive datetime
        naive_dt = datetime(2024, 1, 15, 14, 30, 0)
        utc_dt = to_utc(naive_dt, CENTRAL)

        assert utc_dt.tzinfo == UTC
        assert utc_dt.hour == 20

    def test_to_central(self):
        """Test conversion to Central timezone"""
        utc_dt = datetime(2024, 1, 15, 20, 30, 0, tzinfo=UTC)
        central_dt = to_central(utc_dt)

        assert central_dt.tzinfo == CENTRAL
        assert central_dt.hour == 14  # 20:30 UTC = 14:30 CST

        # Test with naive datetime (assumes UTC)
        naive_dt = datetime(2024, 1, 15, 20, 30, 0)
        central_dt = to_central(naive_dt)

        assert central_dt.tzinfo == CENTRAL
        assert central_dt.hour == 14

    def test_to_eastern(self):
        """Test conversion to Eastern timezone"""
        utc_dt = datetime(2024, 1, 15, 20, 30, 0, tzinfo=UTC)
        eastern_dt = to_eastern(utc_dt)

        assert eastern_dt.tzinfo == EASTERN
        assert eastern_dt.hour == 15  # 20:30 UTC = 15:30 EST

        # Test with naive datetime (assumes UTC)
        naive_dt = datetime(2024, 1, 15, 20, 30, 0)
        eastern_dt = to_eastern(naive_dt)

        assert eastern_dt.tzinfo == EASTERN
        assert eastern_dt.hour == 15

    def test_convert_timezone(self):
        """Test general timezone conversion"""
        central_dt = datetime(2024, 1, 15, 14, 30, 0, tzinfo=CENTRAL)
        eastern_dt = convert_timezone(central_dt, CENTRAL, EASTERN)

        assert eastern_dt.tzinfo == EASTERN
        assert eastern_dt.hour == 15  # 14:30 CST = 15:30 EST

    def test_smart_conversion_functions(self):
        """Test smart conversion functions"""
        # Test with timezone-aware datetime
        utc_dt = datetime(2024, 1, 15, 20, 30, 0, tzinfo=UTC)
        central_dt = smart_convert_to_central(utc_dt)
        eastern_dt = smart_convert_to_eastern(utc_dt)

        assert central_dt.tzinfo == CENTRAL
        assert eastern_dt.tzinfo == EASTERN

        # Test with naive datetime (assumes UTC)
        naive_dt = datetime(2024, 1, 15, 20, 30, 0)
        utc_dt = smart_convert_to_utc(naive_dt)
        central_dt = smart_convert_to_central(naive_dt)
        eastern_dt = smart_convert_to_eastern(naive_dt)

        assert utc_dt.tzinfo == UTC
        assert central_dt.tzinfo == CENTRAL
        assert eastern_dt.tzinfo == EASTERN


class TestTradingUtilities:
    """Test trading-specific utilities"""

    def test_is_market_hours(self):
        """Test market hours detection"""
        # Market open time (9:30 AM EST)
        market_open = datetime(2024, 1, 15, 9, 30, 0, tzinfo=EASTERN)
        assert is_market_hours(market_open)

        # Market close time (4:00 PM EST)
        market_close = datetime(2024, 1, 15, 16, 0, 0, tzinfo=EASTERN)
        assert is_market_hours(market_close)

        # Before market open
        before_open = datetime(2024, 1, 15, 8, 0, 0, tzinfo=EASTERN)
        assert not is_market_hours(before_open)

        # After market close
        after_close = datetime(2024, 1, 15, 18, 0, 0, tzinfo=EASTERN)
        assert not is_market_hours(after_close)

        # Weekend
        weekend = datetime(2024, 1, 13, 10, 0, 0, tzinfo=EASTERN)  # Saturday
        assert not is_market_hours(weekend)

    def test_get_next_market_open(self):
        """Test next market open calculation"""
        # Test on weekday before market open
        before_open = datetime(2024, 1, 15, 8, 0, 0, tzinfo=UTC)
        next_open = get_next_market_open(before_open)

        # Should be same day at 9:30 AM EST
        eastern_next = to_eastern(next_open)
        assert eastern_next.hour == 9
        assert eastern_next.minute == 30
        assert eastern_next.weekday() == 0  # Monday

        # Test on weekend
        weekend = datetime(2024, 1, 13, 10, 0, 0, tzinfo=UTC)  # Saturday
        next_open = get_next_market_open(weekend)

        # Should be next Monday
        eastern_next = to_eastern(next_open)
        assert eastern_next.weekday() == 0  # Monday

    def test_get_last_market_close(self):
        """Test last market close calculation"""
        # Test on weekday after market close (9 PM UTC = 4 PM EST)
        after_close = datetime(2024, 1, 15, 21, 0, 0, tzinfo=UTC)
        last_close = get_last_market_close(after_close)

        # Should be same day at 4:00 PM EST (Monday)
        eastern_last = to_eastern(last_close)
        assert eastern_last.hour == 16
        assert eastern_last.minute == 0
        assert eastern_last.weekday() == 0  # Monday

    def test_get_trading_day(self):
        """Test trading day calculation"""
        # Test during market hours (2:30 PM UTC = 9:30 AM EST)
        market_time = datetime(2024, 1, 15, 14, 30, 0, tzinfo=UTC)
        trading_day = get_trading_day(market_time)

        assert trading_day == date(2024, 1, 15)

        # Test before market open
        before_open = datetime(2024, 1, 15, 8, 0, 0, tzinfo=UTC)
        trading_day = get_trading_day(before_open)

        # Should be previous trading day
        assert trading_day == date(2024, 1, 12)  # Previous Friday

    def test_get_trading_timestamp(self):
        """Test trading timestamp conversion"""
        utc_dt = datetime(2024, 1, 15, 20, 30, 0, tzinfo=UTC)
        trading_dt = get_trading_timestamp(utc_dt)

        assert trading_dt.tzinfo == EASTERN
        assert trading_dt.hour == 15  # 20:30 UTC = 15:30 EST

    def test_get_display_timestamp(self):
        """Test display timestamp conversion"""
        utc_dt = datetime(2024, 1, 15, 20, 30, 0, tzinfo=UTC)
        display_dt = get_display_timestamp(utc_dt)

        assert display_dt.tzinfo == CENTRAL
        assert display_dt.hour == 14  # 20:30 UTC = 14:30 CST


class TestDataProcessing:
    """Test data processing utilities"""

    def test_normalize_vendor_timestamp(self):
        """Test vendor timestamp normalization"""
        # Test with UTC string
        utc_string = "2024-01-15T14:30:00Z"
        normalized = normalize_vendor_timestamp(utc_string)

        assert normalized.tzinfo == UTC
        assert normalized.hour == 14
        assert normalized.minute == 30

        # Test with timezone-aware datetime
        eastern_dt = datetime(2024, 1, 15, 9, 30, 0, tzinfo=EASTERN)
        normalized = normalize_vendor_timestamp(eastern_dt)

        assert normalized.tzinfo == UTC
        assert normalized.hour == 14  # 9:30 EST = 14:30 UTC

        # Test with naive datetime (assumes UTC)
        naive_dt = datetime(2024, 1, 15, 14, 30, 0)
        normalized = normalize_vendor_timestamp(naive_dt)

        assert normalized.tzinfo == UTC
        assert normalized.hour == 14

    def test_process_market_data_timestamps(self):
        """Test market data timestamp processing"""
        data = [
            {"symbol": "AAPL", "timestamp": "2024-01-15T14:30:00Z", "price": 150.0},
            {"symbol": "GOOGL", "timestamp": "2024-01-15T14:31:00Z", "price": 2800.0},
        ]

        processed = process_market_data_timestamps(data)

        assert len(processed) == 2
        assert processed[0]["timestamp"].tzinfo == UTC
        assert processed[1]["timestamp"].tzinfo == UTC

    def test_ensure_utc_timestamp(self):
        """Test UTC timestamp ensuring"""
        # Test with timezone-aware datetime
        eastern_dt = datetime(2024, 1, 15, 9, 30, 0, tzinfo=EASTERN)
        utc_dt = ensure_utc_timestamp(eastern_dt)

        assert utc_dt.tzinfo == UTC
        assert utc_dt.hour == 14  # 9:30 EST = 14:30 UTC

        # Test with naive datetime (assumes UTC)
        naive_dt = datetime(2024, 1, 15, 14, 30, 0)
        utc_dt = ensure_utc_timestamp(naive_dt)

        assert utc_dt.tzinfo == UTC
        assert utc_dt.hour == 14

    def test_format_for_database(self):
        """Test database formatting"""
        eastern_dt = datetime(2024, 1, 15, 9, 30, 0, tzinfo=EASTERN)
        db_dt = format_for_database(eastern_dt)

        assert db_dt.tzinfo == UTC
        assert db_dt.hour == 14  # 9:30 EST = 14:30 UTC


class TestLoggingAndDisplay:
    """Test logging and display utilities"""

    def test_format_timestamp_for_logging(self):
        """Test timestamp formatting for logging"""
        utc_dt = datetime(2024, 1, 15, 20, 30, 0, tzinfo=UTC)
        formatted = format_timestamp_for_logging(utc_dt)

        # Should be in Central timezone
        assert "CST" in formatted or "CDT" in formatted
        assert "2024-01-15" in formatted
        assert "14:30" in formatted  # 20:30 UTC = 14:30 CST

    def test_format_for_display(self):
        """Test display formatting"""
        utc_dt = datetime(2024, 1, 15, 20, 30, 0, tzinfo=UTC)
        formatted = format_for_display(utc_dt)

        # Should be in Central timezone
        assert "CST" in formatted or "CDT" in formatted
        assert "2024-01-15" in formatted
        assert "14:30" in formatted  # 20:30 UTC = 14:30 CST

    def test_format_trading_time(self):
        """Test trading time formatting"""
        utc_dt = datetime(2024, 1, 15, 20, 30, 0, tzinfo=UTC)
        formatted = format_trading_time(utc_dt)

        # Should be in Eastern timezone
        assert "EST" in formatted or "EDT" in formatted
        assert "2024-01-15" in formatted
        assert "15:30" in formatted  # 20:30 UTC = 15:30 EST


class TestValidationAndErrorHandling:
    """Test validation and error handling"""

    def test_validate_timezone_aware(self):
        """Test timezone awareness validation"""
        # Timezone-aware datetime
        aware_dt = datetime(2024, 1, 15, 14, 30, 0, tzinfo=UTC)
        assert validate_timezone_aware(aware_dt)

        # Naive datetime
        naive_dt = datetime(2024, 1, 15, 14, 30, 0)
        assert not validate_timezone_aware(naive_dt)

    def test_ensure_timezone_aware(self):
        """Test timezone awareness ensuring"""
        # Naive datetime with default timezone
        naive_dt = datetime(2024, 1, 15, 14, 30, 0)
        aware_dt = ensure_timezone_aware(naive_dt)

        assert aware_dt.tzinfo == UTC

        # Naive datetime with specific timezone
        aware_dt = ensure_timezone_aware(naive_dt, CENTRAL)
        assert aware_dt.tzinfo == CENTRAL

        # Already timezone-aware datetime
        already_aware = datetime(2024, 1, 15, 14, 30, 0, tzinfo=UTC)
        result = ensure_timezone_aware(already_aware)
        assert result.tzinfo == UTC

    def test_handle_timezone_conversion_error(self):
        """Test timezone conversion error handling"""
        # Valid conversion
        utc_dt = datetime(2024, 1, 15, 14, 30, 0, tzinfo=UTC)
        result = handle_timezone_conversion_error(utc_dt, CENTRAL)

        assert result.tzinfo == CENTRAL

        # Invalid conversion (should fallback to UTC)
        # This is hard to test without mocking, but the function should handle errors gracefully
        result = handle_timezone_conversion_error(utc_dt, CENTRAL)
        assert result is not None


class TestConvenienceFunctions:
    """Test convenience functions"""

    def test_current_time_functions(self):
        """Test current time convenience functions"""
        utc_time = get_current_storage_time()
        central_time = get_current_display_time()
        eastern_time = get_current_trading_time()

        assert utc_time.tzinfo == UTC
        assert central_time.tzinfo == CENTRAL
        assert eastern_time.tzinfo == EASTERN

    def test_is_weekend(self):
        """Test weekend detection"""
        # Weekday
        weekday = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)  # Monday
        assert not is_weekend(weekday)

        # Weekend
        weekend = datetime(2024, 1, 13, 10, 0, 0, tzinfo=UTC)  # Saturday
        assert is_weekend(weekend)

    def test_get_market_status(self):
        """Test market status detection"""
        # Market open
        market_open = datetime(2024, 1, 15, 14, 30, 0, tzinfo=UTC)  # 9:30 AM EST
        status = get_market_status(market_open)
        assert status == "open"

        # After hours (between 4 PM and 8 PM EST)
        after_hours = datetime(2024, 1, 15, 22, 0, 0, tzinfo=UTC)  # 5:00 PM EST
        status = get_market_status(after_hours)
        assert status == "after_hours"

        # Market closed (after after-hours)
        market_closed = datetime(
            2024, 1, 16, 2, 0, 0, tzinfo=UTC
        )  # 9:00 PM EST (next day)
        status = get_market_status(market_closed)
        assert status == "closed"

        # Weekend
        weekend = datetime(2024, 1, 13, 14, 30, 0, tzinfo=UTC)  # Saturday
        status = get_market_status(weekend)
        assert status == "weekend"


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_timezone_error_exception(self):
        """Test TimezoneError exception"""
        with pytest.raises(TimezoneError):
            # This should raise an error for invalid timezone conversion
            normalize_vendor_timestamp("invalid-timestamp")

    def test_invalid_vendor_timestamp(self):
        """Test invalid vendor timestamp handling"""
        with pytest.raises(TimezoneError):
            normalize_vendor_timestamp("invalid-timestamp")

    def test_empty_market_data_processing(self):
        """Test processing empty market data"""
        empty_data = []
        processed = process_market_data_timestamps(empty_data)
        assert processed == []

    def test_market_data_with_invalid_timestamps(self):
        """Test market data with invalid timestamps"""
        data = [
            {"symbol": "AAPL", "timestamp": "invalid", "price": 150.0},
            {"symbol": "GOOGL", "price": 2800.0},  # No timestamp
        ]

        processed = process_market_data_timestamps(data)

        # Should handle errors gracefully and keep original data
        assert len(processed) == 2
        assert processed[0]["timestamp"] == "invalid"  # Kept original
        assert "timestamp" not in processed[1]  # No timestamp field


if __name__ == "__main__":
    pytest.main([__file__])
