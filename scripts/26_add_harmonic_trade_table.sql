-- Migration 26: harmonic_trade table for Gartley (and future harmonic) pattern trades
-- Run once against trading_system and trading_system_test.

CREATE TABLE IF NOT EXISTS strategy_engine.harmonic_trade (
    id              BIGSERIAL PRIMARY KEY,
    symbol          VARCHAR(20)     NOT NULL,
    pattern         VARCHAR(30)     NOT NULL DEFAULT 'gartley',  -- gartley | bat | butterfly
    direction       VARCHAR(10)     NOT NULL,                     -- bullish | bearish
    side            VARCHAR(10)     NOT NULL,                     -- buy | sell

    -- XABCD swing prices recorded at detection time
    x_price         NUMERIC(15, 4)  NOT NULL,
    a_price         NUMERIC(15, 4)  NOT NULL,
    b_price         NUMERIC(15, 4)  NOT NULL,
    c_price         NUMERIC(15, 4)  NOT NULL,
    d_price         NUMERIC(15, 4)  NOT NULL,

    -- Position
    qty             INTEGER         NOT NULL,
    entry_price     NUMERIC(15, 4),
    entry_time      TIMESTAMPTZ     NOT NULL,
    order_id        VARCHAR(50),

    -- Risk levels set at entry
    stop_loss       NUMERIC(15, 4)  NOT NULL,
    target_1        NUMERIC(15, 4)  NOT NULL,
    target_2        NUMERIC(15, 4)  NOT NULL,

    -- Exit
    exit_price      NUMERIC(15, 4),
    exit_time       TIMESTAMPTZ,
    exit_reason     VARCHAR(30),    -- TARGET_1 | TARGET_2 | STOP_LOSS | MANUAL

    -- P&L
    pnl             NUMERIC(15, 4),
    pnl_pct         NUMERIC(8, 4),

    status          VARCHAR(10)     NOT NULL DEFAULT 'OPEN',  -- OPEN | CLOSED | STOPPED

    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_harmonic_trade_symbol_status
    ON strategy_engine.harmonic_trade (symbol, status);

CREATE INDEX IF NOT EXISTS idx_harmonic_trade_entry_time
    ON strategy_engine.harmonic_trade (entry_time);

COMMENT ON TABLE strategy_engine.harmonic_trade IS
    'Open and closed single-leg harmonic pattern trades (Gartley, Bat, Butterfly).';
