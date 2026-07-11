"""
ESG Scores Database Model

SQLAlchemy model for ESG (Environmental, Social, Governance) scores.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import TIMESTAMP, Date, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database.base import Base

if TYPE_CHECKING:
    from .symbols import Symbol


class ESGScore(Base):
    """
    ESG (Environmental, Social, Governance) scores

    Stores ESG scores and related metrics for companies.
    """

    __tablename__ = "esg_scores"
    __table_args__ = (
        Index("idx_esg_scores_symbol", "symbol"),
        Index("idx_esg_scores_date", "date"),
        Index("idx_esg_scores_symbol_date", "symbol", "date"),
        Index("idx_esg_scores_total_esg", "symbol", "total_esg"),
        Index("idx_esg_scores_performance", "esg_performance"),
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

    # ESG Scores (0-100 scale)
    total_esg: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    environment_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    social_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    governance_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True
    )

    # Additional Metrics
    controversy_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    esg_performance: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    peer_group: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    peer_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    percentile: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)

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
        back_populates="esg_scores",
        foreign_keys=[symbol],
    )

    def __repr__(self) -> str:
        return (
            f"<ESGScore(symbol='{self.symbol}', date={self.date}, "
            f"total_esg={self.total_esg})>"
        )

    @property
    def has_complete_scores(self) -> bool:
        """Check if all three component scores are available"""
        return (
            self.environment_score is not None
            and self.social_score is not None
            and self.governance_score is not None
        )

    @property
    def average_component_score(self) -> Optional[float]:
        """Calculate average of E, S, G scores if all are available"""
        if not self.has_complete_scores:
            return None
        # Type narrowing: has_complete_scores guarantees these are not None
        assert self.environment_score is not None
        assert self.social_score is not None
        assert self.governance_score is not None
        return (
            float(self.environment_score)
            + float(self.social_score)
            + float(self.governance_score)
        ) / 3.0

    @property
    def controversy_level_str(self) -> str:
        """Get controversy level as string"""
        if self.controversy_level is None:
            return "Unknown"
        levels = ["None", "Low", "Moderate", "Significant", "High", "Very High"]
        return levels[min(self.controversy_level, len(levels) - 1)]

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "date": self.date.isoformat(),
            "total_esg": float(self.total_esg) if self.total_esg else None,
            "environment_score": float(self.environment_score)
            if self.environment_score
            else None,
            "social_score": float(self.social_score) if self.social_score else None,
            "governance_score": float(self.governance_score)
            if self.governance_score
            else None,
            "controversy_level": self.controversy_level,
            "controversy_level_str": self.controversy_level_str,
            "esg_performance": self.esg_performance,
            "peer_group": self.peer_group,
            "peer_count": self.peer_count,
            "percentile": float(self.percentile) if self.percentile else None,
            "has_complete_scores": self.has_complete_scores,
            "average_component_score": (
                round(self.average_component_score, 2)
                if self.average_component_score
                else None
            ),
            "data_source": self.data_source,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

