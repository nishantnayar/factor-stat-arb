-- Migration: Create strategy_engine schema and pairs trading tables
-- Description: Stores pair definitions, spread time-series, signals,
--              trades, performance metrics, and backtest run history.
--
-- Changelog:
--   v1  Initial creation
--   v2  Added rank_score to pair_registry
--       Added created_at/updated_at audit columns to pair_spread,
--       pair_signal, pair_trade, pair_performance

-- ============================================================================
-- Schema
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS strategy_engine;

-- ============================================================================
-- pair_registry
-- Validated pair definitions. Populated by scripts/discover_pairs.py.
-- ============================================================================
CREATE TABLE IF NOT EXISTS strategy_engine.pair_registry (
    id                   SERIAL PRIMARY KEY,

    -- Pair definition
    symbol1              VARCHAR(20)    NOT NULL,
    symbol2              VARCHAR(20)    NOT NULL,
    sector               VARCHAR(100),
    name                 VARCHAR(50),

    -- Statistical parameters
    hedge_ratio          NUMERIC(12, 6) NOT NULL,
    half_life_hours      NUMERIC(10, 4),
    correlation          NUMERIC(8, 6),
    coint_pvalue         NUMERIC(10, 8),
    z_score_window       INTEGER        NOT NULL DEFAULT 40,

    -- Discovery rank: (1 - coint_pvalue) x liquidity x |correlation|
    rank_score           NUMERIC(10, 6),

    -- Trading thresholds
    entry_threshold      NUMERIC(6, 4)  NOT NULL DEFAULT 2.0,
    exit_threshold       NUMERIC(6, 4)  NOT NULL DEFAULT 0.5,
    stop_loss_threshold  NUMERIC(6, 4)  NOT NULL DEFAULT 3.0,
    max_hold_hours       NUMERIC(10, 2),

    -- Status
    is_active            BOOLEAN        NOT NULL DEFAULT FALSE,
    last_validated       TIMESTAMP WITH TIME ZONE,
    notes                TEXT,

    -- Audit
    created_at           TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_pair_registry_symbols UNIQUE (symbol1, symbol2)
);

CREATE INDEX IF NOT EXISTS idx_pair_registry_active
    ON strategy_engine.pair_registry (is_active);

CREATE INDEX IF NOT EXISTS idx_pair_registry_rank
    ON strategy_engine.pair_registry (rank_score DESC NULLS LAST);

