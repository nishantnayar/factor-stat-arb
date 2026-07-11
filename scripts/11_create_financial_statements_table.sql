-- Create financial statements table
-- Stores income statements, balance sheets, and cash flow statements

CREATE TABLE IF NOT EXISTS data_ingestion.financial_statements (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    period_end DATE NOT NULL,
    statement_type VARCHAR(20) NOT NULL CHECK (statement_type IN ('income', 'balance_sheet', 'cash_flow')),
    period_type VARCHAR(10) NOT NULL CHECK (period_type IN ('annual', 'quarterly', 'ttm')),
    fiscal_year INTEGER,
    fiscal_quarter INTEGER,
    data JSONB NOT NULL DEFAULT '{}',
    data_source VARCHAR(20) NOT NULL DEFAULT 'yahoo',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT fk_financial_statements_symbol 
        FOREIGN KEY (symbol) REFERENCES data_ingestion.symbols(symbol) 
        ON DELETE CASCADE,
    
    -- Unique constraint to prevent duplicates
    CONSTRAINT uk_financial_statements_unique 
        UNIQUE (symbol, period_end, statement_type, period_type)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_financial_statements_symbol 
    ON data_ingestion.financial_statements(symbol);

CREATE INDEX IF NOT EXISTS idx_financial_statements_period 
    ON data_ingestion.financial_statements(period_end DESC);

CREATE INDEX IF NOT EXISTS idx_financial_statements_type 
    ON data_ingestion.financial_statements(statement_type, period_type);

CREATE INDEX IF NOT EXISTS idx_financial_statements_symbol_type 
    ON data_ingestion.financial_statements(symbol, statement_type, period_end DESC);

-- GIN index for JSONB data queries
CREATE INDEX IF NOT EXISTS idx_financial_statements_data 
    ON data_ingestion.financial_statements USING GIN (data);

-- Auto-update trigger
CREATE OR REPLACE FUNCTION update_financial_statements_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_financial_statements_updated_at
    BEFORE UPDATE ON data_ingestion.financial_statements
    FOR EACH ROW
    EXECUTE FUNCTION update_financial_statements_updated_at();

-- Add comments
COMMENT ON TABLE data_ingestion.financial_statements IS 'Financial statements data from Yahoo Finance';
COMMENT ON COLUMN data_ingestion.financial_statements.symbol IS 'Stock symbol';
COMMENT ON COLUMN data_ingestion.financial_statements.period_end IS 'End date of the reporting period';
COMMENT ON COLUMN data_ingestion.financial_statements.statement_type IS 'Type of financial statement (income, balance_sheet, cash_flow)';
COMMENT ON COLUMN data_ingestion.financial_statements.period_type IS 'Period type (annual, quarterly, ttm)';
COMMENT ON COLUMN data_ingestion.financial_statements.fiscal_year IS 'Fiscal year';
COMMENT ON COLUMN data_ingestion.financial_statements.fiscal_quarter IS 'Fiscal quarter (1-4)';
COMMENT ON COLUMN data_ingestion.financial_statements.data IS 'JSONB containing all financial statement line items';
COMMENT ON COLUMN data_ingestion.financial_statements.data_source IS 'Data source (yahoo, polygon, etc.)';
