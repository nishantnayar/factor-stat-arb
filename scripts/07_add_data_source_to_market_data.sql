-- Migration script to add data_source column to market_data table
-- This allows tracking which data provider (polygon, yahoo, etc.) supplied each data point
-- 
-- Author: Trading System
-- Date: 2025-10-11
-- Description: Add data_source column and update unique constraint to support multiple data sources

-- Step 1: Add data_source column with default value
-- Setting default to 'polygon' for backward compatibility with existing data
ALTER TABLE data_ingestion.market_data 
ADD COLUMN data_source VARCHAR(20) NOT NULL DEFAULT 'polygon';

-- Step 2: Create index on data_source for query performance
CREATE INDEX idx_market_data_data_source 
ON data_ingestion.market_data (data_source);

-- Step 3: Create composite index for common queries (symbol + data_source + timestamp)
CREATE INDEX idx_market_data_symbol_source_timestamp 
ON data_ingestion.market_data (symbol, data_source, timestamp DESC);

-- Step 4: Drop the old unique constraint (symbol, timestamp)
-- This constraint prevents multiple sources for the same symbol/timestamp
ALTER TABLE data_ingestion.market_data 
DROP CONSTRAINT IF EXISTS unique_symbol_timestamp;

-- Step 5: Add new unique constraint (symbol, timestamp, data_source)
-- This allows multiple data sources for the same symbol/timestamp
ALTER TABLE data_ingestion.market_data 
ADD CONSTRAINT unique_symbol_timestamp_source UNIQUE (symbol, timestamp, data_source);

-- Step 6: Add check constraint to ensure valid data sources
ALTER TABLE data_ingestion.market_data 
ADD CONSTRAINT valid_data_source 
CHECK (data_source IN ('polygon', 'yahoo', 'alpaca', 'alpha_vantage', 'iex', 'quandl'));

-- Step 7: Update statistics for query optimizer
ANALYZE data_ingestion.market_data;

-- Step 8: Add comments for documentation
COMMENT ON COLUMN data_ingestion.market_data.data_source IS 'Data provider: polygon, yahoo, alpaca, alpha_vantage, iex, quandl';

-- Verification queries
-- Check that all existing records have data_source set to 'polygon'
SELECT 
    data_source,
    COUNT(*) as record_count,
    MIN(timestamp) as earliest_data,
    MAX(timestamp) as latest_data
FROM data_ingestion.market_data
GROUP BY data_source;

-- Verify the new constraint exists
SELECT 
    conname as constraint_name,
    contype as constraint_type,
    pg_get_constraintdef(oid) as definition
FROM pg_constraint
WHERE conrelid = 'data_ingestion.market_data'::regclass
AND conname IN ('unique_symbol_timestamp_source', 'valid_data_source');

-- Verify indexes were created
SELECT 
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'data_ingestion'
AND tablename = 'market_data'
AND indexname IN ('idx_market_data_data_source', 'idx_market_data_symbol_source_timestamp');

-- Display summary
SELECT 
    'Migration completed successfully' as status,
    COUNT(*) as total_records,
    COUNT(DISTINCT symbol) as total_symbols,
    COUNT(DISTINCT data_source) as data_sources,
    MIN(timestamp) as earliest_timestamp,
    MAX(timestamp) as latest_timestamp
FROM data_ingestion.market_data;

