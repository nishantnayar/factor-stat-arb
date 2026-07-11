# Prefect Deployment Code Patterns

> **📋 Implementation Status**: 🚧 In Progress  
> **Prefect Version**: 3.4.14

This document covers code structure, task patterns, flow patterns, and deployment definitions for Prefect 3.4.14.

## Code Structure & Patterns

**Implementation Note:** Each section below will be implemented incrementally. Start with Phase 1 (Configuration), then build flows as needed.

## Configuration Module (Phase 1)

**Create: `src/shared/prefect/config.py`** (First file to create)

```python
"""
Prefect Configuration for Trading System
"""
import os
from typing import Optional
from prefect import get_client
from prefect.settings import PREFECT_API_URL
from src.config.settings import settings
from loguru import logger


def get_prefect_client():
    """
    Get Prefect client with proper configuration
    
    Returns:
        Prefect client instance
    """
    # Ensure API URL is set
    if not os.getenv("PREFECT_API_URL"):
        os.environ["PREFECT_API_URL"] = settings.prefect_api_url
    
    return get_client()


def verify_prefect_connection() -> bool:
    """
    Verify connection to Prefect server
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        client = get_prefect_client()
        # Simple health check
        client.read_flows()
        logger.info("✅ Prefect server connection verified")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to connect to Prefect server: {e}")
        return False
```

## Task Patterns (Phase 2+)

**Create: `src/shared/prefect/tasks/data_ingestion_tasks.py`** (Created when implementing flows)

```python
"""
Reusable Prefect Tasks for Data Ingestion
"""
from datetime import date
from typing import Optional
from prefect import task
from loguru import logger
from src.services.data_ingestion.historical_loader import HistoricalDataLoader
from src.services.yahoo.loader import YahooDataLoader


@task(
    name="load-polygon-symbol-data",
    retries=3,
    retry_delay_seconds=60,
    log_prints=True,
    tags=["data-ingestion", "polygon"]
)
async def load_polygon_symbol_data_task(
    symbol: str,
    days_back: int = 1,
    incremental: bool = True
) -> int:
    """
    Load historical data for a single symbol from Polygon.io
    
    Args:
        symbol: Stock symbol
        days_back: Number of days to look back
        incremental: Whether to use incremental loading
        
    Returns:
        Number of records loaded
    """
    logger.info(f"Loading Polygon data for {symbol} (days_back={days_back})")
    
    loader = HistoricalDataLoader(
        batch_size=100,
        requests_per_minute=2,
        detect_delisted=True
    )
    
    try:
        records_count = await loader.load_symbol_data(
            symbol=symbol,
            days_back=days_back,
            incremental=incremental
        )
        logger.info(f"✅ Loaded {records_count} records for {symbol}")
        return records_count
    except Exception as e:
        logger.error(f"❌ Failed to load {symbol}: {e}")
        raise


@task(
    name="load-yahoo-market-data",
    retries=2,
    retry_delay_seconds=30,
    log_prints=True,
    tags=["data-ingestion", "yahoo"]
)
async def load_yahoo_market_data_task(
    symbol: str,
    days_back: int = 1,
    interval: str = "1h"
) -> dict:
    """
    Load market data for a single symbol from Yahoo Finance
    
    Args:
        symbol: Stock symbol
        days_back: Number of days to look back
        interval: Data interval (1h, 1d, etc.)
        
    Returns:
        Dictionary with load results (includes records_count and records_count_adjusted for unadjusted and adjusted series)
    """
    logger.info(f"Loading Yahoo market data for {symbol}")
    
    loader = YahooDataLoader(batch_size=100, delay_between_requests=0.5)
    
    try:
        from_date = date.today() - timedelta(days=days_back)
        to_date = date.today()
        
        results = await loader.load_all_data(
            symbol=symbol,
            start_date=from_date,
            end_date=to_date,
            include_fundamentals=False,
            include_key_statistics=False
        )
        
        logger.info(f"✅ Loaded Yahoo data for {symbol}: {results}")
        return results
    except Exception as e:
        logger.error(f"❌ Failed to load Yahoo data for {symbol}: {e}")
        raise


@task(
    name="update-load-runs-tracking",
    log_prints=True,
    tags=["data-ingestion", "tracking"]
)
async def update_load_runs_tracking_task(
    symbol: str,
    data_source: str,
    records_count: int,
    status: str = "success"
) -> None:
    """
    Update load_runs table with ingestion results
    
    Args:
        symbol: Stock symbol
        data_source: Data source identifier
        records_count: Number of records loaded
        status: Load status (success, failed, partial)
    """
    # Update load_runs table using existing LoadRun model
    pass
```

## Flow Patterns (Phase 2+)

**Create: `src/shared/prefect/flows/data_ingestion/polygon_flows.py`** (Created when implementing Polygon flows)

