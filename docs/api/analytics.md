# Analytics API

> **📋 Implementation Status**: ✅ Core Features Implemented (v1.0.0)  
> **Current Status**: Market data statistics, symbol management, technical indicators, data quality monitoring available

This guide covers the analytics API endpoints for market data analysis, performance tracking, and reporting.

## Overview

The analytics service provides REST API endpoints for:
- ✅ Market data statistics and analysis
- ✅ Symbol information and data availability
- ✅ Technical indicators retrieval
- ✅ Data quality monitoring
- ✅ Interactive charting data
- 🚧 Strategy performance metrics (planned for v1.1.0)
- 🚧 Backtesting results (planned for v1.1.0)

## Base URL

```
http://localhost:8001/api/market-data
```

## Endpoints

### Market Data Statistics

#### Get Market Data Statistics
```http
GET /api/market-data/stats
```

**Response:**
```json
{
  "total_symbols": 150,
  "total_records": 125000,
  "last_update": "2023-12-01T16:00:00Z",
  "data_sources": [
    {
      "source": "polygon",
      "symbols_count": 150,
      "records_count": 125000,
      "last_update": "2023-12-01T16:00:00Z"
    }
  ],
  "date_range": {
    "earliest": "2022-01-01T00:00:00Z",
    "latest": "2023-12-01T16:00:00Z"
  }
}
```

### Symbol Management

#### Get Available Symbols
```http
GET /api/market-data/symbols
```

**Response:**
```json
[
  {
    "symbol": "AAPL",
    "name": "Apple Inc.",
    "exchange": "NASDAQ",
    "sector": "Technology",
    "market_cap": 3000000000000,
    "status": "active",
    "data_count": 500,
    "last_update": "2023-12-01T16:00:00Z"
  },
  {
    "symbol": "MSFT",
    "name": "Microsoft Corporation",
    "exchange": "NASDAQ",
    "sector": "Technology",
    "market_cap": 2800000000000,
    "status": "active",
    "data_count": 500,
    "last_update": "2023-12-01T16:00:00Z"
  }
]
```

### Market Data Access

#### Get Market Data for Symbol
```http
GET /api/market-data/data/{symbol}
```

**Parameters:**
- `symbol` (path): The trading symbol (e.g., AAPL, MSFT)
- `start_date` (query, optional): Start date in YYYY-MM-DD format
- `end_date` (query, optional): End date in YYYY-MM-DD format
- `limit` (query, optional): Maximum number of records to return (default: 1000)

**Response:**
```json
[
  {
    "symbol": "AAPL",
    "timestamp": "2023-12-01T16:00:00Z",
    "open": 150.00,
    "high": 152.50,
    "low": 149.75,
    "close": 151.25,
    "volume": 45000000,
    "source": "polygon",
    "created_at": "2023-12-01T16:05:00Z"
  }
]
```

#### Get Latest Market Data
```http
GET /api/market-data/data/{symbol}/latest
```

**Parameters:**
- `symbol` (path): The trading symbol

**Response:**
```json
{
  "symbol": "AAPL",
  "timestamp": "2023-12-01T16:00:00Z",
  "open": 150.00,
  "high": 152.50,
  "low": 149.75,
  "close": 151.25,
  "volume": 45000000,
  "source": "polygon",
  "created_at": "2023-12-01T16:05:00Z"
}
```

#### Get Data Count for Symbol
```http
GET /api/market-data/data/{symbol}/count
```

**Parameters:**
- `symbol` (path): The trading symbol

**Response:**
```json
{
  "symbol": "AAPL",
  "count": 500,
  "date_range": {
    "earliest": "2022-01-01T00:00:00Z",
    "latest": "2023-12-01T16:00:00Z"
  }
}
```

#### Get OHLC Summary
```http
GET /api/market-data/data/{symbol}/ohlc
```

**Parameters:**
- `symbol` (path): The trading symbol
- `period` (query, optional): Time period (`1D`, `1W`, `1M`, `3M`, `6M`, `1Y`)

**Response:**
```json
{
  "symbol": "AAPL",
  "period": "1M",
  "summary": {
    "open": 150.00,
    "high": 158.75,
    "low": 148.50,
    "close": 155.25,
    "volume": 1250000000,
    "change": 5.25,
    "change_percent": 3.5
  },
  "daily_data": [
    {
      "date": "2023-12-01",
      "open": 150.00,
      "high": 152.50,
      "low": 149.75,
      "close": 151.25,
      "volume": 45000000
    }
  ]
}
```

