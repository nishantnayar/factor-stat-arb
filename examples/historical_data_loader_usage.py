#!/usr/bin/env python3
"""
Example usage of the Historical Data Loader

This script demonstrates how to use the historical data loader.
"""

import asyncio
import sys
from datetime import date, timedelta

# Add src to path for imports
sys.path.insert(0, "src")

from src.services.data_ingestion.historical_loader import HistoricalDataLoader


async def example_direct_usage():
    """Example of using the loader directly"""
    print("=== Direct Usage Example ===")

    # Initialize the loader (2 requests per minute for free tier)
    loader = HistoricalDataLoader(batch_size=50, requests_per_minute=2)

    # Health check
    healthy = await loader.health_check()
    print(f"Loader health check: {'PASS' if healthy else 'FAIL'}")

    if not healthy:
        print("Skipping data loading due to health check failure")
        return

    # Load daily data for a single symbol
    print("\nLoading daily data for AAPL (last 7 days)...")
    try:
        records_count = await loader.load_symbol_data(
            symbol="AAPL", days_back=7, timespan="day", multiplier=1
        )
        print(f"Loaded {records_count} daily records for AAPL")
    except Exception as e:
        print(f"Error loading AAPL data: {e}")

    # Load hourly data for a single symbol
    print("\nLoading hourly data for AAPL (last 2 days)...")
    try:
        records_count = await loader.load_symbol_data(
            symbol="AAPL", days_back=2, timespan="hour", multiplier=1
        )
        print(f"Loaded {records_count} hourly records for AAPL")
    except Exception as e:
        print(f"Error loading AAPL hourly data: {e}")

    # Load 5-minute data for a single symbol
    print("\nLoading 5-minute data for AAPL (last 1 day)...")
    try:
        records_count = await loader.load_symbol_data(
            symbol="AAPL", days_back=1, timespan="minute", multiplier=5
        )
        print(f"Loaded {records_count} 5-minute records for AAPL")
    except Exception as e:
        print(f"Error loading AAPL 5-minute data: {e}")

    # Load data for multiple symbols
    print("\nLoading daily data for multiple symbols...")
    symbols = ["AAPL", "MSFT", "GOOGL"]
    for symbol in symbols:
        try:
            records_count = await loader.load_symbol_data(
                symbol=symbol, days_back=3, timespan="day", multiplier=1
            )
            print(f"Loaded {records_count} daily records for {symbol}")
        except Exception as e:
            print(f"Error loading {symbol} data: {e}")

    # Get loading progress
    print("\nGetting loading progress...")
    from_date = date.today() - timedelta(days=7)
    to_date = date.today()
    progress = await loader.get_loading_progress(from_date, to_date)
    print(f"Progress: {progress}")


async def example_batch_loading():
    """Example of batch loading multiple symbols"""
    print("\n=== Batch Loading Example ===")

    loader = HistoricalDataLoader(batch_size=50, requests_per_minute=2)

    # Load data for multiple symbols with error handling
    symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"]
    print(f"\nLoading daily data for {len(symbols)} symbols...")

    for i, symbol in enumerate(symbols, 1):
        try:
            print(f"Loading {symbol} ({i}/{len(symbols)})...")
            records_count = await loader.load_symbol_data(
                symbol=symbol, days_back=7, timespan="day", multiplier=1
            )
            print(f"[OK] Loaded {records_count} daily records for {symbol}")
        except Exception as e:
            print(f"[FAIL] Error loading {symbol} data: {e}")


async def example_incremental_loading():
    """Example of incremental loading"""
    print("\n=== Incremental Loading Example ===")

    loader = HistoricalDataLoader(batch_size=50, requests_per_minute=2)

    # First load - full load
    print("\nFirst load (full): Loading 30 days of data...")
    try:
        records_count = await loader.load_symbol_data(
            symbol="AAPL", days_back=30, incremental=False
        )
        print(f"[OK] Full load: {records_count} records loaded")
    except Exception as e:
        print(f"[FAIL] Error in full load: {e}")

    # Second load - incremental (should load only new data)
    print("\nSecond load (incremental): Loading only new data...")
    try:
        records_count = await loader.load_symbol_data(
            symbol="AAPL", days_back=1, incremental=True
        )
        print(f"[OK] Incremental load: {records_count} records loaded")
    except Exception as e:
        print(f"[FAIL] Error in incremental load: {e}")


async def main():
    """Main function to run examples"""
    print("Historical Data Loader Usage Examples")
    print("=" * 50)

    # Run direct usage example
    await example_direct_usage()

    # Run batch loading example
    await example_batch_loading()

    # Run incremental loading example
    await example_incremental_loading()

    print("\nExamples completed!")


if __name__ == "__main__":
    asyncio.run(main())
