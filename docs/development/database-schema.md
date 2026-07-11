# Database Schema Documentation

## Overview

This document provides detailed schema definitions for all database tables in the trading system. For architecture overview and setup, see [Database Overview](database-overview.md). For performance optimization and ORM patterns, see [Database Optimization](database-optimization.md).

**Last Updated**: 4/3/2026  
**Status**: ✅ Core Schema Implemented (v1.0.0); market_data supports yahoo + yahoo_adjusted  
**Author**: Nishant Nayar

## Core Trading Tables

### Market Data Table

```sql
CREATE TABLE data_ingestion.market_data (
    id BIGSERIAL,
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    data_source VARCHAR(20) NOT NULL DEFAULT 'polygon',  -- 'yahoo', 'yahoo_adjusted', 'alpaca', etc.
    open DECIMAL(15,4),
    high DECIMAL(15,4),
    low DECIMAL(15,4),
    close DECIMAL(15,4),
    volume BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints: (symbol, timestamp, data_source) allows multiple series per symbol/timestamp
    CONSTRAINT unique_symbol_timestamp_source UNIQUE (symbol, timestamp, data_source),
    CONSTRAINT valid_data_source CHECK (data_source IN (
        'polygon', 'yahoo', 'yahoo_adjusted', 'alpaca', 'alpha_vantage', 'iex', 'quandl'
    ))
);

-- Indexes for performance
CREATE INDEX idx_market_data_symbol_timestamp ON data_ingestion.market_data(symbol, timestamp DESC);
CREATE INDEX idx_market_data_data_source ON data_ingestion.market_data(data_source);
CREATE INDEX idx_market_data_symbol_source_timestamp ON data_ingestion.market_data(symbol, data_source, timestamp DESC);
```

**Design Features:**

1. **Multi-source**: `data_source` identifies provider; Yahoo stores both `yahoo` (unadjusted) and `yahoo_adjusted` (split/dividend-adjusted) for the same symbol/timestamp.
2. **Unique constraint**: `(symbol, timestamp, data_source)` — run `scripts/20_market_data_allow_yahoo_adjusted.sql` if upgrading from the old `(symbol, timestamp)` constraint.
3. **Increased Precision**: DECIMAL(15,4) for high-priced stocks.
4. **Comprehensive Indexing**: Composite indexes for time-series and source-filtered queries.

### Key Statistics Table

Stores comprehensive financial metrics and fundamental data from Yahoo Finance for stock screening and analysis.

```sql
CREATE TABLE data_ingestion.key_statistics (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    data_source VARCHAR(50) DEFAULT 'yahoo',
    
    -- Valuation Metrics (9 fields)
    market_cap BIGINT,
    enterprise_value BIGINT,
    trailing_pe NUMERIC(10, 2),
    forward_pe NUMERIC(10, 2),
    peg_ratio NUMERIC(10, 2),
    price_to_book NUMERIC(10, 2),
    price_to_sales NUMERIC(10, 2),
    enterprise_to_revenue NUMERIC(10, 2),
    enterprise_to_ebitda NUMERIC(10, 2),
    
    -- Profitability Metrics (6 fields, stored as decimals: 0.15 = 15%)
    profit_margin NUMERIC(10, 4),
    operating_margin NUMERIC(10, 4),
    return_on_assets NUMERIC(10, 4),
    return_on_equity NUMERIC(10, 4),
    gross_margin NUMERIC(10, 4),
    ebitda_margin NUMERIC(10, 4),
    
    -- Financial Health (10 fields)
    revenue BIGINT,
    revenue_per_share NUMERIC(10, 2),
    earnings_per_share NUMERIC(10, 2),
    total_cash BIGINT,
    total_debt BIGINT,
    debt_to_equity NUMERIC(10, 2),
    current_ratio NUMERIC(10, 2),
    quick_ratio NUMERIC(10, 2),
    free_cash_flow BIGINT,
    operating_cash_flow BIGINT,
    
    -- Growth Metrics (2 fields, stored as decimals)
    revenue_growth NUMERIC(10, 4),
    earnings_growth NUMERIC(10, 4),
    
    -- Trading Metrics (6 fields)
    beta NUMERIC(10, 2),
    fifty_two_week_high NUMERIC(10, 2),
    fifty_two_week_low NUMERIC(10, 2),
    fifty_day_average NUMERIC(10, 2),
    two_hundred_day_average NUMERIC(10, 2),
    average_volume BIGINT,
    
    -- Dividend Metrics (3 fields, stored as decimals)
    dividend_yield NUMERIC(10, 4),
    dividend_rate NUMERIC(10, 2),
    payout_ratio NUMERIC(10, 4),
    
    -- Share Information (6 fields)
    shares_outstanding BIGINT,
    float_shares BIGINT,
    shares_short BIGINT,
    short_ratio NUMERIC(10, 2),
    held_percent_insiders NUMERIC(10, 4),
    held_percent_institutions NUMERIC(10, 4),
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT key_statistics_symbol_date_source_key UNIQUE (symbol, date, data_source),
    CONSTRAINT key_statistics_symbol_fkey FOREIGN KEY (symbol) 
        REFERENCES data_ingestion.symbols(symbol) ON DELETE CASCADE
);

-- Performance indexes
CREATE INDEX idx_key_statistics_symbol ON data_ingestion.key_statistics(symbol);
CREATE INDEX idx_key_statistics_date ON data_ingestion.key_statistics(date);
CREATE INDEX idx_key_statistics_symbol_date ON data_ingestion.key_statistics(symbol, date);

-- Screening indexes for common queries
CREATE INDEX idx_key_statistics_valuation 
    ON data_ingestion.key_statistics(trailing_pe, price_to_book, market_cap);
CREATE INDEX idx_key_statistics_profitability 
    ON data_ingestion.key_statistics(return_on_equity, profit_margin);

-- Auto-update trigger
CREATE OR REPLACE FUNCTION update_key_statistics_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_key_statistics_updated_at
    BEFORE UPDATE ON data_ingestion.key_statistics
    FOR EACH ROW
    EXECUTE FUNCTION update_key_statistics_updated_at();
```

