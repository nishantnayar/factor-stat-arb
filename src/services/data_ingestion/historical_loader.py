"""
Historical Data Loader for Polygon.io

This module provides the core functionality for loading historical market data
from Polygon.io into the database.
"""

import asyncio
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert

from src.services.data_ingestion.symbols import SymbolService
from src.services.polygon.client import PolygonClient
from src.shared.database.base import db_transaction
from src.shared.database.models.load_runs import LoadRun
from src.shared.database.models.market_data import MarketData
from src.shared.database.models.symbols import Symbol


class HistoricalDataLoader:
    """Load historical market data from Polygon.io"""

    def __init__(
        self,
        batch_size: int = 100,
        requests_per_minute: int = 2,
        data_source: str = "polygon",
        detect_delisted: bool = True,
    ):
        """
        Initialize the historical data loader

        Args:
            batch_size: Number of records to process in each batch
            requests_per_minute: Maximum requests per minute (default 2 for free tier)
            data_source: Data source identifier ('polygon', 'yahoo', etc.)
            detect_delisted: Whether to detect and mark delisted symbols during loading
        """
        self.polygon_client = PolygonClient()
        self.batch_size = batch_size
        self.requests_per_minute = requests_per_minute
        self.delay_between_requests = (
            60.0 / requests_per_minute
        )  # Calculate delay for rate limiting
        self.data_source = data_source
        self.detect_delisted = detect_delisted
        self.symbol_service = SymbolService() if detect_delisted else None

    async def _update_symbol_status(
        self, 
        symbol: str, 
        status: str, 
        error_message: Optional[str] = None
    ) -> None:
        """Update symbol data ingestion status"""
        try:
            # Always create symbol service for status tracking
            if not self.symbol_service:
                self.symbol_service = SymbolService()
            
            await self.symbol_service.update_symbol_data_status(
                symbol=symbol,
                date=date.today(),
                data_source=self.data_source,
                status=status,
                error_message=error_message,
            )
        except Exception as e:
            # Make this non-blocking - log warning but don't fail the main process
            logger.warning(f"Failed to update symbol status for {symbol}: {e}")

    async def load_symbol_data(
        self,
        symbol: str,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        days_back: Optional[int] = None,
        timespan: str = "day",
        multiplier: int = 1,
        incremental: bool = True,
        force_full: bool = False,
    ) -> int:
        """
        Load historical data for a single symbol

        Args:
            symbol: Stock symbol
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            days_back: Number of days to look back from today
            timespan: Data granularity ('minute', 'hour', 'day', 'week', 'month', 'quarter', 'year')
            multiplier: Number of timespans to aggregate (e.g., 5 with 'minute' = 5-minute bars)
            incremental: Whether to use incremental loading (default True)
            force_full: Force full reload even if incremental data exists (default False)

        Returns:
            Number of records loaded
        """
        symbol = symbol.upper()
        logger.info(f"Starting historical data load for {symbol}")

        # Get last successful date for incremental loading
        last_successful_date = await self._get_last_successful_date(
            symbol, timespan, multiplier
        )

        # Determine date range based on incremental loading
        if incremental and not force_full and last_successful_date:
            # Start from day after last successful load
            from_date = last_successful_date + timedelta(days=1)
            to_date = to_date or date.today()
            logger.info(
                f"Incremental loading: from {from_date} (last successful: {last_successful_date})"
            )
        else:
            # Full loading or first time
            if days_back:
                to_date = to_date or date.today()
                from_date = from_date or (to_date - timedelta(days=days_back))
            elif not from_date:
                from_date = date.today() - timedelta(days=30)
                to_date = to_date or date.today()
            logger.info(f"Full loading: from {from_date}")

        # Skip if no date range to process
        if from_date and to_date and from_date > to_date:
            logger.info(f"No new data to load for {symbol} (from_date > to_date)")
            return 0

        logger.info(f"Date range: {from_date or 'None'} to {to_date or 'None'}")
        logger.info(f"Timespan: {multiplier} {timespan}(s) per bar")

        try:
            # Get data from Polygon
            bars = await self.polygon_client.get_aggregates(
                ticker=symbol,
                from_date=from_date.strftime("%Y-%m-%d") if from_date else None,
                to_date=to_date.strftime("%Y-%m-%d") if to_date else None,
                timespan=timespan,
                multiplier=multiplier,
                adjusted=True,
                sort="asc",
                limit=5000,
            )

            if not bars:
                logger.warning(f"No data found for {symbol} in date range")

                # Check if symbol might be delisted when no data is found
                if self.detect_delisted and self.symbol_service:
                    logger.info(f"Checking if {symbol} is delisted due to no data")
                    is_healthy = await self.symbol_service.check_symbol_health(symbol)
                    if not is_healthy:
                        await self.symbol_service.mark_symbol_delisted(
                            symbol,
                            notes=f"No data found for date range {from_date} to {to_date}",
                        )
                        logger.info(
                            f"Marked {symbol} as delisted due to no data availability"
                        )

                return 0

            # Convert to database records
            records = []
            for bar in bars:
                record = MarketData(
                    symbol=symbol,
                    timestamp=bar.timestamp,
                    data_source=self.data_source,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                )
                records.append(record)

            # Batch insert into database
            inserted_count = await self._batch_insert_records(records)

            # Calculate the actual last successful date from loaded records
            actual_last_successful_date = None
            if records:
                # Get the latest timestamp from the loaded records
                actual_last_successful_date = max(
                    record.timestamp.date() for record in records
                )
            elif last_successful_date:
                # If no new records were loaded but we had a previous successful date, keep it
                actual_last_successful_date = last_successful_date
            else:
                # Fallback to to_date or today if no records and no previous date
                actual_last_successful_date = to_date or date.today()

            # Update load run tracking
            await self._update_load_run(
                symbol=symbol,
                data_source=self.data_source,
                timespan=timespan,
                multiplier=multiplier,
                last_successful_date=actual_last_successful_date,
                records_loaded=inserted_count,
                status="success",
            )

            logger.info(f"Successfully loaded {inserted_count} records for {symbol}")
            return inserted_count

        except Exception as e:
            error_msg = f"Failed to load data for {symbol}: {str(e)}"
            logger.error(error_msg)

            # Check if error indicates symbol might be delisted
            if self.detect_delisted and self.symbol_service:
                error_str = str(e).lower()
                if any(
                    indicator in error_str
                    for indicator in ["not found", "404", "invalid", "delisted"]
                ):
                    logger.info(
                        f"Checking if {symbol} is delisted due to error: {error_str}"
                    )
                    is_healthy = await self.symbol_service.check_symbol_health(symbol)
                    if not is_healthy:
                        await self.symbol_service.mark_symbol_delisted(
                            symbol, notes=f"Delisted due to API error: {str(e)}"
                        )
                        logger.info(f"Marked {symbol} as delisted due to API error")

            # Update load run tracking with error
            # For failed loads, keep the previous successful date if it exists
            error_last_successful_date = last_successful_date or (
                to_date or date.today()
            )

            await self._update_load_run(
                symbol=symbol,
                data_source=self.data_source,
                timespan=timespan,
                multiplier=multiplier,
                last_successful_date=error_last_successful_date,
                records_loaded=0,
                status="failed",
                error_message=str(e),
            )
            raise

    async def load_all_symbols_data(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        days_back: Optional[int] = None,
        max_symbols: Optional[int] = None,
        timespan: str = "day",
        multiplier: int = 1,
        incremental: bool = True,
        force_full: bool = False,
    ) -> dict:
        """
        Load historical data for all active symbols

        Args:
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            days_back: Number of days to look back from today
            max_symbols: Maximum number of symbols to process (for testing)
            timespan: Data granularity ('minute', 'hour', 'day', 'week', 'month', 'quarter', 'year')
            multiplier: Number of timespans to aggregate (e.g., 5 with 'minute' = 5-minute bars)
            incremental: Whether to use incremental loading (default True)
            force_full: Force full reload even if incremental data exists (default False)

        Returns:
            Dictionary with loading statistics
        """
        logger.info("Starting historical data load for all active symbols")

        # Get active symbols
        symbols = await self._get_active_symbols()
        if max_symbols:
            symbols = symbols[:max_symbols]

        logger.info(f"Processing {len(symbols)} symbols")

        stats: Dict[str, Any] = {
            "total_symbols": len(symbols),
            "successful": 0,
            "failed": 0,
            "total_records": 0,
            "errors": [],
        }

        for i, symbol in enumerate(symbols, 1):
            logger.info(f"Processing symbol {i}/{len(symbols)}: {symbol}")

            try:
                records_count = await self.load_symbol_data(
                    symbol=symbol,
                    from_date=from_date,
                    to_date=to_date,
                    days_back=days_back,
                    timespan=timespan,
                    multiplier=multiplier,
                    incremental=incremental,
                    force_full=force_full,
                )

                stats["successful"] += 1
                stats["total_records"] += records_count
                
                # Update status for successful data loading
                await self._update_symbol_status(symbol, "success")

                # Add delay between requests to respect rate limits
                if i < len(symbols):
                    await asyncio.sleep(self.delay_between_requests)

            except Exception as e:
                stats["failed"] += 1
                error_msg = f"Symbol {symbol}: {str(e)}"
                stats["errors"].append(error_msg)
                logger.error(error_msg)
                
                # Update status for failed data loading
                await self._update_symbol_status(symbol, "failed", error_msg)

                # Continue with next symbol
                continue

        logger.info(f"Completed loading data. Stats: {stats}")

        # Run delisting detection after loading all symbols if enabled
        if self.detect_delisted and self.symbol_service:
            logger.info("Running delisting detection on all active symbols...")
            try:
                delisted_symbols = await self.symbol_service.detect_delisted_symbols()
                if delisted_symbols:
                    logger.info(
                        f"Detected {len(delisted_symbols)} delisted symbols: {delisted_symbols}"
                    )
                    stats["delisted_symbols"] = delisted_symbols
                else:
                    logger.info("No new delisted symbols detected")
            except Exception as e:
                logger.error(f"Delisting detection failed: {e}")
                stats["delisting_error"] = str(e)

        return stats

    async def _get_active_symbols(self) -> List[str]:
        """Get list of active symbols"""
        with db_transaction() as session:
            stmt = select(Symbol.symbol).where(Symbol.status == "active")
            result = session.execute(stmt)
            return [row[0] for row in result.fetchall()]

    async def _batch_insert_records(self, records: List[MarketData]) -> int:
        """
        Insert records in batches using upsert logic

        Args:
            records: List of MarketData records to insert

        Returns:
            Number of records actually inserted
        """
        if not records:
            return 0

        inserted_count = 0

        with db_transaction() as session:
            # Process in batches
            for i in range(0, len(records), self.batch_size):
                batch = records[i : i + self.batch_size]

                # Use PostgreSQL upsert (INSERT ... ON CONFLICT)
                stmt = insert(MarketData).values(
                    [
                        {
                            "symbol": record.symbol,
                            "timestamp": record.timestamp,
                            "data_source": record.data_source,
                            "open": record.open,
                            "high": record.high,
                            "low": record.low,
                            "close": record.close,
                            "volume": record.volume,
                        }
                        for record in batch
                    ]
                )

                # Update on conflict (symbol, timestamp, data_source)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["symbol", "timestamp", "data_source"],
                    set_={
                        "open": stmt.excluded.open,
                        "high": stmt.excluded.high,
                        "low": stmt.excluded.low,
                        "close": stmt.excluded.close,
                        "volume": stmt.excluded.volume,
                    },
                )

                session.execute(stmt)
                inserted_count += len(batch)
                session.commit()

                logger.debug(f"Inserted batch of {len(batch)} records")

        return inserted_count

    async def _get_last_successful_date(
        self, symbol: str, timespan: str, multiplier: int
    ) -> Optional[date]:
        """Get the last successful date for a symbol"""
        with db_transaction() as session:
            stmt = select(LoadRun.last_successful_date).where(
                and_(
                    LoadRun.symbol == symbol,
                    LoadRun.data_source == self.data_source,
                    LoadRun.timespan == timespan,
                    LoadRun.multiplier == multiplier,
                )
            )
            result = session.execute(stmt)
            last_date = result.scalar_one_or_none()
            return last_date

    async def _get_or_create_load_run(
        self, symbol: str, timespan: str, multiplier: int
    ) -> LoadRun:
        """Get or create a load run tracking record"""
        with db_transaction() as session:
            stmt = select(LoadRun).where(
                and_(
                    LoadRun.symbol == symbol,
                    LoadRun.data_source == self.data_source,
                    LoadRun.timespan == timespan,
                    LoadRun.multiplier == multiplier,
                )
            )
            result = session.execute(stmt)
            load_run = result.scalar_one_or_none()

            if not load_run:
                # Create new load run
                load_run = LoadRun(
                    symbol=symbol,
                    data_source=self.data_source,
                    timespan=timespan,
                    multiplier=multiplier,
                    last_run_date=date.today(),
                    last_successful_date=date.today()
                    - timedelta(days=365),  # Default to 1 year ago
                    records_loaded=0,
                    status="success",
                )
                session.add(load_run)
                session.commit()
                session.refresh(load_run)
                logger.info(f"Created new load run tracking for {symbol}")

            return load_run

    async def _update_load_run(
        self,
        symbol: str,
        data_source: str,
        timespan: str,
        multiplier: int,
        last_successful_date: date,
        records_loaded: int,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        """Update load run tracking record"""
        with db_transaction() as session:
            # Find the load run within this session
            stmt = select(LoadRun).where(
                and_(
                    LoadRun.symbol == symbol,
                    LoadRun.data_source == data_source,
                    LoadRun.timespan == timespan,
                    LoadRun.multiplier == multiplier,
                )
            )
            result = session.execute(stmt)
            current_load_run = result.scalar_one_or_none()

            if current_load_run:
                # Update existing load run
                current_load_run.last_run_date = date.today()
                current_load_run.last_successful_date = last_successful_date
                current_load_run.records_loaded = records_loaded
                current_load_run.status = status
                current_load_run.error_message = error_message
            else:
                # Create new load run if it doesn't exist
                current_load_run = LoadRun(
                    symbol=symbol,
                    data_source=data_source,
                    timespan=timespan,
                    multiplier=multiplier,
                    last_run_date=date.today(),
                    last_successful_date=last_successful_date,
                    records_loaded=records_loaded,
                    status=status,
                    error_message=error_message,
                )
                session.add(current_load_run)

            session.commit()
            logger.debug(
                f"Updated load run for {symbol}: status={status}, records={records_loaded}"
            )

    async def detect_gaps_and_backfill(
        self,
        symbol: str,
        timespan: str = "day",
        multiplier: int = 1,
        max_gap_days: int = 7,
        max_backfill_days: int = 30,
    ) -> dict:
        """
        Detect gaps in data and perform backfill if needed

        Args:
            symbol: Stock symbol
            timespan: Data granularity
            multiplier: Number of timespans to aggregate
            max_gap_days: Maximum gap in days before backfill is triggered
            max_backfill_days: Maximum days to backfill in one operation

        Returns:
            Dictionary with gap detection and backfill results
        """
        symbol = symbol.upper()
        logger.info(f"Checking for gaps in {symbol} data")

        last_successful_date = await self._get_last_successful_date(
            symbol, timespan, multiplier
        )

        # Check if backfill is needed
        if last_successful_date:
            gap_days = (date.today() - last_successful_date).days
            if gap_days <= max_gap_days:
                logger.info(f"No backfill needed for {symbol} (gap: {gap_days} days)")
                return {
                    "symbol": symbol,
                    "backfill_needed": False,
                    "gap_days": gap_days,
                    "records_loaded": 0,
                }
        else:
            # No previous data, use default gap
            gap_days = 999
            last_successful_date = date.today() - timedelta(days=365)

        # Calculate backfill date range
        backfill_days = min(gap_days, max_backfill_days)

        from_date = last_successful_date + timedelta(days=1)
        to_date = from_date + timedelta(days=backfill_days - 1)

        logger.info(
            f"Backfilling {symbol}: {from_date} to {to_date} ({backfill_days} days)"
        )

        try:
            records_count = await self.load_symbol_data(
                symbol=symbol,
                from_date=from_date,
                to_date=to_date,
                timespan=timespan,
                multiplier=multiplier,
                incremental=False,  # Force full load for backfill
                force_full=False,
            )

            logger.info(f"Backfill completed for {symbol}: {records_count} records")
            return {
                "symbol": symbol,
                "backfill_needed": True,
                "gap_days": gap_days,
                "backfill_days": backfill_days,
                "from_date": from_date,
                "to_date": to_date,
                "records_loaded": records_count,
            }

        except Exception as e:
            logger.error(f"Backfill failed for {symbol}: {e}")
            return {
                "symbol": symbol,
                "backfill_needed": True,
                "gap_days": gap_days,
                "backfill_days": backfill_days,
                "from_date": from_date,
                "to_date": to_date,
                "records_loaded": 0,
                "error": str(e),
            }

    async def get_loading_progress(self, from_date: date, to_date: date) -> dict:
        """
        Get loading progress for date range

        Args:
            from_date: Start date
            to_date: End date

        Returns:
            Dictionary with progress information
        """
        with db_transaction() as session:
            # Get total symbols
            total_symbols = session.scalar(
                select(func.count(Symbol.symbol)).where(Symbol.status == "active")
            )

            # Get symbols with successful data for date range
            successful_symbols = session.scalar(
                select(func.count(func.distinct(MarketData.symbol))).where(
                    and_(
                        MarketData.timestamp >= from_date,
                        MarketData.timestamp <= to_date,
                    )
                )
            )

            # Get total records for date range
            total_records = session.scalar(
                select(func.count(MarketData.id)).where(
                    and_(
                        MarketData.timestamp >= from_date,
                        MarketData.timestamp <= to_date,
                    )
                )
            )

        return {
            "total_symbols": total_symbols or 0,
            "symbols_with_data": successful_symbols or 0,
            "total_records": total_records or 0,
            "progress_percent": (
                (successful_symbols or 0) / (total_symbols or 1) * 100
                if total_symbols
                else 0
            ),
        }

    async def health_check(self) -> bool:
        """
        Check if the loader can connect to required services

        Returns:
            True if all services are accessible
        """
        try:
            # Check Polygon API
            polygon_healthy = await self.polygon_client.health_check()
            if not polygon_healthy:
                logger.error("Polygon API health check failed")
                return False

            # Check database connection
            with db_transaction() as session:
                session.execute(select(1))

            logger.info("All health checks passed")
            return True

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
