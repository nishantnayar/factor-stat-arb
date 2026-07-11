"""
Financial Statements SQLAlchemy model
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from ..base import Base


class FinancialStatement(Base):
    """Financial statement data model"""

    __tablename__ = "financial_statements"
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

    # Statement metadata
    period_end = Column(Date, nullable=False, index=True)
    statement_type = Column(
        String(20), nullable=False, index=True
    )  # 'income', 'balance_sheet', 'cash_flow'
    period_type = Column(
        String(10), nullable=False, index=True
    )  # 'annual', 'quarterly', 'ttm'
    fiscal_year = Column(Integer, nullable=True)
    fiscal_quarter = Column(Integer, nullable=True)

    # Financial data (JSONB for flexible schema)
    data = Column(JSONB, nullable=False, default={})

    # Common financial metrics as separate columns for easy querying
    total_revenue = Column(BigInteger, nullable=True)
    net_income = Column(BigInteger, nullable=True)
    gross_profit = Column(BigInteger, nullable=True)
    operating_income = Column(BigInteger, nullable=True)
    ebitda = Column(BigInteger, nullable=True)
    total_assets = Column(BigInteger, nullable=True)
    total_liabilities = Column(BigInteger, nullable=True)
    total_equity = Column(BigInteger, nullable=True)
    cash_and_equivalents = Column(BigInteger, nullable=True)
    total_debt = Column(BigInteger, nullable=True)
    operating_cash_flow = Column(BigInteger, nullable=True)
    free_cash_flow = Column(BigInteger, nullable=True)
    basic_eps = Column(Numeric(10, 4), nullable=True)
    diluted_eps = Column(Numeric(10, 4), nullable=True)
    book_value_per_share = Column(Numeric(10, 4), nullable=True)

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
    symbol_ref = relationship("Symbol", back_populates="financial_statements")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        result = {
            "id": self.id,
            "symbol": self.symbol,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "statement_type": self.statement_type,
            "period_type": self.period_type,
            "fiscal_year": self.fiscal_year,
            "fiscal_quarter": self.fiscal_quarter,
            "data": self.data,
            "data_source": self.data_source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        # Add common metrics if they exist
        if hasattr(self, "total_revenue") and self.total_revenue is not None:
            result["total_revenue"] = self.total_revenue
        if hasattr(self, "net_income") and self.net_income is not None:
            result["net_income"] = self.net_income
        if hasattr(self, "basic_eps") and self.basic_eps is not None:
            result["basic_eps"] = float(self.basic_eps)

        return result

    def get_line_item(self, line_item: str) -> Optional[float]:
        """Get a specific line item from the financial data"""
        return self.data.get(line_item)  # type: ignore

    def populate_common_metrics(self) -> None:
        """Populate common metrics columns from JSONB data"""
        # Income statement metrics
        self.total_revenue = self._safe_get_int("Total Revenue")  # type: ignore
        self.net_income = self._safe_get_int("Net Income")  # type: ignore
        self.gross_profit = self._safe_get_int("Gross Profit")  # type: ignore
        self.operating_income = self._safe_get_int("Operating Income")  # type: ignore
        self.ebitda = self._safe_get_int("EBITDA")  # type: ignore

        # Balance sheet metrics
        self.total_assets = self._safe_get_int("Total Assets")  # type: ignore
        self.total_liabilities = self._safe_get_int("Total Liabilities")  # type: ignore
        self.total_equity = self._safe_get_int("Total Equity")  # type: ignore
        self.cash_and_equivalents = self._safe_get_int("Cash And Cash Equivalents")  # type: ignore
        self.total_debt = self._safe_get_int("Total Debt")  # type: ignore

        # Cash flow metrics
        self.operating_cash_flow = self._safe_get_int("Operating Cash Flow")  # type: ignore
        self.free_cash_flow = self._safe_get_int("Free Cash Flow")  # type: ignore

        # Per-share metrics
        self.basic_eps = self._safe_get_decimal("Basic EPS")  # type: ignore
        self.diluted_eps = self._safe_get_decimal("Diluted EPS")  # type: ignore
        self.book_value_per_share = self._safe_get_decimal("Book Value Per Share")  # type: ignore

    def _safe_get_int(self, key: str) -> Optional[int]:
        """Safely get integer value from JSONB data"""
        value = self.data.get(key)
        if value is None:
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def _safe_get_decimal(self, key: str) -> Optional[Decimal]:
        """Safely get decimal value from JSONB data"""
        value = self.data.get(key)
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (ValueError, TypeError, Exception):
            return None

    def get_formatted_line_item(
        self, line_item: str, format_type: str = "number"
    ) -> str:
        """Get a formatted line item value"""
        value = self.get_line_item(line_item)
        if value is None:
            return "N/A"

        if format_type == "currency":
            return f"${value:,.0f}" if value >= 0 else f"-${abs(value):,.0f}"
        elif format_type == "percentage":
            return f"{value * 100:.2f}%"
        elif format_type == "number":
            if abs(value) >= 1_000_000_000:
                return f"{value:,.0f}"
            elif abs(value) >= 1_000_000:
                return f"{value:,.0f}"
            elif abs(value) >= 1_000:
                return f"{value:,.0f}"
            else:
                return f"{value:,.2f}" if isinstance(value, float) else f"{value:,.0f}"
        else:
            return str(value)

    @property
    def period_display(self) -> str:
        """Get human-readable period description"""
        if self.period_type == "annual":
            return f"FY{self.fiscal_year}" if self.fiscal_year else "Annual"
        elif self.period_type == "quarterly":
            if self.fiscal_year and self.fiscal_quarter:
                return f"Q{self.fiscal_quarter} {self.fiscal_year}"
            else:
                return "Quarterly"
        else:
            return "TTM"

    @property
    def statement_display(self) -> str:
        """Get human-readable statement type"""
        stmt_type = str(self.statement_type) if self.statement_type else "unknown"
        return {
            "income": "Income Statement",
            "balance_sheet": "Balance Sheet",
            "cash_flow": "Cash Flow Statement",
        }.get(stmt_type, stmt_type.title())

    def __repr__(self) -> str:
        return (
            f"<FinancialStatement(symbol={self.symbol}, "
            f"type={self.statement_type}, period={self.period_display})>"
        )
