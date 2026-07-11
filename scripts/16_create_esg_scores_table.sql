-- Create ESG scores table
-- Stores ESG (Environmental, Social, Governance) scores from Yahoo Finance

CREATE TABLE IF NOT EXISTS data_ingestion.esg_scores (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    total_esg NUMERIC(5, 2),
    environment_score NUMERIC(5, 2),
    social_score NUMERIC(5, 2),
    governance_score NUMERIC(5, 2),
    controversy_level INTEGER,
    esg_performance VARCHAR(50),
    peer_group VARCHAR(100),
    peer_count INTEGER,
    percentile NUMERIC(5, 2),
    data_source VARCHAR(20) NOT NULL DEFAULT 'yahoo',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT fk_esg_scores_symbol 
        FOREIGN KEY (symbol) REFERENCES data_ingestion.symbols(symbol) 
        ON DELETE CASCADE,
    
    -- Unique constraint to prevent duplicates (symbol, date, data_source)
    CONSTRAINT uk_esg_scores_unique 
        UNIQUE (symbol, date, data_source),
    
    -- Check constraints
    CONSTRAINT valid_scores CHECK (
        (total_esg IS NULL OR (total_esg >= 0 AND total_esg <= 100)) AND
        (environment_score IS NULL OR (environment_score >= 0 AND environment_score <= 100)) AND
        (social_score IS NULL OR (social_score >= 0 AND social_score <= 100)) AND
        (governance_score IS NULL OR (governance_score >= 0 AND governance_score <= 100)) AND
        (percentile IS NULL OR (percentile >= 0 AND percentile <= 100)) AND
        (controversy_level IS NULL OR (controversy_level >= 0 AND controversy_level <= 5))
    )
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_esg_scores_symbol 
    ON data_ingestion.esg_scores(symbol);

CREATE INDEX IF NOT EXISTS idx_esg_scores_date 
    ON data_ingestion.esg_scores(date);

CREATE INDEX IF NOT EXISTS idx_esg_scores_symbol_date 
    ON data_ingestion.esg_scores(symbol, date DESC);

CREATE INDEX IF NOT EXISTS idx_esg_scores_total_esg 
    ON data_ingestion.esg_scores(symbol, total_esg DESC NULLS LAST);

-- Index for filtering by ESG performance
CREATE INDEX IF NOT EXISTS idx_esg_scores_performance 
    ON data_ingestion.esg_scores(esg_performance) WHERE esg_performance IS NOT NULL;

-- Auto-update trigger
CREATE OR REPLACE FUNCTION update_esg_scores_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_esg_scores_updated_at
    BEFORE UPDATE ON data_ingestion.esg_scores
    FOR EACH ROW
    EXECUTE FUNCTION update_esg_scores_updated_at();

-- Add comments
COMMENT ON TABLE data_ingestion.esg_scores IS 'ESG (Environmental, Social, Governance) scores from Yahoo Finance';
COMMENT ON COLUMN data_ingestion.esg_scores.symbol IS 'Stock symbol';
COMMENT ON COLUMN data_ingestion.esg_scores.date IS 'Date when ESG scores were recorded';
COMMENT ON COLUMN data_ingestion.esg_scores.total_esg IS 'Overall ESG score (0-100)';
COMMENT ON COLUMN data_ingestion.esg_scores.environment_score IS 'Environmental score (0-100)';
COMMENT ON COLUMN data_ingestion.esg_scores.social_score IS 'Social score (0-100)';
COMMENT ON COLUMN data_ingestion.esg_scores.governance_score IS 'Governance score (0-100)';
COMMENT ON COLUMN data_ingestion.esg_scores.controversy_level IS 'Controversy level (0-5, where 5 is highest)';
COMMENT ON COLUMN data_ingestion.esg_scores.esg_performance IS 'ESG performance rating (e.g., "OUT_PERF", "AVG_PERF")';
COMMENT ON COLUMN data_ingestion.esg_scores.peer_group IS 'Peer group classification';
COMMENT ON COLUMN data_ingestion.esg_scores.peer_count IS 'Number of companies in peer group';
COMMENT ON COLUMN data_ingestion.esg_scores.percentile IS 'ESG percentile within peer group (0-100)';
COMMENT ON COLUMN data_ingestion.esg_scores.data_source IS 'Data source (yahoo, polygon, etc.)';

