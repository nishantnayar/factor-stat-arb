"""
Database model for company information
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, BigInteger, Column, DateTime, Integer, String, Text
from sqlalchemy.ext.hybrid import hybrid_property

from ..base import Base


class CompanyInfo(Base):
    """Company profile and basic information"""

    __tablename__ = "company_info"
    __table_args__ = {"schema": "data_ingestion"}

    # Primary key
    symbol = Column(String(10), primary_key=True)

    # Company details
    name = Column(String(255), nullable=True)
    sector = Column(String(100), nullable=True)
    industry = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)

    # Contact information
    website = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(String(500), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    zip = Column(String(20), nullable=True)
    country = Column(String(100), nullable=True)

    # Company metrics
    employees = Column(Integer, nullable=True)
    market_cap = Column(BigInteger, nullable=True)

    # Trading information
    currency = Column(String(10), nullable=True)
    exchange = Column(String(50), nullable=True)
    quote_type = Column(String(50), nullable=True)

    # Data source and metadata
    data_source = Column(String(20), nullable=False, default="yahoo")
    additional_data = Column(JSON, nullable=True)  # JSONB in PostgreSQL

    # Timestamps
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<CompanyInfo(symbol='{self.symbol}', name='{self.name}', "
            f"sector='{self.sector}', industry='{self.industry}')>"
        )

    @hybrid_property
    def full_address(self) -> Optional[str]:
        """Get full formatted address"""
        parts = []
        if self.address:
            parts.append(self.address)
        if self.city:
            parts.append(self.city)
        if self.state and self.zip:
            parts.append(f"{self.state} {self.zip}")  # type: ignore[arg-type]
        elif self.state:
            parts.append(self.state)
        elif self.zip:
            parts.append(self.zip)
        if self.country:
            parts.append(self.country)

        return ", ".join(parts) if parts else None  # type: ignore[arg-type]

    @hybrid_property
    def market_cap_millions(self) -> Optional[float]:
        """Get market cap in millions"""
        return float(self.market_cap / 1_000_000) if self.market_cap else None

    @hybrid_property
    def market_cap_billions(self) -> Optional[float]:
        """Get market cap in billions"""
        return float(self.market_cap / 1_000_000_000) if self.market_cap else None

    @hybrid_property
    def is_technology_sector(self) -> bool:
        """Check if company is in technology sector"""
        return bool(self.sector and "technology" in self.sector.lower())
