"""
Analyst Recommendations Database Model

SQLAlchemy model for analyst recommendation data.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import TIMESTAMP, Date, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database.base import Base

if TYPE_CHECKING:
    from .symbols import Symbol


class AnalystRecommendation(Base):
    """
    Analyst recommendation information

    Stores analyst recommendation counts over time, including
    Strong Buy, Buy, Hold, Sell, and Strong Sell counts.
    """

    __tablename__ = "analyst_recommendations"
    __table_args__ = (
        Index("idx_analyst_recommendations_symbol", "symbol"),
        Index("idx_analyst_recommendations_date", "date"),
        Index("idx_analyst_recommendations_symbol_date", "symbol", "date"),
        Index("idx_analyst_recommendations_period", "symbol", "period"),
        Index("idx_analyst_recommendations_total_analysts", "symbol", "total_analysts"),
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
    date: Mapped[date] = mapped_column(Date, nullable=False)
    period: Mapped[str] = mapped_column(String(10), nullable=False)

    # Recommendation Counts
    strong_buy: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    buy: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hold: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sell: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    strong_sell: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_analysts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        # Computed column in database: strong_buy + buy + hold + sell + strong_sell
        # Use total_analysts_calculated property for application-level calculation
    )

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
        back_populates="analyst_recommendations",
        foreign_keys=[symbol],
    )

    def __repr__(self) -> str:
        return (
            f"<AnalystRecommendation(symbol='{self.symbol}', "
            f"date={self.date}, period='{self.period}', total={self.total_analysts})>"
        )

    @property
    def total_analysts_calculated(self) -> int:
        """Calculate total number of analysts"""
        return self.strong_buy + self.buy + self.hold + self.sell + self.strong_sell

    @property
    def buy_percentage(self) -> float:
        """Calculate percentage of buy recommendations (Strong Buy + Buy)"""
        if self.total_analysts_calculated == 0:
            return 0.0
        return ((self.strong_buy + self.buy) / self.total_analysts_calculated) * 100

    @property
    def sell_percentage(self) -> float:
        """Calculate percentage of sell recommendations (Sell + Strong Sell)"""
        if self.total_analysts_calculated == 0:
            return 0.0
        return ((self.sell + self.strong_sell) / self.total_analysts_calculated) * 100

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "date": self.date.isoformat(),
            "period": self.period,
            "strong_buy": self.strong_buy,
            "buy": self.buy,
            "hold": self.hold,
            "sell": self.sell,
            "strong_sell": self.strong_sell,
            "total_analysts": self.total_analysts_calculated,
            "buy_percentage": round(self.buy_percentage, 2),
            "sell_percentage": round(self.sell_percentage, 2),
            "data_source": self.data_source,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