## Data Models

### MarketDataResponse
```json
{
  "symbol": "string",
  "timestamp": "datetime",
  "open": "number",
  "high": "number",
  "low": "number",
  "close": "number",
  "volume": "integer",
  "source": "string",
  "created_at": "datetime"
}
```

### MarketDataStats
```json
{
  "total_symbols": "integer",
  "total_records": "integer",
  "last_update": "datetime",
  "data_sources": [
    {
      "source": "string",
      "symbols_count": "integer",
      "records_count": "integer",
      "last_update": "datetime"
    }
  ],
  "date_range": {
    "earliest": "datetime",
    "latest": "datetime"
  }
}
```

### SymbolInfo
```json
{
  "symbol": "string",
  "name": "string",
  "exchange": "string",
  "sector": "string",
  "market_cap": "integer",
  "status": "string",
  "data_count": "integer",
  "last_update": "datetime"
}
```

## Error Handling

### Error Response Format
```json
{
  "error": "string",
  "message": "string",
  "code": "integer",
  "details": "object"
}
```

### Common Error Codes
- `400` - Bad Request (invalid parameters)
- `404` - Not Found (symbol not found or no data available)
- `422` - Unprocessable Entity (invalid date format)
- `500` - Internal Server Error (server-side error)

## Data Quality and Validation

### Data Validation Rules
- Timestamps must be in UTC timezone
- OHLC values must be positive numbers
- Volume must be non-negative integers
- High must be >= Low
- High must be >= Open and Close
- Low must be <= Open and Close

### Data Quality Monitoring
The system continuously monitors data quality:
- Missing data detection
- Anomaly detection (unusual price movements)
- Data freshness monitoring
- Source validation

## Performance Considerations

### Caching Strategy
- Frequently accessed data is cached in Redis
- Cache TTL: 5 minutes for recent data
- Cache invalidation on new data updates

### Query Optimization
- Database indexes on symbol and timestamp
- Pagination for large datasets
- Efficient date range queries

## Examples

### Get Market Statistics
```bash
curl http://localhost:8001/api/market-data/stats
```

### Get Available Symbols
```bash
curl http://localhost:8001/api/market-data/symbols
```

### Get Historical Data for AAPL
```bash
curl "http://localhost:8001/api/market-data/data/AAPL?start_date=2023-11-01&end_date=2023-12-01&limit=100"
```

### Get Latest Data for MSFT
```bash
curl http://localhost:8001/api/market-data/data/MSFT/latest
```

### Get Data Count for GOOGL
```bash
curl http://localhost:8001/api/market-data/data/GOOGL/count
```

### Get Monthly OHLC Summary
```bash
curl "http://localhost:8001/api/market-data/data/AAPL/ohlc?period=1M"
```

## Integration with Streamlit UI

The analytics API is designed to work seamlessly with the Streamlit multipage interface:

### Chart Data
```python
import streamlit as st
import plotly.graph_objects as go
import requests

# Fetch data for Plotly charts
@st.cache_data
def get_market_data(symbol, limit=100):
    response = requests.get(f'http://localhost:8001/api/market-data/data/{symbol}?limit={limit}')
    return response.json()

# Create interactive charts
data = get_market_data('AAPL')
fig = go.Figure(data=go.Candlestick(
    x=[d['timestamp'] for d in data],
    open=[d['open'] for d in data],
    high=[d['high'] for d in data],
    low=[d['low'] for d in data],
    close=[d['close'] for d in data]
))
st.plotly_chart(fig, width='stretch')
```

### Session State Integration
```python
# Use session state for persistent data
if 'market_data' not in st.session_state:
    st.session_state.market_data = get_market_data('AAPL')

# Update data based on user selection
symbol = st.selectbox('Select Symbol', ['AAPL', 'MSFT', 'GOOGL'])
if symbol != st.session_state.get('selected_symbol'):
    st.session_state.market_data = get_market_data(symbol)
    st.session_state.selected_symbol = symbol
```

## Technical Indicators

### Available Indicators