```python
"""
Polygon.io Data Ingestion Flows
"""
from datetime import date, timedelta
from typing import List, Optional
from prefect import flow, task
from prefect.tasks import task_input_hash
from loguru import logger
from src.shared.prefect.tasks.data_ingestion_tasks import (
    load_polygon_symbol_data_task,
    update_load_runs_tracking_task
)
from src.services.data_ingestion.symbols import SymbolService


@flow(
    name="polygon-daily-ingestion",
    log_prints=True,
    retries=1,
    retry_delay_seconds=300,  # 5 minutes
    timeout_seconds=3600,  # 1 hour
    tags=["data-ingestion", "polygon", "scheduled"]
)
async def polygon_daily_ingestion(
    days_back: int = 1,
    symbols: Optional[List[str]] = None,
    incremental: bool = True,
    max_symbols: Optional[int] = None
) -> dict:
    """
    Daily end-of-day data ingestion from Polygon.io
    
    This flow:
    1. Gets active symbols
    2. Loads data for each symbol
    3. Updates load_runs tracking
    4. Returns summary statistics
    
    Args:
        days_back: Number of days to look back (default: 1 for daily updates)
        symbols: Optional list of specific symbols (None = all active)
        incremental: Whether to use incremental loading
        max_symbols: Maximum number of symbols to process (for testing)
        
    Returns:
        Dictionary with ingestion statistics
    """
    logger.info("=" * 60)
    logger.info("Starting Polygon Daily Ingestion Flow")
    logger.info(f"Days back: {days_back}, Incremental: {incremental}")
    logger.info("=" * 60)
    
    # Get symbols to process
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
    
    # Statistics
    successful = []
    failed = []
    total_records = 0
    
    # Process each symbol
    for symbol in symbols_list:
        try:
            logger.info(f"Processing {symbol}...")
            
            # Load data for symbol
            records_count = await load_polygon_symbol_data_task(
                symbol=symbol,
                days_back=days_back,
                incremental=incremental
            )
            
            # Update tracking
            await update_load_runs_tracking_task(
                symbol=symbol,
                data_source="polygon",
                records_count=records_count,
                status="success"
            )
            
            successful.append(symbol)
            total_records += records_count
            
        except Exception as e:
            logger.error(f"Failed to process {symbol}: {e}")
            failed.append({"symbol": symbol, "error": str(e)})
            
            # Update tracking with failure
            await update_load_runs_tracking_task(
                symbol=symbol,
                data_source="polygon",
                records_count=0,
                status="failed"
            )
    
    # Summary
    result = {
        "total_symbols": len(symbols_list),
        "successful": len(successful),
        "failed": len(failed),
        "total_records": total_records,
        "successful_symbols": successful,
        "failed_symbols": failed
    }
    
    logger.info("=" * 60)
    logger.info("Polygon Daily Ingestion Completed")
    logger.info(f"Successful: {result['successful']}/{result['total_symbols']}")
    logger.info(f"Failed: {result['failed']}")
    logger.info(f"Total records: {result['total_records']}")
    logger.info("=" * 60)
    
    return result


@flow(
    name="polygon-historical-backfill",
    log_prints=True,
    timeout_seconds=7200,  # 2 hours for backfills
    tags=["data-ingestion", "polygon", "on-demand"]
)
async def polygon_historical_backfill(
    start_date: date,
    end_date: date,
    symbols: Optional[List[str]] = None,
    max_symbols: Optional[int] = None
) -> dict:
    """
    Historical data backfill from Polygon.io
    
    Used for:
    - Initial data population
    - Backfilling missing data
    - Testing
    
    Args:
        start_date: Start date for backfill
        end_date: End date for backfill
        symbols: Optional list of symbols
        max_symbols: Maximum symbols to process
        
    Returns:
        Dictionary with backfill statistics
    """
    # Similar structure to daily ingestion but with date range
    pass
```

**Sample: `src/shared/prefect/flows/analytics/indicator_flows.py`**

