"""
Reusable Prefect Tasks for Data Ingestion

Yahoo Finance data ingestion tasks.
"""

from datetime import date, timedelta
from typing import Optional

from loguru import logger
from prefect import task

from src.services.data_ingestion.symbols import SymbolService
from src.services.yahoo.exceptions import YahooDataError
from src.services.yahoo.loader import YahooDataLoader


@task(
    name="load-yahoo-market-data",
    retries=2,
    retry_delay_seconds=30,
    log_prints=True,
    tags=["data-ingestion", "yahoo", "market-data"],
)
async def load_yahoo_market_data_task(
    symbol: str,
    days_back: int = 1,
    interval: str = "1h",
) -> dict:
    """
    Load market data for a single symbol from Yahoo Finance

    Args:
        symbol: Stock symbol
        days_back: Number of days to look back (default: 1 for daily updates)
        interval: Data interval (1h, 1d, etc.)

    Returns:
        Dictionary with load results
    """
    logger.info(
        f"Loading Yahoo market data for {symbol} (days_back={days_back}, interval={interval})"
    )

    loader = YahooDataLoader(batch_size=100, delay_between_requests=0.5)

    try:
        # Calculate date range
        today = date.today()
        to_date = today
        from_date = to_date - timedelta(days=days_back)

        # yfinance's end parameter is exclusive, so add 1 day to include today's data
        # Only do this if to_date is today (to get latest data)
        if to_date == today:
            to_date = to_date + timedelta(days=1)
            logger.debug(
                f"Adjusted end_date to {to_date} to include today's data "
                f"(yfinance end is exclusive)"
            )

        # Load both unadjusted and adjusted market data
        records_count = await loader.load_market_data(
            symbol=symbol,
            start_date=from_date,
            end_date=to_date,
            interval=interval,
            auto_adjust=False,
        )
        records_count_adjusted = await loader.load_market_data(
            symbol=symbol,
            start_date=from_date,
            end_date=to_date,
            interval=interval,
            auto_adjust=True,
        )

        logger.info(
            f"Loaded {records_count} unadjusted + {records_count_adjusted} adjusted "
            f"market data records for {symbol}"
        )
        await loader._update_symbol_status(symbol, "success")
        return {
            "symbol": symbol,
            "records_count": records_count,
            "records_count_adjusted": records_count_adjusted,
            "status": "success",
        }
    except YahooDataError as e:
        # No data available is a valid state (symbol might be delisted, etc.)
        # Don't treat this as a fatal error that needs retries
        logger.warning(f"No data available for {symbol}: {e}")
        await loader._update_symbol_status(symbol, "no_data", str(e))
        return {
            "symbol": symbol,
            "records_count": 0,
            "records_count_adjusted": 0,
            "status": "no_data",
        }
    except Exception as e:
        # Other errors (network, API issues) should be retried
        logger.error(f"Failed to load Yahoo market data for {symbol}: {e}")
        await loader._update_symbol_status(symbol, "failed", str(e))
        raise


@task(
    name="load-yahoo-company-info",
    retries=2,
    retry_delay_seconds=30,
    log_prints=True,
    tags=["data-ingestion", "yahoo", "company-info"],
)
async def load_yahoo_company_info_task(symbol: str) -> dict:
    """
    Load company information for a single symbol from Yahoo Finance

    Args:
        symbol: Stock symbol

    Returns:
        Dictionary with load results
    """
    logger.info(f"Loading Yahoo company info for {symbol}")

    loader = YahooDataLoader(batch_size=100, delay_between_requests=0.5)

    try:
        success = await loader.load_company_info(symbol=symbol)

        if success:
            logger.info(f"Loaded company info for {symbol}")
            return {"symbol": symbol, "status": "success"}
        else:
            logger.warning(f"No company info found for {symbol}")
            return {"symbol": symbol, "status": "no_data"}
    except YahooDataError as e:
        # No data available is a valid state - don't treat as fatal error
        logger.warning(f"No company info available for {symbol}: {e}")
        return {"symbol": symbol, "status": "no_data"}
    except Exception as e:
        # Other errors (network, API issues) should be retried
        logger.error(f"Failed to load company info for {symbol}: {e}")
        raise


@task(
    name="load-yahoo-key-statistics",
    retries=2,
    retry_delay_seconds=30,
    log_prints=True,
    tags=["data-ingestion", "yahoo", "key-statistics"],
)
async def load_yahoo_key_statistics_task(symbol: str) -> dict:
    """
    Load key statistics for a single symbol from Yahoo Finance

    Args:
        symbol: Stock symbol

    Returns:
        Dictionary with load results
    """
    logger.info(f"Loading Yahoo key statistics for {symbol}")

    loader = YahooDataLoader(batch_size=100, delay_between_requests=0.5)

    try:
        success = await loader.load_key_statistics(symbol=symbol)

        if success:
            logger.info(f"Loaded key statistics for {symbol}")
            return {"symbol": symbol, "status": "success"}
        else:
            logger.warning(f"No key statistics found for {symbol}")
            return {"symbol": symbol, "status": "no_data"}
    except YahooDataError as e:
        # No data available is a valid state - don't treat as fatal error
        logger.warning(f"No key statistics available for {symbol}: {e}")
        return {"symbol": symbol, "status": "no_data"}
    except Exception as e:
        # Other errors (network, API issues) should be retried
        logger.error(f"Failed to load key statistics for {symbol}: {e}")
        raise
