"""
Symbol management service for data ingestion
"""

from datetime import date, datetime, timezone
from typing import List, Optional

from loguru import logger
from sqlalchemy import and_, func, select

from src.services.polygon.client import PolygonClient
from src.services.polygon.exceptions import PolygonDataError
from src.shared.database.base import db_transaction
from src.shared.database.models.symbols import DelistedSymbol, Symbol, SymbolDataStatus


class SymbolService:
    """Service for managing symbols and delisting detection"""

    def __init__(self) -> None:
        self._polygon_client: Optional[PolygonClient] = None  # Lazy initialization - only create when needed

    async def get_active_symbols(self) -> List[Symbol]:
        """Get all active symbols, sorted alphabetically by symbol."""
        with db_transaction() as session:
            stmt = (
                select(Symbol).where(Symbol.status == "active").order_by(Symbol.symbol)
            )
            result = session.execute(stmt)
            return list(result.scalars().all())

    async def get_active_symbol_strings(self) -> List[str]:
        """Get list of active symbol strings, sorted alphabetically."""
        with db_transaction() as session:
            stmt = (
                select(Symbol.symbol)
                .where(Symbol.status == "active")
                .order_by(Symbol.symbol)
            )
            result = session.execute(stmt)
            return [row[0] for row in result.fetchall()]

    async def get_symbol_by_ticker(self, symbol: str) -> Optional[Symbol]:
        """Get symbol by ticker"""
        with db_transaction() as session:
            stmt = select(Symbol).where(Symbol.symbol == symbol.upper())
            result = session.execute(stmt)
            return result.scalar_one_or_none()

    async def add_symbol(
        self,
        symbol: str,
        name: Optional[str] = None,
        exchange: Optional[str] = None,
        sector: Optional[str] = None,
        market_cap: Optional[int] = None,
    ) -> Symbol:
        """Add a new symbol"""
        symbol = symbol.upper()

        with db_transaction() as session:
            # Check if symbol already exists
            existing = await self.get_symbol_by_ticker(symbol)
            if existing:
                logger.warning(f"Symbol {symbol} already exists")
                return existing

            # Create new symbol
            new_symbol = Symbol(
                symbol=symbol,
                name=name,
                exchange=exchange,
                sector=sector,
                market_cap=market_cap,
                status="active",
            )

            session.add(new_symbol)
            session.commit()
            session.refresh(new_symbol)

            logger.info(f"Added new symbol: {symbol}")
            return new_symbol

    async def mark_symbol_delisted(
        self,
        symbol: str,
        last_price: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """Mark a symbol as delisted"""
        symbol = symbol.upper()

        with db_transaction() as session:
            # Get the symbol
            stmt = select(Symbol).where(Symbol.symbol == symbol)
            result = session.execute(stmt)
            symbol_obj = result.scalar_one_or_none()

            if not symbol_obj:
                logger.warning(f"Symbol {symbol} not found")
                return False

            # Check if already in delisted_symbols table
            delisted_stmt = select(DelistedSymbol).where(DelistedSymbol.symbol == symbol)
            delisted_result = session.execute(delisted_stmt)
            existing_delisted = delisted_result.scalar_one_or_none()

            if existing_delisted:
                # Symbol already marked as delisted, just update the symbol status if needed
                logger.info(f"Symbol {symbol} is already in delisted_symbols table")
                if symbol_obj.status != "delisted":
                    symbol_obj.status = "delisted"  # type: ignore
                    symbol_obj.last_updated = datetime.now(timezone.utc)  # type: ignore
                    session.commit()
                return True

            # Update symbol status
            symbol_obj.status = "delisted"  # type: ignore
            symbol_obj.last_updated = datetime.now(timezone.utc)  # type: ignore

            # Add to delisted symbols table
            delisted_symbol = DelistedSymbol(
                symbol=symbol,
                delist_date=date.today(),
                last_price=last_price,
                notes=notes or "Automatically detected as delisted",
            )

            session.add(delisted_symbol)
            session.commit()

            logger.info(f"Marked symbol {symbol} as delisted")
            return True

    @property
    def polygon_client(self) -> PolygonClient:
        """Lazy-load Polygon client only when needed"""
        if self._polygon_client is None:
            self._polygon_client = PolygonClient()
        # Type narrowing: after the check above, _polygon_client cannot be None
        assert self._polygon_client is not None
        return self._polygon_client

    async def check_symbol_health(self, symbol: str) -> bool:
        """Check if a symbol is still valid by attempting to fetch data"""
        try:
            # Try to get ticker details from Polygon
            await self.polygon_client.get_ticker_details(symbol)
            return True
        except PolygonDataError as e:
            if "not found" in str(e).lower() or "404" in str(e):
                logger.warning(f"Symbol {symbol} appears to be delisted: {e}")
                return False
            else:
                # Other errors might be temporary
                logger.error(f"Error checking symbol {symbol}: {e}")
                return True
        except Exception as e:
            logger.error(f"Unexpected error checking symbol {symbol}: {e}")
            return True

    async def detect_delisted_symbols(self) -> List[str]:
        """Detect and mark delisted symbols"""
        delisted_symbols = []
        active_symbols = await self.get_active_symbol_strings()

        for symbol in active_symbols:
            logger.info(f"Checking health of symbol: {symbol}")

            is_healthy = await self.check_symbol_health(symbol)
            if not is_healthy:
                # Mark as delisted
                success = await self.mark_symbol_delisted(symbol)
                if success:
                    delisted_symbols.append(symbol)

        logger.info(
            f"Detected {len(delisted_symbols)} delisted symbols: {delisted_symbols}"
        )
        return delisted_symbols

    async def get_symbol_data_status(
        self,
        symbol: str,
        date: date,
        data_source: str = "polygon",
    ) -> Optional[SymbolDataStatus]:
        """Get data ingestion status for a symbol"""
        with db_transaction() as session:
            stmt = select(SymbolDataStatus).where(
                and_(
                    SymbolDataStatus.symbol == symbol.upper(),
                    SymbolDataStatus.date == date,
                    SymbolDataStatus.data_source == data_source,
                )
            )
            result = session.execute(stmt)
            return result.scalar_one_or_none()

    async def update_symbol_data_status(
        self,
        symbol: str,
        date: date,
        data_source: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> SymbolDataStatus:
        """Update data ingestion status for a symbol"""
        symbol = symbol.upper()

        with db_transaction() as session:
            # Check if status already exists within this session
            stmt = select(SymbolDataStatus).where(
                and_(
                    SymbolDataStatus.symbol == symbol,
                    SymbolDataStatus.date == date,
                    SymbolDataStatus.data_source == data_source,
                )
            )
            result = session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing
                existing.status = status  # type: ignore
                existing.error_message = error_message  # type: ignore
                existing.last_attempt = datetime.now(timezone.utc)  # type: ignore
                session.commit()
                session.refresh(existing)
                return existing
            else:
                # Create new
                new_status = SymbolDataStatus(
                    symbol=symbol,
                    date=date,
                    data_source=data_source,
                    status=status,
                    error_message=error_message,
                )
                session.add(new_status)
                session.commit()
                session.refresh(new_status)
                return new_status

    async def get_symbols_needing_data(
        self,
        target_date: date,
        data_source: str = "polygon",
    ) -> List[Symbol]:
        """Get symbols that need data for a specific date"""
        with db_transaction() as session:
            # Get active symbols that don't have successful data for the date
            stmt = (
                select(Symbol)
                .where(Symbol.status == "active")
                .where(
                    ~Symbol.symbol.in_(
                        select(SymbolDataStatus.symbol).where(
                            and_(
                                SymbolDataStatus.date == target_date,
                                SymbolDataStatus.data_source == data_source,
                                SymbolDataStatus.status == "success",
                            )
                        )
                    )
                )
            )
            result = session.execute(stmt)
            return list(result.scalars().all())

    async def get_delisted_symbols(self) -> List[DelistedSymbol]:
        """Get all delisted symbols"""
        with db_transaction() as session:
            stmt = select(DelistedSymbol).order_by(DelistedSymbol.delist_date.desc())
            result = session.execute(stmt)
            return list(result.scalars().all())

    async def get_symbol_statistics(self) -> dict:
        """Get statistics about symbols"""
        with db_transaction() as session:
            # Count active symbols
            active_count = session.scalar(
                select(func.count(Symbol.symbol)).where(Symbol.status == "active")
            )

            # Count delisted symbols
            delisted_count = session.scalar(select(func.count(DelistedSymbol.symbol)))

            # Count symbols by exchange
            exchange_counts = session.execute(
                select(Symbol.exchange, func.count(Symbol.symbol))
                .where(Symbol.status == "active")
                .group_by(Symbol.exchange)
            ).all()

            return {
                "active_symbols": active_count or 0,
                "delisted_symbols": delisted_count or 0,
                "total_symbols": (active_count or 0) + (delisted_count or 0),
                "by_exchange": {row[0]: row[1] for row in exchange_counts},
            }
