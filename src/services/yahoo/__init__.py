"""
Yahoo Finance Service

Service for fetching market data and fundamentals from Yahoo Finance.
"""

from .client import YahooClient
from .exceptions import (
    YahooAPIError,
    YahooAuthenticationError,
    YahooConnectionError,
    YahooDataError,
    YahooDataQualityError,
    YahooRateLimitError,
    YahooSymbolNotFoundError,
)
from .loader import YahooDataLoader
from .models import (
    AnalystRecommendation,
    CompanyInfo,
    CompanyOfficer,
    Dividend,
    EarningsCalendar,
    ESGScore,
    FinancialStatement,
    InstitutionalHolder,
    KeyStatistics,
    StockSplit,
    YahooBar,
    YahooHealthCheck,
)

__all__ = [
    # Client & Loader
    "YahooClient",
    "YahooDataLoader",
    # Exceptions
    "YahooAPIError",
    "YahooAuthenticationError",
    "YahooConnectionError",
    "YahooDataError",
    "YahooDataQualityError",
    "YahooRateLimitError",
    "YahooSymbolNotFoundError",
    # Models
    "YahooBar",
    "CompanyInfo",
    "CompanyOfficer",
    "KeyStatistics",
    "Dividend",
    "StockSplit",
    "InstitutionalHolder",
    "AnalystRecommendation",
    "EarningsCalendar",
    "ESGScore",
    "FinancialStatement",
    "YahooHealthCheck",
]
