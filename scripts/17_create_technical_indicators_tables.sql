-- Migration: Create technical_indicators tables for storing calculated technical indicators
-- Author: Trading System
-- Date: 2025-01-XX
-- Description: Stores technical indicators (RSI, MACD, SMA, EMA, Bollinger Bands, etc.)
--              Uses hybrid approach: latest values table for fast screening + time-series table for historical analysis

-- ============================================================================
-- Table 1: technical_indicators_latest
-- Purpose: Store latest indicator values for fast screening queries
-- ============================================================================
CREATE TABLE IF NOT EXISTS analytics.technical_indicators_latest (
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
    price_change_1d NUMERIC(5,2),  -- 1-day price change percentage
    price_change_5d NUMERIC(5,2),  -- 5-day price change percentage
    price_change_30d NUMERIC(5,2),  -- 30-day price change percentage
    
    -- Volume Indicators
    avg_volume_20 BIGINT,  -- 20-day average volume
    current_volume BIGINT,  -- Most recent volume
    
    -- Metadata
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign Key
    CONSTRAINT technical_indicators_latest_symbol_fkey 
        FOREIGN KEY (symbol) 
        REFERENCES data_ingestion.symbols(symbol) 
        ON DELETE CASCADE
);

-- Indexes for technical_indicators_latest
CREATE INDEX IF NOT EXISTS idx_technical_indicators_latest_date 
    ON analytics.technical_indicators_latest(calculated_date);
CREATE INDEX IF NOT EXISTS idx_technical_indicators_latest_rsi 
    ON analytics.technical_indicators_latest(rsi);
CREATE INDEX IF NOT EXISTS idx_technical_indicators_latest_sma_20 
    ON analytics.technical_indicators_latest(sma_20);
CREATE INDEX IF NOT EXISTS idx_technical_indicators_latest_volatility 
    ON analytics.technical_indicators_latest(volatility_20);

-- ============================================================================
-- Table 2: technical_indicators (Time-Series)
-- Purpose: Store historical indicator values for analysis and backtesting
-- ============================================================================
CREATE TABLE IF NOT EXISTS analytics.technical_indicators (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    
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
    price_change_1d NUMERIC(5,2),  -- 1-day price change percentage
    price_change_5d NUMERIC(5,2),  -- 5-day price change percentage
    price_change_30d NUMERIC(5,2),  -- 30-day price change percentage
    
    -- Volume Indicators
    avg_volume_20 BIGINT,  -- 20-day average volume
    current_volume BIGINT,  -- Volume for this date
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT technical_indicators_symbol_date_key 
        UNIQUE (symbol, date),
    CONSTRAINT technical_indicators_symbol_fkey 
        FOREIGN KEY (symbol) 
        REFERENCES data_ingestion.symbols(symbol) 
        ON DELETE CASCADE
);

-- Indexes for technical_indicators (time-series)
CREATE INDEX IF NOT EXISTS idx_technical_indicators_symbol 
    ON analytics.technical_indicators(symbol);
CREATE INDEX IF NOT EXISTS idx_technical_indicators_date 
    ON analytics.technical_indicators(date DESC);
CREATE INDEX IF NOT EXISTS idx_technical_indicators_symbol_date 
    ON analytics.technical_indicators(symbol, date DESC);
CREATE INDEX IF NOT EXISTS idx_technical_indicators_rsi 
    ON analytics.technical_indicators(rsi);
CREATE INDEX IF NOT EXISTS idx_technical_indicators_sma_20 
    ON analytics.technical_indicators(sma_20);

-- ============================================================================
-- Triggers
-- ============================================================================

-- Trigger to update updated_at timestamp for latest table
CREATE OR REPLACE FUNCTION update_technical_indicators_latest_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_technical_indicators_latest_updated_at
    BEFORE UPDATE ON analytics.technical_indicators_latest
    FOR EACH ROW
    EXECUTE FUNCTION update_technical_indicators_latest_updated_at();

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE analytics.technical_indicators_latest IS 
    'Latest technical indicator values for fast screening queries. Updated daily after market close.';

COMMENT ON TABLE analytics.technical_indicators IS 
    'Historical time-series of technical indicators for analysis and backtesting.';

COMMENT ON COLUMN analytics.technical_indicators_latest.symbol IS 
    'Stock ticker symbol (primary key)';
COMMENT ON COLUMN analytics.technical_indicators_latest.calculated_date IS 
    'Date for which indicators were calculated (usually most recent trading day)';
COMMENT ON COLUMN analytics.technical_indicators_latest.rsi IS 
    'Relative Strength Index (0-100, typically 14-period)';
COMMENT ON COLUMN analytics.technical_indicators_latest.macd_line IS 
    'MACD line value (fast EMA - slow EMA)';
COMMENT ON COLUMN analytics.technical_indicators_latest.bb_position IS 
    'Position within Bollinger Bands (0 = lower band, 1 = upper band)';
COMMENT ON COLUMN analytics.technical_indicators_latest.volatility_20 IS 
    'Annualized volatility percentage based on 20-day rolling window';

COMMENT ON COLUMN analytics.technical_indicators.symbol IS 
    'Stock ticker symbol';
COMMENT ON COLUMN analytics.technical_indicators.date IS 
    'Trading date for which indicators were calculated';

-- ============================================================================
-- Permissions (adjust as needed for your setup)
-- ============================================================================
-- GRANT SELECT, INSERT, UPDATE, DELETE ON analytics.technical_indicators_latest TO trading_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON analytics.technical_indicators TO trading_app;
-- GRANT USAGE, SELECT ON SEQUENCE analytics.technical_indicators_id_seq TO trading_app;

