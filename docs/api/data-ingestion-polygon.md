# Polygon.io Integration

## Overview

Polygon.io provides historical end-of-day market data for backtesting and strategy development. The free tier offers 2 years of historical data with a rate limit of 5 calls per minute.

**Status**: ✅ Implemented (v1.0.0)  
**Data Type**: End-of-day OHLCV bars  
**Use Case**: Historical backtesting, strategy development

## Free Tier Capabilities

- **API Calls**: 5 per minute (300 per hour)
- **Historical Data**: 2 years available
- **Real-time Data**: **Not available** (end-of-day only)
- **Data Types**: End-of-day OHLCV bars, basic market data
- **WebSocket**: **Not available** on free tier
- **Delayed Data**: **Not available** (end-of-day only)

## Data Collection Strategy

### Historical Backfill

```
1. Download 2 years of daily end-of-day data (1 call per symbol)
2. Download recent end-of-day data for active symbols
3. Batch multiple symbols per call when possible
4. Store in PostgreSQL with compression
```

### End-of-Day Updates

```
1. Daily: Update end-of-day data after market close
2. Use 4 calls/minute (80% of limit) for safety
3. Prioritize symbols in trading universe
4. Cache recent data in Redis
```

**Note**: Free tier only provides end-of-day data, not intraday or real-time data.

## Implications for Trading Strategies

### Limitations of End-of-Day Data

- **No Intraday Trading**: Cannot execute strategies that require minute/hourly data
- **Delayed Execution**: Can only place orders based on previous day's close
- **Limited Technical Analysis**: Many indicators require intraday data
- **Backtesting Constraints**: Historical testing limited to daily timeframes

### Suitable Strategy Types

- **Swing Trading**: Hold positions for days/weeks
- **Position Trading**: Long-term investment strategies
- **End-of-Day Rebalancing**: Portfolio rebalancing based on daily close
- **Fundamental Analysis**: Strategies based on company fundamentals

### Alternative Data Sources for Real-Time

- **Alpaca Markets**: Provides real-time trading data for positions/orders
- **Yahoo Finance**: Free real-time quotes (with limitations)
- **Alpha Vantage**: Real-time data with higher rate limits

## Rate Limiting Strategy

```python
# Free Tier: 5 calls/minute
# Strategy: Use 4 calls/minute (80% safety margin)
# Batch Strategy: Group symbols when possible

class PolygonRateLimiter:
    def __init__(self):
        self.calls_per_minute = 4  # 80% of 5
        self.sliding_window = deque(maxlen=self.calls_per_minute)
    
    async def can_make_call(self) -> bool:
        now = time.time()
        # Remove calls older than 1 minute
        while self.sliding_window and now - self.sliding_window[0] > 60:
            self.sliding_window.popleft()
        
        return len(self.sliding_window) < self.calls_per_minute
```

## Integration Details

### Client Implementation

The Polygon.io client is located in `src/services/data_ingestion/polygon/` and handles:
- API authentication
- Rate limiting (4 calls/minute for safety)
- Data fetching and transformation
- Error handling and retries

### Prefect Flows

Polygon.io data ingestion uses the following Prefect flows:

1. **Historical Backfill Flow**: Downloads 2 years of historical data for symbols
2. **End-of-Day Update Flow**: Daily updates after market close
3. **Data Quality Monitoring**: Validates data quality and detects anomalies

See [Data Ingestion Overview](data-ingestion-overview.md#prefect-flows) for flow implementation details.

### Data Storage

- **PostgreSQL**: Historical OHLCV data stored in `data_ingestion.market_data` table
- **Redis**: Recent data cached for fast access
- **Data Source Tag**: All Polygon.io data tagged with `source='polygon'`

### Symbol Management

Polygon.io is used for:
- Symbol health checking (detecting delisted symbols)
- Historical data backfill
- End-of-day data updates

The `SymbolService` integrates with Polygon.io for symbol validation. See [Yahoo Finance Integration](data-ingestion-yahoo.md#symbolservice-api) for SymbolService details.

## Configuration

### Environment Variables

```bash
POLYGON_API_KEY=your_polygon_api_key
POLYGON_RATE_LIMIT_PER_MINUTE=4
POLYGON_BASE_URL=https://api.polygon.io
POLYGON_UPDATE_INTERVAL=86400  # 24 hours (end-of-day)
```

### Settings

```python
class PolygonSettings(BaseSettings):
    polygon_api_key: str = Field(default="", alias="POLYGON_API_KEY")
    polygon_rate_limit_per_minute: int = Field(default=4, alias="POLYGON_RATE_LIMIT_PER_MINUTE")
    polygon_base_url: str = Field(default="https://api.polygon.io", alias="POLYGON_BASE_URL")
    polygon_update_interval: int = Field(default=86400, alias="POLYGON_UPDATE_INTERVAL")
```

## Usage Examples

### Historical Data Backfill

```python
from prefect import flow
from src.services.data_ingestion.polygon.client import PolygonClient

@flow(name="polygon_historical_backfill")
async def backfill_historical_data(symbols: List[str], start_date: datetime, end_date: datetime):
    client = PolygonClient()
    
    for symbol in symbols:
        # Fetch historical data
        data = await client.get_historical_bars(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timespan="day"
        )
        
        # Store in database
        await store_market_data(data, source="polygon")
```

### End-of-Day Update

```python
@flow(name="polygon_eod_update")
async def update_end_of_day_data(symbols: List[str]):
    client = PolygonClient()
    
    for symbol in symbols:
        # Fetch latest end-of-day data
        eod_data = await client.get_latest_bar(symbol=symbol)
        
        # Store in database
        await store_market_data([eod_data], source="polygon")
```

## Best Practices

1. **Respect Rate Limits**: Always use 4 calls/minute (80% of limit) for safety
2. **Batch Processing**: Process symbols in batches to optimize API usage
3. **Error Handling**: Implement retry logic with exponential backoff
4. **Data Validation**: Validate all data before storage
5. **Status Tracking**: Update `symbol_data_status` table after each ingestion attempt

## Limitations

- **No Real-Time Data**: Free tier only provides end-of-day data
- **No WebSocket**: Real-time streaming not available
- **Limited Historical Data**: Only 2 years available (not 5 years)
- **Rate Limits**: 5 calls/minute may be limiting for large symbol universes

## Future Enhancements

- Upgrade to paid tier for real-time data
- Implement WebSocket streaming (paid tier)
- Add intraday data support (paid tier)
- Expand historical data range (paid tier)

---

**See Also**:
- [Data Ingestion Overview](data-ingestion-overview.md) - Overall architecture and common patterns
- [Yahoo Finance Integration](data-ingestion-yahoo.md) - Yahoo Finance integration
- [Alpaca Integration](data-ingestion-alpaca.md) - Alpaca integration