```python
"""
Technical Indicators Calculation Flows
"""
from datetime import date
from typing import List, Optional
from prefect import flow, task
from loguru import logger
from src.services.analytics import IndicatorService
from src.services.data_ingestion.symbols import SymbolService


@flow(
    name="indicators-daily-calculation",
    log_prints=True,
    retries=1,
    timeout_seconds=3600,
    tags=["analytics", "indicators", "scheduled"]
)
async def calculate_daily_indicators(
    days_back: int = 300,
    symbols: Optional[List[str]] = None,
    calculation_date: Optional[date] = None
) -> dict:
    """
    Calculate technical indicators for all symbols
    
    Runs after data ingestion flows complete.
    
    Args:
        days_back: Days of history to fetch from database for calculations (default: 300)
                   Note: This fetches historical data from DB, not from API.
                   Need at least 200 days for SMA_200, 14 days for RSI, etc.
        symbols: Optional list of specific symbols
        calculation_date: Date to calculate for (default: today)
        
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
    else:
        symbols_list = [s.upper() for s in symbols]
    
    # Initialize indicator service
    indicator_service = IndicatorService(data_source="yahoo")
    
    successful = []
    failed = []
    
    for symbol in symbols_list:
        try:
            logger.info(f"Calculating indicators for {symbol}...")
            
            # Use existing IndicatorService methods
            await indicator_service.calculate_and_store_indicators(
                symbol=symbol,
                calculation_date=calculation_date,
                days_back=days_back
            )
            
            successful.append(symbol)
            
        except Exception as e:
            logger.error(f"Failed to calculate indicators for {symbol}: {e}")
            failed.append({"symbol": symbol, "error": str(e)})
    
    result = {
        "calculation_date": calculation_date.isoformat(),
        "total_symbols": len(symbols_list),
        "successful": len(successful),
        "failed": len(failed),
        "successful_symbols": successful,
        "failed_symbols": failed
    }
    
    logger.info("=" * 60)
    logger.info(f"Indicators calculation completed: {result['successful']}/{result['total_symbols']} successful")
    logger.info("=" * 60)
    
    return result
```

## Deployment Definitions (Phase 7)

**Create: `src/shared/prefect/deployments/deployments.py`** (Created after flows are working)

```python
"""
Prefect Deployment Definitions
"""
from prefect import serve
from prefect.server.schemas.schedules import CronSchedule
from src.shared.prefect.flows.data_ingestion.polygon_flows import (
    polygon_daily_ingestion,
    polygon_historical_backfill
)
from src.shared.prefect.flows.data_ingestion.yahoo_flows import (
    yahoo_market_data_flow
)
from src.shared.prefect.flows.analytics.indicator_flows import (
    calculate_daily_indicators
)


def create_deployments():
    """
    Create all Prefect deployments
    
    This function defines deployments using Prefect's serve() API
    """
    
    # Polygon Daily Ingestion
    polygon_daily_ingestion.serve(
        name="polygon-daily-ingestion",
        work_pool_name="data-ingestion-pool",
        schedule=CronSchedule(
            cron="0 20 * * 1-5",  # 8 PM CT weekdays
            timezone="America/Chicago"
        ),
        parameters={
            "days_back": 1,
            "incremental": True
        },
        tags=["data-ingestion", "polygon", "scheduled"],
        description="Daily end-of-day data ingestion from Polygon.io"
    )
    
    # Yahoo Market Data Daily End-of-Day
    yahoo_market_data_flow.serve(
        name="Daily Market Data Update",
        work_pool_name="data-ingestion-pool",
        schedule=CronSchedule(
            cron="15 22 * * 1-5",  # 22:15 UTC Mon-Fri (after US market close)
            timezone="UTC"
        ),
        parameters={
            "days_back": 7,
            "interval": "1h"
        },
        tags=["data-ingestion", "yahoo", "market-data", "scheduled"],
        description="Daily end-of-day market data ingestion from Yahoo Finance (hourly bars)"
    )
    
    # Indicators Daily Calculation
    calculate_daily_indicators.serve(
        name="indicators-daily-calculation",
        work_pool_name="analytics-pool",
        schedule=CronSchedule(
            cron="0 21 * * 1-5",  # 9 PM CT weekdays (after data ingestion)
            timezone="America/Chicago"
        ),
        parameters={
            "days_back": 300  # Need sufficient history from DB to calculate indicators
                               # (SMA_200 needs 200 days, RSI_14 needs 14 days, etc.)
        },
        tags=["analytics", "indicators", "scheduled"],
        description="Daily technical indicators calculation"
    )
    
    # Historical backfill (on-demand, no schedule)
    polygon_historical_backfill.serve(
        name="polygon-historical-backfill",
        work_pool_name="data-ingestion-pool",
        # No schedule - manual trigger only
        tags=["data-ingestion", "polygon", "on-demand"],
        description="Historical data backfill (manual trigger)"
    )


if __name__ == "__main__":
    # Run this script to deploy all flows
    create_deployments()
```

## Task Granularity

**Coarse-grained tasks**: One task per symbol (better for parallelization)
- Example: `load_polygon_symbol_data_task(symbol)` processes entire symbol

**Fine-grained tasks**: Separate tasks for fetch/validate/store (better for observability)
- Example: `fetch_data_task()`, `validate_data_task()`, `store_data_task()`

**Recommendation**: Start coarse-grained, refine as needed.

## Related Documentation

- [Prefect Deployment](prefect-deployment.md) — Overview and index
- [Configuration](prefect-deployment-configuration.md) — YAML configs, environment variables, settings
- [Operations](prefect-deployment-operations.md) — Runbook, monitoring, testing
- [Advanced Topics](prefect-deployment-advanced.md) — Design decisions

---

**Last Updated**: 4/3/2026  
**Status**: 🚧 In Progress

