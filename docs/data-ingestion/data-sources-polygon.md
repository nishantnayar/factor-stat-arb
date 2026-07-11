# Polygon.io Integration

> **📋 Implementation Status**: ✅ Core Features Implemented (v1.0.0)

This document details the Polygon.io integration for high-quality, real-time market data.

---

## Overview

Polygon.io is the primary data source for high-quality, real-time market data. Ideal for production trading systems requiring accuracy and reliability.

### Features

- **Historical OHLCV**: Minute, hour, day, week, month aggregates
- **Real-time Data**: WebSocket streaming (paid plans)
- **Corporate Actions**: Dividends, splits
- **Adjusted Data**: Split-adjusted and dividend-adjusted prices
- **Tick Data**: Individual trades and quotes (paid plans)

---

## Configuration

```bash
# Environment variables
POLYGON_API_KEY=your_api_key_here
POLYGON_BASE_URL=https://api.polygon.io
```

---

## Usage

```python
from src.services.data_ingestion.historical_loader import HistoricalDataLoader

# Initialize loader for Polygon (default)
loader = HistoricalDataLoader(
    batch_size=100,
    requests_per_minute=2,  # Free tier limit
    data_source="polygon"
)

# Load data
await loader.load_symbol_data(
    symbol="AAPL",
    days_back=30,
    timespan="day"
)
```

---

## CLI

```bash
# Load Polygon data
python scripts/load_historical_data.py --symbol AAPL --days-back 30
```

---

## Rate Limits

- **Free Tier**: 5 requests/minute
- **Starter Plan**: 100 requests/minute
- **Developer Plan**: Unlimited

---

## Best Use Cases

- ✅ Production trading systems
- ✅ High-frequency data needs
- ✅ Real-time streaming
- ✅ Accurate corporate actions
- ❌ High-volume backtesting (expensive)
- ❌ Fundamental analysis (not available)

---

## Related Documentation

- [Data Sources Overview](data-sources-overview.md): Multi-source architecture overview
- [Data Source Comparison](data-sources-comparison.md): Feature comparison with other sources
- [API Reference: Polygon.io Integration](../api/data-ingestion-polygon.md): Detailed API documentation

---

**Last Updated**: 4/3/2026  
**Status**: ✅ Core Features Implemented (v1.0.0)

