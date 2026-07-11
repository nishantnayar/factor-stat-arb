"""
Yahoo Finance Data Loader Usage Examples

Demonstrates how to use the Yahoo Finance data loader.
"""

import asyncio
from datetime import date, timedelta

from src.services.yahoo.loader import YahooDataLoader
from src.shared.logging import setup_logging


async def example_1_basic_usage() -> None:
    """Example 1: Basic usage - load market data for a single symbol"""
    print("\n" + "=" * 80)
    print("Example 1: Load 30 days of daily data for AAPL")
    print("=" * 80)

    loader = YahooDataLoader()

    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    count = await loader.load_market_data(
        symbol="AAPL", start_date=start_date, end_date=end_date, interval="1d"
    )

    print(f"[OK] Loaded {count} records for AAPL")


async def example_2_multiple_symbols() -> None:
    """Example 2: Load data for multiple specific symbols"""
    print("\n" + "=" * 80)
    print("Example 2: Load data for FAANG stocks")
    print("=" * 80)

    loader = YahooDataLoader(delay_between_requests=0.5)
    symbols = ["META", "AAPL", "AMZN", "NFLX", "GOOGL"]

    end_date = date.today()
    start_date = end_date - timedelta(days=7)

    for symbol in symbols:
        try:
            count = await loader.load_market_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
            )
            print(f"[OK] {symbol}: {count} records")
            await asyncio.sleep(0.5)  # Be polite to Yahoo
        except Exception as e:
            print(f"[FAIL] {symbol}: {e}")


async def example_3_all_symbols() -> None:
    """Example 3: Load data for all active symbols"""
    print("\n" + "=" * 80)
    print("Example 3: Load data for all active symbols (limited to 5 for demo)")
    print("=" * 80)

    loader = YahooDataLoader()

    end_date = date.today()
    start_date = end_date - timedelta(days=7)

    stats = await loader.load_all_symbols_data(
        start_date=start_date,
        end_date=end_date,
        max_symbols=5,  # Limit for demo
    )

    print(f"\nLoading Statistics:")
    print(f"   Total symbols processed: {stats['total_symbols']}")
    print(f"   Successful: {stats['successful']}")
    print(f"   Failed: {stats['failed']}")
    print(f"   Total records loaded: {stats['total_records']}")


async def example_4_intraday_data() -> None:
    """Example 4: Load intraday data (1-hour intervals)"""
    print("\n" + "=" * 80)
    print("Example 4: Load 1-hour intraday data for AAPL (last 5 days)")
    print("=" * 80)

    loader = YahooDataLoader()

    end_date = date.today()
    start_date = end_date - timedelta(days=5)

    count = await loader.load_market_data(
        symbol="AAPL",
        start_date=start_date,
        end_date=end_date,
        interval="1h",  # Hourly data
    )

    print(f"[OK] Loaded {count} hourly records for AAPL")


async def example_5_health_check() -> None:
    """Example 5: Health check"""
    print("\n" + "=" * 80)
    print("Example 5: Health check")
    print("=" * 80)

    loader = YahooDataLoader()

    healthy = await loader.health_check()

    if healthy:
        print("[OK] Yahoo Finance API is accessible")
    else:
        print("[FAIL] Yahoo Finance API is not accessible")


async def example_6_comprehensive_load() -> None:
    """Example 6: Load all data types"""
    print("\n" + "=" * 80)
    print("Example 6: Comprehensive data load (market data + fundamentals)")
    print("=" * 80)

    loader = YahooDataLoader()

    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    results = await loader.load_all_data(
        symbol="AAPL",
        start_date=start_date,
        end_date=end_date,
        include_fundamentals=True,
        include_dividends=True,
        include_splits=True,
    )

    print(f"\nLoading Results:")
    print(f"   Market data records: {results['market_data']}")
    print(f"   Company info: {results['company_info']}")
    print(f"   Dividends: {results['dividends']}")
    print(f"   Splits: {results['splits']}")


async def main() -> None:
    """Run all examples"""
    setup_logging()

    print("\n" + "#" * 80)
    print("# Yahoo Finance Data Loader - Usage Examples")
    print("#" * 80)

    # Run examples
    await example_5_health_check()
    await example_1_basic_usage()
    await example_4_intraday_data()
    await example_2_multiple_symbols()
    await example_3_all_symbols()
    await example_6_comprehensive_load()

    print("\n" + "#" * 80)
    print("# All examples completed!")
    print("#" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
