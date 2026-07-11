-- Migration: Create key_statistics table for Yahoo Finance fundamental data
-- Author: Trading System
-- Date: 2025-10-12
-- Description: Stores comprehensive financial statistics and metrics for stocks

-- Create table for key statistics
CREATE TABLE IF NOT EXISTS data_ingestion.key_statistics (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    data_source VARCHAR(50) DEFAULT 'yahoo',
    
    -- Valuation Metrics
    market_cap BIGINT,
    enterprise_value BIGINT,
    trailing_pe NUMERIC(10, 2),
    forward_pe NUMERIC(10, 2),
    peg_ratio NUMERIC(10, 2),
    price_to_book NUMERIC(10, 2),
    price_to_sales NUMERIC(10, 2),
    enterprise_to_revenue NUMERIC(10, 2),
    enterprise_to_ebitda NUMERIC(10, 2),
    
    -- Profitability Metrics
    profit_margin NUMERIC(10, 4),
    operating_margin NUMERIC(10, 4),
    return_on_assets NUMERIC(10, 4),
    return_on_equity NUMERIC(10, 4),
    gross_margin NUMERIC(10, 4),
    ebitda_margin NUMERIC(10, 4),
    
    -- Financial Health
    revenue BIGINT,
    revenue_per_share NUMERIC(10, 2),
    earnings_per_share NUMERIC(10, 2),
    total_cash BIGINT,
    total_debt BIGINT,
    debt_to_equity NUMERIC(10, 2),
    current_ratio NUMERIC(10, 2),
    quick_ratio NUMERIC(10, 2),
    free_cash_flow BIGINT,
    operating_cash_flow BIGINT,
    
    -- Growth Metrics
    revenue_growth NUMERIC(10, 4),
    earnings_growth NUMERIC(10, 4),
    
    -- Trading Metrics
    beta NUMERIC(10, 2),
    fifty_two_week_high NUMERIC(10, 2),
    fifty_two_week_low NUMERIC(10, 2),
    fifty_day_average NUMERIC(10, 2),
    two_hundred_day_average NUMERIC(10, 2),
    average_volume BIGINT,
    
    -- Dividend Metrics
    dividend_yield NUMERIC(10, 4),
    dividend_rate NUMERIC(10, 2),
    payout_ratio NUMERIC(10, 4),
    
    -- Share Information
    shares_outstanding BIGINT,
    float_shares BIGINT,
    shares_short BIGINT,
    short_ratio NUMERIC(10, 2),
    held_percent_insiders NUMERIC(10, 4),
    held_percent_institutions NUMERIC(10, 4),
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT key_statistics_symbol_date_source_key UNIQUE (symbol, date, data_source),
    CONSTRAINT key_statistics_symbol_fkey FOREIGN KEY (symbol) 
        REFERENCES data_ingestion.symbols(symbol) ON DELETE CASCADE
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_key_statistics_symbol ON data_ingestion.key_statistics(symbol);
CREATE INDEX IF NOT EXISTS idx_key_statistics_date ON data_ingestion.key_statistics(date);
CREATE INDEX IF NOT EXISTS idx_key_statistics_symbol_date ON data_ingestion.key_statistics(symbol, date);
CREATE INDEX IF NOT EXISTS idx_key_statistics_data_source ON data_ingestion.key_statistics(data_source);

-- Create index for valuation screening
CREATE INDEX IF NOT EXISTS idx_key_statistics_valuation ON data_ingestion.key_statistics(trailing_pe, price_to_book, market_cap);

-- Create index for profitability screening
CREATE INDEX IF NOT EXISTS idx_key_statistics_profitability ON data_ingestion.key_statistics(return_on_equity, profit_margin);

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_key_statistics_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_key_statistics_updated_at
    BEFORE UPDATE ON data_ingestion.key_statistics
    FOR EACH ROW
    EXECUTE FUNCTION update_key_statistics_updated_at();

-- Add comment to table
COMMENT ON TABLE data_ingestion.key_statistics IS 'Key financial statistics and metrics from Yahoo Finance';

-- Add comments to important columns
COMMENT ON COLUMN data_ingestion.key_statistics.symbol IS 'Stock ticker symbol';
COMMENT ON COLUMN data_ingestion.key_statistics.date IS 'Date of statistics (usually current date when fetched)';
COMMENT ON COLUMN data_ingestion.key_statistics.data_source IS 'Data source identifier (yahoo, alpaca, etc)';
COMMENT ON COLUMN data_ingestion.key_statistics.market_cap IS 'Market capitalization in dollars';
COMMENT ON COLUMN data_ingestion.key_statistics.trailing_pe IS 'Trailing price-to-earnings ratio';
COMMENT ON COLUMN data_ingestion.key_statistics.return_on_equity IS 'Return on equity (decimal, e.g., 0.15 = 15%)';
COMMENT ON COLUMN data_ingestion.key_statistics.profit_margin IS 'Net profit margin (decimal, e.g., 0.25 = 25%)';
COMMENT ON COLUMN data_ingestion.key_statistics.free_cash_flow IS 'Free cash flow in dollars';
COMMENT ON COLUMN data_ingestion.key_statistics.dividend_yield IS 'Dividend yield (decimal, e.g., 0.02 = 2%)';

-- Grant permissions (adjust as needed for your setup)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON data_ingestion.key_statistics TO trading_app;
-- GRANT USAGE, SELECT ON SEQUENCE data_ingestion.key_statistics_id_seq TO trading_app;

