"""
Pydantic models for Yahoo Finance data

Data models for all Yahoo Finance API responses.
"""

from datetime import date, datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class YahooBar(BaseModel):
    """OHLCV bar from Yahoo Finance"""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    dividends: Optional[float] = 0.0
    stock_splits: Optional[float] = 0.0


class CompanyInfo(BaseModel):
    """Company profile and basic information"""

    symbol: str
    name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = Field(None, alias="longBusinessSummary")
    website: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = Field(None, alias="address1")
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    country: Optional[str] = None
    employees: Optional[int] = Field(None, alias="fullTimeEmployees")
    market_cap: Optional[int] = Field(None, alias="marketCap")
    currency: Optional[str] = None
    exchange: Optional[str] = None
    quote_type: Optional[str] = Field(None, alias="quoteType")
    additional_data: Optional[Dict[str, Any]] = None  # Store remaining fields

    class Config:
        populate_by_name = True


class CompanyOfficer(BaseModel):
    """Company officer/executive information"""

    symbol: str
    name: str
    title: Optional[str] = None
    age: Optional[int] = None
    year_born: Optional[int] = Field(None, alias="yearBorn")
    fiscal_year: Optional[int] = Field(None, alias="fiscalYear")
    total_pay: Optional[int] = Field(None, alias="totalPay")
    exercised_value: Optional[int] = Field(None, alias="exercisedValue")
    unexercised_value: Optional[int] = Field(None, alias="unexercisedValue")

    class Config:
        populate_by_name = True


class KeyStatistics(BaseModel):
    """Key financial statistics and metrics"""

    symbol: str
    date: date

    # Valuation Metrics
    market_cap: Optional[int] = Field(None, alias="marketCap")
    enterprise_value: Optional[int] = Field(None, alias="enterpriseValue")
    trailing_pe: Optional[float] = Field(None, alias="trailingPE")
    forward_pe: Optional[float] = Field(None, alias="forwardPE")
    peg_ratio: Optional[float] = Field(None, alias="pegRatio")
    price_to_book: Optional[float] = Field(None, alias="priceToBook")
    price_to_sales: Optional[float] = Field(None, alias="priceToSalesTrailing12Months")
    enterprise_to_revenue: Optional[float] = Field(None, alias="enterpriseToRevenue")
    enterprise_to_ebitda: Optional[float] = Field(None, alias="enterpriseToEbitda")

    # Profitability Metrics
    profit_margin: Optional[float] = Field(None, alias="profitMargins")
    operating_margin: Optional[float] = Field(None, alias="operatingMargins")
    return_on_assets: Optional[float] = Field(None, alias="returnOnAssets")
    return_on_equity: Optional[float] = Field(None, alias="returnOnEquity")
    gross_margin: Optional[float] = Field(None, alias="grossMargins")
    ebitda_margin: Optional[float] = Field(None, alias="ebitdaMargins")

    # Financial Health
    revenue: Optional[int] = Field(None, alias="totalRevenue")
    revenue_per_share: Optional[float] = Field(None, alias="revenuePerShare")
    earnings_per_share: Optional[float] = Field(None, alias="trailingEps")
    total_cash: Optional[int] = Field(None, alias="totalCash")
    total_debt: Optional[int] = Field(None, alias="totalDebt")
    debt_to_equity: Optional[float] = Field(None, alias="debtToEquity")
    current_ratio: Optional[float] = Field(None, alias="currentRatio")
    quick_ratio: Optional[float] = Field(None, alias="quickRatio")
    free_cash_flow: Optional[int] = Field(None, alias="freeCashflow")
    operating_cash_flow: Optional[int] = Field(None, alias="operatingCashflow")

    # Growth Metrics
    revenue_growth: Optional[float] = Field(None, alias="revenueGrowth")
    earnings_growth: Optional[float] = Field(None, alias="earningsGrowth")

    # Trading Metrics
    beta: Optional[float] = None
    fifty_two_week_high: Optional[float] = Field(None, alias="fiftyTwoWeekHigh")
    fifty_two_week_low: Optional[float] = Field(None, alias="fiftyTwoWeekLow")
    fifty_day_average: Optional[float] = Field(None, alias="fiftyDayAverage")
    two_hundred_day_average: Optional[float] = Field(None, alias="twoHundredDayAverage")
    average_volume: Optional[int] = Field(None, alias="averageVolume")

    # Dividend Metrics
    dividend_yield: Optional[float] = Field(None, alias="dividendYield")
    dividend_rate: Optional[float] = Field(None, alias="dividendRate")
    payout_ratio: Optional[float] = Field(None, alias="payoutRatio")

    # Share Information
    shares_outstanding: Optional[int] = Field(None, alias="sharesOutstanding")
    float_shares: Optional[int] = Field(None, alias="floatShares")
    shares_short: Optional[int] = Field(None, alias="sharesShort")
    short_ratio: Optional[float] = Field(None, alias="shortRatio")
    held_percent_insiders: Optional[float] = Field(None, alias="heldPercentInsiders")
    held_percent_institutions: Optional[float] = Field(
        None, alias="heldPercentInstitutions"
    )

    class Config:
        populate_by_name = True


