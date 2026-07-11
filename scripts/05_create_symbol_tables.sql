-- Create symbol management tables
-- This script creates tables for tracking active symbols, delisted symbols, and data ingestion status

-- Main symbols table
CREATE TABLE IF NOT EXISTS data_ingestion.symbols (
    symbol VARCHAR(10) PRIMARY KEY,
    name VARCHAR(255),
    exchange VARCHAR(50),
    sector VARCHAR(100),
    market_cap BIGINT,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'delisted', 'suspended')),
    added_date TIMESTAMP DEFAULT NOW(),
    last_updated TIMESTAMP DEFAULT NOW()
);

-- Delisting tracking table
CREATE TABLE IF NOT EXISTS data_ingestion.delisted_symbols (
    symbol VARCHAR(10) PRIMARY KEY,
    delist_date DATE,
    last_price DECIMAL(10,2),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Data ingestion tracking table
CREATE TABLE IF NOT EXISTS data_ingestion.symbol_data_status (
    symbol VARCHAR(10),
    date DATE,
    data_source VARCHAR(50),
    status VARCHAR(20) CHECK (status IN ('success', 'failed', 'no_data')),
    error_message TEXT,
    last_attempt TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (symbol, date, data_source)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_symbols_status ON data_ingestion.symbols(status);
CREATE INDEX IF NOT EXISTS idx_symbols_exchange ON data_ingestion.symbols(exchange);
CREATE INDEX IF NOT EXISTS idx_delisted_symbols_date ON data_ingestion.delisted_symbols(delist_date);
CREATE INDEX IF NOT EXISTS idx_symbol_data_status_symbol ON data_ingestion.symbol_data_status(symbol);
CREATE INDEX IF NOT EXISTS idx_symbol_data_status_date ON data_ingestion.symbol_data_status(date);

-- Comments for documentation
COMMENT ON TABLE data_ingestion.symbols IS 'Active symbols being tracked for data ingestion';
COMMENT ON TABLE data_ingestion.delisted_symbols IS 'Symbols that have been delisted from exchanges';
COMMENT ON TABLE data_ingestion.symbol_data_status IS 'Tracking data ingestion status for each symbol and date';

COMMENT ON COLUMN data_ingestion.symbols.status IS 'Symbol status: active, delisted, suspended';
COMMENT ON COLUMN data_ingestion.symbols.market_cap IS 'Market capitalization in dollars';
COMMENT ON COLUMN data_ingestion.delisted_symbols.delist_date IS 'Date when symbol was delisted';
COMMENT ON COLUMN data_ingestion.delisted_symbols.last_price IS 'Last known price before delisting';
COMMENT ON COLUMN data_ingestion.symbol_data_status.data_source IS 'Data source: polygon, alpaca, etc.';
COMMENT ON COLUMN data_ingestion.symbol_data_status.status IS 'Ingestion status: success, failed, no_data';
