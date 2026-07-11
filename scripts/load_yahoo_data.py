#!/usr/bin/env python3
"""
Yahoo Finance Data Loader Script

Load market data from Yahoo Finance into the database.

Usage:
    python scripts/load_yahoo_data.py --symbol AAPL --days 365
    python scripts/load_yahoo_data.py --all-symbols --days 30
    python scripts/load_yahoo_data.py --symbol AAPL --from-date 2023-01-01 --to-date 2024-12-31
"""

import asyncio
import os
import sys
from datetime import date, datetime, timedelta
from typing import Optional

import click

# Add project root to path
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)

from loguru import logger

from src.services.yahoo.loader import YahooDataLoader
from src.shared.logging import setup_logging


@click.command()
@click.option(
    "--symbol",
    type=str,
    help="Stock symbol to load data for (e.g., AAPL)",
)
@click.option(
    "--all-symbols",
    is_flag=True,
    help="Load data for all active symbols",
)
@click.option(
    "--from-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Start date (YYYY-MM-DD)",
)
@click.option(
    "--to-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="End date (YYYY-MM-DD)",
)
@click.option(
    "--days",
    type=int,
    help="Number of days to look back from today",
)
@click.option(
    "--interval",
    type=click.Choice(["1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"]),
    default="1h",
    help="Data interval (default: 1h for hourly)",
)
@click.option(
    "--batch-size",
    type=int,
    default=100,
    help="Batch size for database inserts (default: 100)",
)
@click.option(
    "--delay",
    type=float,
    default=0.5,
    help="Delay between requests in seconds (default: 0.5)",
)
@click.option(
    "--max-symbols",
    type=int,
    help="Maximum number of symbols to process (for testing)",
)
@click.option(
    "--market-data",
    is_flag=True,
    help="Load market data (default if no other flags specified)",
)
@click.option(
    "--company-info",
    is_flag=True,
    help="Load company info (fundamentals)",
)
@click.option(
    "--key-statistics",
    is_flag=True,
    help="Load key financial statistics (P/E, ROE, margins, etc.)",
)
@click.option(
    "--institutional-holders",
    is_flag=True,
    help="Load institutional holders data",
)
@click.option(
    "--financial-statements",
    is_flag=True,
    help="Load financial statements (income, balance sheet, cash flow)",
)
@click.option(
    "--company-officers",
    is_flag=True,
    help="Load company officers and executives",
)
@click.option(
    "--dividends",
    is_flag=True,
    help="Load dividend history",
)
@click.option(
    "--splits",
    is_flag=True,
    help="Load stock split history",
)
@click.option(
    "--analyst-recommendations",
    is_flag=True,
    help="Load analyst recommendations",
)
@click.option(
    "--esg-scores",
    is_flag=True,
    help="Load ESG (Environmental, Social, Governance) scores",
)
@click.option(
    "--health-check",
    is_flag=True,
    help="Run health check and exit",
)
def main(
    symbol: Optional[str],
    all_symbols: bool,
    from_date: Optional[datetime],
    to_date: Optional[datetime],
    days: Optional[int],
    interval: str,
    batch_size: int,
    delay: float,
    max_symbols: Optional[int],
    market_data: bool,
    company_info: bool,
    key_statistics: bool,
    institutional_holders: bool,
    financial_statements: bool,
    company_officers: bool,
    dividends: bool,
    splits: bool,
    analyst_recommendations: bool,
    esg_scores: bool,
    health_check: bool,
) -> int:
    """
    Load market data from Yahoo Finance

    Examples:
        # Load daily data for AAPL for the last 30 days (market data only)
        python scripts/load_yahoo_data.py --symbol AAPL --days 30

        # Load hourly data for AAPL for the last 7 days
        python scripts/load_yahoo_data.py --symbol AAPL --days 7 --interval 1h

        # Load company info only (no market data)
        python scripts/load_yahoo_data.py --symbol AAPL --company-info

        # Load key statistics only
        python scripts/load_yahoo_data.py --symbol AAPL --key-statistics

        # Load market data + company info + key statistics
        python scripts/load_yahoo_data.py --symbol AAPL --days 30 --market-data --company-info --key-statistics

        # Load key statistics for all symbols
        python scripts/load_yahoo_data.py --all-symbols --key-statistics --max-symbols 10

        # Load data for all symbols for specific date range
        python scripts/load_yahoo_data.py --all-symbols --from-date 2023-01-01 --to-date 2023-12-31

        # Load company info for all symbols
        python scripts/load_yahoo_data.py --all-symbols --company-info

        # Health check
        python scripts/load_yahoo_data.py --health-check
    """
    # Setup logging
    setup_logging()

    async def run_loader() -> int:
        loader = YahooDataLoader(
            batch_size=batch_size,
            delay_between_requests=delay,
        )

        if health_check:
            healthy = await loader.health_check()
            if healthy:
                logger.info("Health check passed - Yahoo Finance is accessible")
                return 0
            else:
                logger.error("Health check failed - Yahoo Finance not accessible")
                return 1

        if not symbol and not all_symbols:
            logger.error("Must specify either --symbol or --all-symbols")
            return 1

        if symbol and all_symbols:
            logger.error("Cannot specify both --symbol and --all-symbols")
            return 1

        # Determine what data types to load
        data_flags = {
            "market_data": market_data,
            "company_info": company_info,
            "key_statistics": key_statistics,
            "institutional_holders": institutional_holders,
            "financial_statements": financial_statements,
            "company_officers": company_officers,
            "dividends": dividends,
            "splits": splits,
            "analyst_recommendations": analyst_recommendations,
            "esg_scores": esg_scores,
        }

        # If no flags specified, default to market data only
        if not any(data_flags.values()):
            data_flags["market_data"] = True

        # Calculate date range if market data, dividends, or splits are needed
        from_date_obj: Optional[date] = None
        to_date_obj: Optional[date] = None

        if data_flags["market_data"] or data_flags["dividends"] or data_flags["splits"]:
            from_date_obj = from_date.date() if from_date else None
            to_date_obj = to_date.date() if to_date else None

            # Calculate date range
            if days:
                to_date_obj = to_date_obj or date.today()
                from_date_obj = from_date_obj or (to_date_obj - timedelta(days=days))
            elif not from_date_obj:
                # Default to 30 days if no date range specified
                to_date_obj = to_date_obj or date.today()
                from_date_obj = to_date_obj - timedelta(days=30)

            # yfinance's end parameter is exclusive, so add 1 day to include today's data
            # Only do this if to_date_obj is today (to get latest data)
            today = date.today()
            if to_date_obj == today:
                to_date_obj = to_date_obj + timedelta(days=1)
                logger.debug(
                    f"Adjusted end_date to {to_date_obj} to include today's data "
                    f"(yfinance end is exclusive)"
                )

            logger.info(f"Date range: {from_date_obj} to {to_date_obj}")
            if data_flags["market_data"]:
                logger.info(f"Interval: {interval}")

        try:
            if symbol:
                # Load single symbol
                return await _load_single_symbol(
                    loader=loader,
                    symbol=symbol,
                    data_flags=data_flags,
                    from_date_obj=from_date_obj,
                    to_date_obj=to_date_obj,
                    interval=interval,
                )
            elif all_symbols:
                # Load all symbols
                return await _load_all_symbols(
                    loader=loader,
                    data_flags=data_flags,
                    from_date_obj=from_date_obj,
                    to_date_obj=to_date_obj,
                    interval=interval,
                    max_symbols=max_symbols,
                )

        except Exception as e:
            logger.error(f"Loader failed: {e}")
            return 1

    # Run the async function
    return asyncio.run(run_loader())


