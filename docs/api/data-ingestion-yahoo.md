# Yahoo Finance Integration

## Overview

Yahoo Finance provides comprehensive company fundamentals, financial statements, key statistics, and institutional holdings data. The integration supports 10 different data types for stock screening and fundamental analysis.

**Status**: ✅ Implemented (v1.0.0)  
**Data Types**: Company information, financial statements, key statistics, institutional holdings, company officers  
**Use Case**: Fundamental analysis, stock screening, company research

## Yahoo Finance Integration

### Data Types Implemented

- **Company Information**: Basic company details, sector, industry, employees
- **Financial Statements**: Income statements, balance sheets, cash flow statements
- **Key Statistics**: Market cap, P/E ratios, financial metrics (50+ fields)
- **Institutional Holdings**: Major institutional investors and holdings
- **Company Officers**: Executive compensation and leadership information

### Market Data (OHLCV)

- **Dual series**: The loader stores both unadjusted (`data_source='yahoo'`) and adjusted (`data_source='yahoo_adjusted'`) OHLCV. Adjusted prices are corrected for splits and dividends (suitable for backtesting total return).
- **Prefect task**: `load_yahoo_market_data_task` loads both series and returns `records_count` and `records_count_adjusted`. It also writes a `symbol_data_status` row for each symbol after every attempt (`"success"`, `"no_data"`, or `"failed"`).
- **Status tracking**: `symbol_data_status` is populated automatically by the Prefect task — no manual call to `update_symbol_data_status()` is needed in the flow.
- **Backpopulate**: For historical backfill of adjusted only, run `python scripts/backpopulate_yahoo_adjusted.py --all-symbols --days 365` (default interval 1h to match scheduled flow).

### Integration Details

Yahoo Finance data is used for:
- Stock screening and filtering
- Fundamental analysis
- Company research
- Institutional ownership tracking
- Backtesting with adjusted or unadjusted prices

Yahoo Finance data is stored in the `data_ingestion` schema. Market data uses two source values:
- **Unadjusted prices**: `data_source='yahoo'`
- **Adjusted prices (splits/dividends)**: `data_source='yahoo_adjusted'`

Other Yahoo data types use `data_source='yahoo'`. The scheduled Prefect flow and `load_all_data()` load both market data series; use `scripts/backpopulate_yahoo_adjusted.py` to backfill adjusted prices.

## Institutional Holders API

### Overview

The Institutional Holders API provides access to institutional ownership data with enhanced percentage calculations and visualization features.

### Endpoints

#### GET `/api/institutional-holders/{symbol}`

Retrieves institutional holders data for a specific symbol with automatic percentage calculation.

**Parameters:**
- `symbol` (path): Stock symbol (e.g., "AAPL", "MSFT")
- `limit` (query, optional): Maximum number of holders to return (default: 10)

**Response Format:**
```json
{
  "success": true,
  "symbol": "AAPL",
  "count": 10,
  "holders": [
    {
      "id": 1,
      "symbol": "AAPL",
      "date_reported": "2024-09-30",
      "holder_name": "Vanguard Group Inc",
      "shares": 1234567890,
      "shares_display": "1.23B",
      "value": 24567890123.45,
      "value_display": "$24.57B",
      "percent_held": 0.0954,
      "percent_held_display": "9.54%",
      "percent_change": 0.0125,
      "percent_change_display": "1.25%",
      "data_source": "yahoo",
      "created_at": "2024-10-16T19:30:00Z",
      "updated_at": "2024-10-16T19:30:00Z"
    }
  ]
}
```

#### GET `/api/institutional-holders`

Lists all symbols that have institutional holders data.

**Response Format:**
```json
{
  "success": true,
  "count": 25,
  "symbols": [
    {
      "symbol": "AAPL",
      "holder_count": 10
    }
  ]
}
```

### Enhanced Features

#### Automatic Percentage Calculation

When Yahoo Finance doesn't provide percentage data, the API automatically calculates percentages using:

