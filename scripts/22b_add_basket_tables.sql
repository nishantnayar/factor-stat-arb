-- Migration 22: Add basket trading tables
-- Supports N-stock baskets discovered via Johansen cointegration.
-- Run against both trading_system and trading_system_test databases.

BEGIN;

-- -------------------------------------------------------------------------
-- basket_registry
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategy_engine.basket_registry (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100)  NOT NULL UNIQUE,
    sector          VARCHAR(100),
    -- JSON array of ticker strings, e.g. ["EWBC","FNB","COLB"]
    symbols         JSONB         NOT NULL,
    -- Johansen cointegrating vector normalized so weights[0] = 1.0
    hedge_weights   JSONB         NOT NULL,

    -- Statistical validation
    half_life_hours NUMERIC(8,2)  NOT NULL,
    coint_pvalue    NUMERIC(8,6)  NOT NULL,
    min_correlation NUMERIC(6,4)  NOT NULL,
    z_score_window  INTEGER       NOT NULL,
    z_score_abs_mean NUMERIC(8,4),
    rank_score      NUMERIC(10,6),

    -- Strategy parameters
    entry_threshold      NUMERIC(5,2) NOT NULL DEFAULT 2.0,
    exit_threshold       NUMERIC(5,2) NOT NULL DEFAULT 0.5,
    stop_loss_threshold  NUMERIC(5,2) NOT NULL DEFAULT 3.0,
    max_hold_hours       NUMERIC(8,2),
    max_allocation_pct   NUMERIC(5,4),

    -- Status
    is_active       BOOLEAN       NOT NULL DEFAULT FALSE,
    last_validated  TIMESTAMPTZ,
    notes           TEXT,

    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_basket_registry_active
    ON strategy_engine.basket_registry (is_active);

CREATE INDEX IF NOT EXISTS idx_basket_registry_sector
    ON strategy_engine.basket_registry (sector);

-- -------------------------------------------------------------------------
-- basket_spread
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategy_engine.basket_spread (
    id          BIGSERIAL PRIMARY KEY,
    basket_id   INTEGER     NOT NULL
                REFERENCES strategy_engine.basket_registry(id) ON DELETE CASCADE,
    timestamp   TIMESTAMPTZ NOT NULL,
    -- snapshot of per-symbol close prices: {"EWBC": 32.1, "FNB": 14.2}
    prices      JSONB,
    spread      NUMERIC(15,8),
    z_score     NUMERIC(10,4),
    -- hedge_weights snapshot at calculation time
    hedge_weights JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_basket_spread_basket_timestamp
    ON strategy_engine.basket_spread (basket_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_basket_spread_timestamp
    ON strategy_engine.basket_spread (timestamp);

-- -------------------------------------------------------------------------
-- basket_trade
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategy_engine.basket_trade (
    id          BIGSERIAL PRIMARY KEY,
    basket_id   INTEGER     NOT NULL
                REFERENCES strategy_engine.basket_registry(id) ON DELETE CASCADE,

    entry_time  TIMESTAMPTZ NOT NULL,
    entry_z_score NUMERIC(10,4),
    side        VARCHAR(20) NOT NULL,   -- LONG_SPREAD / SHORT_SPREAD

    -- JSON array: [{"symbol":"EWBC","qty":100,"entry_price":32.1,"order_id":"abc"}, ...]
    legs        JSONB       NOT NULL,

    exit_time   TIMESTAMPTZ,
    exit_z_score NUMERIC(10,4),
    exit_reason VARCHAR(50),           -- EXIT / STOP_LOSS / EXPIRE
    -- JSON array: [{"symbol":"EWBC","exit_price":33.0,"order_id":"xyz"}, ...]
    exit_legs   JSONB,

    pnl         NUMERIC(15,4),
    pnl_pct     NUMERIC(8,4),
    status      VARCHAR(10) NOT NULL DEFAULT 'OPEN',  -- OPEN / CLOSED / STOPPED

    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_basket_trade_basket_status
    ON strategy_engine.basket_trade (basket_id, status);

CREATE INDEX IF NOT EXISTS idx_basket_trade_entry_time
    ON strategy_engine.basket_trade (entry_time);

COMMIT;
