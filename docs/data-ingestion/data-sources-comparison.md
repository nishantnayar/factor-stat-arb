# Data Source Comparison & Best Practices

> **📋 Implementation Status**: ✅ Core Features Implemented (v1.0.0)

This document provides a comprehensive comparison of data sources and best practices for using them effectively in the trading system.

---

## Data Source Comparison

### Feature Matrix

| Feature | Polygon.io | Yahoo Finance | Alpaca |
|---------|-----------|---------------|---------|
| **OHLCV Data** | ✅ Excellent | ✅ Good | ✅ Good |
| **Real-time** | ✅ Yes | ⚠️ 15-min delay | ✅ Yes |
| **Historical Depth** | 10+ years | 50+ years | 5+ years |
| **Intraday Data** | ✅ All history | ⚠️ 60 days | ✅ All history |
| **Fundamentals** | ❌ No | ✅ Comprehensive | ❌ No |
| **Dividends** | ✅ Yes | ✅ Yes | ❌ No |
| **Splits** | ✅ Yes | ✅ Yes | ❌ No |
| **Options** | ✅ Yes | ✅ Yes | ❌ No |
| **News** | ✅ Yes | ✅ Yes | ✅ Yes |
| **API Stability** | ✅ Excellent | ⚠️ Good | ✅ Excellent |
| **Rate Limits** | 5/min (free) | None (soft) | ✅ Generous |
| **Cost** | $$ Paid | Free | Free |
| **Best For** | Production | Research | Paper Trading |

---

## When to Use Each Source

### Use Polygon.io for:

- Production trading systems
- Real-time data needs
- High-frequency strategies
- Accurate corporate actions
- Professional-grade data quality

### Use Yahoo Finance for:

- Backtesting and research
- Fundamental analysis
- Cost-conscious development
- Long historical data
- Company screening and research

### Use Alpaca for:

- Paper trading
- Order execution
- Real-time trading (with account)
- Integrated trading and data

---

## Data Validation Strategy

```python
# Validate by comparing sources
async def validate_market_data(symbol: str, date: date):
    """Compare data from Polygon and Yahoo"""
    
    # Get data from both sources
    polygon_data = await get_market_data(symbol, date, source="polygon")
    yahoo_data = await get_market_data(symbol, date, source="yahoo")
    
    # Compare close prices (should be within 0.5%)
    price_diff = abs(polygon_data.close - yahoo_data.close) / polygon_data.close
    
    if price_diff > 0.005:  # 0.5% threshold
        logger.warning(f"Price discrepancy for {symbol}: {price_diff:.2%}")
        return False
    
    return True
```

---

## Best Practices

### Data Freshness

```python
# Recommended update schedules

# Market Data
Polygon: Intraday (real-time)
Yahoo:   Daily EOD
Alpaca:  Intraday (real-time)

# Fundamentals (Yahoo only)
Company Info:      Weekly or on-demand
Key Statistics:    Daily EOD
Financial Statements: Quarterly + after earnings
Dividends:         Monthly check
Splits:           Monthly check
```

### Error Handling

```python
from src.services.yahoo.exceptions import YahooAPIError, YahooDataError

try:
    data = await yahoo_client.get_historical_data("AAPL", start, end)
except YahooAPIError as e:
    # API connection issues, rate limits
    logger.error(f"Yahoo API error: {e}")
    # Fall back to Polygon if available
    data = await polygon_client.get_aggregates("AAPL", start, end)
except YahooDataError as e:
    # Data quality issues
    logger.warning(f"Yahoo data quality issue: {e}")
    # Skip this symbol or mark for manual review
```

### Data Quality Checks