1. **Primary Method**: Uses `shares_outstanding` from Key Statistics table
   ```python
   percentage = (holder_shares / shares_outstanding) * 100
   ```

2. **Fallback Method**: Uses relative percentages based on total institutional shares
   ```python
   percentage = (holder_shares / total_institutional_shares) * 100
   ```

#### Standardized ag-Grid Display

The frontend displays institutional holders using a standardized ag-grid component:

**Table Features:**
- **Standardized Columns**: Institution, Shares, Value, % Held, Direction, % Change, Date Reported
- **Direction Column**: Shows "Up", "Down", or "—" based on % Change direction
- **% Change Column**: 
  - Numeric, sortable column (absolute value, rounded to 2 decimal places)
  - No +/- signs displayed (shows only absolute value with % symbol)
  - Color-coded cells:
    - 🟢 **Green background** for positive changes (increases)
    - 🔴 **Red background** for negative changes (decreases)
    - ⚪ **Gray background** for no change
- **All columns**: Sortable, resizable, but no filtering enabled
- **Summary Metrics**: Displayed above the table in a single line:
  - Number of Holders
  - Total Shares (formatted with B/M/K)
  - Total Value (formatted currency with B/M/K)

**UI Layout:**
1. Section Header: "🏦 Top Institutional Holders"
2. Summary Metrics (single line): Number of Holders | Total Shares | Total Value
3. ag-Grid Table with all institutional holder data

### Error Handling

- **Invalid Symbol**: Returns empty results with `count: 0`
- **Missing Data**: Automatically calculates percentages when possible
- **Database Errors**: Returns HTTP 500 with error details

### Usage Examples

```python
import requests

# Get institutional holders for AAPL
response = requests.get("http://localhost:8002/api/institutional-holders/AAPL")
data = response.json()

if data["success"]:
    print(f"Found {data['count']} institutional holders for {data['symbol']}")
    for holder in data["holders"]:
        print(f"{holder['holder_name']}: {holder['percent_held_display']}")
```

## SymbolService API

The `SymbolService` class (`src/services/data_ingestion/symbols.py`) provides comprehensive symbol management functionality for the data ingestion pipeline. It handles symbol tracking, delisting detection, data ingestion status monitoring, and symbol statistics.

### Class Overview

```python
from src.services.data_ingestion.symbols import SymbolService

service = SymbolService()
```

The `SymbolService` integrates with the Polygon.io client for symbol health checking and uses database transactions for all operations.

### Core Methods

#### Symbol Retrieval

##### `get_active_symbols() -> List[Symbol]`
Retrieves all symbols with `status == "active"` from the database.

**Returns**: List of `Symbol` model objects with full symbol information

**Example:**
```python
symbols = await service.get_active_symbols()
for symbol in symbols:
    print(f"{symbol.symbol}: {symbol.name} ({symbol.exchange})")
```

##### `get_active_symbol_strings() -> List[str]`
Gets a lightweight list of active symbol tickers as strings.

**Returns**: List of symbol ticker strings (e.g., `["AAPL", "MSFT", "GOOGL"]`)

**Use Case**: Efficient when you only need ticker symbols without full symbol details

**Example:**
```python
tickers = await service.get_active_symbol_strings()
# ['AAPL', 'MSFT', 'GOOGL', ...]
```

##### `get_symbol_by_ticker(symbol: str) -> Optional[Symbol]`
Retrieves a specific symbol by its ticker.

**Parameters:**
- `symbol` (str): Ticker symbol (case-insensitive, automatically uppercased)

**Returns**: `Symbol` object if found, `None` otherwise

**Example:**
```python
symbol = await service.get_symbol_by_ticker("AAPL")
if symbol:
    print(f"Found: {symbol.name}")
```

#### Symbol Management

##### `add_symbol(symbol: str, name: Optional[str] = None, exchange: Optional[str] = None, sector: Optional[str] = None, market_cap: Optional[int] = None) -> Symbol`
Adds a new symbol to the tracking system. If the symbol already exists, returns the existing symbol.