The system uses **pandas-ta** library for technical indicator calculations:

- **SMA** (Simple Moving Average) - 20, 50, 200 periods
- **EMA** (Exponential Moving Average) - 12, 26, 50 periods
- **RSI** (Relative Strength Index) - 14 period default
- **MACD** (Moving Average Convergence Divergence) - with proper signal line
- **Bollinger Bands** - 20 period, 2 standard deviations
- **Volatility** - Annualized volatility calculation
- **Price Change** - 1d, 5d, 30d percentage changes

All indicators are calculated using industry-standard formulas via pandas-ta library.

### Data Frequency Handling

The technical indicator calculation system automatically handles different data frequencies to ensure accurate daily indicator calculations.

#### Problem Statement

When market data is stored at hourly intervals (e.g., from Yahoo Finance with `interval="1h"`), calculating daily indicators directly on hourly data would produce incorrect results:
- **SMA_20** would use 20 hours of data instead of 20 days
- **RSI_14** would use 14 hours of data instead of 14 days
- **SMA_200** would use 200 hours (~8 days) instead of 200 days

#### Solution: Automatic Resampling

The `IndicatorCalculationService` automatically detects and resamples hourly data to daily bars before calculating indicators:

1. **Frequency Detection**: Analyzes time intervals between consecutive records to detect if data is hourly or daily
2. **Automatic Resampling**: Converts hourly data to daily OHLCV bars using proper aggregation:
   - **Open**: First open price of the day
   - **High**: Maximum high price of the day
   - **Low**: Minimum low price of the day
   - **Close**: Last close price of the day
   - **Volume**: Sum of all volumes for the day
3. **Indicator Calculation**: Calculates all indicators on the resampled daily bars

#### Implementation Details

```python
# Automatic detection and resampling
data_frequency = self._detect_data_frequency(market_data)

if data_frequency == 'hourly':
    # Resample hourly data to daily bars
    market_data = self._resample_to_daily(market_data)
    # Then calculate indicators on daily bars
```

#### Resampling Rules

The resampling process:
- Uses pandas `resample('D')` to aggregate to daily frequency
- Automatically removes weekends and holidays (days with no trading data)
- Preserves all OHLCV relationships (High >= Open/Close, Low <= Open/Close)
- Maintains UTC timezone awareness

#### Example

**Input (Hourly Data):**
```
2024-01-15 09:00:00 - Open: 150.00, High: 150.50, Low: 149.75, Close: 150.25, Volume: 1000000
2024-01-15 10:00:00 - Open: 150.25, High: 151.00, Low: 150.20, Close: 150.80, Volume: 1200000
2024-01-15 11:00:00 - Open: 150.80, High: 151.50, Low: 150.75, Close: 151.20, Volume: 1100000
... (more hourly bars)
```

**Output (Daily Bar):**
```
2024-01-15 - Open: 150.00, High: 152.00, Low: 149.50, Close: 151.50, Volume: 8500000
```

**Then Indicators Calculated:**
- SMA_20 = Average of last 20 daily closes (not 20 hours)
- RSI_14 = 14-day RSI (not 14-hour RSI)

#### Benefits

1. **Data Storage Flexibility**: Store hourly data for detailed analysis while calculating daily indicators correctly
2. **Automatic Handling**: No manual intervention required - system detects and handles frequency automatically
3. **Accurate Indicators**: All daily indicators (SMA_20, RSI_14, etc.) are calculated correctly regardless of input frequency
4. **Logging**: System logs when resampling occurs for transparency

#### Configuration

The resampling is automatic and requires no configuration. The system:
- Detects hourly data when average interval < 12 hours
- Detects daily data when average interval is 20-28 hours (accounting for weekends)
- Logs resampling operations for monitoring

#### Notes

- Original hourly data remains in the database unchanged
- Resampling only occurs in-memory during indicator calculation
- Daily data passes through without modification
- Unknown frequencies trigger a warning but calculation proceeds

## Future Enhancements

### Planned Features
- Portfolio performance analytics
- Risk metrics calculation
- Backtesting results analysis
- Real-time data streaming
- Advanced charting endpoints

### Data Sources
- Integration with additional data providers
- Real-time market data feeds
- Alternative data sources (news, sentiment)
- Economic indicators integration