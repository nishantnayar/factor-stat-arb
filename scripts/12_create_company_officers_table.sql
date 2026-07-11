-- Create company officers table
-- Stores executive and officer information

CREATE TABLE IF NOT EXISTS data_ingestion.company_officers (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    name VARCHAR(255) NOT NULL,
    title VARCHAR(255),
    age INTEGER,
    year_born INTEGER,
    fiscal_year INTEGER,
    total_pay BIGINT,
    exercised_value BIGINT,
    unexercised_value BIGINT,
    data_source VARCHAR(20) NOT NULL DEFAULT 'yahoo',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT fk_company_officers_symbol 
        FOREIGN KEY (symbol) REFERENCES data_ingestion.symbols(symbol) 
        ON DELETE CASCADE,
    
    -- Unique constraint to prevent duplicates
    CONSTRAINT uk_company_officers_unique 
        UNIQUE (symbol, name, title)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_company_officers_symbol 
    ON data_ingestion.company_officers(symbol);

CREATE INDEX IF NOT EXISTS idx_company_officers_name 
    ON data_ingestion.company_officers(name);

CREATE INDEX IF NOT EXISTS idx_company_officers_title 
    ON data_ingestion.company_officers(title);

CREATE INDEX IF NOT EXISTS idx_company_officers_symbol_title 
    ON data_ingestion.company_officers(symbol, title);

-- Auto-update trigger
CREATE OR REPLACE FUNCTION update_company_officers_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_company_officers_updated_at
    BEFORE UPDATE ON data_ingestion.company_officers
    FOR EACH ROW
    EXECUTE FUNCTION update_company_officers_updated_at();

-- Add comments
COMMENT ON TABLE data_ingestion.company_officers IS 'Company officers and executives data from Yahoo Finance';
COMMENT ON COLUMN data_ingestion.company_officers.symbol IS 'Stock symbol';
COMMENT ON COLUMN data_ingestion.company_officers.name IS 'Officer name';
COMMENT ON COLUMN data_ingestion.company_officers.title IS 'Job title/position';
COMMENT ON COLUMN data_ingestion.company_officers.age IS 'Officer age';
COMMENT ON COLUMN data_ingestion.company_officers.year_born IS 'Birth year';
COMMENT ON COLUMN data_ingestion.company_officers.fiscal_year IS 'Fiscal year for compensation data';
COMMENT ON COLUMN data_ingestion.company_officers.total_pay IS 'Total compensation in cents';
COMMENT ON COLUMN data_ingestion.company_officers.exercised_value IS 'Value of exercised options in cents';
COMMENT ON COLUMN data_ingestion.company_officers.unexercised_value IS 'Value of unexercised options in cents';
COMMENT ON COLUMN data_ingestion.company_officers.data_source IS 'Data source (yahoo, polygon, etc.)';
