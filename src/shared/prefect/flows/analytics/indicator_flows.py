"""
Technical Indicators Calculation Flows

Prefect flows for calculating and storing technical indicators.
"""

import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

# Add project root to path when running directly
if __file__ and Path(__file__).exists():
    project_root = Path(__file__).parent.parent.parent.parent.parent.parent
    if project_root.exists() and str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from loguru import logger
from prefect import flow

from src.services.analytics import IndicatorService
from src.services.data_ingestion.symbols import SymbolService


def _indicators_run_name() -> str:
    """Generate business-friendly run name for indicators flow."""
    from datetime import datetime
    run_date = datetime.now().strftime("%Y-%m-%d")
    return f"Technical Indicators Calculation - {run_date}"


@flow(
    name="Daily Technical Indicators Calculation",
    flow_run_name=_indicators_run_name,
    log_prints=True,
    retries=1,
    retry_delay_seconds=300,
    timeout_seconds=3600,
)
async def calculate_daily_indicators(
    symbols: Optional[List[str]] = None,
    calculation_date: Optional[date] = None,
    days_back: int = 300,
    max_symbols: Optional[int] = None,
) -> dict:
    """
    Calculate technical indicators for all symbols
    
    Runs after data ingestion flows complete.
    
    Args:
        symbols: Optional list of specific symbols (None = all active)
        calculation_date: Date to calculate for (default: today)
        days_back: Days of history to fetch from database for calculations (default: 300)
                   Note: This fetches historical data from DB, not from API.
                   Need at least 200 days for SMA_200, 14 days for RSI, etc.
        max_symbols: Maximum number of symbols to process (for testing)
        
    Returns:
        Dictionary with calculation statistics
    """
    logger.info("=" * 60)
    logger.info("Starting Daily Indicators Calculation")
    logger.info("=" * 60)
    
    if calculation_date is None:
        calculation_date = date.today()
    
    # Get symbols
    if symbols is None:
        symbol_service = SymbolService()
        symbols_list = await symbol_service.get_active_symbol_strings()
        logger.info(f"Found {len(symbols_list)} active symbols")
    else:
        symbols_list = [s.upper() for s in symbols]
        logger.info(f"Processing {len(symbols_list)} specified symbols")
    
    if max_symbols:
        symbols_list = symbols_list[:max_symbols]
        logger.info(f"Limited to {max_symbols} symbols for testing")
    
    # Initialize indicator service
    indicator_service = IndicatorService(data_source="yahoo_adjusted")
    
    successful = []
    failed = []
    
    logger.info(f"Calculating indicators for {len(symbols_list)} symbols on {calculation_date}")
    logger.info(f"Using {days_back} days of history for calculations")
    
    # Batch calculate and store indicators
    results = await indicator_service.batch_calculate_and_store(
        symbols=symbols_list,
        calculation_date=calculation_date,
        days_back=days_back,
    )
    
    # Process results
    for symbol, success in results.items():
        if success:
            successful.append(symbol)
        else:
            failed.append(symbol)
    
    result = {
        "calculation_date": calculation_date.isoformat(),
        "total_symbols": len(symbols_list),
        "successful": len(successful),
        "failed": len(failed),
        "successful_symbols": successful,
        "failed_symbols": failed,
    }
    
    logger.info("=" * 60)
    logger.info("Indicators Calculation Completed")
    logger.info(f"Successful: {result['successful']}/{result['total_symbols']}")
    logger.info(f"Failed: {result['failed']}")
    logger.info("=" * 60)
    
    return result