async def _load_single_symbol(
    loader: YahooDataLoader,
    symbol: str,
    data_flags: dict,
    from_date_obj: Optional[date],
    to_date_obj: Optional[date],
    interval: str,
) -> int:
    """Load data for a single symbol"""
    # Check if only one data type is requested (no market data)
    only_flags = [
        ("company_info", loader.load_company_info),
        ("key_statistics", loader.load_key_statistics),
        ("institutional_holders", loader.load_institutional_holders),
        ("financial_statements", loader.load_financial_statements),
        ("company_officers", loader.load_company_officers),
    ]

    # Check for single data type only (no market data)
    single_type = None
    single_loader = None
    for flag_name, loader_func in only_flags:
        if data_flags[flag_name] and not data_flags["market_data"]:
            if single_type:
                # Multiple non-market-data flags, use load_all_data
                single_type = None
                break
            single_type = flag_name
            single_loader = loader_func

    if single_type and single_loader:
        # Load single data type only
        if single_type == "institutional_holders":
            count = await single_loader(symbol)
            if count > 0:
                logger.info(f"Successfully loaded {count} institutional holders for {symbol}")
                return 0
            else:
                logger.warning(f"No institutional holders found for {symbol}")
                return 1
        elif single_type == "financial_statements":
            statements = await single_loader(symbol)
            if statements:
                logger.info(f"Successfully loaded {len(statements)} financial statements for {symbol}")
                return 0
            else:
                logger.warning(f"No financial statements found for {symbol}")
                return 1
        elif single_type == "company_officers":
            officers = await single_loader(symbol)
            if officers:
                logger.info(f"Successfully loaded {len(officers)} company officers for {symbol}")
                return 0
            else:
                logger.warning(f"No company officers found for {symbol}")
                return 1
        elif single_type == "analyst_recommendations":
            count = await single_loader(symbol)
            if count > 0:
                logger.info(f"Successfully loaded {count} analyst recommendation records for {symbol}")
                return 0
            else:
                logger.warning(f"No analyst recommendations found for {symbol}")
                return 1
        else:
            # company_info, key_statistics, or esg_scores (return boolean)
            # Note: The loader methods already log success/failure, so we don't duplicate here
            success = await single_loader(symbol)
            if success:
                # Only log if loader didn't already log (for cases where loader is silent)
                # For company_info, the loader already logs, so we skip to avoid duplicates
                if single_type != "company_info":
                    logger.info(f"Successfully loaded {single_type.replace('_', ' ')} for {symbol}")
                return 0
            else:
                logger.error(f"Failed to load {single_type.replace('_', ' ')} for {symbol}")
                return 1

    # Load multiple data types or market data
    if data_flags["market_data"] or any(
        data_flags[k] for k in ["company_info", "key_statistics", "institutional_holders", 
                                "financial_statements", "company_officers", "dividends", "splits", "analyst_recommendations", "esg_scores"]
    ):
        # Use load_all_data for comprehensive loading
        results = await loader.load_all_data(
            symbol=symbol,
            start_date=from_date_obj,
            end_date=to_date_obj,
            include_fundamentals=data_flags["company_info"],
            include_key_statistics=data_flags["key_statistics"],
            include_institutional_holders=data_flags["institutional_holders"],
            include_financial_statements=data_flags["financial_statements"],
            include_company_officers=data_flags["company_officers"],
            include_dividends=data_flags["dividends"],
            include_splits=data_flags["splits"],
            include_analyst_recommendations=data_flags["analyst_recommendations"],
            include_esg_scores=data_flags["esg_scores"],
        )
        logger.info(f"Loaded data for {symbol}: {results}")
        return 0
    else:
        # This shouldn't happen due to default logic, but handle it
        logger.error("No data types specified")
        return 1


