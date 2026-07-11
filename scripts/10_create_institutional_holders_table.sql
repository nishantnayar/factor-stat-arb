-- Migration: Create institutional_holders table for Yahoo Finance data
-- Author: Trading System
-- Date: 2025-10-12
-- Description: Stores institutional ownership information for stocks

-- Create table for institutional holders
CREATE TABLE IF NOT EXISTS data_ingestion.institutional_holders (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    date_reported DATE NOT NULL,
    holder_name VARCHAR(255) NOT NULL,
    shares BIGINT,
    value BIGINT,
    percent_held NUMERIC(10, 4),
    data_source VARCHAR(50) DEFAULT 'yahoo',
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT institutional_holders_symbol_holder_date_key UNIQUE (symbol, holder_name, date_reported),
    CONSTRAINT institutional_holders_symbol_fkey FOREIGN KEY (symbol) 
        REFERENCES data_ingestion.symbols(symbol) ON DELETE CASCADE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_institutional_holders_symbol ON data_ingestion.institutional_holders(symbol);
CREATE INDEX IF NOT EXISTS idx_institutional_holders_date ON data_ingestion.institutional_holders(date_reported);
CREATE INDEX IF NOT EXISTS idx_institutional_holders_symbol_date ON data_ingestion.institutional_holders(symbol, date_reported);
CREATE INDEX IF NOT EXISTS idx_institutional_holders_holder_name ON data_ingestion.institutional_holders(holder_name);

-- Create index for top holders queries
CREATE INDEX IF NOT EXISTS idx_institutional_holders_shares ON data_ingestion.institutional_holders(symbol, shares DESC);
CREATE INDEX IF NOT EXISTS idx_institutional_holders_percent ON data_ingestion.institutional_holders(symbol, percent_held DESC);

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_institutional_holders_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_institutional_holders_updated_at
    BEFORE UPDATE ON data_ingestion.institutional_holders
    FOR EACH ROW
    EXECUTE FUNCTION update_institutional_holders_updated_at();

-- Add comments
COMMENT ON TABLE data_ingestion.institutional_holders IS 'Institutional ownership data from Yahoo Finance';
COMMENT ON COLUMN data_ingestion.institutional_holders.symbol IS 'Stock ticker symbol';
COMMENT ON COLUMN data_ingestion.institutional_holders.date_reported IS 'Date when holding was reported';
COMMENT ON COLUMN data_ingestion.institutional_holders.holder_name IS 'Name of the institutional holder';
COMMENT ON COLUMN data_ingestion.institutional_holders.shares IS 'Number of shares held';
COMMENT ON COLUMN data_ingestion.institutional_holders.value IS 'Dollar value of the holding';
COMMENT ON COLUMN data_ingestion.institutional_holders.percent_held IS 'Percentage of total shares (decimal, e.g., 0.05 = 5%)';

