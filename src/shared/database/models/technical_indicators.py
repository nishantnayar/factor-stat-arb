"""
Technical Indicators Database Models

SQLAlchemy models for technical indicator calculations and storage.
Stores calculated/derived metrics from market data (Yahoo Finance only).
"""

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import TIMESTAMP, BigInteger, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database.base import Base

if TYPE_CHECKING:
    from src.shared.database.models.symbols import Symbol


class TechnicalIndicatorsLatest(Base):
    """
    Latest technical indicator values for fast screening queries
    
    Stores the most recent calculated indicator values for each symbol.
    Updated daily after market close via scheduled Prefect flows.
    Uses only Yahoo Finance data (data_source = 'yahoo') for calculations.
    """

    __tablename__ = "technical_indicators_latest"
    __table_args__ = (
        Index("idx_technical_indicators_latest_date", "calculated_date"),
        Index("idx_technical_indicators_latest_rsi", "rsi"),
        Index("idx_technical_indicators_latest_sma_20", "sma_20"),
        Index("idx_technical_indicators_latest_volatility", "volatility_20"),
        {"schema": "analytics"},
    )

    # Primary Key
    symbol: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("data_ingestion.symbols.symbol", ondelete="CASCADE"),
        primary_key=True,
    )
    calculated_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Moving Averages
    sma_20: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))
    sma_50: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))
    sma_200: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))
    ema_12: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))
    ema_26: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))
    ema_50: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))

    # Momentum Indicators
    rsi: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))  # 0-100
    rsi_14: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))  # Explicit 14-period RSI

    # MACD
    macd_line: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))
    macd_signal: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))
    macd_histogram: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))

    # Bollinger Bands
    bb_upper: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))
    bb_middle: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))
    bb_lower: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))
    bb_position: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))  # 0-1
    bb_width: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))  # Band width as percentage

    # Volatility & Price Changes
    volatility_20: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))  # Annualized volatility %
    price_change_1d: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))  # 1-day price change %
    price_change_5d: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))  # 5-day price change %
    price_change_30d: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))  # 30-day price change %

    # Volume Indicators
    avg_volume_20: Mapped[Optional[int]] = mapped_column(BigInteger)
    current_volume: Mapped[Optional[int]] = mapped_column(BigInteger)

    # Metadata
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    symbol_ref: Mapped["Symbol"] = relationship(
        "Symbol",
        back_populates="technical_indicators_latest",
        foreign_keys=[symbol],
    )

    def __repr__(self) -> str:
        return (
            f"<TechnicalIndicatorsLatest(symbol='{self.symbol}', "
            f"date={self.calculated_date}, rsi={self.rsi}, sma_20={self.sma_20})>"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "symbol": self.symbol,
            "calculated_date": self.calculated_date.isoformat(),
            # Moving Averages
            "sma_20": float(self.sma_20) if self.sma_20 else None,
            "sma_50": float(self.sma_50) if self.sma_50 else None,
            "sma_200": float(self.sma_200) if self.sma_200 else None,
            "ema_12": float(self.ema_12) if self.ema_12 else None,
            "ema_26": float(self.ema_26) if self.ema_26 else None,
            "ema_50": float(self.ema_50) if self.ema_50 else None,
            # Momentum
            "rsi": float(self.rsi) if self.rsi else None,
            "rsi_14": float(self.rsi_14) if self.rsi_14 else None,
            # MACD
            "macd_line": float(self.macd_line) if self.macd_line else None,
            "macd_signal": float(self.macd_signal) if self.macd_signal else None,
            "macd_histogram": float(self.macd_histogram) if self.macd_histogram else None,
            # Bollinger Bands
            "bb_upper": float(self.bb_upper) if self.bb_upper else None,
            "bb_middle": float(self.bb_middle) if self.bb_middle else None,
            "bb_lower": float(self.bb_lower) if self.bb_lower else None,
            "bb_position": float(self.bb_position) if self.bb_position else None,
            "bb_width": float(self.bb_width) if self.bb_width else None,
            # Volatility & Price Changes
            "volatility_20": float(self.volatility_20) if self.volatility_20 else None,
            "price_change_1d": float(self.price_change_1d) if self.price_change_1d else None,
            "price_change_5d": float(self.price_change_5d) if self.price_change_5d else None,
            "price_change_30d": float(self.price_change_30d) if self.price_change_30d else None,
            # Volume
            "avg_volume_20": self.avg_volume_20,
            "current_volume": self.current_volume,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class TechnicalIndicators(Base):
    """
    Historical time-series of technical indicators
    
    Stores daily calculated indicator values for historical analysis and backtesting.
    Uses only Yahoo Finance data (data_source = 'yahoo') for calculations.
    """

    __tablename__ = "technical_indicators"
    __table_args__ = (
        Index("idx_technical_indicators_symbol", "symbol"),
        Index("idx_technical_indicators_date", "date"),
        Index("idx_technical_indicators_symbol_date", "symbol", "date"),
        Index("idx_technical_indicators_rsi", "rsi"),
        Index("idx_technical_indicators_sma_20", "sma_20"),
        {"schema": "analytics"},
    )

    # Primary Key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Foreign Key & Metadata
    symbol: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("data_ingestion.symbols.symbol", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)

    # Moving Averages
    sma_20: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))
    sma_50: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))
    sma_200: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))
    ema_12: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))
    ema_26: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))
    ema_50: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))

    # Momentum Indicators
    rsi: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))  # 0-100
    rsi_14: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))  # Explicit 14-period RSI

    # MACD
    macd_line: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))
    macd_signal: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))
    macd_histogram: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))

    # Bollinger Bands
    bb_upper: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))
    bb_middle: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))
    bb_lower: Mapped[Optional[float]] = mapped_column(Numeric(15, 4))
    bb_position: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))  # 0-1
    bb_width: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))  # Band width as percentage

    # Volatility & Price Changes
    volatility_20: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))  # Annualized volatility %
    price_change_1d: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))  # 1-day price change %
    price_change_5d: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))  # 5-day price change %
    price_change_30d: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))  # 30-day price change %

    # Volume Indicators
    avg_volume_20: Mapped[Optional[int]] = mapped_column(BigInteger)
    current_volume: Mapped[Optional[int]] = mapped_column(BigInteger)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    symbol_ref: Mapped["Symbol"] = relationship(
        "Symbol",
        back_populates="technical_indicators",
        foreign_keys=[symbol],
    )

    def __repr__(self) -> str:
        return (
            f"<TechnicalIndicators(symbol='{self.symbol}', "
            f"date={self.date}, rsi={self.rsi}, sma_20={self.sma_20})>"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "date": self.date.isoformat(),
            # Moving Averages
            "sma_20": float(self.sma_20) if self.sma_20 else None,
            "sma_50": float(self.sma_50) if self.sma_50 else None,
            "sma_200": float(self.sma_200) if self.sma_200 else None,
            "ema_12": float(self.ema_12) if self.ema_12 else None,
            "ema_26": float(self.ema_26) if self.ema_26 else None,
            "ema_50": float(self.ema_50) if self.ema_50 else None,
            # Momentum
            "rsi": float(self.rsi) if self.rsi else None,
            "rsi_14": float(self.rsi_14) if self.rsi_14 else None,
            # MACD
            "macd_line": float(self.macd_line) if self.macd_line else None,
            "macd_signal": float(self.macd_signal) if self.macd_signal else None,
            "macd_histogram": float(self.macd_histogram) if self.macd_histogram else None,
            # Bollinger Bands
            "bb_upper": float(self.bb_upper) if self.bb_upper else None,
            "bb_middle": float(self.bb_middle) if self.bb_middle else None,
            "bb_lower": float(self.bb_lower) if self.bb_lower else None,
            "bb_position": float(self.bb_position) if self.bb_position else None,
            "bb_width": float(self.bb_width) if self.bb_width else None,
            # Volatility & Price Changes
            "volatility_20": float(self.volatility_20) if self.volatility_20 else None,
            "price_change_1d": float(self.price_change_1d) if self.price_change_1d else None,
            "price_change_5d": float(self.price_change_5d) if self.price_change_5d else None,
            "price_change_30d": float(self.price_change_30d) if self.price_change_30d else None,
            # Volume
            "avg_volume_20": self.avg_volume_20,
            "current_volume": self.current_volume,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

