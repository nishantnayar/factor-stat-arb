# Yahoo Finance Integration

> **📋 Implementation Status**: ✅ Complete (10/10 data types implemented - 100%)

This document provides comprehensive documentation for the Yahoo Finance integration, including features, architecture, database schema, usage examples, and best practices.

---

## Overview

Yahoo Finance provides free, unlimited market data including OHLCV, fundamentals, dividends, and company information. Perfect for backtesting, fundamental analysis, and development.

### Implementation Status

**✅ Complete (10/10 data types implemented - 100%)**

All Yahoo Finance data types have been fully implemented:

| # | Data Type | Client Method | Loader Method | Database Model | SQL Script | CLI Flag | Status |
|---|-----------|---------------|---------------|----------------|------------|----------|--------|
| 1 | **Market Data (OHLCV)** | `get_historical_data()` | `load_market_data()` | `MarketData` | ✅ | `--market-data` | ✅ Complete |
| 2 | **Company Information** | `get_company_info()` | `load_company_info()` | `CompanyInfo` | ✅ | `--company-info` | ✅ Complete |
| 3 | **Key Statistics** | `get_key_statistics()` | `load_key_statistics()` | `KeyStatistics` | ✅ | `--key-statistics` | ✅ Complete |
| 4 | **Dividends** | `get_dividends()` | `load_dividends()` | `Dividend` | ✅ | `--dividends` | ✅ Complete |
| 5 | **Stock Splits** | `get_splits()` | `load_splits()` | `StockSplit` | ✅ | `--splits` | ✅ Complete |
| 6 | **Institutional Holders** | `get_institutional_holders()` | `load_institutional_holders()` | `InstitutionalHolder` | ✅ | `--institutional-holders` | ✅ Complete |
| 7 | **Financial Statements** | `get_financial_statements()` | `load_financial_statements()` | `FinancialStatement` | ✅ | `--financial-statements` | ✅ Complete |
| 8 | **Company Officers** | `get_company_officers()` | `load_company_officers()` | `CompanyOfficer` | ✅ | `--company-officers` | ✅ Complete |
| 9 | **Analyst Recommendations** | `get_analyst_recommendations()` | `load_analyst_recommendations()` | `AnalystRecommendation` | ✅ | `--analyst-recommendations` | ✅ Complete |
| 10 | **ESG Scores** | `get_esg_scores()` | `load_esg_scores()` | `ESGScore` | ✅ | `--esg-scores` | ✅ Complete |

**What's Working:**
- ✅ All core market data and fundamentals (unadjusted and adjusted OHLCV)
- ✅ All financial statements and metrics
- ✅ Corporate actions (dividends, splits)
- ✅ Ownership data (institutional holders, officers)
- ✅ Analyst recommendations
- ✅ ESG scores
- ✅ Complete CLI integration; backpopulate script for adjusted prices
- ✅ Comprehensive test coverage

**Note:** HTTP 404 errors when loading ESG scores are expected and normal - not all symbols have ESG data available. These are handled silently by the system.

---

## Features

### Market Data

- ✅ Historical OHLCV (daily, hourly, minute)
- ✅ **Dual price series**: unadjusted (raw) and adjusted (splits/dividends)
  - Unadjusted: `data_source='yahoo'`
  - Adjusted: `data_source='yahoo_adjusted'`
- ✅ Volume data
- ✅ Intraday data (up to 60 days history)
- ⚠️ 15-minute delayed real-time data

### Fundamental Data

- ✅ Company profile (name, sector, industry, description)
- ✅ Key statistics (50+ metrics: market cap, PE ratios, profitability, financial health, growth, trading, ownership)
- ✅ Financial statements (income, balance sheet, cash flow)
- ✅ Earnings history and estimates
- ✅ Analyst recommendations
- ✅ Major shareholders

### Corporate Actions

- ✅ Dividends (amount, ex-date, payment date)
- ✅ Stock splits (ratio, date)

### Additional Data

- ✅ News and press releases
- ✅ Options chains (if needed)
- ✅ Institutional holdings

---

## Architecture

### Components

```python
# Yahoo Client (src/services/yahoo/client.py)
class YahooClient:
    """Yahoo Finance API client using yfinance library"""
    
    async def get_historical_data(symbol, start_date, end_date, interval, auto_adjust=False)
    async def get_company_info(symbol)
    async def get_financials(symbol)
    async def get_dividends(symbol, start_date, end_date)
    async def get_splits(symbol, start_date, end_date)
    async def get_key_statistics(symbol)
    async def health_check()

# Yahoo Loader (src/services/yahoo/loader.py)
class YahooDataLoader:
    """Load data from Yahoo Finance into database"""
    
    async def load_market_data(symbol, start_date, end_date, interval, auto_adjust=False)
    async def load_company_info(symbol)
    async def load_financials(symbol)
    async def load_dividends(symbol, start_date, end_date)
    async def load_splits(symbol, start_date, end_date)
    async def load_analyst_recommendations(symbol)
    async def load_esg_scores(symbol)
    async def load_all_data(symbol, start_date, end_date)
```

