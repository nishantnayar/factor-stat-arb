-- Create analyst recommendations table
-- Stores analyst recommendation data from Yahoo Finance

CREATE TABLE IF NOT EXISTS data_ingestion.analyst_recommendations (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    period VARCHAR(10) NOT NULL,
    strong_buy INTEGER DEFAULT 0,
    buy INTEGER DEFAULT 0,
    hold INTEGER DEFAULT 0,
    sell INTEGER DEFAULT 0,
    strong_sell INTEGER DEFAULT 0,
    total_analysts INTEGER GENERATED ALWAYS AS (strong_buy + buy + hold + sell + strong_sell) STORED,
    data_source VARCHAR(20) NOT NULL DEFAULT 'yahoo',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT fk_analyst_recommendations_symbol 
        FOREIGN KEY (symbol) REFERENCES data_ingestion.symbols(symbol) 
        ON DELETE CASCADE,
    
    -- Unique constraint to prevent duplicates (symbol, date, period, data_source)
    CONSTRAINT uk_analyst_recommendations_unique 
        UNIQUE (symbol, date, period, data_source),
    
    -- Check constraints
    CONSTRAINT non_negative_counts CHECK (
        strong_buy >= 0 AND buy >= 0 AND hold >= 0 AND sell >= 0 AND strong_sell >= 0
    ),
    CONSTRAINT valid_period CHECK (period IN ('0m', '-1m', '-2m', '-3m', '-6m', '-1y'))
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_analyst_recommendations_symbol 
    ON data_ingestion.analyst_recommendations(symbol);

CREATE INDEX IF NOT EXISTS idx_analyst_recommendations_date 
    ON data_ingestion.analyst_recommendations(date);

CREATE INDEX IF NOT EXISTS idx_analyst_recommendations_symbol_date 
    ON data_ingestion.analyst_recommendations(symbol, date DESC);

CREATE INDEX IF NOT EXISTS idx_analyst_recommendations_period 
    ON data_ingestion.analyst_recommendations(symbol, period);

-- Index for total analysts queries
CREATE INDEX IF NOT EXISTS idx_analyst_recommendations_total_analysts 
    ON data_ingestion.analyst_recommendations(symbol, total_analysts DESC);

-- Auto-update trigger
CREATE OR REPLACE FUNCTION update_analyst_recommendations_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_analyst_recommendations_updated_at
    BEFORE UPDATE ON data_ingestion.analyst_recommendations
    FOR EACH ROW
    EXECUTE FUNCTION update_analyst_recommendations_updated_at();

-- Add comments
COMMENT ON TABLE data_ingestion.analyst_recommendations IS 'Analyst recommendation counts over time from Yahoo Finance';
COMMENT ON COLUMN data_ingestion.analyst_recommendations.symbol IS 'Stock symbol';
COMMENT ON COLUMN data_ingestion.analyst_recommendations.date IS 'Date when recommendations were recorded';
COMMENT ON COLUMN data_ingestion.analyst_recommendations.period IS 'Time period (0m=current month, -1m=previous month, etc.)';
COMMENT ON COLUMN data_ingestion.analyst_recommendations.strong_buy IS 'Number of analysts with Strong Buy recommendation';
COMMENT ON COLUMN data_ingestion.analyst_recommendations.buy IS 'Number of analysts with Buy recommendation';
COMMENT ON COLUMN data_ingestion.analyst_recommendations.hold IS 'Number of analysts with Hold recommendation';
COMMENT ON COLUMN data_ingestion.analyst_recommendations.sell IS 'Number of analysts with Sell recommendation';
COMMENT ON COLUMN data_ingestion.analyst_recommendations.strong_sell IS 'Number of analysts with Strong Sell recommendation';
COMMENT ON COLUMN data_ingestion.analyst_recommendations.total_analysts IS 'Total number of analysts (computed column)';
COMMENT ON COLUMN data_ingestion.analyst_recommendations.data_source IS 'Data source (yahoo, polygon, etc.)';

