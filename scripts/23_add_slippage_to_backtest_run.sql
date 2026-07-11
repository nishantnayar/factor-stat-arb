-- Migration 23: Add slippage and commission columns to backtest_run
-- These columns record the cost assumptions used in each backtest run
-- so historical results are fully reproducible.

ALTER TABLE strategy_engine.backtest_run
    ADD COLUMN IF NOT EXISTS slippage_bps NUMERIC(6, 2) DEFAULT 5.0,
    ADD COLUMN IF NOT EXISTS commission_per_trade NUMERIC(8, 2) DEFAULT 0.0;

COMMENT ON COLUMN strategy_engine.backtest_run.slippage_bps IS
    'Basis points of slippage applied per leg fill (buy worsened up, sell worsened down)';

COMMENT ON COLUMN strategy_engine.backtest_run.commission_per_trade IS
    'Flat USD commission deducted from P&L per closed round-trip trade';