-- ============================================================================
-- pair_spread
-- Hourly spread / z-score time series.
-- ============================================================================
CREATE TABLE IF NOT EXISTS strategy_engine.pair_spread (
    id           BIGSERIAL PRIMARY KEY,
    pair_id      INTEGER                  NOT NULL
                     REFERENCES strategy_engine.pair_registry (id) ON DELETE CASCADE,
    timestamp    TIMESTAMP WITH TIME ZONE NOT NULL,
    price1       NUMERIC(15, 4),
    price2       NUMERIC(15, 4),
    spread       NUMERIC(20, 8),
    z_score      NUMERIC(12, 6),
    hedge_ratio  NUMERIC(12, 6),
    created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pair_spread_pair_ts
    ON strategy_engine.pair_spread (pair_id, timestamp DESC);

-- ============================================================================
-- pair_signal
-- Generated trading signals.
-- ============================================================================
CREATE TABLE IF NOT EXISTS strategy_engine.pair_signal (
    id           BIGSERIAL PRIMARY KEY,
    pair_id      INTEGER                  NOT NULL
                     REFERENCES strategy_engine.pair_registry (id) ON DELETE CASCADE,
    timestamp    TIMESTAMP WITH TIME ZONE NOT NULL,
    signal_type  VARCHAR(20)              NOT NULL,  -- LONG_SPREAD, SHORT_SPREAD, EXIT, STOP_LOSS, EXPIRE
    z_score      NUMERIC(12, 6),
    reason       TEXT,
    acted_on     BOOLEAN                  NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pair_signal_pair_ts
    ON strategy_engine.pair_signal (pair_id, timestamp DESC);

-- ============================================================================
-- pair_trade
-- Open and closed pair trades.
-- ============================================================================
CREATE TABLE IF NOT EXISTS strategy_engine.pair_trade (
    id              BIGSERIAL PRIMARY KEY,
    pair_id         INTEGER                  NOT NULL
                        REFERENCES strategy_engine.pair_registry (id) ON DELETE CASCADE,

    -- Entry
    entry_time      TIMESTAMP WITH TIME ZONE NOT NULL,
    entry_z_score   NUMERIC(12, 6),
    side            VARCHAR(20)              NOT NULL,  -- LONG_SPREAD or SHORT_SPREAD

    -- Position sizes
    qty1            NUMERIC(15, 4)           NOT NULL,
    qty2            NUMERIC(15, 4)           NOT NULL,

    -- Entry prices & order IDs
    entry_price1    NUMERIC(15, 4),
    entry_price2    NUMERIC(15, 4),
    order_id1       VARCHAR(100),
    order_id2       VARCHAR(100),

    -- Exit
    exit_time       TIMESTAMP WITH TIME ZONE,
    exit_z_score    NUMERIC(12, 6),
    exit_price1     NUMERIC(15, 4),
    exit_price2     NUMERIC(15, 4),
    exit_reason     VARCHAR(30),             -- EXIT, STOP_LOSS, EXPIRE, MANUAL_CLOSE, EMERGENCY_STOP, END_OF_BACKTEST

    -- P&L
    pnl             NUMERIC(15, 4),
    pnl_pct         NUMERIC(10, 4),

    -- Status
    status          VARCHAR(10)              NOT NULL DEFAULT 'OPEN',  -- OPEN, CLOSED, STOPPED

    -- Audit
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pair_trade_pair_status
    ON strategy_engine.pair_trade (pair_id, status);
CREATE INDEX IF NOT EXISTS idx_pair_trade_entry_time
    ON strategy_engine.pair_trade (entry_time DESC);

-- ============================================================================
-- pair_performance
-- Daily cumulative performance metrics (one row per pair per day).
-- ============================================================================
CREATE TABLE IF NOT EXISTS strategy_engine.pair_performance (
    id              SERIAL PRIMARY KEY,
    pair_id         INTEGER NOT NULL
                        REFERENCES strategy_engine.pair_registry (id) ON DELETE CASCADE,
    date            DATE    NOT NULL,

    total_trades    INTEGER,
    winning_trades  INTEGER,
    win_rate        NUMERIC(8, 6),
    avg_pnl         NUMERIC(15, 4),
    total_pnl       NUMERIC(15, 4),
    sharpe          NUMERIC(10, 6),
    max_drawdown    NUMERIC(10, 6),
    avg_hold_hours  NUMERIC(10, 4),
    kelly_fraction  NUMERIC(10, 6),

    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_pair_performance_pair_date UNIQUE (pair_id, date)
);

-- ============================================================================
-- backtest_run
-- Historical backtest results.
-- ============================================================================
CREATE TABLE IF NOT EXISTS strategy_engine.backtest_run (
    id                    SERIAL PRIMARY KEY,
    pair_id               INTEGER NOT NULL
                              REFERENCES strategy_engine.pair_registry (id) ON DELETE CASCADE,
    run_date              DATE    NOT NULL,

    -- Date range tested
    start_date            DATE    NOT NULL,
    end_date              DATE    NOT NULL,

    -- Parameters used
    entry_threshold       NUMERIC(6, 4),
    exit_threshold        NUMERIC(6, 4),
    stop_loss_threshold   NUMERIC(6, 4),
    z_score_window        INTEGER,
    initial_capital       NUMERIC(15, 2),

    -- Results
    total_return          NUMERIC(12, 6),
    annualized_return     NUMERIC(12, 6),
    sharpe_ratio          NUMERIC(10, 6),
    max_drawdown          NUMERIC(10, 6),
    win_rate              NUMERIC(8, 6),
    profit_factor         NUMERIC(10, 4),
    total_trades          INTEGER,
    avg_hold_time_hours   NUMERIC(10, 4),
    kelly_fraction        NUMERIC(10, 6),

    -- Gate
    passed_gate           BOOLEAN NOT NULL DEFAULT FALSE,

    -- Full data (JSON)
    equity_curve          JSONB,
    trade_log             JSONB,
    notes                 TEXT,

    created_at            TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_backtest_run_pair_date
    ON strategy_engine.backtest_run (pair_id, run_date DESC);

-- ============================================================================
-- Auto-update updated_at on pair_registry and pair_trade
-- ============================================================================
CREATE OR REPLACE FUNCTION strategy_engine.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_pair_registry_updated_at ON strategy_engine.pair_registry;
CREATE TRIGGER trg_pair_registry_updated_at
    BEFORE UPDATE ON strategy_engine.pair_registry
    FOR EACH ROW EXECUTE FUNCTION strategy_engine.set_updated_at();

DROP TRIGGER IF EXISTS trg_pair_trade_updated_at ON strategy_engine.pair_trade;
CREATE TRIGGER trg_pair_trade_updated_at
    BEFORE UPDATE ON strategy_engine.pair_trade
    FOR EACH ROW EXECUTE FUNCTION strategy_engine.set_updated_at();
