"""
Timezone Usage Examples

This module demonstrates how to use the timezone utilities in the trading system.
It shows practical examples for data ingestion, trading operations, UI display,
and logging with proper timezone handling.

Author: Nishant Nayar
Email: nishant.nayar@hotmail.com
"""

from datetime import datetime
from typing import Dict, List

from src.shared.utils.timezone import (  # Core timezone functions; Trading utilities; Data processing; Display formatting; Logging
    ensure_utc_timestamp,
    format_for_display,
    format_timestamp_for_logging,
    format_trading_time,
    get_market_status,
    get_trading_day,
    is_market_hours,
    log_with_timezone,
    normalize_vendor_timestamp,
    now_central,
    now_eastern,
    now_utc,
    to_central,
    to_eastern,
    to_utc,
)
from src.web.api.timezone_helpers import (
    TimestampResponse,
    format_api_response_with_timestamps,
    get_current_time_info,
    get_market_status_info,
)


def example_data_ingestion():
    """Example: Processing vendor data with UTC timestamps"""
    print("=== Data Ingestion Example ===")

    # Simulate vendor data (often comes in UTC)
    vendor_data = {
        "symbol": "AAPL",
        "timestamp": "2024-01-15T14:30:00Z",  # UTC timestamp
        "price": 150.25,
        "volume": 1000000,
    }

    # Normalize vendor timestamp to UTC
    utc_timestamp = normalize_vendor_timestamp(vendor_data["timestamp"])
    print(f"Vendor timestamp: {vendor_data['timestamp']}")
    print(f"Normalized UTC: {utc_timestamp.isoformat()}")

    # Store in database (already UTC)
    db_record = {
        "symbol": vendor_data["symbol"],
        "timestamp": ensure_utc_timestamp(utc_timestamp),
        "price": vendor_data["price"],
        "volume": vendor_data["volume"],
    }

    print(f"Database record timestamp: {db_record['timestamp'].isoformat()}")
    print()


