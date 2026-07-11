"""
Populate Technical Indicators Tables

Backfill script to calculate and store technical indicators for all active symbols.
Can be run to:
1. Initial population of tables
2. Backfill historical data
3. Update missing dates

Usage:
    python scripts/populate_technical_indicators.py --symbols AAPL MSFT GOOGL
    python scripts/populate_technical_indicators.py --all --days-back 365
    python scripts/populate_technical_indicators.py --date 2025-01-15
"""

import asyncio
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional

import click
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.analytics import IndicatorService
from src.services.data_ingestion.symbols import SymbolService


async def check_tables_exist() -> bool:
    """Check if technical indicators tables exist"""
    from sqlalchemy import inspect

    from src.shared.database.base import get_engine
    
    engine = get_engine("trading")
    inspector = inspect(engine)
    
    # Check if tables exist in analytics schema
    tables = inspector.get_table_names(schema="analytics")
    
    required_tables = ["technical_indicators_latest", "technical_indicators"]
    missing = [t for t in required_tables if t not in tables]
    
    if missing:
        logger.error(
            f"Missing required tables in analytics schema: {', '.join(missing)}\n"
            f"Please run: psql -U postgres -d trading_system -f scripts/17_create_technical_indicators_tables.sql"
        )
        return False
    
    logger.info("Technical indicators tables verified")
    return True


async def populate_indicators(
    symbols: Optional[List[str]] = None,
    calculation_date: Optional[date] = None,
    days_back: int = 300,
    all_symbols: bool = False,
) -> None:
    """
    Populate technical indicators for symbols
    
    Args:
        symbols: List of symbols to process (if None and all_symbols=False, uses all active)
        calculation_date: Date to calculate for (default: today)
        days_back: Days of history to fetch for calculations (default: 300)
        all_symbols: If True, process all active symbols
    """
    if calculation_date is None:
        calculation_date = date.today()
    
    # Warn if calculating for a weekend (no market data on weekends)
    weekday = calculation_date.weekday()
    if weekday >= 5:  # Saturday or Sunday
        logger.warning(
            f"Warning: {calculation_date} is a {'Saturday' if weekday == 5 else 'Sunday'}. "
            f"No market data available on weekends. Indicators will use the last trading day's data."
        )
    
    # Check if tables exist
    if not await check_tables_exist():
        logger.error("Cannot proceed - tables do not exist")
        return
    
    service = IndicatorService(data_source="yahoo_adjusted")
    symbol_service = SymbolService()
    
    # Get symbols to process
    if all_symbols or symbols is None:
        logger.info("Fetching all active symbols...")
        active_symbols = await symbol_service.get_active_symbol_strings()
        symbols_to_process = active_symbols
        logger.info(f"Found {len(symbols_to_process)} active symbols")
    else:
        symbols_to_process = [s.upper() for s in symbols]
        logger.info(f"Processing {len(symbols_to_process)} specified symbols")
    
    if not symbols_to_process:
        logger.warning("No symbols to process")
        return
    
    logger.info(
        f"Starting indicator population for {len(symbols_to_process)} symbols "
        f"on {calculation_date} (using {days_back} days of history)"
    )
    
    # Batch calculate and store
    results = await service.batch_calculate_and_store(
        symbols=symbols_to_process,
        calculation_date=calculation_date,
        days_back=days_back,
    )
    
    # Report results
    successful = [s for s, success in results.items() if success]
    failed = [s for s, success in results.items() if not success]
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Population Complete")
    logger.info(f"{'='*60}")
    logger.info(f"Total symbols: {len(symbols_to_process)}")
    logger.info(f"Successful: {len(successful)}")
    logger.info(f"Failed: {len(failed)}")
    
    if successful:
        logger.info(f"\nSuccessful symbols: {', '.join(successful[:10])}")
        if len(successful) > 10:
            logger.info(f"... and {len(successful) - 10} more")
    
    if failed:
        logger.warning(f"\nFailed symbols: {', '.join(failed)}")