```python
async def validate_data_quality(symbol: str, bars: List[YahooBar]):
    """Validate Yahoo data quality"""
    
    checks = []
    
    # Check for gaps
    has_gaps = check_for_date_gaps(bars)
    checks.append(("no_gaps", not has_gaps))
    
    # Check for zero/negative prices
    has_bad_prices = any(b.close <= 0 for b in bars)
    checks.append(("valid_prices", not has_bad_prices))
    
    # Check for zero volume
    has_zero_volume = any(b.volume == 0 for b in bars)
    checks.append(("valid_volume", not has_zero_volume))
    
    # Check OHLC logic
    has_valid_ohlc = all(
        b.high >= max(b.open, b.close) and 
        b.low <= min(b.open, b.close)
        for b in bars
    )
    checks.append(("valid_ohlc", has_valid_ohlc))
    
    # Log results
    failed = [name for name, passed in checks if not passed]
    if failed:
        logger.warning(f"{symbol}: Failed quality checks: {failed}")
    
    return len(failed) == 0
```

### Caching Strategy

```python
# Cache company info (changes rarely)
from functools import lru_cache

@lru_cache(maxsize=1000)
async def get_company_info_cached(symbol: str):
    """Cache company info for 24 hours"""
    return await yahoo_client.get_company_info(symbol)

# Cache fundamentals (changes daily)
# Use Redis for distributed caching
await redis_client.setex(
    f"fundamentals:{symbol}",
    86400,  # 24 hours
    json.dumps(fundamentals.dict())
)
```

### Query Patterns

```sql
-- Get latest data from preferred source with fallback
SELECT 
    symbol,
    timestamp,
    close,
    volume,
    data_source
FROM data_ingestion.market_data
WHERE symbol = 'AAPL'
AND timestamp >= '2024-01-01'
AND data_source = COALESCE(
    (SELECT 'polygon' WHERE EXISTS (
        SELECT 1 FROM data_ingestion.market_data 
        WHERE symbol = 'AAPL' AND data_source = 'polygon'
    )),
    'yahoo'
)
ORDER BY timestamp DESC;

-- Compare prices across sources
SELECT 
    m1.symbol,
    m1.timestamp,
    m1.close as polygon_close,
    m2.close as yahoo_close,
    ABS(m1.close - m2.close) / m1.close * 100 as diff_pct
FROM data_ingestion.market_data m1
JOIN data_ingestion.market_data m2 
    ON m1.symbol = m2.symbol 
    AND m1.timestamp = m2.timestamp
WHERE m1.data_source = 'polygon'
AND m2.data_source = 'yahoo'
AND m1.symbol = 'AAPL'
AND ABS(m1.close - m2.close) / m1.close > 0.01  -- More than 1% difference
ORDER BY m1.timestamp DESC;

-- Get comprehensive company data
SELECT 
    c.symbol,
    c.name,
    c.sector,
    c.industry,
    k.market_cap,
    k.pe_ratio,
    k.earnings_per_share,
    k.dividend_yield
FROM data_ingestion.company_info c
LEFT JOIN data_ingestion.key_statistics k 
    ON c.symbol = k.symbol
WHERE k.date = (
    SELECT MAX(date) FROM data_ingestion.key_statistics
    WHERE symbol = c.symbol
)
AND c.sector = 'Technology'
ORDER BY k.market_cap DESC;
```

### Monitoring & Alerts

```python
# Set up alerts for data quality issues

async def monitor_data_loads():
    """Monitor daily data loads"""
    
    # Check for failed loads
    failed_loads = await get_failed_loads(date.today())
    if len(failed_loads) > 5:
        send_alert(f"Multiple failed loads: {len(failed_loads)}")
    
    # Check for stale data
    stale_symbols = await get_stale_symbols(max_age_days=2)
    if len(stale_symbols) > 10:
        send_alert(f"Stale data for {len(stale_symbols)} symbols")
    
    # Check for price discrepancies
    discrepancies = await compare_sources_today()
    if len(discrepancies) > 5:
        send_alert(f"Price discrepancies: {len(discrepancies)}")
```

---

## Related Documentation

- [Data Sources Overview](data-sources-overview.md): Multi-source architecture overview
- [Polygon.io Integration](data-sources-polygon.md): Detailed Polygon.io integration guide
- [Yahoo Finance Integration](data-sources-yahoo.md): Comprehensive Yahoo Finance integration guide
- [Implementation Plan](data-sources-implementation.md): Yahoo Finance implementation phases

---

**Last Updated**: 4/3/2026  
**Status**: ✅ Core Features Implemented (v1.0.0)

