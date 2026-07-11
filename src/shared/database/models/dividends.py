"""
Dividends Database Model

SQLAlchemy model for dividend payment history.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import TIMESTAMP, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database.base import Base

if TYPE_CHECKING:
    from .symbols import Symbol


class Dividend(Base):
    """
    Dividend payment information

    Stores historical dividend payments including ex-dividend date,
    payment date, amount, and type.
    """

    __tablename__ = "dividends"
    __table_args__ = (
        Index("idx_dividends_symbol", "symbol"),
        Index("idx_dividends_ex_date", "ex_date"),
        Index("idx_dividends_symbol_ex_date", "symbol", "ex_date"),
        Index("idx_dividends_payment_date", "payment_date"),
        Index("idx_dividends_symbol_date_range", "symbol", "ex_date", "payment_date"),
        Index("idx_dividends_amount", "symbol", "amount"),
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
    ex_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)

    # Optional Dates
    payment_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    record_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Dividend Details
    dividend_type: Mapped[str] = mapped_column(
        String(20), default="regular", nullable=False
    )
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)

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
        back_populates="dividends",
        foreign_keys=[symbol],
    )

    def __repr__(self) -> str:
        return (
            f"<Dividend(symbol='{self.symbol}', "
            f"ex_date={self.ex_date}, amount={self.amount})>"
        )

    @property
    def amount_display(self) -> str:
        """Display amount with formatting"""
        return f"${float(self.amount):.4f}"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "ex_date": self.ex_date.isoformat(),
            "amount": float(self.amount),
            "amount_display": self.amount_display,
            "payment_date": self.payment_date.isoformat() if self.payment_date else None,
            "record_date": self.record_date.isoformat() if self.record_date else None,
            "dividend_type": self.dividend_type,
            "currency": self.currency,
            "data_source": self.data_source,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

