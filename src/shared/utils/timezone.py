"""
Timezone utilities for the trading system

This module provides comprehensive timezone handling for:
- UTC: Universal storage and vendor data (database storage)
- EST/EDT: Trading operations (market timezone)
- CST/CDT: User interface (your local timezone)

Author: Nishant Nayar
Email: nishant.nayar@hotmail.com
"""

from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Union
from zoneinfo import ZoneInfo

from loguru import logger

# Timezone definitions
UTC = ZoneInfo("UTC")
CENTRAL = ZoneInfo("America/Chicago")
EASTERN = ZoneInfo("America/New_York")

# Timezone aliases for clarity
USER_TIMEZONE = CENTRAL
TRADING_TIMEZONE = EASTERN
STORAGE_TIMEZONE = UTC


class TimezoneError(Exception):
    """Custom exception for timezone-related errors"""

    pass


# 1. Timezone Configuration Functions
def get_central_timezone() -> ZoneInfo:
    """Get Central timezone (user's local timezone)"""
    return CENTRAL


def get_eastern_timezone() -> ZoneInfo:
    """Get Eastern timezone (trading timezone)"""
    return EASTERN


def get_utc_timezone() -> ZoneInfo:
    """Get UTC timezone (storage timezone)"""
    return UTC


def now_utc() -> datetime:
    """Get current time in UTC"""
    return datetime.now(UTC)


def now_central() -> datetime:
    """Get current time in Central timezone"""
    return datetime.now(CENTRAL)


def now_eastern() -> datetime:
    """Get current time in Eastern timezone"""
    return datetime.now(EASTERN)


# 2. Conversion Functions
def to_utc(dt: datetime, tz: ZoneInfo) -> datetime:
    """
    Convert datetime to UTC

    Args:
        dt: Datetime to convert
        tz: Source timezone

    Returns:
        Datetime in UTC

    Raises:
        TimezoneError: If conversion fails
    """
    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        return dt.astimezone(UTC)
    except Exception as e:
        raise TimezoneError(f"Failed to convert to UTC: {e}")


def to_central(dt: datetime) -> datetime:
    """
    Convert datetime to Central timezone

    Args:
        dt: Datetime to convert

    Returns:
        Datetime in Central timezone

    Raises:
        TimezoneError: If conversion fails
    """
    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(CENTRAL)
    except Exception as e:
        raise TimezoneError(f"Failed to convert to Central: {e}")


def to_eastern(dt: datetime) -> datetime:
    """
    Convert datetime to Eastern timezone

    Args:
        dt: Datetime to convert

    Returns:
        Datetime in Eastern timezone

    Raises:
        TimezoneError: If conversion fails
    """
    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(EASTERN)
    except Exception as e:
        raise TimezoneError(f"Failed to convert to Eastern: {e}")


def convert_timezone(dt: datetime, from_tz: ZoneInfo, to_tz: ZoneInfo) -> datetime:
    """
    Convert datetime between timezones

    Args:
        dt: Datetime to convert
        from_tz: Source timezone
        to_tz: Target timezone

    Returns:
        Datetime in target timezone

    Raises:
        TimezoneError: If conversion fails
    """
    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=from_tz)
        return dt.astimezone(to_tz)
    except Exception as e:
        raise TimezoneError(f"Failed to convert from {from_tz} to {to_tz}: {e}")


# Smart conversion functions (detects source timezone)
def smart_convert_to_utc(dt: datetime) -> datetime:
    """
    Smart conversion to UTC, handling naive datetimes

    Args:
        dt: Datetime to convert

    Returns:
        Datetime in UTC

    Note:
        Assumes naive datetimes are in UTC
    """
    if dt.tzinfo is None:
        # Assume naive datetime is in UTC
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def smart_convert_to_central(dt: datetime) -> datetime:
    """
    Smart conversion to Central timezone

    Args:
        dt: Datetime to convert

    Returns:
        Datetime in Central timezone
    """
    utc_dt = smart_convert_to_utc(dt)
    return utc_dt.astimezone(CENTRAL)


def smart_convert_to_eastern(dt: datetime) -> datetime:
    """
    Smart conversion to Eastern timezone

    Args:
        dt: Datetime to convert

    Returns:
        Datetime in Eastern timezone
    """
    utc_dt = smart_convert_to_utc(dt)
    return utc_dt.astimezone(EASTERN)


# 3. Trading-Specific Utilities
def is_market_hours(dt: datetime) -> bool:
    """
    Check if datetime is during market hours (9:30 AM - 4:00 PM EST)

    Args:
        dt: Datetime to check

    Returns:
        True if during market hours, False otherwise
    """
    try:
        eastern_dt = to_eastern(dt)
        market_open = eastern_dt.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = eastern_dt.replace(hour=16, minute=0, second=0, microsecond=0)

        # Check if it's a weekday
        if eastern_dt.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False

        return market_open <= eastern_dt <= market_close
    except Exception as e:
        logger.error(f"Error checking market hours: {e}")
        return False


