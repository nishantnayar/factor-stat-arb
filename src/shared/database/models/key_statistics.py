"""
Key Statistics Database Model

SQLAlchemy model for key financial statistics and metrics.
Stores comprehensive fundamental data from Yahoo Finance.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import TIMESTAMP, BigInteger, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database.base import Base

if TYPE_CHECKING:
    from src.shared.database.models.symbols import Symbol


class KeyStatistics(Base):
    """
    Key financial statistics and metrics for stocks

    Stores comprehensive fundamental data including:
    - Valuation metrics (P/E, P/B, Market Cap, etc.)
    - Profitability metrics (ROE, ROA, margins)
    - Financial health (debt, cash, ratios)
    - Growth metrics (revenue growth, earnings growth)
    - Trading metrics (beta, moving averages)
    - Dividend metrics (yield, payout ratio)
    - Share information (outstanding, float, short interest)

    Data is typically updated daily or as needed.
    All percentage values stored as decimals (e.g., 0.15 = 15%).
    """

    __tablename__ = "key_statistics"
    __table_args__ = (
        Index("idx_key_statistics_symbol", "symbol"),
        Index("idx_key_statistics_date", "date"),
        Index("idx_key_statistics_symbol_date", "symbol", "date"),
        Index("idx_key_statistics_data_source", "data_source"),
        Index(
            "idx_key_statistics_valuation",
            "trailing_pe",
            "price_to_book",
            "market_cap",
        ),
        Index(
            "idx_key_statistics_profitability",
            "return_on_equity",
            "profit_margin",
        ),
        {"schema": "data_ingestion"},
    )

    # Primary Key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Foreign Key & Metadata
    symbol: Mapped[str] = mapped_column(
        String(10),
        ForeignKey("data_ingestion.symbols.symbol", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    data_source: Mapped[str] = mapped_column(
        String(50), default="yahoo", nullable=False
    )

    # Valuation Metrics
    market_cap: Mapped[Optional[int]] = mapped_column(BigInteger)
    enterprise_value: Mapped[Optional[int]] = mapped_column(BigInteger)
    trailing_pe: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    forward_pe: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    peg_ratio: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    price_to_book: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    price_to_sales: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    enterprise_to_revenue: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    enterprise_to_ebitda: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))

    # Profitability Metrics (stored as decimals: 0.15 = 15%)
    profit_margin: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    operating_margin: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    return_on_assets: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    return_on_equity: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    gross_margin: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    ebitda_margin: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))

    # Financial Health
    revenue: Mapped[Optional[int]] = mapped_column(BigInteger)
    revenue_per_share: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    earnings_per_share: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    total_cash: Mapped[Optional[int]] = mapped_column(BigInteger)
    total_debt: Mapped[Optional[int]] = mapped_column(BigInteger)
    debt_to_equity: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    current_ratio: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    quick_ratio: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    free_cash_flow: Mapped[Optional[int]] = mapped_column(BigInteger)
    operating_cash_flow: Mapped[Optional[int]] = mapped_column(BigInteger)

    # Growth Metrics (stored as decimals: 0.10 = 10% growth)
    revenue_growth: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    earnings_growth: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))

    # Trading Metrics
    beta: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    fifty_two_week_high: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    fifty_two_week_low: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    fifty_day_average: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    two_hundred_day_average: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    average_volume: Mapped[Optional[int]] = mapped_column(BigInteger)

    # Dividend Metrics (stored as decimals: 0.02 = 2% yield)
    dividend_yield: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    dividend_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    payout_ratio: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))

    # Share Information
    shares_outstanding: Mapped[Optional[int]] = mapped_column(BigInteger)
    float_shares: Mapped[Optional[int]] = mapped_column(BigInteger)
    shares_short: Mapped[Optional[int]] = mapped_column(BigInteger)
    short_ratio: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    held_percent_insiders: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    held_percent_institutions: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))

    # Timestamps
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
        back_populates="key_statistics",
        foreign_keys=[symbol],
    )

    def __repr__(self) -> str:
        return (
            f"<KeyStatistics(symbol='{self.symbol}', date={self.date}, "
            f"pe={self.trailing_pe}, roe={self.return_on_equity})>"
        )

    @property
    def debt_to_equity_display(self) -> str:
        """Display debt to equity ratio with formatting"""
        if self.debt_to_equity is None:
            return "N/A"
        return f"{float(self.debt_to_equity):.2f}"

    @property
    def roe_display(self) -> str:
        """Display ROE as percentage"""
        if self.return_on_equity is None:
            return "N/A"
        return f"{float(self.return_on_equity) * 100:.2f}%"

    @property
    def profit_margin_display(self) -> str:
        """Display profit margin as percentage"""
        if self.profit_margin is None:
            return "N/A"
        return f"{float(self.profit_margin) * 100:.2f}%"

    @property
    def dividend_yield_display(self) -> str:
        """Display dividend yield as percentage"""
        if self.dividend_yield is None:
            return "N/A"
        return f"{float(self.dividend_yield) * 100:.2f}%"

    @property
    def market_cap_display(self) -> str:
        """Display market cap with formatting"""
        if self.market_cap is None:
            return "N/A"

        mc = float(self.market_cap)
        if mc >= 1_000_000_000_000:  # Trillion
            return f"${mc / 1_000_000_000_000:.2f}T"
        elif mc >= 1_000_000_000:  # Billion
            return f"${mc / 1_000_000_000:.2f}B"
        elif mc >= 1_000_000:  # Million
            return f"${mc / 1_000_000:.2f}M"
        else:
            return f"${mc:,.0f}"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "symbol": self.symbol,
            "date": self.date.isoformat(),
            "data_source": self.data_source,
            # Valuation
            "market_cap": self.market_cap,
            "enterprise_value": self.enterprise_value,
            "trailing_pe": float(self.trailing_pe) if self.trailing_pe else None,
            "forward_pe": float(self.forward_pe) if self.forward_pe else None,
            "peg_ratio": float(self.peg_ratio) if self.peg_ratio else None,
            "price_to_book": float(self.price_to_book) if self.price_to_book else None,
            "price_to_sales": (
                float(self.price_to_sales) if self.price_to_sales else None
            ),
            # Profitability
            "profit_margin": float(self.profit_margin) if self.profit_margin else None,
            "operating_margin": (
                float(self.operating_margin) if self.operating_margin else None
            ),
            "return_on_assets": (
                float(self.return_on_assets) if self.return_on_assets else None
            ),
            "return_on_equity": (
                float(self.return_on_equity) if self.return_on_equity else None
            ),
            "gross_margin": float(self.gross_margin) if self.gross_margin else None,
            # Financial Health
            "revenue": self.revenue,
            "earnings_per_share": (
                float(self.earnings_per_share) if self.earnings_per_share else None
            ),
            "total_cash": self.total_cash,
            "total_debt": self.total_debt,
            "debt_to_equity": (
                float(self.debt_to_equity) if self.debt_to_equity else None
            ),
            "current_ratio": float(self.current_ratio) if self.current_ratio else None,
            "free_cash_flow": self.free_cash_flow,
            # Growth
            "revenue_growth": (
                float(self.revenue_growth) if self.revenue_growth else None
            ),
            "earnings_growth": (
                float(self.earnings_growth) if self.earnings_growth else None
            ),
            # Trading
            "beta": float(self.beta) if self.beta else None,
            "fifty_two_week_high": (
                float(self.fifty_two_week_high) if self.fifty_two_week_high else None
            ),
            "fifty_two_week_low": (
                float(self.fifty_two_week_low) if self.fifty_two_week_low else None
            ),
            # Dividends
            "dividend_yield": (
                float(self.dividend_yield) if self.dividend_yield else None
            ),
            "dividend_rate": float(self.dividend_rate) if self.dividend_rate else None,
            # Shares
            "shares_outstanding": self.shares_outstanding,
            "held_percent_insiders": (
                float(self.held_percent_insiders)
                if self.held_percent_insiders
                else None
            ),
            "held_percent_institutions": (
                float(self.held_percent_institutions)
                if self.held_percent_institutions
                else None
            ),
        }
