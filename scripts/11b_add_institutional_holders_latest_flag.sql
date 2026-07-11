-- Migration: Add is_latest flag and percent_change to institutional_holders table
-- Author: Trading System
-- Date: 2025-01-XX
-- Description: Adds is_latest boolean flag and percent_change column to track latest holdings and changes

-- Add is_latest column
ALTER TABLE data_ingestion.institutional_holders
ADD COLUMN IF NOT EXISTS is_latest BOOLEAN DEFAULT FALSE NOT NULL;

-- Add percent_change column
ALTER TABLE data_ingestion.institutional_holders
ADD COLUMN IF NOT EXISTS percent_change NUMERIC(10, 4);

-- Add index for fast queries on latest records
CREATE INDEX IF NOT EXISTS idx_institutional_holders_latest 
ON data_ingestion.institutional_holders(symbol, is_latest) 
WHERE is_latest = TRUE;

-- Update existing records to set is_latest flag
-- For each (symbol, holder_name) combination, mark the record with the latest date_reported as is_latest = TRUE
WITH latest_dates AS (
    SELECT 
        symbol,
        holder_name,
        MAX(date_reported) AS max_date
    FROM data_ingestion.institutional_holders
    GROUP BY symbol, holder_name
)
UPDATE data_ingestion.institutional_holders ih
SET is_latest = TRUE
FROM latest_dates ld
WHERE ih.symbol = ld.symbol
    AND ih.holder_name = ld.holder_name
    AND ih.date_reported = ld.max_date;

-- Calculate percent_change for existing records
-- Compare current percent_held with previous period's percent_held
WITH previous_periods AS (
    SELECT 
        ih1.id,
        ih1.symbol,
        ih1.holder_name,
        ih1.date_reported,
        ih1.percent_held AS current_percent,
        ih2.percent_held AS previous_percent
    FROM data_ingestion.institutional_holders ih1
    LEFT JOIN LATERAL (
        SELECT percent_held
        FROM data_ingestion.institutional_holders ih2
        WHERE ih2.symbol = ih1.symbol
            AND ih2.holder_name = ih1.holder_name
            AND ih2.date_reported < ih1.date_reported
        ORDER BY ih2.date_reported DESC
        LIMIT 1
    ) ih2 ON TRUE
    WHERE ih1.percent_held IS NOT NULL
)
UPDATE data_ingestion.institutional_holders ih
SET percent_change = pp.current_percent - pp.previous_percent
FROM previous_periods pp
WHERE ih.id = pp.id
    AND pp.previous_percent IS NOT NULL;

-- Add comments
COMMENT ON COLUMN data_ingestion.institutional_holders.is_latest IS 'Flag indicating if this is the latest record for this holder (TRUE) or historical data (FALSE)';
COMMENT ON COLUMN data_ingestion.institutional_holders.percent_change IS 'Change in percentage held from previous period (decimal format, e.g., 0.05 = +5 percentage points)';

