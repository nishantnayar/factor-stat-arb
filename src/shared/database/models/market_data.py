"""
Database models for market data storage
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class MarketData(Base):
    """Market data (OHLCV) from various sources"""

    __tablename__ = "market_data"
    __table_args__ = {"schema": "data_ingestion"}

    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Symbol and timestamp
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # Data source
    data_source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="polygon", index=True
    )  # 'polygon', 'yahoo', 'alpaca', etc.

    # OHLCV data
    open: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)
    high: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)
    low: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)
    close: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)
    volume: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<MarketData(symbol='{self.symbol}', source='{self.data_source}', "
            f"timestamp='{self.timestamp}', close={self.close}, volume={self.volume})>"
        )

    @property
    def is_complete(self) -> bool:
        """Check if all OHLCV data is present"""
        return all(
            [
                self.open is not None,
                self.high is not None,
                self.low is not None,
                self.close is not None,
                self.volume is not None,
            ]
        )

    @property
    def price_change(self) -> Optional[float]:
        """Calculate price change from open to close"""
        if self.open is not None and self.close is not None:
            return self.close - self.open
        return None

    @property
    def price_change_percent(self) -> Optional[float]:
        """Calculate price change percentage from open to close"""
        if self.open is not None and self.close is not None and self.open != 0:
            return ((self.close - self.open) / self.open) * 100
        return None