**Design Features:**

1. **Comprehensive Metrics**: 50+ financial indicators covering valuation, profitability, growth, and trading
2. **Screening Optimization**: Dedicated indexes for common stock screening queries
3. **Decimal Precision**: NUMERIC(10,4) for percentage values, NUMERIC(10,2) for ratios
4. **Data Integrity**: Unique constraint on (symbol, date, data_source) prevents duplicates
5. **Automatic Updates**: Trigger maintains updated_at timestamp
6. **Cascade Delete**: Foreign key ensures referential integrity with symbols table

**Use Cases:**

- Stock screening and filtering based on fundamental metrics
- Historical fundamental analysis and trend tracking
- Portfolio fundamental assessment
- Value/growth stock identification
- Risk assessment based on financial health metrics

**Migration Location**: `scripts/09_create_key_statistics_table.sql`  
**SQLAlchemy Model**: `src/shared/database/models/key_statistics.py`

### Institutional Holders Table

Stores institutional ownership data from Yahoo Finance, tracking major shareholders like investment firms, mutual funds, and pension funds.

```sql
CREATE TABLE data_ingestion.institutional_holders (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    date_reported DATE NOT NULL,
    holder_name VARCHAR(255) NOT NULL,
    shares BIGINT,
    value BIGINT,
    percent_held NUMERIC(10, 4),
    data_source VARCHAR(50) DEFAULT 'yahoo',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT institutional_holders_symbol_holder_date_key UNIQUE (symbol, holder_name, date_reported),
    CONSTRAINT institutional_holders_symbol_fkey FOREIGN KEY (symbol) 
        REFERENCES data_ingestion.symbols(symbol) ON DELETE CASCADE
);

-- Performance indexes
CREATE INDEX idx_institutional_holders_symbol ON data_ingestion.institutional_holders(symbol);
CREATE INDEX idx_institutional_holders_date ON data_ingestion.institutional_holders(date_reported);
CREATE INDEX idx_institutional_holders_shares ON data_ingestion.institutional_holders(symbol, shares DESC);
CREATE INDEX idx_institutional_holders_percent ON data_ingestion.institutional_holders(symbol, percent_held DESC);
```

**Design Features:**

1. **Ownership Tracking**: Captures major institutional shareholders and their positions
2. **Historical Data**: Tracks ownership changes over time via date_reported
3. **Top Holders Optimization**: Indexes for quickly finding largest shareholders
4. **Unique Constraint**: Prevents duplicates based on (symbol, holder_name, date_reported)
5. **Value Tracking**: Stores both share count and dollar value of holdings

**Use Cases:**

