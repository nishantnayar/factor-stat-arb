-- Allow yahoo_adjusted_1h in market_data valid_data_source CHECK constraint.
-- Used by refresh_pair_prices_task (pairs_flow) for intraday 1h bars fetched
-- from Yahoo Finance during each strategy cycle.  Kept separate from
-- yahoo_adjusted (EOD/backfill bars) so the two can be queried independently.
--
-- Safe to run multiple times (idempotent).

ALTER TABLE data_ingestion.market_data
DROP CONSTRAINT IF EXISTS valid_data_source;

ALTER TABLE data_ingestion.market_data
ADD CONSTRAINT valid_data_source
CHECK (data_source IN (
    'polygon', 'yahoo', 'yahoo_adjusted', 'yahoo_adjusted_1h', 'alpaca',
    'alpha_vantage', 'iex', 'quandl'
));

ANALYZE data_ingestion.market_data;