def get_next_market_open(dt: datetime) -> datetime:
    """
    Get next market open time in UTC

    Args:
        dt: Reference datetime

    Returns:
        Next market open time in UTC
    """
    try:
        eastern_dt = to_eastern(dt)
        next_open = eastern_dt.replace(hour=9, minute=30, second=0, microsecond=0)

        # If it's past today's market open, get tomorrow's
        if eastern_dt.time() > next_open.time():
            next_open += timedelta(days=1)

        # Skip weekends
        while next_open.weekday() >= 5:
            next_open += timedelta(days=1)

        return to_utc(next_open, EASTERN)
    except Exception as e:
        logger.error(f"Error getting next market open: {e}")
        return dt


def get_last_market_close(dt: datetime) -> datetime:
    """
    Get last market close time in UTC

    Args:
        dt: Reference datetime

    Returns:
        Last market close time in UTC
    """
    try:
        eastern_dt = to_eastern(dt)
        last_close = eastern_dt.replace(hour=16, minute=0, second=0, microsecond=0)

        # If it's before today's market close, get yesterday's
        if eastern_dt.time() < last_close.time():
            last_close -= timedelta(days=1)

        # Skip weekends
        while last_close.weekday() >= 5:
            last_close -= timedelta(days=1)

        return to_utc(last_close, EASTERN)
    except Exception as e:
        logger.error(f"Error getting last market close: {e}")
        return dt


def get_trading_day(dt: datetime) -> date:
    """
    Get trading day for a given datetime

    Args:
        dt: Datetime to get trading day for

    Returns:
        Trading day date
    """
    try:
        eastern_dt = to_eastern(dt)

        # If before market open, use previous trading day
        if eastern_dt.time() < time(9, 30):
            eastern_dt -= timedelta(days=1)

        # Skip weekends
        while eastern_dt.weekday() >= 5:
            eastern_dt -= timedelta(days=1)

        return eastern_dt.date()
    except Exception as e:
        logger.error(f"Error getting trading day: {e}")
        return dt.date()


def get_trading_timestamp(dt: datetime) -> datetime:
    """
    Convert to EST for trading operations

    Args:
        dt: Datetime to convert

    Returns:
        Datetime in Eastern timezone
    """
    return to_eastern(dt)


def get_display_timestamp(dt: datetime) -> datetime:
    """
    Convert to Central for UI display

    Args:
        dt: Datetime to convert

    Returns:
        Datetime in Central timezone
    """
    return to_central(dt)


# 4. Data Processing Utilities
def normalize_vendor_timestamp(
    dt: Union[datetime, str], vendor_tz: str = "UTC"
) -> datetime:
    """
    Normalize vendor timestamp to UTC

    Args:
        dt: Datetime or ISO string to normalize
        vendor_tz: Vendor's timezone (default: UTC)

    Returns:
        Normalized datetime in UTC

    Raises:
        TimezoneError: If normalization fails
    """
    try:
        if isinstance(dt, str):
            # Handle ISO format strings
            if dt.endswith("Z"):
                dt = dt.replace("Z", "+00:00")
            dt = datetime.fromisoformat(dt)

        if dt.tzinfo is None:
            # Assume vendor timezone
            vendor_zone = ZoneInfo(vendor_tz)
            dt = dt.replace(tzinfo=vendor_zone)

        return dt.astimezone(UTC)
    except Exception as e:
        raise TimezoneError(f"Failed to normalize vendor timestamp: {e}")


def process_market_data_timestamps(data: List[Dict]) -> List[Dict]:
    """
    Process market data timestamps to UTC

    Args:
        data: List of market data records

    Returns:
        Processed data with UTC timestamps
    """
    processed_data = []
    for record in data:
        try:
            if "timestamp" in record:
                record["timestamp"] = normalize_vendor_timestamp(record["timestamp"])
            processed_data.append(record)
        except Exception as e:
            logger.error(f"Error processing timestamp in record: {e}")
            # Keep original record if timestamp processing fails
            processed_data.append(record)

    return processed_data


def ensure_utc_timestamp(dt: datetime) -> datetime:
    """
    Ensure timestamp is in UTC for database storage

    Args:
        dt: Datetime to ensure is in UTC

    Returns:
        Datetime in UTC
    """
    if dt.tzinfo is None:
        # Assume naive datetime is in UTC
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def format_for_database(dt: datetime) -> datetime:
    """
    Format timestamp for database storage (UTC)

    Args:
        dt: Datetime to format

    Returns:
        Datetime in UTC for database storage
    """
    return ensure_utc_timestamp(dt)


