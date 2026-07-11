"""
Company Officers SQLAlchemy model
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, cast

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..base import Base


class CompanyOfficer(Base):
    """Company officer/executive data model"""

    __tablename__ = "company_officers"
    __table_args__ = {"schema": "data_ingestion"}

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Foreign key to symbols table
    symbol = Column(
        String(20),
        ForeignKey("data_ingestion.symbols.symbol", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Officer details
    name = Column(String(255), nullable=False)
    title = Column(String(255), nullable=True)
    age = Column(Integer, nullable=True)
    year_born = Column(Integer, nullable=True)
    fiscal_year = Column(Integer, nullable=True)

    # Compensation data (stored in cents)
    total_pay = Column(BigInteger, nullable=True)
    exercised_value = Column(BigInteger, nullable=True)
    unexercised_value = Column(BigInteger, nullable=True)

    # Metadata
    data_source = Column(String(20), nullable=False, default="yahoo")
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    symbol_ref = relationship("Symbol", back_populates="company_officers")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "name": self.name,
            "title": self.title,
            "age": self.age,
            "year_born": self.year_born,
            "fiscal_year": self.fiscal_year,
            "total_pay": self.total_pay,
            "total_pay_display": self.total_pay_display,
            "exercised_value": self.exercised_value,
            "exercised_value_display": self.exercised_value_display,
            "unexercised_value": self.unexercised_value,
            "unexercised_value_display": self.unexercised_value_display,
            "data_source": self.data_source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @property
    def total_pay_display(self) -> str:
        """Get formatted total pay"""
        total_pay = cast(Optional[int], self.total_pay)
        if total_pay is None:
            return "N/A"
        elif total_pay == 0:
            return "$0"
        else:
            # Convert from cents to dollars
            amount = total_pay / 100

            if amount >= 1_000_000:
                return f"${amount / 1_000_000:.1f}M"
            elif amount >= 1_000:
                return f"${amount / 1_000:.1f}K"
            else:
                return f"${amount:,.0f}"

    @property
    def exercised_value_display(self) -> str:
        """Get formatted exercised value"""
        exercised_value = cast(Optional[int], self.exercised_value)
        if exercised_value is None:
            return "N/A"
        elif exercised_value == 0:
            return "$0"
        else:
            # Convert from cents to dollars
            amount = exercised_value / 100

            if amount >= 1_000_000:
                return f"${amount / 1_000_000:.1f}M"
            elif amount >= 1_000:
                return f"${amount / 1_000:.1f}K"
            else:
                return f"${amount:,.0f}"

    @property
    def unexercised_value_display(self) -> str:
        """Get formatted unexercised value"""
        unexercised_value = cast(Optional[int], self.unexercised_value)
        if unexercised_value is None:
            return "N/A"
        elif unexercised_value == 0:
            return "$0"
        else:
            # Convert from cents to dollars
            amount = unexercised_value / 100

            if amount >= 1_000_000:
                return f"${amount / 1_000_000:.1f}M"
            elif amount >= 1_000:
                return f"${amount / 1_000:.1f}K"
            else:
                return f"${amount:,.0f}"

    def __repr__(self) -> str:
        return f"<CompanyOfficer(symbol={self.symbol}, name={self.name}, title={self.title})>"