- Identifying major shareholders and ownership concentration
- Tracking institutional buying/selling trends
- Analyzing ownership structure for risk assessment
- Monitoring whale movements and institutional sentiment

**Migration Location**: `scripts/10_create_institutional_holders_table.sql`  
**SQLAlchemy Model**: `src/shared/database/models/institutional_holders.py`

## Analytics Schema Tables

### Technical Indicators Tables

Technical indicators are calculated/derived metrics from market data, used across the system for:
- **Stock Screening**: Fast filtering by RSI, moving averages, volatility
- **Analysis Page**: Displaying current indicator values
- **Strategy Engine**: Signal generation based on technical analysis
- **Backtesting**: Historical indicator values for strategy testing
- **Portfolio Analysis**: Performance metrics and risk assessment

**Schema Decision**: Stored in `analytics` schema (not `data_ingestion`) because they are calculated/derived metrics, not raw ingested data.

**Data Source**: Technical indicators are calculated using **only Yahoo Finance data** (`data_source = 'yahoo'`) from the `market_data` table. This ensures:
- Consistent data source for all calculations
- Single source of truth for technical analysis
- Avoids mixing data from different providers (Yahoo vs Polygon)
- Yahoo data is typically more complete for daily OHLCV data

**Architecture**: Hybrid approach with two tables:
1. **`technical_indicators_latest`**: Latest values for fast screening queries
2. **`technical_indicators`**: Historical time-series for analysis and backtesting

**Latest Values Table** (for fast screening):
```sql
CREATE TABLE analytics.technical_indicators_latest (
    symbol VARCHAR(20) PRIMARY KEY,
    calculated_date DATE NOT NULL,
    
    -- Moving Averages
    sma_20 NUMERIC(15,4),
    sma_50 NUMERIC(15,4),
    sma_200 NUMERIC(15,4),
    ema_12 NUMERIC(15,4),
    ema_26 NUMERIC(15,4),
    ema_50 NUMERIC(15,4),
    
    -- Momentum Indicators
    rsi NUMERIC(5,2),  -- 0-100
    rsi_14 NUMERIC(5,2),  -- Explicit 14-period RSI
    
    -- MACD
    macd_line NUMERIC(15,4),
    macd_signal NUMERIC(15,4),
    macd_histogram NUMERIC(15,4),
    
    -- Bollinger Bands
    bb_upper NUMERIC(15,4),
    bb_middle NUMERIC(15,4),
    bb_lower NUMERIC(15,4),
    bb_position NUMERIC(5,4),  -- Position within bands (0-1)
    bb_width NUMERIC(10,4),  -- Band width as percentage
    
    -- Volatility & Price Changes
    volatility_20 NUMERIC(5,2),  -- Annualized volatility percentage
    price_change_1d NUMERIC(5,2),
    price_change_5d NUMERIC(5,2),
    price_change_30d NUMERIC(5,2),
    
    -- Volume Indicators
    avg_volume_20 BIGINT,
    current_volume BIGINT,
    
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT technical_indicators_latest_symbol_fkey 
        FOREIGN KEY (symbol) 
        REFERENCES data_ingestion.symbols(symbol) 
        ON DELETE CASCADE
);
```

**Time-Series Table** (for historical analysis):
```sql
CREATE TABLE analytics.technical_indicators (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    
    -- Same indicator fields as latest table
    -- Moving Averages: sma_20, sma_50, sma_200, ema_12, ema_26, ema_50
    -- Momentum: rsi, rsi_14
    -- MACD: macd_line, macd_signal, macd_histogram
    -- Bollinger Bands: bb_upper, bb_middle, bb_lower, bb_position, bb_width
    -- Volatility & Price Changes: volatility_20, price_change_1d, price_change_5d, price_change_30d
    -- Volume: avg_volume_20, current_volume
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_symbol_date UNIQUE (symbol, date),
    CONSTRAINT technical_indicators_symbol_fkey 
        FOREIGN KEY (symbol) 
        REFERENCES data_ingestion.symbols(symbol) 
        ON DELETE CASCADE
);
```

**Design Features:**

1. **Hybrid Storage**: Latest values for fast queries + time-series for historical analysis
2. **Yahoo Data Only**: Calculations use only `data_source = 'yahoo'` from market_data table
3. **Performance Optimization**: Indexes on commonly filtered fields (RSI, SMA, volatility)
4. **Calculation Fallback**: UI can calculate on-the-fly if database values are missing
5. **Daily Updates**: Calculated after market close via scheduled Prefect flows
6. **Incremental Updates**: Only calculates for new market data, skips if already calculated