async def _load_all_symbols(
    loader: YahooDataLoader,
    data_flags: dict,
    from_date_obj: Optional[date],
    to_date_obj: Optional[date],
    interval: str,
    max_symbols: Optional[int],
) -> int:
    """Load data for all symbols"""
    symbols_list = await loader._get_active_symbols()
    if max_symbols:
        symbols_list = symbols_list[:max_symbols]

    # Check if only one data type is requested (no market data)
    only_flags = [
        ("company_info", loader.load_company_info),
        ("key_statistics", loader.load_key_statistics),
        ("institutional_holders", loader.load_institutional_holders),
        ("financial_statements", loader.load_financial_statements),
        ("company_officers", loader.load_company_officers),
        ("analyst_recommendations", loader.load_analyst_recommendations),
        ("esg_scores", loader.load_esg_scores),
    ]

    # Special handling for dividends and splits (they need date parameters)
    if data_flags["dividends"] and not data_flags["market_data"] and not any(
        data_flags[k] for k in ["company_info", "key_statistics", "institutional_holders", 
                                "financial_statements", "company_officers", "splits"]
    ):
        # Load dividends only for all symbols
        logger.info(f"Loading dividends for {len(symbols_list)} symbols")
        successful = 0
        no_data = 0
        failed = 0
        total_dividends = 0

        for i, sym in enumerate(symbols_list, 1):
            logger.debug(f"Processing {i}/{len(symbols_list)}: {sym}")
            try:
                count = await loader.load_dividends(
                    symbol=sym,
                    start_date=from_date_obj,
                    end_date=to_date_obj,
                )
                if count > 0:
                    successful += 1
                    total_dividends += count
                else:
                    no_data += 1
            except Exception as e:
                logger.error(f"Failed to load dividends for {sym}: {e}")
                failed += 1

            if i < len(symbols_list):
                await asyncio.sleep(loader.delay_between_requests)

        logger.info(f"Dividends loading completed:")
        logger.info(f"  Total symbols: {len(symbols_list)}")
        logger.info(f"  Successful (with data): {successful}")
        logger.info(f"  No data available: {no_data}")
        logger.info(f"  Failed (errors): {failed}")
        logger.info(f"  Total dividends: {total_dividends}")

        return 0 if failed == 0 else 1

    if data_flags["splits"] and not data_flags["market_data"] and not any(
        data_flags[k] for k in ["company_info", "key_statistics", "institutional_holders", 
                                "financial_statements", "company_officers", "dividends"]
    ):
        # Load splits only for all symbols
        logger.info(f"Loading stock splits for {len(symbols_list)} symbols")
        successful = 0
        no_data = 0
        failed = 0
        total_splits = 0

        for i, sym in enumerate(symbols_list, 1):
            logger.debug(f"Processing {i}/{len(symbols_list)}: {sym}")
            try:
                count = await loader.load_splits(
                    symbol=sym,
                    start_date=from_date_obj,
                    end_date=to_date_obj,
                )
                if count > 0:
                    successful += 1
                    total_splits += count
                else:
                    no_data += 1
            except Exception as e:
                logger.error(f"Failed to load stock splits for {sym}: {e}")
                failed += 1

            if i < len(symbols_list):
                await asyncio.sleep(loader.delay_between_requests)

        logger.info(f"Stock splits loading completed:")
        logger.info(f"  Total symbols: {len(symbols_list)}")
        logger.info(f"  Successful (with data): {successful}")
        logger.info(f"  No data available: {no_data}")
        logger.info(f"  Failed (errors): {failed}")
        logger.info(f"  Total splits: {total_splits}")

        return 0 if failed == 0 else 1

    # Check for single data type only (no market data)
    single_type = None
    single_loader = None
    for flag_name, loader_func in only_flags:
        if data_flags[flag_name] and not data_flags["market_data"]:
            if single_type:
                # Multiple non-market-data flags, use load_all_symbols_data
                single_type = None
                break
            single_type = flag_name
            single_loader = loader_func

    if single_type and single_loader:
        # Load single data type for all symbols
        logger.info(f"Loading {single_type.replace('_', ' ')} for {len(symbols_list)} symbols")
        successful = 0
        no_data = 0
        failed = 0
        total_items = 0

        for i, sym in enumerate(symbols_list, 1):
            logger.debug(f"Processing {i}/{len(symbols_list)}: {sym}")
            try:
                if single_type == "institutional_holders":
                    count = await single_loader(sym)
                    if count > 0:
                        successful += 1
                        total_items += count
                    else:
                        no_data += 1
                elif single_type == "financial_statements":
                    statements = await single_loader(sym)
                    if statements:
                        successful += 1
                        total_items += len(statements)
                    else:
                        no_data += 1
                elif single_type == "company_officers":
                    officers = await single_loader(sym)
                    if officers:
                        successful += 1
                        total_items += len(officers)
                    else:
                        no_data += 1
                elif single_type == "analyst_recommendations":
                    count = await single_loader(sym)
                    if count > 0:
                        successful += 1
                        total_items += count
                    else:
                        no_data += 1
                else:
                    # company_info, key_statistics, or esg_scores (return boolean)
                    success = await single_loader(sym)
                    if success:
                        successful += 1
                    else:
                        no_data += 1
            except Exception as e:
                logger.error(f"Failed to load {single_type.replace('_', ' ')} for {sym}: {e}")
                failed += 1

            if i < len(symbols_list):
                await asyncio.sleep(loader.delay_between_requests)

        logger.info(f"{single_type.replace('_', ' ').title()} loading completed:")
        logger.info(f"  Total symbols: {len(symbols_list)}")
        logger.info(f"  Successful (with data): {successful}")
        logger.info(f"  No data available: {no_data}")
        logger.info(f"  Failed (errors): {failed}")
        if total_items > 0:
            logger.info(f"  Total items: {total_items}")

        return 0 if failed == 0 else 1
    else:
        # Load multiple data types or market data
        stats = await loader.load_all_symbols_data(
            start_date=from_date_obj,
            end_date=to_date_obj,
            interval=interval,
            max_symbols=max_symbols,
            include_fundamentals=data_flags["company_info"],
            include_key_statistics=data_flags["key_statistics"],
            include_institutional_holders=data_flags["institutional_holders"],
            include_financial_statements=data_flags["financial_statements"],
            include_company_officers=data_flags["company_officers"],
            include_dividends=data_flags["dividends"],
            include_splits=data_flags["splits"],
            include_analyst_recommendations=data_flags["analyst_recommendations"],
            include_esg_scores=data_flags["esg_scores"],
        )

        logger.info("Loading completed:")
        logger.info(f"  Total symbols: {stats['total_symbols']}")
        logger.info(f"  Successful: {stats['successful']}")
        logger.info(f"  Failed: {stats['failed']}")
        logger.info(f"  Total records: {stats['total_records']}")

        if stats["errors"]:
            logger.error("Errors encountered:")
            for error in stats["errors"]:
                logger.error(f"  {error}")

        return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    exit(main())
