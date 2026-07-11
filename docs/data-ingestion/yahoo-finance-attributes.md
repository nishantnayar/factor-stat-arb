# Yahoo Finance Data Attributes Reference

Complete guide to all available data attributes from Yahoo Finance.

## Overview

The Yahoo Finance integration provides **10 major data categories** with 100+ individual attributes covering:
- Market prices and volume
- Company fundamentals
- Financial statements
- Ownership and analyst coverage
- ESG metrics

## Quick Reference

### Available Data Categories

Your Yahoo Finance integration provides **10 comprehensive data categories** with **100+ individual attributes**:

1. **📈 Market Data (OHLCV)** - Price: Open, High, Low, Close, Volume. Intervals: 1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo
2. **🏢 Company Information** - Name, Sector, Industry, Description, Website, Contact, Address, Employees, Market Cap, Exchange
3. **💰 Key Statistics (50+ Metrics)** - Valuation, Profitability, Financial Health, Growth, Trading, Dividends, Shares
4. **💵 Dividends** - Ex-Date, Payment Date, Record Date, Amount, Type (regular/special/stock)
5. **🔀 Stock Splits** - Split Date, Split Ratio (numeric & readable)
6. **🏦 Institutional Holders** - Institution Name, Shares Held, Dollar Value, Percentage Ownership
7. **📊 Analyst Recommendations** - Strong Buy, Buy, Hold, Sell, Strong Sell, Total Analyst Count
8. **📑 Financial Statements** - Income Statement, Balance Sheet, Cash Flow (Annual or Quarterly)
9. **🌱 ESG Scores** - Total ESG Score, Environment, Social, Governance scores, Controversy Level, Peer Group Comparison
10. **👔 Company Officers** - Executive Name, Title, Age, Total Compensation, Stock Options

### Quick Start Examples

```bash
# Load key statistics for single symbol
python scripts/load_yahoo_data.py --symbol AAPL --key-statistics

# Load key statistics for all symbols
python scripts/load_yahoo_data.py --all-symbols --key-statistics --max-symbols 10

# Load market data + key statistics together
python scripts/load_yahoo_data.py --symbol AAPL --days 30 --market-data --key-statistics

# Load all data types
python scripts/load_yahoo_data.py --symbol AAPL --days 365 \
    --market-data \
    --company-info \
    --key-statistics \
    --institutional-holders \
    --financial-statements \
    --company-officers \
    --dividends \
    --splits \
    --analyst-recommendations \
    --esg-scores
```

### Programmatic Usage

```python
from src.services.yahoo.loader import YahooDataLoader
from datetime import date, timedelta

loader = YahooDataLoader()

# Load key statistics
success = await loader.load_key_statistics("AAPL")

# Load market data
count = await loader.load_market_data(
    symbol="AAPL",
    start_date=date.today() - timedelta(days=30),
    end_date=date.today(),
    interval="1d"
)

# Load all data types
results = await loader.load_all_data(
    symbol="AAPL",
    start_date=date.today() - timedelta(days=30),
    end_date=date.today(),
    include_fundamentals=True,
    include_dividends=True,
    include_splits=True,
    include_analyst_recommendations=True,
    include_esg_scores=True
)
```

### Use Cases

- **Stock Screening**: Load Key Statistics (PE, PB, ROE, margins, growth)
- **Dividend Investing**: Load Dividends, Dividend Metrics (yield, payout ratio)
- **Financial Analysis**: Load Financial Statements, Key Statistics, Cash Flow
- **Technical Analysis**: Load Market Data, Moving Averages, 52W High/Low, Beta
- **Fundamental Analysis**: Load Company Info, Financial Statements, Growth Metrics
- **Risk Assessment**: Load Debt/Equity, Current Ratio, Interest Coverage, Beta
- **Sentiment Analysis**: Load Analyst Recommendations, Institutional Holders, Short Interest

### Key Features