**Use Cases:**

- Fast stock screening by technical criteria (RSI < 30, price above SMA 50, etc.)
- Displaying current indicator values in Analysis page
- Historical backtesting with time-series indicator data
- Strategy signal generation based on technical analysis
- Portfolio risk assessment using volatility metrics

**Performance Benefits:**

| Approach | Symbols/Second | Storage | Scalability |
|----------|---------------|---------|-------------|
| **On-the-fly Calculation** | 0.5-1 | None | Limited (50 symbols) |
| **Database Storage** | 10-50 | ~50-100 bytes/symbol/day | Excellent (1000+ symbols) |

**Migration Location**: `scripts/17_create_technical_indicators_tables.sql`  
**SQLAlchemy Model**: `src/shared/database/models/technical_indicators.py` (Pending)  
**Calculation Service**: `src/services/analytics/indicator_calculator.py` (Pending)

### Orders Table

```sql
CREATE TYPE order_side AS ENUM ('buy', 'sell');
CREATE TYPE order_type AS ENUM ('market', 'limit', 'stop', 'stop_limit');
CREATE TYPE order_status AS ENUM ('pending', 'submitted', 'filled', 'partially_filled', 'cancelled', 'rejected');
CREATE TYPE time_in_force AS ENUM ('day', 'gtc', 'ioc', 'fok');

CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    order_id VARCHAR(100) UNIQUE NOT NULL,
    account_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side order_side NOT NULL,
    order_type order_type NOT NULL,
    quantity DECIMAL(15,4) NOT NULL,
    price DECIMAL(15,4),
    stop_price DECIMAL(15,4),
    time_in_force time_in_force DEFAULT 'day',
    status order_status NOT NULL DEFAULT 'pending',
    strategy VARCHAR(100),
    session_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT positive_quantity CHECK (quantity > 0),
    CONSTRAINT valid_price CHECK (price IS NULL OR price > 0),
    CONSTRAINT valid_stop_price CHECK (stop_price IS NULL OR stop_price > 0)
);

-- Indexes
CREATE INDEX idx_orders_symbol_status ON orders(symbol, status);
CREATE INDEX idx_orders_strategy ON orders(strategy);
CREATE INDEX idx_orders_created_at ON orders(created_at DESC);
CREATE INDEX idx_orders_account_id ON orders(account_id);
```

### Trades Table

```sql
CREATE TABLE trades (
    id BIGSERIAL PRIMARY KEY,
    trade_id VARCHAR(100) UNIQUE NOT NULL,
    order_id VARCHAR(100) REFERENCES orders(order_id),
    account_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    quantity DECIMAL(15,4) NOT NULL,
    price DECIMAL(15,4) NOT NULL,
    commission DECIMAL(10,4) DEFAULT 0,
    executed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    settlement_date DATE,
    strategy VARCHAR(100),
    trade_type VARCHAR(20), -- 'opening', 'closing', 'partial'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT positive_quantity CHECK (quantity > 0),
    CONSTRAINT positive_price CHECK (price > 0),
    CONSTRAINT non_negative_commission CHECK (commission >= 0)
);

-- Indexes
CREATE INDEX idx_trades_symbol_executed_at ON trades(symbol, executed_at DESC);
CREATE INDEX idx_trades_strategy ON trades(strategy);
CREATE INDEX idx_trades_account_id ON trades(account_id);
```

### Positions Table

```sql
CREATE TABLE positions (
    id BIGSERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    quantity DECIMAL(15,4) NOT NULL,
    avg_price DECIMAL(15,4) NOT NULL,
    market_value DECIMAL(15,4),
    unrealized_pnl DECIMAL(15,4),
    realized_pnl DECIMAL(15,4) DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_account_symbol UNIQUE (account_id, symbol),
    CONSTRAINT non_negative_quantity CHECK (quantity >= 0)
);

-- Indexes
CREATE INDEX idx_positions_account_id ON positions(account_id);
CREATE INDEX idx_positions_symbol ON positions(symbol);
CREATE INDEX idx_positions_last_updated ON positions(last_updated DESC);
```

---

**See Also**:
- [Database Overview](database-overview.md) - Architecture overview and setup
- [Database Optimization](database-optimization.md) - Performance tuning and ORM patterns