def example_trading_operations():
    """Example: Trading operations with Eastern timezone"""
    print("=== Trading Operations Example ===")

    # Get current time in different timezones
    utc_now = now_utc()
    eastern_now = now_eastern()
    central_now = now_central()

    print(f"Current UTC time: {utc_now.isoformat()}")
    print(f"Current Eastern time: {eastern_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Current Central time: {central_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # Check market status
    market_status = get_market_status(utc_now)
    print(f"Market status: {market_status}")

    # Check if market is open
    if is_market_hours(utc_now):
        print("[OK] Market is open - can execute trades")

        # Simulate trade execution
        trade_data = {
            "symbol": "AAPL",
            "side": "buy",
            "quantity": 100,
            "price": 150.25,
            "executed_at": utc_now,
        }

        print(f"Trade executed at: {format_trading_time(trade_data['executed_at'])}")
    else:
        print("[FAIL] Market is closed - no trading")

    print()


def example_ui_display():
    """Example: UI display with Central timezone"""
    print("=== UI Display Example ===")

    # Simulate database record with UTC timestamp
    db_record = {
        "trade_id": "TRD-001",
        "symbol": "AAPL",
        "executed_at": datetime(2024, 1, 15, 20, 30, 0, tzinfo=None),  # Naive UTC
    }

    # Convert to UTC for processing
    utc_timestamp = ensure_utc_timestamp(db_record["executed_at"])

    # Display in user's timezone (Central)
    display_time = format_for_display(utc_timestamp)
    print(f"Trade executed at: {display_time}")

    # Create timezone-aware API response
    api_response = {
        "trade_id": db_record["trade_id"],
        "symbol": db_record["symbol"],
        "executed_at": utc_timestamp,
    }

    # Format with timezone information
    formatted_response = format_api_response_with_timestamps(api_response)
    print(f"API Response: {formatted_response}")

    # Get current time information for UI
    time_info = get_current_time_info()
    print(f"Current time info: {time_info}")
    print()


def example_logging():
    """Example: Logging with timezone context"""
    print("=== Logging Example ===")

    # Log with timezone context
    log_with_timezone("System started successfully", "INFO")
    log_with_timezone("Database connection established", "INFO")

    # Simulate trade logging
    trade_timestamp = now_utc()
    log_with_timezone(f"Trade executed: AAPL 100 shares at $150.25", "INFO")

    # Format timestamp for logging
    formatted_timestamp = format_timestamp_for_logging(trade_timestamp)
    print(f"Formatted log timestamp: {formatted_timestamp}")

    # Log with specific timezone
    log_with_timezone("Trading session ended", "INFO")
    print()


def example_market_data_processing():
    """Example: Processing market data with timestamps"""
    print("=== Market Data Processing Example ===")

    # Simulate market data from vendor
    market_data = [
        {
            "symbol": "AAPL",
            "timestamp": "2024-01-15T14:30:00Z",
            "open": 150.00,
            "high": 150.50,
            "low": 149.75,
            "close": 150.25,
            "volume": 1000000,
        },
        {
            "symbol": "GOOGL",
            "timestamp": "2024-01-15T14:31:00Z",
            "open": 2800.00,
            "high": 2805.00,
            "low": 2798.00,
            "close": 2802.50,
            "volume": 500000,
        },
    ]

    print("Original market data:")
    for data in market_data:
        print(f"  {data['symbol']}: {data['timestamp']} - ${data['close']}")

    # Process timestamps to UTC
    from src.shared.utils.timezone import process_market_data_timestamps

    processed_data = process_market_data_timestamps(market_data)

    print("\nProcessed market data (UTC):")
    for data in processed_data:
        utc_time = data["timestamp"]
        display_time = format_for_display(utc_time)
        trading_time = format_trading_time(utc_time)
        print(f"  {data['symbol']}:")
        print(f"    UTC: {utc_time.isoformat()}")
        print(f"    Central: {display_time}")
        print(f"    Eastern: {trading_time}")
        print(f"    Price: ${data['close']}")

    print()


def example_api_responses():
    """Example: API responses with timezone information"""
    print("=== API Response Example ===")

    # Simulate trade data
    trade_data = {
        "trade_id": "TRD-001",
        "symbol": "AAPL",
        "side": "buy",
        "quantity": 100,
        "price": 150.25,
        "executed_at": now_utc(),
    }

    # Create timezone-aware response
    timestamp_response = TimestampResponse.from_datetime(trade_data["executed_at"])

    print("Trade data with timezone information:")
    print(f"  Trade ID: {trade_data['trade_id']}")
    print(f"  Symbol: {trade_data['symbol']}")
    print(f"  Executed at:")
    print(f"    Display (Central): {timestamp_response.timestamp}")
    print(f"    UTC: {timestamp_response.timestamp_utc}")
    print(f"    Trading (Eastern): {timestamp_response.timestamp_trading}")

    # Get market status for API
    market_info = get_market_status_info()
    print(f"\nMarket status: {market_info}")

    print()


def example_error_handling():
    """Example: Error handling in timezone operations"""
    print("=== Error Handling Example ===")

    try:
        # This should work fine
        utc_time = now_utc()
        central_time = to_central(utc_time)
        print(
            f"[OK] Conversion successful: {central_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )

    except Exception as e:
        print(f"[FAIL] Conversion failed: {e}")

    try:
        # This might fail with invalid timezone
        invalid_timezone = None
        result = to_utc(datetime.now(), invalid_timezone)
        print(f"[OK] Fallback successful: {result}")

    except Exception as e:
        print(f"[FAIL] Conversion failed: {e}")

    # Test vendor data with invalid timestamp
    try:
        invalid_timestamp = "invalid-timestamp-format"
        normalized = normalize_vendor_timestamp(invalid_timestamp)
        print(f"[OK] Normalization successful: {normalized}")

    except Exception as e:
        print(f"[FAIL] Normalization failed: {e}")

    print()


def main():
    """Run all examples"""
    print("Trading System Timezone Usage Examples")
    print("=" * 50)
    print()

    example_data_ingestion()
    example_trading_operations()
    example_ui_display()
    example_logging()
    example_market_data_processing()
    example_api_responses()
    example_error_handling()

    print("[OK] All examples completed successfully!")
    print("\nKey Takeaways:")
    print("1. Always store timestamps in UTC in the database")
    print("2. Convert to user timezone (Central) for UI display")
    print("3. Convert to trading timezone (Eastern) for trading operations")
    print("4. Use timezone-aware logging for better debugging")
    print("5. Handle timezone conversion errors gracefully")


if __name__ == "__main__":
    main()