# 5. Logging and Display
def log_with_timezone(message: str, level: str, tz: Optional[ZoneInfo] = None) -> None:
    """
    Log message with timezone context

    Args:
        message: Log message
        level: Log level (ERROR, WARNING, INFO, DEBUG)
        tz: Timezone for timestamp (default: Central)
    """
    if tz is None:
        tz = CENTRAL  # Default to user timezone

    timestamp = datetime.now(tz)
    formatted_message = f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S %Z')}] {message}"

    # Use appropriate log level
    if level.upper() == "ERROR":
        logger.error(formatted_message)
    elif level.upper() == "WARNING":
        logger.warning(formatted_message)
    elif level.upper() == "INFO":
        logger.info(formatted_message)
    else:
        logger.debug(formatted_message)


def format_timestamp_for_logging(dt: datetime) -> str:
    """
    Format timestamp for logging with timezone info

    Args:
        dt: Datetime to format

    Returns:
        Formatted timestamp string
    """
    central_dt = to_central(dt)
    return central_dt.strftime("%Y-%m-%d %H:%M:%S %Z")


def format_for_display(dt: datetime, format_str: Optional[str] = None) -> str:
    """
    Format timestamp for UI display

    Args:
        dt: Datetime to format
        format_str: Custom format string

    Returns:
        Formatted timestamp string
    """
    if format_str is None:
        format_str = "%Y-%m-%d %H:%M:%S %Z"

    central_dt = to_central(dt)
    return central_dt.strftime(format_str)


def format_trading_time(dt: datetime) -> str:
    """
    Format timestamp for trading context (Eastern)

    Args:
        dt: Datetime to format

    Returns:
        Formatted timestamp string in Eastern timezone
    """
    eastern_dt = to_eastern(dt)
    return eastern_dt.strftime("%Y-%m-%d %H:%M:%S %Z")


# 6. Validation and Error Handling
def validate_timezone_aware(dt: datetime) -> bool:
    """
    Validate that datetime is timezone-aware

    Args:
        dt: Datetime to validate

    Returns:
        True if timezone-aware, False otherwise
    """
    return dt.tzinfo is not None


def ensure_timezone_aware(
    dt: datetime, default_tz: Optional[ZoneInfo] = None
) -> datetime:
    """
    Ensure datetime is timezone-aware

    Args:
        dt: Datetime to make timezone-aware
        default_tz: Default timezone if datetime is naive

    Returns:
        Timezone-aware datetime
    """
    if dt.tzinfo is None:
        if default_tz is None:
            default_tz = UTC
        return dt.replace(tzinfo=default_tz)
    return dt


def handle_timezone_conversion_error(dt: datetime, target_tz: ZoneInfo) -> datetime:
    """
    Handle timezone conversion errors gracefully

    Args:
        dt: Datetime to convert
        target_tz: Target timezone

    Returns:
        Converted datetime or fallback to UTC
    """
    try:
        return dt.astimezone(target_tz)
    except Exception as e:
        logger.error(f"Timezone conversion error: {e}")
        # Fallback to UTC
        return ensure_timezone_aware(dt, UTC).astimezone(target_tz)


# 7. Convenience Functions
def get_current_trading_time() -> datetime:
    """Get current time in trading timezone (Eastern)"""
    return now_eastern()


def get_current_display_time() -> datetime:
    """Get current time in display timezone (Central)"""
    return now_central()


def get_current_storage_time() -> datetime:
    """Get current time in storage timezone (UTC)"""
    return now_utc()


def is_weekend(dt: datetime) -> bool:
    """
    Check if datetime is on a weekend

    Args:
        dt: Datetime to check

    Returns:
        True if weekend, False otherwise
    """
    eastern_dt = to_eastern(dt)
    return eastern_dt.weekday() >= 5


def get_market_status(dt: datetime) -> str:
    """
    Get market status for a given datetime

    Args:
        dt: Datetime to check

    Returns:
        Market status: 'open', 'closed', 'weekend', 'pre_market', 'after_hours'
    """
    if is_weekend(dt):
        return "weekend"

    eastern_dt = to_eastern(dt)
    market_open = eastern_dt.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = eastern_dt.replace(hour=16, minute=0, second=0, microsecond=0)
    pre_market_start = eastern_dt.replace(hour=4, minute=0, second=0, microsecond=0)
    after_hours_end = eastern_dt.replace(hour=20, minute=0, second=0, microsecond=0)

    if pre_market_start <= eastern_dt < market_open:
        return "pre_market"
    elif market_open <= eastern_dt <= market_close:
        return "open"
    elif market_close < eastern_dt <= after_hours_end:
        return "after_hours"
    else:
        return "closed"
