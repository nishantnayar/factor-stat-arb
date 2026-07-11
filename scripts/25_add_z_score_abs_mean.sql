-- Migration 25: Add z_score_abs_mean to pair_registry
-- Stores the average absolute z-score from discovery, used as a tradeability signal.
-- Pairs with low z_score_abs_mean rarely cross entry thresholds regardless of cointegration.
-- Run once against trading_system DB.

ALTER TABLE strategy_engine.pair_registry
    ADD COLUMN IF NOT EXISTS z_score_abs_mean NUMERIC(8, 4) DEFAULT NULL;

COMMENT ON COLUMN strategy_engine.pair_registry.z_score_abs_mean IS
    'Mean absolute z-score over the discovery window. '
    'Higher values indicate a more tradeable spread (crosses entry thresholds more often). '
    'Used as a factor in rank_score: coint_strength x |correlation| x z_score_abs_mean.';