### Pydantic Models

```python
# src/services/yahoo/models.py

class YahooBar(BaseModel):
    """OHLCV bar from Yahoo Finance"""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    adj_close: Optional[float]
    volume: int

class CompanyInfo(BaseModel):
    """Company profile and details"""
    symbol: str
    name: str
    sector: Optional[str]
    industry: Optional[str]
    description: Optional[str]
    website: Optional[str]
    market_cap: Optional[int]
    employees: Optional[int]
    headquarters: Optional[str]

class KeyStatistics(BaseModel):
    """Key financial metrics"""
    symbol: str
    date: date
    market_cap: Optional[int]
    pe_ratio: Optional[float]
    forward_pe: Optional[float]
    peg_ratio: Optional[float]
    price_to_book: Optional[float]
    price_to_sales: Optional[float]
    enterprise_value: Optional[int]
    profit_margin: Optional[float]
    operating_margin: Optional[float]
    return_on_assets: Optional[float]
    return_on_equity: Optional[float]
    revenue: Optional[int]
    revenue_per_share: Optional[float]
    earnings_per_share: Optional[float]
    dividend_yield: Optional[float]
    beta: Optional[float]
    fifty_two_week_high: Optional[float]
    fifty_two_week_low: Optional[float]

class Dividend(BaseModel):
    """Dividend payment"""
    symbol: str
    ex_date: date
    payment_date: Optional[date]
    amount: float
    data_source: str = "yahoo"

class StockSplit(BaseModel):
    """Stock split event"""
    symbol: str
    split_date: date
    ratio: str  # e.g., "2:1", "3:2"
    numerator: int
    denominator: int
    data_source: str = "yahoo"

class FinancialStatement(BaseModel):
    """Financial statement data"""
    symbol: str
    period_end: date
    statement_type: str  # 'income', 'balance_sheet', 'cash_flow'
    period_type: str  # 'annual', 'quarterly'
    data: dict  # Flexible JSON storage for all line items
```

---

## Database Schema

### Market Data Table (data_ingestion.market_data)

Yahoo stores two price series in the same table, distinguished by `data_source`:

- **Unadjusted (raw)**: `data_source='yahoo'` — prices as reported by Yahoo
- **Adjusted (splits/dividends)**: `data_source='yahoo_adjusted'` — OHLC adjusted for corporate actions

Unique constraint is `(symbol, timestamp, data_source)` so both series coexist. Run migration `scripts/20_market_data_allow_yahoo_adjusted.sql` if you see duplicate-key errors when loading adjusted data.

```sql
-- Unadjusted prices
SELECT * FROM data_ingestion.market_data
WHERE data_source = 'yahoo' AND symbol = 'AAPL';

-- Adjusted prices (for backtesting / total return)
SELECT * FROM data_ingestion.market_data
WHERE data_source = 'yahoo_adjusted' AND symbol = 'AAPL';
```

### New Tables Required

See [API Reference: Yahoo Finance Integration](../api/data-ingestion-yahoo.md) for complete database schema definitions, including:

- `company_info` - Company profile and basic information
- `company_officers` - Company officers and executives
- `key_statistics` - Time-series of key financial metrics
- `institutional_holders` - Institutional ownership history
- `analyst_recommendations` - Analyst recommendation counts over time
- `dividends` - Dividend payment history
- `stock_splits` - Stock split history
- `financial_statements` - Financial statements stored as JSONB
- `earnings_calendar` - Upcoming earnings dates and estimates
- `esg_scores` - ESG scores and ratings

---

## Usage Examples

### Load Market Data Only

```python
from src.services.yahoo.loader import YahooDataLoader

loader = YahooDataLoader(batch_size=100)

# Load unadjusted OHLCV (data_source='yahoo')
await loader.load_market_data(
    symbol="AAPL",
    start_date=date(2023, 1, 1),
    end_date=date(2024, 1, 1),
    interval="1d",
    auto_adjust=False,
)

# Load adjusted OHLCV (data_source='yahoo_adjusted')
await loader.load_market_data(
    symbol="AAPL",
    start_date=date(2023, 1, 1),
    end_date=date(2024, 1, 1),
    interval="1d",
    auto_adjust=True,
)
```

### Load Company Fundamentals

```python
# Load company profile
await loader.load_company_info(symbol="AAPL")

# Load key statistics
await loader.load_key_statistics(symbol="AAPL")

# Load key statistics with specific date
await loader.load_key_statistics(symbol="AAPL", stats_date=date(2024, 1, 15))

# Load financial statements
await loader.load_financials(
    symbol="AAPL",
    statement_type="income",  # 'income', 'balance_sheet', 'cash_flow'
    period_type="quarterly"   # 'annual', 'quarterly'
)
```

