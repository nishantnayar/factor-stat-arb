"""
Database models for symbol management
"""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, Date, DateTime, Numeric, String, Text
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from ..base import Base


class Symbol(Base):
    """Active symbols being tracked for data ingestion"""

    __tablename__ = "symbols"
    __table_args__ = {"schema": "data_ingestion"}

    # Primary key
    symbol = Column(String(10), primary_key=True)

    # Symbol details
    name = Column(String(255), nullable=True)
    exchange = Column(String(50), nullable=True)
    sector = Column(String(100), nullable=True)
    market_cap = Column(BigInteger, nullable=True)

    # Status tracking
    status = Column(String(20), default="active", nullable=False)

    # Timestamps
    added_date = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    last_updated = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    key_statistics = relationship(
        "KeyStatistics",
        back_populates="symbol_ref",
        cascade="all, delete-orphan",
    )
    institutional_holders = relationship(
        "InstitutionalHolder",
        back_populates="symbol_ref",
        cascade="all, delete-orphan",
    )
    financial_statements = relationship(
        "FinancialStatement",
        back_populates="symbol_ref",
        cascade="all, delete-orphan",
    )
    company_officers = relationship(
        "CompanyOfficer",
        back_populates="symbol_ref",
        cascade="all, delete-orphan",
    )
    dividends = relationship(
        "Dividend",
        back_populates="symbol_ref",
        cascade="all, delete-orphan",
    )
    stock_splits = relationship(
        "StockSplit",
        back_populates="symbol_ref",
        cascade="all, delete-orphan",
    )
    analyst_recommendations = relationship(
        "AnalystRecommendation",
        back_populates="symbol_ref",
        cascade="all, delete-orphan",
    )
    esg_scores = relationship(
        "ESGScore",
        back_populates="symbol_ref",
        cascade="all, delete-orphan",
    )
    technical_indicators_latest = relationship(
        "TechnicalIndicatorsLatest",
        back_populates="symbol_ref",
        cascade="all, delete-orphan",
        uselist=False,  # One-to-one relationship
    )
    technical_indicators = relationship(
        "TechnicalIndicators",
        back_populates="symbol_ref",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Symbol(symbol='{self.symbol}', name='{self.name}', status='{self.status}')>"

    @hybrid_property
    def is_active(self) -> bool:
        """Check if symbol is active"""
        return bool(self.status == "active")

    @hybrid_property
    def is_delisted(self) -> bool:
        """Check if symbol is delisted"""
        return bool(self.status == "delisted")


class DelistedSymbol(Base):
    """Symbols that have been delisted from exchanges"""

    __tablename__ = "delisted_symbols"
    __table_args__ = {"schema": "data_ingestion"}

    # Primary key
    symbol = Column(String(10), primary_key=True)

    # Delisting details
    delist_date = Column(Date, nullable=True)
    last_price = Column(Numeric(10, 2), nullable=True)
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def __repr__(self) -> str:
        return f"<DelistedSymbol(symbol='{self.symbol}', delist_date='{self.delist_date}')>"


class SymbolDataStatus(Base):
    """Tracking data ingestion status for each symbol and date"""

    __tablename__ = "symbol_data_status"
    __table_args__ = {"schema": "data_ingestion"}

    # Composite primary key
    symbol = Column(String(10), primary_key=True)
    date = Column(Date, primary_key=True)
    data_source = Column(String(50), primary_key=True)

    # Status tracking
    status = Column(String(20), nullable=False)
    error_message = Column(Text, nullable=True)

    # Timestamps
    last_attempt = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<SymbolDataStatus(symbol='{self.symbol}', "
            f"date='{self.date}', status='{self.status}')>"
        )

    @hybrid_property
    def is_success(self) -> bool:
        """Check if data ingestion was successful"""
        return bool(self.status == "success")

    @hybrid_property
    def is_failed(self) -> bool:
        """Check if data ingestion failed"""
        return bool(self.status == "failed")

    @hybrid_property
    def is_no_data(self) -> bool:
        """Check if no data was available"""
        return bool(self.status == "no_data")
