-- Create stock splits table
-- Stores stock split history from Yahoo Finance

CREATE TABLE IF NOT EXISTS data_ingestion.stock_splits (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    split_date DATE NOT NULL,
    split_ratio NUMERIC(10, 4) NOT NULL,
    ratio_str VARCHAR(20),
    data_source VARCHAR(20) NOT NULL DEFAULT 'yahoo',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT fk_stock_splits_symbol 
        FOREIGN KEY (symbol) REFERENCES data_ingestion.symbols(symbol) 
        ON DELETE CASCADE,
    
    -- Unique constraint to prevent duplicates (same symbol can't have multiple splits on same date)
    CONSTRAINT uk_stock_splits_unique 
        UNIQUE (symbol, split_date, data_source),
    
    -- Check constraints
    CONSTRAINT positive_ratio CHECK (split_ratio > 0)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_stock_splits_symbol 
    ON data_ingestion.stock_splits(symbol);

CREATE INDEX IF NOT EXISTS idx_stock_splits_split_date 
    ON data_ingestion.stock_splits(split_date);

CREATE INDEX IF NOT EXISTS idx_stock_splits_symbol_split_date 
    ON data_ingestion.stock_splits(symbol, split_date DESC);

-- Index for split ratio queries
CREATE INDEX IF NOT EXISTS idx_stock_splits_ratio 
    ON data_ingestion.stock_splits(symbol, split_ratio DESC);

-- Auto-update trigger
CREATE OR REPLACE FUNCTION update_stock_splits_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_stock_splits_updated_at
    BEFORE UPDATE ON data_ingestion.stock_splits
    FOR EACH ROW
    EXECUTE FUNCTION update_stock_splits_updated_at();

-- Add comments
COMMENT ON TABLE data_ingestion.stock_splits IS 'Stock split history from Yahoo Finance';
COMMENT ON COLUMN data_ingestion.stock_splits.symbol IS 'Stock symbol';
COMMENT ON COLUMN data_ingestion.stock_splits.split_date IS 'Date when stock split occurred';
COMMENT ON COLUMN data_ingestion.stock_splits.split_ratio IS 'Numeric split ratio (e.g., 2.0 for 2:1 split, 0.5 for 1:2 reverse split)';
COMMENT ON COLUMN data_ingestion.stock_splits.ratio_str IS 'Human-readable ratio string (e.g., "2:1", "7:1", "1:2")';
COMMENT ON COLUMN data_ingestion.stock_splits.data_source IS 'Data source (yahoo, polygon, etc.)';

