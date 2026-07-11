-- Migration script to create load_runs table for incremental data loading
-- This table tracks data loading runs for different data sources and timespans

-- Create the load_runs table for tracking incremental data loading
CREATE TABLE data_ingestion.load_runs (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    data_source VARCHAR(20) NOT NULL,  -- 'polygon', 'yahoo', 'alpha_vantage', etc.
    timespan VARCHAR(10) NOT NULL,     -- 'minute', 'hour', 'day', 'week', 'month', 'quarter', 'year'
    multiplier INTEGER NOT NULL,       -- 1, 5, 15, 30, etc.
    last_run_date DATE NOT NULL,       -- When the loader last attempted to run
    last_successful_date DATE NOT NULL, -- Last date with successfully loaded data
    records_loaded INTEGER DEFAULT 0,  -- Number of records loaded in last run
    status VARCHAR(20) DEFAULT 'success', -- 'success', 'failed', 'partial'
    error_message TEXT,                -- Error details if status is 'failed'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_symbol_data_source_timespan UNIQUE (symbol, data_source, timespan, multiplier),
    CONSTRAINT valid_timespan CHECK (timespan IN ('minute', 'hour', 'day', 'week', 'month', 'quarter', 'year')),
    CONSTRAINT valid_data_source CHECK (data_source IN ('polygon', 'yahoo', 'alpha_vantage', 'iex', 'quandl')),
    CONSTRAINT valid_status CHECK (status IN ('success', 'failed', 'partial')),
    CONSTRAINT positive_multiplier CHECK (multiplier > 0),
    CONSTRAINT positive_records CHECK (records_loaded >= 0)
);

-- Create indexes for better query performance
CREATE INDEX idx_load_runs_symbol ON data_ingestion.load_runs (symbol);
CREATE INDEX idx_load_runs_data_source ON data_ingestion.load_runs (data_source);
CREATE INDEX idx_load_runs_last_successful_date ON data_ingestion.load_runs (last_successful_date);
CREATE INDEX idx_load_runs_symbol_data_source ON data_ingestion.load_runs (symbol, data_source);

-- Create a function to automatically update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_load_runs_updated_at 
    BEFORE UPDATE ON data_ingestion.load_runs 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE data_ingestion.load_runs IS 'Tracks incremental data loading runs for different data sources and timespans';
COMMENT ON COLUMN data_ingestion.load_runs.data_source IS 'Data provider: polygon, yahoo, alpha_vantage, iex, quandl';
COMMENT ON COLUMN data_ingestion.load_runs.timespan IS 'Data granularity: minute, hour, day, week, month, quarter, year';
COMMENT ON COLUMN data_ingestion.load_runs.multiplier IS 'Number of timespans to aggregate (e.g., 5 with minute = 5-minute bars)';
COMMENT ON COLUMN data_ingestion.load_runs.last_run_date IS 'Date when the loader last attempted to fetch data';
COMMENT ON COLUMN data_ingestion.load_runs.last_successful_date IS 'Last date with successfully loaded data for this symbol/source/timespan';
COMMENT ON COLUMN data_ingestion.load_runs.records_loaded IS 'Number of records loaded in the last successful run';
COMMENT ON COLUMN data_ingestion.load_runs.status IS 'Status of the last run: success, failed, or partial';
COMMENT ON COLUMN data_ingestion.load_runs.error_message IS 'Error details if the last run failed';

-- Insert initial data for existing symbols (if any)
-- This will create entries for all active symbols with polygon as data source
-- and set last_successful_date to beginning of current year
INSERT INTO data_ingestion.load_runs (symbol, data_source, timespan, multiplier, last_run_date, last_successful_date, records_loaded, status)
SELECT 
    s.symbol,
    'polygon' as data_source,
    'day' as timespan,
    1 as multiplier,
    CURRENT_DATE - INTERVAL '1 day' as last_run_date,
    DATE_TRUNC('year', CURRENT_DATE)::DATE - INTERVAL '1 day' as last_successful_date,
    0 as records_loaded,
    'success' as status
FROM data_ingestion.symbols s
WHERE s.status = 'active'
ON CONFLICT (symbol, data_source, timespan, multiplier) DO NOTHING;

-- Verify the table was created successfully
SELECT 
    'load_runs table created successfully' as status,
    COUNT(*) as total_symbols_initialized
FROM data_ingestion.load_runs;