✅ **100+ Data Attributes** across 10 categories  
✅ **Real-time Data** for US equities  
✅ **Multiple Timeframes** (1-minute to monthly)  
✅ **Automatic Database Storage** with upsert logic  
✅ **Rate Limiting** built-in (0.5s delay)  
✅ **Error Handling** with specific exceptions  
✅ **Timezone Aware** (UTC storage, Central display)  
✅ **Type Safe** with Pydantic models  
✅ **Async/Await** for performance

### Important Notes

- **Free Service**: Yahoo Finance is free but has informal rate limits
- **Best Practices**: Use 0.5-1 second delays between requests
- **Data Coverage**: Most complete for large-cap US stocks
- **Updates**: Market data is real-time, fundamentals lag by 1-2 days
- **Timezone**: All data stored in UTC, convert to Central for display
- **HTTP 404 Errors**: Expected when ESG data is not available for a symbol (handled silently)

## 1. Market Data (OHLCV)

### Available Attributes
- `symbol`: Stock ticker symbol
- `timestamp`: UTC timestamp
- `open`: Opening price
- `high`: Highest price
- `low`: Lowest price
- `close`: Closing price
- `volume`: Trading volume
- `dividends`: Dividend amount (if applicable)
- `stock_splits`: Split ratio (if applicable)

### Intervals Supported
- Intraday: `1m`, `5m`, `15m`, `30m`, `1h`
- Daily+: `1d`, `1wk`, `1mo`

### Usage
```python
from src.services.yahoo.client import YahooClient
from datetime import date, timedelta

client = YahooClient()

# Get daily bars
bars = await client.get_historical_data(
    symbol="AAPL",
    start_date=date.today() - timedelta(days=30),
    end_date=date.today(),
    interval="1d"
)

# Access attributes
for bar in bars:
    print(f"{bar.timestamp}: O={bar.open} H={bar.high} L={bar.low} C={bar.close} V={bar.volume}")
```

## 2. Company Information

### Available Attributes
- `symbol`: Stock ticker
- `name`: Company name
- `sector`: Business sector
- `industry`: Industry classification
- `description`: Business description
- `website`: Company website
- `phone`: Contact phone
- `address`, `city`, `state`, `zip`, `country`: Location
- `employees`: Full-time employee count
- `market_cap`: Market capitalization
- `currency`: Trading currency
- `exchange`: Exchange code
- `quote_type`: Security type
- `additional_data`: Full info dictionary

### Usage
```python
info = await client.get_company_info("AAPL")
print(f"{info.name} - {info.sector}")
print(f"Employees: {info.employees:,}")
print(f"Market Cap: ${info.market_cap:,}")
```

## 3. Key Statistics (50+ Metrics)

### Valuation Metrics
- `market_cap`: Market capitalization
- `enterprise_value`: Enterprise value
- `trailing_pe`: Trailing P/E ratio
- `forward_pe`: Forward P/E ratio
- `peg_ratio`: PEG ratio
- `price_to_book`: Price-to-book ratio
- `price_to_sales`: Price-to-sales ratio
- `enterprise_to_revenue`: EV/Revenue
- `enterprise_to_ebitda`: EV/EBITDA

### Profitability Metrics
- `profit_margin`: Net profit margin
- `operating_margin`: Operating margin
- `return_on_assets`: ROA
- `return_on_equity`: ROE
- `gross_margin`: Gross margin
- `ebitda_margin`: EBITDA margin

### Financial Health
- `revenue`: Total revenue
- `revenue_per_share`: Revenue per share
- `earnings_per_share`: EPS (trailing)
- `total_cash`: Total cash
- `total_debt`: Total debt
- `debt_to_equity`: Debt-to-equity ratio
- `current_ratio`: Current ratio
- `quick_ratio`: Quick ratio
- `free_cash_flow`: Free cash flow
- `operating_cash_flow`: Operating cash flow

### Growth Metrics
- `revenue_growth`: Revenue growth rate
- `earnings_growth`: Earnings growth rate

### Trading Metrics
- `beta`: Stock beta
- `fifty_two_week_high`: 52-week high
- `fifty_two_week_low`: 52-week low
- `fifty_day_average`: 50-day moving average
- `two_hundred_day_average`: 200-day moving average
- `average_volume`: Average daily volume