**Parameters:**
- `symbol` (str): Ticker symbol (required, automatically uppercased)
- `name` (str, optional): Company name
- `exchange` (str, optional): Exchange name (e.g., "NASDAQ", "NYSE")
- `sector` (str, optional): Industry sector
- `market_cap` (int, optional): Market capitalization

**Returns**: `Symbol` object (existing or newly created)

**Behavior:**
- Automatically sets status to "active"
- Returns existing symbol if already in database (no duplicate creation)
- Logs warning if symbol already exists

**Example:**
```python
new_symbol = await service.add_symbol(
    symbol="TSLA",
    name="Tesla Inc.",
    exchange="NASDAQ",
    sector="Consumer Cyclical",
    market_cap=800_000_000_000
)
```

##### `mark_symbol_delisted(symbol: str, last_price: Optional[float] = None, notes: Optional[str] = None) -> bool`
Marks a symbol as delisted and adds it to the `delisted_symbols` table.

**Parameters:**
- `symbol` (str): Ticker symbol to mark as delisted
- `last_price` (float, optional): Last known price before delisting
- `notes` (str, optional): Additional notes about the delisting

**Returns**: `True` if successful, `False` if symbol not found

**Behavior:**
- Updates symbol status to "delisted" in `symbols` table
- Creates entry in `delisted_symbols` table with delist date (today)
- Handles already-delisted symbols gracefully (updates status if needed)
- Sets default notes to "Automatically detected as delisted" if not provided

**Example:**
```python
success = await service.mark_symbol_delisted(
    symbol="OLD",
    last_price=10.50,
    notes="Acquired by another company"
)
```

#### Symbol Health Checking

##### `check_symbol_health(symbol: str) -> bool`
Validates if a symbol is still active by attempting to fetch data from Polygon.io.

**Parameters:**
- `symbol` (str): Ticker symbol to check

**Returns**: 
- `True` if symbol is valid/healthy
- `False` if symbol appears to be delisted (404/not found errors)

**Behavior:**
- Uses Polygon.io API to verify symbol validity
- Returns `False` for 404 or "not found" errors
- Returns `True` for other errors (treats as temporary issues)
- Logs warnings for delisted symbols

**Example:**
```python
is_healthy = await service.check_symbol_health("AAPL")
if not is_healthy:
    await service.mark_symbol_delisted("AAPL")
```

##### `detect_delisted_symbols() -> List[str]`
Automatically scans all active symbols and detects which ones have been delisted.

**Returns**: List of symbol tickers that were detected as delisted

**Process:**
1. Retrieves all active symbols
2. Checks health of each symbol via Polygon.io
3. Marks unhealthy symbols as delisted
4. Returns list of newly delisted symbols

**Use Case**: Scheduled job to periodically clean up delisted symbols

**Example:**
```python
delisted = await service.detect_delisted_symbols()
print(f"Detected {len(delisted)} delisted symbols: {delisted}")
# Output: Detected 3 delisted symbols: ['OLD', 'GONE', 'DELISTED']
```

#### Data Ingestion Status Tracking

##### `get_symbol_data_status(symbol: str, date: date, data_source: str = "polygon") -> Optional[SymbolDataStatus]`
Retrieves the data ingestion status for a specific symbol, date, and data source.

**Parameters:**
- `symbol` (str): Ticker symbol
- `date` (date): Date to check status for
- `data_source` (str): Data source name (default: "polygon")

**Returns**: `SymbolDataStatus` object if found, `None` otherwise

**Use Case**: Check if data has already been ingested for a symbol/date

**Example:**
```python
from datetime import date

status = await service.get_symbol_data_status("AAPL", date(2024, 1, 15))
if status:
    print(f"Status: {status.status}, Last attempt: {status.last_attempt}")
```