class Dividend(BaseModel):
    """Dividend payment information"""

    symbol: str
    ex_date: date
    amount: float
    payment_date: Optional[date] = None
    record_date: Optional[date] = None
    dividend_type: str = "regular"  # 'regular', 'special', 'stock'
    currency: str = "USD"


class StockSplit(BaseModel):
    """Stock split information"""

    symbol: str
    split_date: date
    split_ratio: float  # Numeric ratio (e.g., 2.0 for 2:1, 0.5 for 1:2)
    ratio_str: Optional[str] = None  # Human readable (e.g., "2:1", "7:1")


class InstitutionalHolder(BaseModel):
    """Institutional holder information"""

    symbol: str
    date_reported: date
    holder_name: str
    shares: Optional[int] = None
    value: Optional[int] = None
    percent_held: Optional[float] = Field(None, alias="pctHeld")
    percent_change: Optional[float] = Field(None, alias="pctChange")

    class Config:
        populate_by_name = True


class AnalystRecommendation(BaseModel):
    """Analyst recommendation data"""

    symbol: str
    date: date
    period: str  # '0m', '-1m', '-2m', '-3m'
    strong_buy: int = Field(0, alias="strongBuy")
    buy: int = 0
    hold: int = 0
    sell: int = 0
    strong_sell: int = Field(0, alias="strongSell")

    class Config:
        populate_by_name = True

    @property
    def total_analysts(self) -> int:
        """Calculate total number of analysts"""
        return self.strong_buy + self.buy + self.hold + self.sell + self.strong_sell


class EarningsCalendar(BaseModel):
    """Earnings calendar and estimates"""

    symbol: str
    earnings_date: date
    earnings_call_date: Optional[datetime] = None
    eps_estimate_low: Optional[float] = None
    eps_estimate_high: Optional[float] = None
    eps_estimate_avg: Optional[float] = None
    revenue_estimate_low: Optional[int] = None
    revenue_estimate_high: Optional[int] = None
    revenue_estimate_avg: Optional[int] = None
    is_estimate: bool = True


class ESGScore(BaseModel):
    """ESG (Environmental, Social, Governance) scores"""

    symbol: str
    date: date
    total_esg: Optional[float] = Field(None, alias="totalEsg")
    environment_score: Optional[float] = Field(None, alias="environmentScore")
    social_score: Optional[float] = Field(None, alias="socialScore")
    governance_score: Optional[float] = Field(None, alias="governanceScore")
    controversy_level: Optional[int] = Field(None, alias="highestControversy")
    esg_performance: Optional[str] = Field(None, alias="esgPerformance")
    peer_group: Optional[str] = Field(None, alias="peerGroup")
    peer_count: Optional[int] = Field(None, alias="peerCount")
    percentile: Optional[float] = None

    class Config:
        populate_by_name = True


class FinancialStatement(BaseModel):
    """Financial statement data (income, balance sheet, cash flow)"""

    symbol: str
    period_end: date
    statement_type: str  # 'income', 'balance_sheet', 'cash_flow'
    period_type: str  # 'annual', 'quarterly', 'ttm'
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[int] = None
    data: Dict[str, Any]  # Full statement data as dict


class YahooHealthCheck(BaseModel):
    """Yahoo Finance API health check result"""

    healthy: bool
    symbol_tested: str
    data_available: bool
    error_message: Optional[str] = None
    timestamp: datetime