### Load Corporate Actions

```python
# Load dividends
count = await loader.load_dividends(
    symbol="AAPL",
    start_date=date(2023, 1, 1),
    end_date=date(2024, 1, 1)
)
print(f"Loaded {count} dividends")

# Load stock splits
count = await loader.load_splits(
    symbol="AAPL",
    start_date=date(2020, 1, 1),
    end_date=date(2024, 1, 1)
)
print(f"Loaded {count} stock splits")

# Load analyst recommendations
count = await loader.load_analyst_recommendations(symbol="AAPL")
print(f"Loaded {count} analyst recommendation records")

# Load ESG scores
success = await loader.load_esg_scores(symbol="AAPL")
if success:
    print("ESG scores loaded successfully")
else:
    print("No ESG scores available")
```

### Load Everything

```python
# Load all available data
await loader.load_all_data(
    symbol="AAPL",
    start_date=date(2023, 1, 1),
    end_date=date(2024, 1, 1),
    include_fundamentals=True,
    include_dividends=True,
    include_splits=True,
    include_analyst_recommendations=True,
    include_esg_scores=True
)
```

---

## CLI Script

```bash
# Load market data only (default)
python scripts/load_yahoo_data.py --symbol AAPL --days 30

# Load company info only (no market data)
python scripts/load_yahoo_data.py --symbol AAPL --company-info

# Load key statistics only
python scripts/load_yahoo_data.py --symbol AAPL --key-statistics

# Load market data + company info + key statistics
python scripts/load_yahoo_data.py --symbol AAPL --days 30 --market-data --company-info --key-statistics

# Load for all active symbols (market data only)
python scripts/load_yahoo_data.py --all-symbols --days 30

# Load key statistics for all symbols
python scripts/load_yahoo_data.py --all-symbols --key-statistics --max-symbols 10

# Load company info for all symbols
python scripts/load_yahoo_data.py --all-symbols --company-info

# Load multiple data types
python scripts/load_yahoo_data.py --symbol AAPL --days 30 \
    --market-data \
    --company-info \
    --key-statistics \
    --institutional-holders

# Backpopulate adjusted prices only (hourly by default; matches scheduled flow)
python scripts/backpopulate_yahoo_adjusted.py --all-symbols --days 365
python scripts/backpopulate_yahoo_adjusted.py --symbol AAPL --days 30 --interval 1h
# Daily adjusted
python scripts/backpopulate_yahoo_adjusted.py --all-symbols --days 365 --interval 1d

# Load analyst recommendations only
python scripts/load_yahoo_data.py --symbol AAPL --analyst-recommendations

# Load analyst recommendations for all symbols
python scripts/load_yahoo_data.py --all-symbols --analyst-recommendations

# Load ESG scores only
python scripts/load_yahoo_data.py --symbol AAPL --esg-scores

# Load ESG scores for all symbols
python scripts/load_yahoo_data.py --all-symbols --esg-scores
```

---

## Rate Limits & Best Practices

**Rate Limits:**
- No official rate limit
- Recommended: 2000 requests/hour (safe limit)
- Implement polite delays (0.5-1 second between requests)
- Use batch processing for multiple symbols

**Best Practices:**
1. **Caching**: Yahoo data changes less frequently than Polygon
2. **Update Frequency**:
   - Market data: Daily (EOD)
   - Fundamentals: Weekly or after earnings
   - Dividends/Splits: Monthly check
3. **Error Handling**: Yahoo API can be flaky, implement retries
4. **Data Validation**: Cross-check with Polygon when available

---

## Limitations

- ❌ No tick-level data
- ❌ 15-minute delayed real-time data
- ❌ Intraday history limited to 60 days
- ❌ API can be unreliable (no SLA)
- ❌ Data quality varies by symbol
- ⚠️ Unofficial API (could change)

---

## Best Use Cases

- ✅ Backtesting and research
- ✅ Fundamental analysis
- ✅ Development and testing
- ✅ Long-term historical data (decades)
- ✅ Dividend/split data validation
- ✅ Company research and screening
- ❌ Production real-time trading
- ❌ High-frequency strategies

---

## Related Documentation

- [Data Sources Overview](data-sources-overview.md): Multi-source architecture overview
- [Data Source Comparison](data-sources-comparison.md): Feature comparison with other sources
- [Implementation Plan](data-sources-implementation.md): Yahoo Finance implementation phases
- [API Reference: Yahoo Finance Integration](../api/data-ingestion-yahoo.md): Detailed API documentation

---

**Last Updated**: 4/3/2026  
**Status**: ✅ Complete (10/10 data types; dual market data series: yahoo + yahoo_adjusted)