### Dividend Metrics
- `dividend_yield`: Dividend yield
- `dividend_rate`: Annual dividend rate
- `payout_ratio`: Payout ratio

### Share Information
- `shares_outstanding`: Shares outstanding
- `float_shares`: Float shares
- `shares_short`: Shares short
- `short_ratio`: Short ratio
- `held_percent_insiders`: % held by insiders
- `held_percent_institutions`: % held by institutions

### Usage
```python
stats = await client.get_key_statistics("AAPL")

# Valuation
print(f"P/E Ratio: {stats.trailing_pe:.2f}")
print(f"Market Cap: ${stats.market_cap:,}")

# Profitability
print(f"Profit Margin: {stats.profit_margin*100:.2f}%")
print(f"ROE: {stats.return_on_equity*100:.2f}%")

# Financial Health
print(f"Debt/Equity: {stats.debt_to_equity:.2f}")
print(f"Current Ratio: {stats.current_ratio:.2f}")
```

## 4. Dividends

### Available Attributes
- `symbol`: Stock ticker
- `ex_date`: Ex-dividend date
- `amount`: Dividend amount per share
- `payment_date`: Payment date (if available)
- `record_date`: Record date (if available)
- `dividend_type`: Type ('regular', 'special', 'stock')
- `currency`: Currency code

### Usage
```python
dividends = await client.get_dividends(
    symbol="AAPL",
    start_date=date.today() - timedelta(days=365),
    end_date=date.today()
)

total_dividends = sum(div.amount for div in dividends)
print(f"Total dividends in last year: ${total_dividends:.2f}")
```

## 5. Stock Splits

### Available Attributes
- `symbol`: Stock ticker
- `split_date`: Split date
- `split_ratio`: Numeric ratio (e.g., 2.0 for 2:1 split)
- `ratio_str`: Human-readable ratio (e.g., "2:1")

### Usage
```python
splits = await client.get_splits(
    symbol="AAPL",
    start_date=date(2020, 1, 1),
    end_date=date.today()
)

for split in splits:
    print(f"{split.split_date}: {split.ratio_str} split")
```

## 6. Institutional Holders

### Available Attributes
- `symbol`: Stock ticker
- `date_reported`: Reporting date
- `holder_name`: Institution name
- `shares`: Number of shares held
- `value`: Dollar value of holdings
- `percent_held`: Percentage of shares held
- `percent_change`: Change in holding percentage

### Usage
```python
holders = await client.get_institutional_holders("AAPL")

print("Top 10 Institutional Holders:")
for holder in holders[:10]:
    print(f"{holder.holder_name}: {holder.shares:,} shares ({holder.percent_held*100:.2f}%)")
```

### Enhanced API Features

The institutional holders data is now enhanced with automatic percentage calculations and standardized ag-grid display:

#### Automatic Percentage Calculation
When Yahoo Finance doesn't provide percentage data, the system automatically calculates percentages using:
- **Primary**: Shares outstanding from Key Statistics
- **Fallback**: Relative percentages based on total institutional shares

#### API Endpoint
```python
# Direct API access with enhanced features
import requests

response = requests.get("http://localhost:8002/api/institutional-holders/AAPL")
data = response.json()

if data["success"]:
    for holder in data["holders"]:
        print(f"{holder['holder_name']}: {holder['percent_held_display']}")
```

#### Frontend Visualization
The institutional holders are displayed in a standardized ag-grid table with:
- **Direction column**: Shows "Up", "Down", or "—" based on % Change
- **% Change column**: Color-coded (green for positive, red for negative, gray for neutral)
- **Summary metrics**: Number of Holders, Total Shares, and Total Value displayed above the table
- **All columns**: Sortable and resizable
- Blue gradient bars for visual representation
- Black text positioned for optimal readability
- Responsive design that scales with container width

## 7. Analyst Recommendations

### Available Attributes
- `symbol`: Stock ticker
- `date`: Date of analysis
- `period`: Time period ('0m', '-1m', '-2m', '-3m')
- `strong_buy`: Number of strong buy ratings
- `buy`: Number of buy ratings
- `hold`: Number of hold ratings
- `sell`: Number of sell ratings
- `strong_sell`: Number of strong sell ratings
- `total_analysts`: Total number of analysts (computed property)

