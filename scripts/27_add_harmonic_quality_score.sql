-- Migration 27: add quality_score to strategy_engine.harmonic_trade
-- Stores pattern Fibonacci quality (0.0-1.0) at detection time for future learning agent use.

ALTER TABLE strategy_engine.harmonic_trade
    ADD COLUMN IF NOT EXISTS quality_score NUMERIC(6, 4);
