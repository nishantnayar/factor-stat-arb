-- Update Symbols Table from Company Info
-- This script updates the symbols table with information from the company_info table
-- Run this script in the trading_system database

-- Set search path to include data_ingestion schema
SET search_path TO public, data_ingestion;

-- Update symbols table with company information
-- This will update existing symbols with more detailed information from company_info
UPDATE data_ingestion.symbols s
SET 
    name = COALESCE(ci.name, s.name),
    exchange = COALESCE(ci.exchange, s.exchange),
    sector = COALESCE(ci.sector, s.sector),
    market_cap = COALESCE(ci.market_cap, s.market_cap),
    last_updated = NOW()
FROM data_ingestion.company_info ci
WHERE s.symbol = ci.symbol
  AND (
    -- Only update if company_info has better data
    (s.name IS NULL OR s.name = '') OR
    (s.exchange IS NULL OR s.exchange = '') OR
    (s.sector IS NULL OR s.sector = 'Unknown') OR
    (s.market_cap IS NULL)
  );

-- Insert new symbols from company_info that don't exist in symbols table
INSERT INTO data_ingestion.symbols (symbol, name, exchange, sector, market_cap, status, added_date, last_updated)
SELECT 
    ci.symbol,
    ci.name,
    ci.exchange,
    ci.sector,
    ci.market_cap,
    'active' as status,
    NOW() as added_date,
    NOW() as last_updated
FROM data_ingestion.company_info ci
LEFT JOIN data_ingestion.symbols s ON ci.symbol = s.symbol
WHERE s.symbol IS NULL  -- Only insert if symbol doesn't exist in symbols table
  AND ci.symbol IS NOT NULL
  AND ci.symbol != '';

-- Show summary of updates
SELECT 
    'Updated symbols' as operation,
    COUNT(*) as count
FROM data_ingestion.symbols s
INNER JOIN data_ingestion.company_info ci ON s.symbol = ci.symbol
WHERE s.last_updated > NOW() - INTERVAL '1 minute'

UNION ALL

SELECT 
    'Total symbols' as operation,
    COUNT(*) as count
FROM data_ingestion.symbols
WHERE status = 'active'

UNION ALL

SELECT 
    'Total company info records' as operation,
    COUNT(*) as count
FROM data_ingestion.company_info;

-- Show sample of updated symbols
SELECT 
    s.symbol,
    s.name,
    s.exchange,
    s.sector,
    s.market_cap,
    s.status,
    s.last_updated
FROM data_ingestion.symbols s
INNER JOIN data_ingestion.company_info ci ON s.symbol = ci.symbol
WHERE s.last_updated > NOW() - INTERVAL '1 minute'
ORDER BY s.symbol
LIMIT 10;
