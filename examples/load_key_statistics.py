"""
Load Key Statistics from Yahoo Finance

Simple script to load comprehensive financial metrics into the database.
"""

import asyncio
from datetime import date

from loguru import logger

from src.services.yahoo.loader import YahooDataLoader
from src.shared.logging import setup_logging


async def load_single_symbol(symbol: str) -> None:
    """Load key statistics for a single symbol"""
    loader = YahooDataLoader()

    logger.info(f"Loading key statistics for {symbol}...")
    success = await loader.load_key_statistics(symbol)

    if success:
        logger.info(f"Successfully loaded key statistics for {symbol} [OK]")
    else:
        logger.error(f"Failed to load key statistics for {symbol} [FAIL]")


async def load_multiple_symbols(symbols: list[str]) -> None:
    """Load key statistics for multiple symbols"""
    loader = YahooDataLoader(delay_between_requests=0.5)

    successful = 0
    failed = 0

    for i, symbol in enumerate(symbols, 1):
        logger.info(f"Processing {i}/{len(symbols)}: {symbol}")

        try:
            success = await loader.load_key_statistics(symbol)
            if success:
                successful += 1
                logger.info(f"[OK] {symbol}")
            else:
                failed += 1
                logger.error(f"[FAIL] {symbol}")

            # Rate limiting
            if i < len(symbols):
                await asyncio.sleep(0.5)

        except Exception as e:
            failed += 1
            logger.error(f"[FAIL] {symbol}: {e}")

    logger.info(f"\nCompleted: {successful} successful, {failed} failed")


async def main() -> None:
    """Main execution"""
    setup_logging()

    # Example 1: Load single symbol
    await load_single_symbol("AAPL")

    # Example 2: Load multiple symbols
    tech_stocks = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
    await load_multiple_symbols(tech_stocks)


if __name__ == "__main__":
    asyncio.run(main())