### Usage
```python
recommendations = await client.get_analyst_recommendations("AAPL")

latest = recommendations[0]
print(f"Strong Buy: {latest.strong_buy}")
print(f"Buy: {latest.buy}")
print(f"Hold: {latest.hold}")
print(f"Sell: {latest.sell}")
print(f"Strong Sell: {latest.strong_sell}")
print(f"Total Analysts: {latest.total_analysts}")
```

## 8. Financial Statements

### Statement Types
- `income`: Income statement
- `balance_sheet`: Balance sheet
- `cash_flow`: Cash flow statement

### Period Types
- `annual`: Annual statements
- `quarterly`: Quarterly statements

### Available Attributes
- `symbol`: Stock ticker
- `period_end`: Period end date
- `statement_type`: Type of statement
- `period_type`: Annual or quarterly
- `fiscal_year`: Fiscal year (if available)
- `fiscal_quarter`: Fiscal quarter (if available)
- `data`: Dictionary with all line items

### Common Income Statement Items
- Total Revenue
- Gross Profit
- Operating Income
- Net Income
- Basic EPS
- Diluted EPS

### Common Balance Sheet Items
- Total Assets
- Total Liabilities
- Stockholders Equity
- Cash and Cash Equivalents
- Total Debt

### Common Cash Flow Items
- Operating Cash Flow
- Investing Cash Flow
- Financing Cash Flow
- Free Cash Flow
- Capital Expenditure

### Usage
```python
# Income statement
income_stmts = await client.get_financial_statements(
    symbol="AAPL",
    statement_type="income",
    period_type="annual"
)

latest = income_stmts[0]
print(f"Period: {latest.period_end}")
print(f"Revenue: ${latest.data['Total Revenue']:,.0f}")
print(f"Net Income: ${latest.data['Net Income']:,.0f}")

# Balance sheet
balance_stmts = await client.get_financial_statements(
    symbol="AAPL",
    statement_type="balance_sheet",
    period_type="annual"
)

# Cash flow
cashflow_stmts = await client.get_financial_statements(
    symbol="AAPL",
    statement_type="cash_flow",
    period_type="quarterly"
)
```

## 9. ESG Scores

### Available Attributes
- `symbol`: Stock ticker
- `date`: Score date
- `total_esg`: Total ESG score
- `environment_score`: Environmental score
- `social_score`: Social score
- `governance_score`: Governance score
- `controversy_level`: Controversy level (1-5)
- `esg_performance`: Performance rating
- `peer_group`: Peer group classification
- `peer_count`: Number of peers
- `percentile`: Percentile ranking (if available)

### Usage
```python
esg = await client.get_esg_scores("AAPL")

if esg:
    print(f"Total ESG: {esg.total_esg}")
    print(f"Environment: {esg.environment_score}")
    print(f"Social: {esg.social_score}")
    print(f"Governance: {esg.governance_score}")
    print(f"Controversy Level: {esg.controversy_level}")
```

## 10. Company Officers

### Available Attributes
- `symbol`: Stock ticker
- `name`: Officer name
- `title`: Job title
- `age`: Age
- `year_born`: Birth year
- `fiscal_year`: Fiscal year of compensation data
- `total_pay`: Total compensation
- `exercised_value`: Exercised options value
- `unexercised_value`: Unexercised options value

### Usage
```python
officers = await client.get_company_officers("AAPL")

print("Executive Team:")
for officer in officers:
    pay_str = f"${officer.total_pay:,}" if officer.total_pay else "N/A"
    print(f"{officer.name} - {officer.title} - {pay_str}")
```

## Loading Data into Database

Use the `YahooDataLoader` to persist data:

