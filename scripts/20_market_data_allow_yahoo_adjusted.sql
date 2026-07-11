-- Allow yahoo_adjusted in market_data: (symbol, timestamp, data_source) unique + CHECK
-- Run this if you get: duplicate key value violates unique constraint "unique_symbol_timestamp"
-- when backfilling adjusted prices (data_source='yahoo_adjusted').
--
-- Prerequisites: data_ingestion.market_data exists with a data_source column.
-- Safe to run multiple times (idempotent).

-- 1. Drop old unique constraint (symbol, timestamp) so we can store both yahoo and yahoo_adjusted
ALTER TABLE data_ingestion.market_data
DROP CONSTRAINT IF EXISTS unique_symbol_timestamp;

-- 2. Ensure new unique constraint (symbol, timestamp, data_source) exists
ALTER TABLE data_ingestion.market_data
DROP CONSTRAINT IF EXISTS unique_symbol_timestamp_source;

ALTER TABLE data_ingestion.market_data
ADD CONSTRAINT unique_symbol_timestamp_source
UNIQUE (symbol, timestamp, data_source);

-- 3. Allow data_source = 'yahoo_adjusted' in the check
ALTER TABLE data_ingestion.market_data
DROP CONSTRAINT IF EXISTS valid_data_source;

ALTER TABLE data_ingestion.market_data
ADD CONSTRAINT valid_data_source
CHECK (data_source IN (
    'polygon', 'yahoo', 'yahoo_adjusted', 'alpaca',
    'alpha_vantage', 'iex', 'quandl'
));

-- 4. Refresh stats
ANALYZE data_ingestion.market_data;
