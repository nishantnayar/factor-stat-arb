"""
Technical Indicator Storage Service

Handles database storage operations for technical indicators.
Stores in both latest and time-series tables.
"""

from datetime import date
from typing import Dict, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.shared.database.base import db_transaction
from src.shared.database.models.technical_indicators import (
    TechnicalIndicators,
    TechnicalIndicatorsLatest,
)


class IndicatorStorageService:
    """
    Service for storing technical indicators in the database
    
    Handles storage in both:
    - technical_indicators_latest: Latest values (one row per symbol)
    - technical_indicators: Time-series data (one row per symbol per date)
    """

    async def store_indicators(
        self,
        indicators: Dict,
        calculation_date: Optional[date] = None,
    ) -> bool:
        """
        Store indicators in both latest and time-series tables
        
        Args:
            indicators: Dictionary with indicator values (from calculate_all_indicators)
            calculation_date: Date for which indicators were calculated
            
        Returns:
            True if storage successful, False otherwise
        """
        if not indicators:
            logger.warning("No indicators provided for storage")
            return False
        
        symbol = indicators.get("symbol")
        if not symbol:
            logger.error(f"No symbol in indicators dictionary. Keys: {list(indicators.keys())}")
            return False
        
        # Check if we have any actual indicator values (not just symbol and date)
        indicator_keys = [
            "sma_20", "sma_50", "sma_200", "ema_12", "ema_26", "ema_50",
            "rsi", "rsi_14", "macd_line", "macd_signal", "macd_histogram",
            "bb_upper", "bb_middle", "bb_lower", "bb_position", "bb_width",
            "volatility_20", "price_change_1d", "price_change_5d", "price_change_30d",
            "avg_volume_20", "current_volume"
        ]
        
        has_values = any(
            indicators.get(key) is not None 
            for key in indicator_keys
        )
        
        if not has_values:
            logger.warning(
                f"No indicator values calculated for {symbol} on {calculation_date}. "
                f"This usually means insufficient historical data. "
                f"Skipping storage to avoid blank rows."
            )
            return False
        
        if calculation_date is None:
            calculation_date = indicators.get("calculated_date")
            if not calculation_date:
                calculation_date = date.today()
        
        try:
            # Store in latest table (upsert)
            await self.store_latest_indicators(indicators, calculation_date)
            
            # Store in time-series table (insert, skip if exists)
            await self.store_time_series_indicators(indicators, calculation_date)
            
            logger.info(f"Successfully stored indicators for {symbol} on {calculation_date}")
            return True
            
        except Exception as e:
            logger.error(
                f"Error storing indicators for {symbol}: {e}",
                exc_info=True,
            )
            return False

    async def store_latest_indicators(
        self,
        indicators: Dict,
        calculation_date: date,
    ) -> None:
        """
        Store/update latest indicators (upsert operation)
        
        Args:
            indicators: Dictionary with indicator values
            calculation_date: Date for which indicators were calculated
        """
        symbol = indicators.get("symbol")
        if not symbol:
            raise ValueError(f"Missing 'symbol' key in indicators dict. Available keys: {list(indicators.keys())}")
        
        try:
            with db_transaction() as session:
                # Use PostgreSQL INSERT ... ON CONFLICT for upsert
                stmt = insert(TechnicalIndicatorsLatest).values(
                    symbol=symbol,
                    calculated_date=calculation_date,
                    sma_20=indicators.get("sma_20"),
                    sma_50=indicators.get("sma_50"),
                    sma_200=indicators.get("sma_200"),
                    ema_12=indicators.get("ema_12"),
                    ema_26=indicators.get("ema_26"),
                    ema_50=indicators.get("ema_50"),
                    rsi=indicators.get("rsi"),
                    rsi_14=indicators.get("rsi_14"),
                    macd_line=indicators.get("macd_line"),
                    macd_signal=indicators.get("macd_signal"),
                    macd_histogram=indicators.get("macd_histogram"),
                    bb_upper=indicators.get("bb_upper"),
                    bb_middle=indicators.get("bb_middle"),
                    bb_lower=indicators.get("bb_lower"),
                    bb_position=indicators.get("bb_position"),
                    bb_width=indicators.get("bb_width"),
                    volatility_20=indicators.get("volatility_20"),
                    price_change_1d=indicators.get("price_change_1d"),
                    price_change_5d=indicators.get("price_change_5d"),
                    price_change_30d=indicators.get("price_change_30d"),
                    avg_volume_20=indicators.get("avg_volume_20"),
                    current_volume=indicators.get("current_volume"),
                )
                
                # On conflict, update all fields except symbol
                stmt = stmt.on_conflict_do_update(
                    index_elements=["symbol"],
                    set_={
                        "calculated_date": stmt.excluded.calculated_date,
                        "sma_20": stmt.excluded.sma_20,
                        "sma_50": stmt.excluded.sma_50,
                        "sma_200": stmt.excluded.sma_200,
                        "ema_12": stmt.excluded.ema_12,
                        "ema_26": stmt.excluded.ema_26,
                        "ema_50": stmt.excluded.ema_50,
                        "rsi": stmt.excluded.rsi,
                        "rsi_14": stmt.excluded.rsi_14,
                        "macd_line": stmt.excluded.macd_line,
                        "macd_signal": stmt.excluded.macd_signal,
                        "macd_histogram": stmt.excluded.macd_histogram,
                        "bb_upper": stmt.excluded.bb_upper,
                        "bb_middle": stmt.excluded.bb_middle,
                        "bb_lower": stmt.excluded.bb_lower,
                        "bb_position": stmt.excluded.bb_position,
                        "bb_width": stmt.excluded.bb_width,
                        "volatility_20": stmt.excluded.volatility_20,
                        "price_change_1d": stmt.excluded.price_change_1d,
                        "price_change_5d": stmt.excluded.price_change_5d,
                        "price_change_30d": stmt.excluded.price_change_30d,
                        "avg_volume_20": stmt.excluded.avg_volume_20,
                        "current_volume": stmt.excluded.current_volume,
                    },
                )
                
                result = session.execute(stmt)
                rowcount = getattr(result, 'rowcount', None)
                if rowcount is not None:
                    logger.debug(f"Upserted latest indicators for {symbol}: {rowcount} row(s) affected")
                else:
                    logger.debug(f"Upserted latest indicators for {symbol}")
                # Explicitly flush and commit to ensure data is persisted
                session.flush()
                session.commit()
                logger.debug(f"Committed latest indicators for {symbol}")
        except Exception as e:
            logger.error(f"Error storing latest indicators for {symbol}: {e}", exc_info=True)
            raise

    async def store_time_series_indicators(
        self,
        indicators: Dict,
        calculation_date: date,
    ) -> None:
        """
        Store indicators in time-series table (insert, skip if exists)
        
        Args:
            indicators: Dictionary with indicator values
            calculation_date: Date for which indicators were calculated
        """
        symbol = indicators.get("symbol")
        if not symbol:
            raise ValueError(f"Missing 'symbol' key in indicators dict. Available keys: {list(indicators.keys())}")
        
        try:
            with db_transaction() as session:
                # Check if record already exists
                stmt = select(TechnicalIndicators).where(
                    TechnicalIndicators.symbol == symbol,
                    TechnicalIndicators.date == calculation_date,
                )
                result = session.execute(stmt)
                existing = result.scalar_one_or_none()
                
                if existing:
                    logger.debug(
                        f"Indicators for {symbol} on {calculation_date} already exist, skipping"
                    )
                    return
                
                # Insert new record
                indicator_record = TechnicalIndicators(
                    symbol=symbol,
                    date=calculation_date,
                sma_20=indicators.get("sma_20"),
                sma_50=indicators.get("sma_50"),
                sma_200=indicators.get("sma_200"),
                ema_12=indicators.get("ema_12"),
                ema_26=indicators.get("ema_26"),
                ema_50=indicators.get("ema_50"),
                rsi=indicators.get("rsi"),
                rsi_14=indicators.get("rsi_14"),
                macd_line=indicators.get("macd_line"),
                macd_signal=indicators.get("macd_signal"),
                macd_histogram=indicators.get("macd_histogram"),
                bb_upper=indicators.get("bb_upper"),
                bb_middle=indicators.get("bb_middle"),
                bb_lower=indicators.get("bb_lower"),
                bb_position=indicators.get("bb_position"),
                bb_width=indicators.get("bb_width"),
                volatility_20=indicators.get("volatility_20"),
                price_change_1d=indicators.get("price_change_1d"),
                price_change_5d=indicators.get("price_change_5d"),
                price_change_30d=indicators.get("price_change_30d"),
                avg_volume_20=indicators.get("avg_volume_20"),
                    current_volume=indicators.get("current_volume"),
                )
                
                session.add(indicator_record)
                logger.debug(f"Inserted time-series indicators for {symbol} on {calculation_date}")
                # Explicitly flush and commit to ensure data is persisted
                session.flush()
                session.commit()
                logger.debug(f"Committed time-series indicators for {symbol}")
        except Exception as e:
            logger.error(f"Error storing time-series indicators for {symbol}: {e}", exc_info=True)
            raise

    async def get_latest_indicators(
        self,
        symbol: str,
    ) -> Optional[TechnicalIndicatorsLatest]:
        """
        Get latest indicators for a symbol
        
        Args:
            symbol: Stock symbol
            
        Returns:
            TechnicalIndicatorsLatest record or None if not found
        """
        symbol = symbol.upper()
        
        with db_transaction() as session:
            stmt = select(TechnicalIndicatorsLatest).where(
                TechnicalIndicatorsLatest.symbol == symbol
            )
            result = session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_indicators_for_date_range(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[TechnicalIndicators]:
        """
        Get historical indicators for a symbol within a date range
        
        Args:
            symbol: Stock symbol
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            
        Returns:
            List of TechnicalIndicators records
        """
        symbol = symbol.upper()
        
        with db_transaction() as session:
            stmt = (
                select(TechnicalIndicators)
                .where(
                    TechnicalIndicators.symbol == symbol,
                    TechnicalIndicators.date >= start_date,
                    TechnicalIndicators.date <= end_date,
                )
                .order_by(TechnicalIndicators.date.asc())
            )
            result = session.execute(stmt)
            return list(result.scalars().all())