```python
from src.services.yahoo.loader import YahooDataLoader

loader = YahooDataLoader()

# Load market data
count = await loader.load_market_data(
    symbol="AAPL",
    start_date=date.today() - timedelta(days=30),
    end_date=date.today(),
    interval="1d"
)

# Load company info
success = await loader.load_company_info("AAPL")

# Load all data types
results = await loader.load_all_data(
    symbol="AAPL",
    start_date=date.today() - timedelta(days=30),
    end_date=date.today(),
    include_fundamentals=True,
    include_dividends=True,
    include_splits=True
)
```

## Data Quality Notes

### Market Data
- ✅ Highly reliable for US equities
- ✅ Real-time for daily data
- ⚠️ Intraday data limited to recent periods (7-60 days)
- ⚠️ Some international symbols may have delayed data

### Fundamentals
- ✅ Comprehensive for large-cap US stocks
- ⚠️ May be incomplete for small-cap or international stocks
- ⚠️ Updates lag actual filings by 1-2 days

### ESG Scores
- ⚠️ Only available for larger companies
- ⚠️ Updates quarterly or less frequently

### Analyst Recommendations
- ✅ Good coverage for widely-followed stocks
- ⚠️ Limited or no coverage for small-cap stocks

## Rate Limiting

Yahoo Finance is free but has informal rate limits:
- Recommended: 0.5-1 second delay between requests
- The `YahooDataLoader` includes built-in rate limiting

```python
loader = YahooDataLoader(
    delay_between_requests=0.5  # 0.5 second delay
)
```

## Error Handling

```python
from src.services.yahoo.exceptions import (
    YahooAPIError,
    YahooSymbolNotFoundError,
    YahooDataError
)

try:
    data = await client.get_historical_data("INVALID")
except YahooSymbolNotFoundError:
    print("Symbol not found")
except YahooDataError as e:
    print(f"Data error: {e}")
except YahooAPIError as e:
    print(f"API error: {e}")
```

## Complete Example

```python
import asyncio
from datetime import date, timedelta
from src.services.yahoo.client import YahooClient

async def analyze_stock(symbol: str):
    """Complete stock analysis using all data attributes"""
    client = YahooClient()
    
    # 1. Company overview
    info = await client.get_company_info(symbol)
    print(f"\n{info.name} ({symbol})")
    print(f"Sector: {info.sector} | Industry: {info.industry}")
    
    # 2. Valuation
    stats = await client.get_key_statistics(symbol)
    print(f"\nValuation:")
    print(f"  Market Cap: ${stats.market_cap:,}")
    print(f"  P/E Ratio: {stats.trailing_pe:.2f}")
    print(f"  P/B Ratio: {stats.price_to_book:.2f}")
    
    # 3. Profitability
    print(f"\nProfitability:")
    print(f"  Profit Margin: {stats.profit_margin*100:.2f}%")
    print(f"  ROE: {stats.return_on_equity*100:.2f}%")
    
    # 4. Recent price action
    bars = await client.get_historical_data(
        symbol,
        start_date=date.today() - timedelta(days=30),
        end_date=date.today()
    )
    latest = bars[-1]
    print(f"\nLatest Price: ${latest.close:.2f}")
    print(f"Volume: {latest.volume:,}")
    
    # 5. Dividends
    dividends = await client.get_dividends(
        symbol,
        start_date=date.today() - timedelta(days=365),
        end_date=date.today()
    )
    if dividends:
        annual_div = sum(d.amount for d in dividends)
        print(f"\nAnnual Dividend: ${annual_div:.2f}")
    
    # 6. Analyst sentiment
    recommendations = await client.get_analyst_recommendations(symbol)
    if recommendations:
        latest_rec = recommendations[0]
        buy_pct = (latest_rec.strong_buy + latest_rec.buy) / latest_rec.total_analysts * 100
        print(f"\nAnalyst Ratings:")
        print(f"  Buy/Strong Buy: {buy_pct:.1f}%")
        print(f"  Total Analysts: {latest_rec.total_analysts}")

if __name__ == "__main__":
    asyncio.run(analyze_stock("AAPL"))
```

## See Also

- [Data Ingestion API](../api/data-ingestion.md)
- [Database Schema](../development/database.md)
- [Trading Dashboard](../user-guide/dashboard.md)

