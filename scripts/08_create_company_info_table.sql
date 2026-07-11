-- Migration script to create company_info table
-- This table stores company profile and basic information from Yahoo Finance
-- 
-- Author: Trading System
-- Date: 2025-10-11
-- Description: Create company_info table for storing company profiles

-- Create company_info table
CREATE TABLE data_ingestion.company_info (
    symbol VARCHAR(10) PRIMARY KEY,
    name VARCHAR(255),
    sector VARCHAR(100),
    industry VARCHAR(100),
    description TEXT,
    website VARCHAR(255),
    phone VARCHAR(50),
    address VARCHAR(500),
    city VARCHAR(100),
    state VARCHAR(50),
    zip VARCHAR(20),
    country VARCHAR(100),
    employees INTEGER,
    market_cap BIGINT,
    currency VARCHAR(10),
    exchange VARCHAR(50),
    quote_type VARCHAR(50),
    data_source VARCHAR(20) NOT NULL DEFAULT 'yahoo',
    additional_data JSONB,  -- For flexible storage of remaining 150+ info fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT fk_symbol FOREIGN KEY (symbol) 
        REFERENCES data_ingestion.symbols(symbol) ON DELETE CASCADE,
    CONSTRAINT valid_data_source CHECK (data_source IN ('yahoo', 'polygon', 'alpaca'))
);

-- Create indexes for common queries
CREATE INDEX idx_company_info_sector ON data_ingestion.company_info(sector);
CREATE INDEX idx_company_info_industry ON data_ingestion.company_info(industry);
CREATE INDEX idx_company_info_country ON data_ingestion.company_info(country);
CREATE INDEX idx_company_info_market_cap ON data_ingestion.company_info(market_cap DESC NULLS LAST);
CREATE INDEX idx_company_info_data_source ON data_ingestion.company_info(data_source);
CREATE INDEX idx_company_info_additional_data ON data_ingestion.company_info USING gin(additional_data);

-- Create trigger function to update updated_at
CREATE OR REPLACE FUNCTION update_company_info_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger
CREATE TRIGGER update_company_info_updated_at_trigger
    BEFORE UPDATE ON data_ingestion.company_info
    FOR EACH ROW
    EXECUTE FUNCTION update_company_info_updated_at();

-- Add comments for documentation
COMMENT ON TABLE data_ingestion.company_info IS 'Company profile and basic information from Yahoo Finance and other sources';
COMMENT ON COLUMN data_ingestion.company_info.symbol IS 'Stock symbol (primary key)';
COMMENT ON COLUMN data_ingestion.company_info.name IS 'Company full name';
COMMENT ON COLUMN data_ingestion.company_info.sector IS 'Business sector (e.g., Technology, Healthcare)';
COMMENT ON COLUMN data_ingestion.company_info.industry IS 'Specific industry within sector';
COMMENT ON COLUMN data_ingestion.company_info.description IS 'Long business summary/description';
COMMENT ON COLUMN data_ingestion.company_info.employees IS 'Number of full-time employees';
COMMENT ON COLUMN data_ingestion.company_info.market_cap IS 'Market capitalization in dollars';
COMMENT ON COLUMN data_ingestion.company_info.data_source IS 'Data provider: yahoo, polygon, alpaca';
COMMENT ON COLUMN data_ingestion.company_info.additional_data IS 'JSONB storage for remaining 150+ info fields from Yahoo API';

-- Verification queries
SELECT 'Company info table created successfully' as status;

-- Show table structure
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'data_ingestion'
AND table_name = 'company_info'
ORDER BY ordinal_position;

-- Show indexes
SELECT 
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'data_ingestion'
AND tablename = 'company_info';