async def backfill_historical(
    start_date: date,
    end_date: date,
    symbols: Optional[List[str]] = None,
    all_symbols: bool = False,
) -> None:
    """
    Backfill historical indicators for a date range
    
    Args:
        symbols: List of symbols to process
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        all_symbols: If True, process all active symbols
    """
    service = IndicatorService(data_source="yahoo_adjusted")
    symbol_service = SymbolService()
    
    # Get symbols to process
    if all_symbols or symbols is None:
        active_symbols = await symbol_service.get_active_symbol_strings()
        symbols_to_process = active_symbols
    else:
        symbols_to_process = [s.upper() for s in symbols]
    
    logger.info(
        f"Backfilling indicators for {len(symbols_to_process)} symbols "
        f"from {start_date} to {end_date}"
    )
    
    # Process each date (skip weekends - only process trading days)
    current_date = start_date
    total_days = (end_date - start_date).days + 1
    processed_days = 0
    skipped_weekends = 0
    
    while current_date <= end_date:
        # Skip weekends (Saturday=5, Sunday=6)
        weekday = current_date.weekday()
        if weekday >= 5:  # Saturday or Sunday
            skipped_weekends += 1
            logger.debug(f"Skipping weekend date: {current_date} ({'Saturday' if weekday == 5 else 'Sunday'})")
            current_date += timedelta(days=1)
            continue
        
        processed_days += 1
        logger.info(f"\nProcessing date: {current_date} ({processed_days} trading days processed, {skipped_weekends} weekends skipped)")
        
        results = await service.batch_calculate_and_store(
            symbols=symbols_to_process,
            calculation_date=current_date,
            days_back=300,  # Need enough history for calculations
        )
        
        successful = sum(1 for success in results.values() if success)
        logger.info(f"  Completed: {successful}/{len(symbols_to_process)} symbols")
        
        current_date += timedelta(days=1)
        
        # Small delay to avoid overwhelming the database
        await asyncio.sleep(0.1)
    
    logger.info(f"\nBackfill complete: Processed {processed_days} trading days, skipped {skipped_weekends} weekend days")


@click.command()
@click.option(
    "--symbols",
    "-s",
    multiple=True,
    help="Symbols to process (can specify multiple: -s AAPL -s MSFT)",
)
@click.option(
    "--all",
    "all_symbols",
    is_flag=True,
    help="Process all active symbols",
)
@click.option(
    "--date",
    "calculation_date_str",
    type=str,
    help="Date to calculate for (YYYY-MM-DD, default: today)",
)
@click.option(
    "--days-back",
    default=300,
    type=int,
    help="Days of history to fetch for calculations (default: 300)",
)
@click.option(
    "--backfill",
    is_flag=True,
    help="Backfill historical data (requires --start-date and --end-date)",
)
@click.option(
    "--start-date",
    type=str,
    help="Start date for backfill (YYYY-MM-DD)",
)
@click.option(
    "--end-date",
    type=str,
    help="End date for backfill (YYYY-MM-DD)",
)
def main(
    symbols: tuple,
    all_symbols: bool,
    calculation_date_str: Optional[str],
    days_back: int,
    backfill: bool,
    start_date: Optional[str],
    end_date: Optional[str],
):
    """
    Populate technical indicators tables
    
    Examples:
        # Process specific symbols for today
        python populate_technical_indicators.py -s AAPL -s MSFT
        
        # Process all active symbols for today
        python populate_technical_indicators.py --all
        
        # Process for a specific date
        python populate_technical_indicators.py --all --date 2025-01-15
        
        # Backfill historical data
        python populate_technical_indicators.py --all --backfill --start-date 2024-01-01 --end-date 2024-12-31
    """
    # Configure logging
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
    )
    
    # Parse calculation date
    calculation_date = None
    if calculation_date_str:
        try:
            calculation_date = datetime.strptime(calculation_date_str, "%Y-%m-%d").date()
        except ValueError:
            logger.error(f"Invalid date format: {calculation_date_str}. Use YYYY-MM-DD")
            sys.exit(1)
    
    # Convert symbols tuple to list
    symbols_list = list(symbols) if symbols else None
    
    # Validate options
    if not all_symbols and not symbols_list:
        logger.error("Must specify either --symbols or --all")
        sys.exit(1)
    
    if backfill:
        if not start_date or not end_date:
            logger.error("Backfill requires --start-date and --end-date")
            sys.exit(1)
        
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            logger.error("Invalid date format. Use YYYY-MM-DD")
            sys.exit(1)
        
        if start > end:
            logger.error("Start date must be before end date")
            sys.exit(1)
        
        # Run backfill
        asyncio.run(backfill_historical(start, end, symbols_list, all_symbols))
    else:
        # Run normal population
        asyncio.run(
            populate_indicators(
                symbols=symbols_list,
                calculation_date=calculation_date,
                days_back=days_back,
                all_symbols=all_symbols,
            )
        )


if __name__ == "__main__":
    main()

