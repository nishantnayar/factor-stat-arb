-- Add commonly used financial metrics as separate columns
-- This provides both flexibility (JSONB) and queryability (columns)

ALTER TABLE data_ingestion.financial_statements 
ADD COLUMN IF NOT EXISTS total_revenue BIGINT,
ADD COLUMN IF NOT EXISTS net_income BIGINT,
ADD COLUMN IF NOT EXISTS gross_profit BIGINT,
ADD COLUMN IF NOT EXISTS operating_income BIGINT,
ADD COLUMN IF NOT EXISTS ebitda BIGINT,
ADD COLUMN IF NOT EXISTS total_assets BIGINT,
ADD COLUMN IF NOT EXISTS total_liabilities BIGINT,
ADD COLUMN IF NOT EXISTS total_equity BIGINT,
ADD COLUMN IF NOT EXISTS cash_and_equivalents BIGINT,
ADD COLUMN IF NOT EXISTS total_debt BIGINT,
ADD COLUMN IF NOT EXISTS operating_cash_flow BIGINT,
ADD COLUMN IF NOT EXISTS free_cash_flow BIGINT,
ADD COLUMN IF NOT EXISTS basic_eps DECIMAL(10,4),
ADD COLUMN IF NOT EXISTS diluted_eps DECIMAL(10,4),
ADD COLUMN IF NOT EXISTS book_value_per_share DECIMAL(10,4);

-- Add indexes for common queries
CREATE INDEX IF NOT EXISTS idx_financial_statements_total_revenue 
    ON data_ingestion.financial_statements(symbol, period_end, total_revenue);

CREATE INDEX IF NOT EXISTS idx_financial_statements_net_income 
    ON data_ingestion.financial_statements(symbol, period_end, net_income);

CREATE INDEX IF NOT EXISTS idx_financial_statements_eps 
    ON data_ingestion.financial_statements(symbol, period_end, basic_eps);

-- Add comments
COMMENT ON COLUMN data_ingestion.financial_statements.total_revenue IS 'Total Revenue from JSONB data';
COMMENT ON COLUMN data_ingestion.financial_statements.net_income IS 'Net Income from JSONB data';
COMMENT ON COLUMN data_ingestion.financial_statements.gross_profit IS 'Gross Profit from JSONB data';
COMMENT ON COLUMN data_ingestion.financial_statements.operating_income IS 'Operating Income from JSONB data';
COMMENT ON COLUMN data_ingestion.financial_statements.ebitda IS 'EBITDA from JSONB data';
COMMENT ON COLUMN data_ingestion.financial_statements.total_assets IS 'Total Assets from JSONB data';
COMMENT ON COLUMN data_ingestion.financial_statements.total_liabilities IS 'Total Liabilities from JSONB data';
COMMENT ON COLUMN data_ingestion.financial_statements.total_equity IS 'Total Equity from JSONB data';
COMMENT ON COLUMN data_ingestion.financial_statements.cash_and_equivalents IS 'Cash and Equivalents from JSONB data';
COMMENT ON COLUMN data_ingestion.financial_statements.total_debt IS 'Total Debt from JSONB data';
COMMENT ON COLUMN data_ingestion.financial_statements.operating_cash_flow IS 'Operating Cash Flow from JSONB data';
COMMENT ON COLUMN data_ingestion.financial_statements.free_cash_flow IS 'Free Cash Flow from JSONB data';
COMMENT ON COLUMN data_ingestion.financial_statements.basic_eps IS 'Basic EPS from JSONB data';
COMMENT ON COLUMN data_ingestion.financial_statements.diluted_eps IS 'Diluted EPS from JSONB data';
COMMENT ON COLUMN data_ingestion.financial_statements.book_value_per_share IS 'Book Value Per Share from JSONB data';