##### `update_symbol_data_status(symbol: str, date: date, data_source: str, status: str, error_message: Optional[str] = None) -> SymbolDataStatus`
Updates or creates the data ingestion status for a symbol.

**Parameters:**
- `symbol` (str): Ticker symbol
- `date` (date): Date of data ingestion
- `data_source` (str): Data source name (e.g., "polygon", "alpaca", "yahoo")
- `status` (str): Status value ("success", "failed", "no_data", etc.)
- `error_message` (str, optional): Error message if ingestion failed

**Returns**: `SymbolDataStatus` object (created or updated)

**Behavior:**
- Creates new status record if doesn't exist
- Updates existing record if already present
- Automatically sets `last_attempt` timestamp

**Example:**
```python
status = await service.update_symbol_data_status(
    symbol="AAPL",
    date=date(2024, 1, 15),
    data_source="yahoo",
    status="success"
)
```

##### `get_symbols_needing_data(target_date: date, data_source: str = "polygon") -> List[Symbol]`
Retrieves active symbols that don't have successful data ingestion for the specified date.

**Parameters:**
- `target_date` (date): Date to check for missing data
- `data_source` (str): Data source to check (default: "polygon")

**Returns**: List of `Symbol` objects that need data for the target date

**Use Case**: Identify symbols that need data backfill or retry ingestion

**Example:**
```python
from datetime import date, timedelta

yesterday = date.today() - timedelta(days=1)
needing_data = await service.get_symbols_needing_data(yesterday, data_source="yahoo")
print(f"{len(needing_data)} symbols need data for {yesterday}")
```

#### Delisted Symbol Management

##### `get_delisted_symbols() -> List[DelistedSymbol]`
Retrieves all delisted symbols from the `delisted_symbols` table.

**Returns**: List of `DelistedSymbol` objects, ordered by delist date (most recent first)

**Example:**
```python
delisted = await service.get_delisted_symbols()
for symbol in delisted:
    print(f"{symbol.symbol}: Delisted on {symbol.delist_date}, Last price: ${symbol.last_price}")
```

#### Statistics and Reporting

##### `get_symbol_statistics() -> dict`
Generates comprehensive statistics about the symbol universe.

**Returns**: Dictionary with the following keys:
- `active_symbols` (int): Count of active symbols
- `delisted_symbols` (int): Count of delisted symbols
- `total_symbols` (int): Total symbol count
- `by_exchange` (dict): Dictionary mapping exchange names to symbol counts

**Example:**
```python
stats = await service.get_symbol_statistics()
print(f"Active: {stats['active_symbols']}")
print(f"Delisted: {stats['delisted_symbols']}")
print(f"By Exchange: {stats['by_exchange']}")
# Output:
# Active: 95
# Delisted: 5
# By Exchange: {'NASDAQ': 60, 'NYSE': 35}
```

### Integration with Data Ingestion Flows

`symbol_data_status` is written automatically by `load_yahoo_market_data_task` — you do not need to call `update_symbol_data_status()` manually in Prefect flows. The task covers all three outcomes:

| Outcome | Status written |
|---|---|
| Both `load_market_data()` calls succeed | `"success"` |
| `YahooDataError` (no data / delisted) | `"no_data"` |
| Any other exception (retried by Prefect) | `"failed"` |

To query which symbols still need data for a given date (e.g. for a backfill job), use `SymbolService.get_symbols_needing_data()`:

```python
from datetime import date, timedelta
from src.services.data_ingestion.symbols import SymbolService

service = SymbolService()
yesterday = date.today() - timedelta(days=1)
missing = await service.get_symbols_needing_data(yesterday, data_source="yahoo")
print(f"{len(missing)} symbols need data for {yesterday}")
```

### Database Models

The `SymbolService` interacts with the following database models:

