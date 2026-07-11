# Data Sources Overview

> **📋 Implementation Status**: ✅ Core Features Implemented (v1.0.0)

This document provides a high-level overview of the multi-source data integration architecture for the trading system.

---

## Overview

The trading system supports multiple market data sources to provide:

- **Redundancy**: Backup sources if one fails
- **Data Validation**: Cross-validate data between sources
- **Rich Data**: Different sources provide different data types
- **Cost Optimization**: Use free sources where possible
- **Flexibility**: Choose best source for each use case

### Supported Data Sources

| Source | OHLCV | Fundamentals | Dividends | Splits | Real-time | Role | Cost |
|--------|-------|--------------|-----------|---------|-----------|------|------|
| **Yahoo Finance** | ✅ | ✅ | ✅ | ✅ | ⚠️ Delayed | **Primary price data** | Free (Unlimited) |
| **Polygon.io** | ✅ | ❌ | ✅ | ✅ | ✅ | Historical research | Paid (Free tier: 5 calls/min) |
| **Alpaca** | ❌* | ❌ | ❌ | ❌ | ✅ | **Order execution only** | Free with account |

> **Important (updated 2026-04-03)**: Alpaca is used **only for order placement** (`place_order`, `get_positions`, `get_clock`). All price data — including intraday bars for the live strategy — comes from Yahoo Finance via `yfinance`.

For detailed integration guides, see:
- [Polygon.io Integration](data-sources-polygon.md)
- [Yahoo Finance Integration](data-sources-yahoo.md)
- [Data Source Comparison](data-sources-comparison.md)

---

## Multi-Source Architecture

### Design Principles

1. **Independent Services**: Each data source has its own service module
2. **Unified Storage**: All market data stored in `data_ingestion.market_data` with a `data_source` field
3. **Source Tracking**: Track which provider supplied each data point
4. **Separate Loaders**: Each source has dedicated loader class
5. **Consistent Interface**: Similar API patterns across sources

### `data_source` Values in `market_data`

| Value | Written by | Used by | Notes |
|---|---|---|---|
| `yahoo_adjusted` | Daily Prefect flow, backpopulate scripts | Backtesting, indicators, pair discovery | EOD/multi-day adjusted bars |
| `yahoo_adjusted_1h` | `refresh_pair_prices_task` in `pairs_flow.py` | `get_price_series()` in pairs strategy | Intraday 1h bars, refreshed before each hourly cycle |
| `yahoo` | Daily Prefect flow | General market data | Unadjusted bars |
| `polygon` | Polygon ingestion flow | Research / historical | Requires paid Polygon.io account |

> **DB migration required**: Run `scripts/21_add_yahoo_adjusted_1h_source.sql` to add `yahoo_adjusted_1h` to the `data_source` CHECK constraint before running the live strategy.

### Directory Structure

```
src/services/
├── polygon/
│   ├── __init__.py
│   ├── client.py           # PolygonClient
│   ├── exceptions.py       # Polygon-specific exceptions
│   └── models.py           # Pydantic models
│
├── yahoo/
│   ├── __init__.py
│   ├── client.py           # YahooClient
│   ├── exceptions.py       # Yahoo-specific exceptions
│   ├── models.py           # Pydantic models
│   └── loader.py           # YahooDataLoader
│
├── alpaca/
│   ├── __init__.py
│   ├── client.py           # AlpacaClient
│   └── exceptions.py
│
└── data_ingestion/
    ├── __init__.py
    ├── historical_loader.py  # HistoricalDataLoader (Polygon)
    └── symbols.py
```

### Data Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────────┐
│  Polygon.io │────▶│ PolygonClient│────▶│ HistoricalDataLoader│
└─────────────┘     └──────────────┘     └─────────────────────┘
                                                    │
                                                    │
┌─────────────┐     ┌──────────────┐     ┌─────────▼─────────┐
│Yahoo Finance│────▶│ YahooClient  │────▶│ YahooDataLoader   │
└─────────────┘     └──────────────┘     └───────────────────┘
                                                    │
                                                    │
┌─────────────┐     ┌──────────────┐               │
│   Alpaca    │────▶│ AlpacaClient │               │
└─────────────┘     └──────────────┘               │
                                                    │
                                         ┌──────────▼──────────┐
                                         │   PostgreSQL DB     │
                                         │  ┌──────────────┐   │
                                         │  │ market_data  │   │
                                         │  │ fundamentals │   │
                                         │  │ dividends    │   │
                                         │  │ splits       │   │
                                         │  └──────────────┘   │
                                         └─────────────────────┘
```

---

## Related Documentation

- [Polygon.io Integration](data-sources-polygon.md): Detailed Polygon.io integration guide
- [Yahoo Finance Integration](data-sources-yahoo.md): Comprehensive Yahoo Finance integration guide
- [Data Source Comparison](data-sources-comparison.md): Feature comparison and best practices
- [Implementation Plan](data-sources-implementation.md): Yahoo Finance implementation phases

---

**Last Updated**: 4/3/2026  
**Status**: ✅ Core Features Implemented (v1.0.0)

