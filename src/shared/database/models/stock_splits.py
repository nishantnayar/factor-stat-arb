"""
Stock Splits Database Model

SQLAlchemy model for stock split history.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import TIMESTAMP, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database.base import Base

if TYPE_CHECKING:
    from .symbols import Symbol


class StockSplit(Base):
    """
    Stock split information

    Stores historical stock split events including split date,
    ratio, and human-readable ratio string.
    """

    __tablename__ = "stock_splits"
    __table_args__ = (
        Index("idx_stock_splits_symbol", "symbol"),
        Index("idx_stock_splits_split_date", "split_date"),
        Index("idx_stock_splits_symbol_split_date", "symbol", "split_date"),
        Index("idx_stock_splits_ratio", "symbol", "split_ratio"),
        {"schema": "data_ingestion"},
    )

    # Primary Key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Foreign Key & Core Fields
    symbol: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("data_ingestion.symbols.symbol", ondelete="CASCADE"),
        nullable=False,
    )
    split_date: Mapped[date] = mapped_column(Date, nullable=False)
    split_ratio: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)

    # Optional Fields
    ratio_str: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Metadata
    data_source: Mapped[str] = mapped_column(
        String(20), default="yahoo", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    symbol_ref: Mapped["Symbol"] = relationship(
        "Symbol",
        back_populates="stock_splits",
        foreign_keys=[symbol],
    )

    def __repr__(self) -> str:
        return (
            f"<StockSplit(symbol='{self.symbol}', "
            f"split_date={self.split_date}, ratio={self.split_ratio})>"
        )

    @property
    def ratio_display(self) -> str:
        """Display ratio with formatting"""
        if self.ratio_str:
            return self.ratio_str
        if self.split_ratio >= 1:
            return f"{int(self.split_ratio)}:1"
        else:
            return f"1:{int(1 / float(self.split_ratio))}"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "split_date": self.split_date.isoformat(),
            "split_ratio": float(self.split_ratio),
            "ratio_str": self.ratio_str or self.ratio_display,
            "ratio_display": self.ratio_display,
            "data_source": self.data_source,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

