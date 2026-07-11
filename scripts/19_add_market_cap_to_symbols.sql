-- Migration script to add market_cap column to symbols table if it doesn't exist
-- This allows tracking market capitalization for symbols
-- 
-- Author: Trading System
-- Date: 2025-12-16
-- Description: Add market_cap column to symbols table for backward compatibility

-- Step 1: Add market_cap column if it doesn't exist
ALTER TABLE data_ingestion.symbols 
ADD COLUMN IF NOT EXISTS market_cap BIGINT;

-- Step 2: Add comment for documentation
COMMENT ON COLUMN data_ingestion.symbols.market_cap IS 'Market capitalization in dollars';

-- Verification query
SELECT 
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'data_ingestion'
AND table_name = 'symbols'
AND column_name = 'market_cap';