- **`Symbol`**: Main symbols table (`data_ingestion.symbols`)
  - Primary key: `symbol` (VARCHAR(10))
  - Fields: `name`, `exchange`, `sector`, `market_cap`, `status`, `added_date`, `last_updated`
  - Relationships: `key_statistics`, `institutional_holders`, `financial_statements`, `company_officers`, `dividends`, `stock_splits`, `analyst_recommendations`, `esg_scores`

- **`DelistedSymbol`**: Delisted symbols tracking (`data_ingestion.delisted_symbols`)
  - Primary key: `symbol` (VARCHAR(10))
  - Fields: `delist_date`, `last_price`, `notes`, `created_at`

- **`SymbolDataStatus`**: Data ingestion status tracking (`data_ingestion.symbol_data_status`)
  - Primary key: (`symbol`, `date`, `data_source`)
  - Fields: `status`, `error_message`, `last_attempt`

### Error Handling

The service handles various error scenarios gracefully:

- **Symbol not found**: Returns `None` for retrieval methods, `False` for operations
- **Database errors**: All operations use transactions for atomicity
- **API errors**: Health checking distinguishes between delisted symbols (404) and temporary errors
- **Duplicate symbols**: `add_symbol()` safely handles existing symbols

### Best Practices

1. **Always use transactions**: All database operations are wrapped in `db_transaction()` context
2. **Check health before marking delisted**: Use `check_symbol_health()` to verify before calling `mark_symbol_delisted()`
3. **Update status after ingestion**: Always update `SymbolDataStatus` after data ingestion attempts
4. **Use statistics for monitoring**: Regularly call `get_symbol_statistics()` to monitor symbol universe health
5. **Schedule delisting detection**: Run `detect_delisted_symbols()` periodically (e.g., weekly) to clean up inactive symbols

## Configuration

### Environment Variables

```bash
# Yahoo Finance doesn't require API keys (free service)
# Rate limiting is handled automatically
```

### Settings

Yahoo Finance integration uses default settings and doesn't require special configuration. Rate limiting is handled automatically by the yfinance library.

## Usage Examples

### Fetching Company Information

```python
import yfinance as yf

# Get company info
ticker = yf.Ticker("AAPL")
info = ticker.info

# Get key statistics
key_stats = ticker.key_stats

# Get institutional holders
institutional_holders = ticker.institutional_holders
```

### Using SymbolService

```python
from src.services.data_ingestion.symbols import SymbolService

service = SymbolService()

# Add a new symbol
symbol = await service.add_symbol(
    symbol="AAPL",
    name="Apple Inc.",
    exchange="NASDAQ",
    sector="Technology"
)

# Check symbol health
is_healthy = await service.check_symbol_health("AAPL")

# Get statistics
stats = await service.get_symbol_statistics()
```

## Best Practices

1. **Data Source Tagging**: Always tag Yahoo Finance data with `data_source='yahoo'`
2. **Status Tracking**: `symbol_data_status` is updated automatically by `load_yahoo_market_data_task` for all outcomes (`"success"`, `"no_data"`, `"failed"`). Do not add manual `update_symbol_data_status()` calls in Prefect flows — this would create duplicate writes.
3. **Error Handling**: Handle missing data gracefully (Yahoo Finance may not have data for all symbols)
4. **Rate Limiting**: Yahoo Finance has implicit rate limits; implement delays between requests
5. **Data Validation**: Validate all Yahoo Finance data before storage

## Limitations

- **No API Key**: Yahoo Finance is free but has implicit rate limits
- **Data Availability**: Not all symbols have complete data
- **Data Freshness**: Some data may be delayed
- **Rate Limits**: Implicit rate limits may cause throttling

## Future Enhancements

- Additional data types (earnings, analyst recommendations, ESG scores)
- Real-time quote updates
- Historical data backfill
- Enhanced data validation

---

**See Also**:
- [Data Ingestion Overview](data-ingestion-overview.md) - Overall architecture and common patterns
- [Polygon.io Integration](data-ingestion-polygon.md) - Historical data integration
- [Alpaca Integration](data-ingestion-alpaca.md) - Real-time trading integration

