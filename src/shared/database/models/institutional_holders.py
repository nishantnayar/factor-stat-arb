"""
Institutional Holders Database Model

SQLAlchemy model for institutional ownership data.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database.base import Base

if TYPE_CHECKING:
    from .symbols import Symbol


class InstitutionalHolder(Base):
    """
    Institutional ownership information

    Stores data about major institutional investors holding shares,
    including investment firms, mutual funds, pension funds, etc.
    """

    __tablename__ = "institutional_holders"
    __table_args__ = (
        Index("idx_institutional_holders_symbol", "symbol"),
        Index("idx_institutional_holders_date", "date_reported"),
        Index("idx_institutional_holders_symbol_date", "symbol", "date_reported"),
        Index("idx_institutional_holders_holder_name", "holder_name"),
        Index("idx_institutional_holders_shares", "symbol", "shares"),
        Index("idx_institutional_holders_percent", "symbol", "percent_held"),
        Index("idx_institutional_holders_latest", "symbol", "is_latest"),
        {"schema": "data_ingestion"},
    )

    # Primary Key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Foreign Key & Core Fields
    symbol: Mapped[str] = mapped_column(
        String(10),
        ForeignKey("data_ingestion.symbols.symbol", ondelete="CASCADE"),
        nullable=False,
    )
    date_reported: Mapped[date] = mapped_column(Date, nullable=False)
    holder_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Holding Details
    shares: Mapped[Optional[int]] = mapped_column(BigInteger)
    value: Mapped[Optional[int]] = mapped_column(BigInteger)
    percent_held: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    percent_change: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    
    # Flag to indicate latest record for this holder
    is_latest: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Metadata
    data_source: Mapped[str] = mapped_column(
        String(50), default="yahoo", nullable=False
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
        back_populates="institutional_holders",
        foreign_keys=[symbol],
    )

    def __repr__(self) -> str:
        return (
            f"<InstitutionalHolder(symbol='{self.symbol}', "
            f"holder='{self.holder_name}', shares={self.shares})>"
        )

    @property
    def shares_display(self) -> str:
        """Display shares with formatting"""
        if self.shares is None:
            return "N/A"

        shares = float(self.shares)
        if shares >= 1_000_000_000:
            return f"{shares / 1_000_000_000:.2f}B"
        elif shares >= 1_000_000:
            return f"{shares / 1_000_000:.2f}M"
        elif shares >= 1_000:
            return f"{shares / 1_000:.2f}K"
        else:
            return f"{shares:,.0f}"

    @property
    def value_display(self) -> str:
        """Display value with formatting"""
        if self.value is None:
            return "N/A"

        val = float(self.value)
        if val >= 1_000_000_000:
            return f"${val / 1_000_000_000:.2f}B"
        elif val >= 1_000_000:
            return f"${val / 1_000_000:.2f}M"
        else:
            return f"${val:,.0f}"

    @property
    def percent_held_display(self) -> str:
        """Display percentage held"""
        if self.percent_held is None:
            return "N/A"
        return f"{float(self.percent_held) * 100:.2f}%"
    
    @property
    def percent_change_display(self) -> str:
        """Display percentage change with arrow indicators"""
        if self.percent_change is None:
            return "N/A"
        change_val = float(self.percent_change) * 100  # Convert to percentage
        if change_val > 0:
            return f"+ {abs(change_val):.2f}%"
        if change_val < 0:
            return f"- {abs(change_val):.2f}%"
        return f"= {abs(change_val):.2f}%"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "symbol": self.symbol,
            "date_reported": self.date_reported.isoformat(),
            "holder_name": self.holder_name,
            "shares": self.shares,
            "shares_display": self.shares_display,
            "value": self.value,
            "value_display": self.value_display,
            "percent_held": float(self.percent_held) if self.percent_held is not None else None,
            "percent_held_display": self.percent_held_display,
            "percent_change": float(self.percent_change) if self.percent_change is not None else None,
            "percent_change_display": self.percent_change_display,
            "is_latest": self.is_latest,
            "data_source": self.data_source,
        }
