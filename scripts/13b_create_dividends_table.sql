-- Create dividends table
-- Stores dividend payment history from Yahoo Finance

CREATE TABLE IF NOT EXISTS data_ingestion.dividends (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    ex_date DATE NOT NULL,
    amount NUMERIC(10, 4) NOT NULL,
    payment_date DATE,
    record_date DATE,
    dividend_type VARCHAR(20) DEFAULT 'regular',
    currency VARCHAR(10) DEFAULT 'USD',
    data_source VARCHAR(20) NOT NULL DEFAULT 'yahoo',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT fk_dividends_symbol 
        FOREIGN KEY (symbol) REFERENCES data_ingestion.symbols(symbol) 
        ON DELETE CASCADE,
    
    -- Unique constraint to prevent duplicates (same symbol can't have multiple dividends on same ex_date)
    CONSTRAINT uk_dividends_unique 
        UNIQUE (symbol, ex_date, data_source),
    
    -- Check constraints
    CONSTRAINT positive_amount CHECK (amount > 0),
    CONSTRAINT valid_dividend_type CHECK (dividend_type IN ('regular', 'special', 'stock', 'extra'))
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_dividends_symbol 
    ON data_ingestion.dividends(symbol);

CREATE INDEX IF NOT EXISTS idx_dividends_ex_date 
    ON data_ingestion.dividends(ex_date);

CREATE INDEX IF NOT EXISTS idx_dividends_symbol_ex_date 
    ON data_ingestion.dividends(symbol, ex_date DESC);

CREATE INDEX IF NOT EXISTS idx_dividends_payment_date 
    ON data_ingestion.dividends(payment_date);

CREATE INDEX IF NOT EXISTS idx_dividends_symbol_date_range 
    ON data_ingestion.dividends(symbol, ex_date DESC, payment_date);

-- Index for dividend yield calculations
CREATE INDEX IF NOT EXISTS idx_dividends_amount 
    ON data_ingestion.dividends(symbol, amount DESC);

-- Auto-update trigger
CREATE OR REPLACE FUNCTION update_dividends_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_dividends_updated_at
    BEFORE UPDATE ON data_ingestion.dividends
    FOR EACH ROW
    EXECUTE FUNCTION update_dividends_updated_at();

-- Add comments
COMMENT ON TABLE data_ingestion.dividends IS 'Dividend payment history from Yahoo Finance';
COMMENT ON COLUMN data_ingestion.dividends.symbol IS 'Stock symbol';
COMMENT ON COLUMN data_ingestion.dividends.ex_date IS 'Ex-dividend date (date when stock trades without dividend)';
COMMENT ON COLUMN data_ingestion.dividends.amount IS 'Dividend amount per share in dollars';
COMMENT ON COLUMN data_ingestion.dividends.payment_date IS 'Date when dividend is paid to shareholders';
COMMENT ON COLUMN data_ingestion.dividends.record_date IS 'Date of record for dividend eligibility';
COMMENT ON COLUMN data_ingestion.dividends.dividend_type IS 'Type of dividend: regular, special, stock, or extra';
COMMENT ON COLUMN data_ingestion.dividends.currency IS 'Currency code (e.g., USD, EUR)';
COMMENT ON COLUMN data_ingestion.dividends.data_source IS 'Data source (yahoo, polygon, etc.)';

