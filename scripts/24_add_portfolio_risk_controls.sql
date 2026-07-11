-- Migration 24: Portfolio Risk Controls
-- Adds portfolio_risk_state table and max_allocation_pct column to pair_registry.
-- Run once against trading_system DB.

-- 1. Per-pair allocation cap -----------------------------------------------
ALTER TABLE strategy_engine.pair_registry
    ADD COLUMN IF NOT EXISTS max_allocation_pct NUMERIC(5, 4) DEFAULT NULL;

COMMENT ON COLUMN strategy_engine.pair_registry.max_allocation_pct IS
    'Optional per-pair max fraction of portfolio per leg (e.g. 0.05 = 5%). '
    'Overrides Kelly if lower. NULL = use system default (Kelly-derived).';

-- 2. Portfolio risk state (single-row) -------------------------------------
CREATE TABLE IF NOT EXISTS strategy_engine.portfolio_risk_state (
    id                          INTEGER PRIMARY KEY DEFAULT 1,
    peak_equity                 NUMERIC(15, 2) NOT NULL DEFAULT 0,
    circuit_breaker_active      BOOLEAN NOT NULL DEFAULT FALSE,
    circuit_breaker_triggered_at TIMESTAMP WITH TIME ZONE,
    drawdown_threshold          NUMERIC(5, 4) NOT NULL DEFAULT 0.05,
    updated_at                  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE strategy_engine.portfolio_risk_state IS
    'Single-row table tracking portfolio-level risk state across Prefect flow runs. '
    'id is always 1 — enforced by PRIMARY KEY.';

-- Seed the single row (no-op if already exists)
INSERT INTO strategy_engine.portfolio_risk_state
    (id, peak_equity, circuit_breaker_active, drawdown_threshold)
VALUES (1, 0, FALSE, 0.05)
ON CONFLICT (id) DO NOTHING;
