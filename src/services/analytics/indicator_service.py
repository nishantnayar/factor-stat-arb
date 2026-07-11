"""
Technical Indicator Service

Combined service for calculating and storing technical indicators.
This is the main entry point for indicator operations.
"""

from datetime import date
from typing import Dict, List, Optional

from loguru import logger

from .indicator_calculator import IndicatorCalculationService
from .indicator_storage import IndicatorStorageService


class IndicatorService:
    """
    Main service for technical indicator operations
    
    Combines calculation and storage functionality.
    """

    def __init__(self, data_source: str = "yahoo_adjusted"):
        """
        Initialize the indicator service.

        Args:
            data_source: Data source for OHLC; use 'yahoo_adjusted' (default)
                so indicators are calculated on adjusted prices.
        """
        self.calculator = IndicatorCalculationService(data_source=data_source)
        self.storage = IndicatorStorageService()

    async def calculate_and_store(
        self,
        symbol: str,
        calculation_date: Optional[date] = None,
        days_back: int = 300,
    ) -> bool:
        """
        Calculate indicators for a symbol and store in database
        
        Args:
            symbol: Stock symbol
            calculation_date: Date for which to calculate (default: today)
            days_back: Number of days of history to fetch (default: 300)
            
        Returns:
            True if successful, False otherwise
        """
        if calculation_date is None:
            calculation_date = date.today()
        
        symbol = symbol.upper()
        logger.info(f"Calculating and storing indicators for {symbol} on {calculation_date}")
        
        # Calculate indicators
        indicators = await self.calculator.calculate_indicators_for_symbol(
            symbol=symbol,
            calculation_date=calculation_date,
            days_back=days_back,
        )
        
        if not indicators:
            logger.warning(f"Failed to calculate indicators for {symbol}")
            return False
        
        # Store indicators
        success = await self.storage.store_indicators(
            indicators=indicators,
            calculation_date=calculation_date,
        )
        
        return success

    async def batch_calculate_and_store(
        self,
        symbols: List[str],
        calculation_date: Optional[date] = None,
        days_back: int = 300,
    ) -> Dict[str, bool]:
        """
        Calculate and store indicators for multiple symbols
        
        Args:
            symbols: List of stock symbols
            calculation_date: Date for which to calculate (default: today)
            days_back: Number of days of history to fetch (default: 300)
            
        Returns:
            Dictionary mapping symbol to success status
        """
        if calculation_date is None:
            calculation_date = date.today()
        
        results = {}
        
        logger.info(
            f"Batch calculating and storing indicators for {len(symbols)} symbols "
            f"on {calculation_date}"
        )
        
        # Calculate all indicators
        calculated_indicators = await self.calculator.batch_calculate_indicators(
            symbols=symbols,
            calculation_date=calculation_date,
            days_back=days_back,
        )
        
        # Store all indicators
        logger.info(f"Starting to store indicators for {len(calculated_indicators)} symbols...")
        for symbol, indicators in calculated_indicators.items():
            if indicators:
                logger.debug(f"Storing indicators for {symbol}...")
                success = await self.storage.store_indicators(
                    indicators=indicators,
                    calculation_date=calculation_date,
                )
                results[symbol] = success
                if success:
                    logger.debug(f"Stored {symbol} OK")
            else:
                logger.warning(f"No indicators to store for {symbol}")
                results[symbol] = False
        
        successful = sum(1 for v in results.values() if v)
        logger.info(
            f"Batch calculation and storage complete: "
            f"{successful}/{len(symbols)} symbols successful"
        )
        
        return results

    async def get_latest_indicators(
        self,
        symbol: str,
    ) -> Optional[Dict]:
        """
        Get latest indicators for a symbol from database
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dictionary with indicator values, or None if not found
        """
        latest = await self.storage.get_latest_indicators(symbol)
        
        if latest:
            return latest.to_dict()
        
        return None

    async def get_indicators_for_date_range(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[Dict]:
        """
        Get historical indicators for a symbol within a date range
        
        Args:
            symbol: Stock symbol
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            
        Returns:
            List of dictionaries with indicator values
        """
        indicators = await self.storage.get_indicators_for_date_range(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )
        
        return [ind.to_dict() for ind in indicators]

