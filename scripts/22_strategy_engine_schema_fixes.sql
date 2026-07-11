-- Migration: strategy_engine schema fixes
-- Description: Incremental ALTER statements for installs that ran
--              21_create_strategy_engine_tables.sql before these columns existed.
--              Safe to re-run (all use ADD COLUMN IF NOT EXISTS).
--
-- Changes:
--   1. pair_registry  — add rank_score, add idx_pair_registry_rank
--   2. pair_spread    — add created_at audit column
--   3. pair_signal    — add created_at audit column
--   4. pair_trade     — add created_at, updated_at audit columns
--                       add auto-update trigger for updated_at
--   5. pair_performance — add created_at audit column

-- ============================================================================
-- 1. pair_registry — rank_score
-- ============================================================================
ALTER TABLE strategy_engine.pair_registry
    ADD COLUMN IF NOT EXISTS rank_score NUMERIC(10, 6);

CREATE INDEX IF NOT EXISTS idx_pair_registry_rank
    ON strategy_engine.pair_registry (rank_score DESC NULLS LAST);

-- ============================================================================
-- 2. pair_spread — audit column
-- ============================================================================
ALTER TABLE strategy_engine.pair_spread
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW();

-- ============================================================================
-- 3. pair_signal — audit column
-- ============================================================================
ALTER TABLE strategy_engine.pair_signal
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW();

-- ============================================================================
-- 4. pair_trade — audit columns + updated_at trigger
-- ============================================================================
ALTER TABLE strategy_engine.pair_trade
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW();

-- set_updated_at function is already created by migration 21; reuse it
DROP TRIGGER IF EXISTS trg_pair_trade_updated_at ON strategy_engine.pair_trade;
CREATE TRIGGER trg_pair_trade_updated_at
    BEFORE UPDATE ON strategy_engine.pair_trade
    FOR EACH ROW EXECUTE FUNCTION strategy_engine.set_updated_at();

-- ============================================================================
-- 5. pair_performance — audit column
-- ============================================================================
ALTER TABLE strategy_engine.pair_performance
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW();
