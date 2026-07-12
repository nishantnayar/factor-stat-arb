-- Migration 28: Add basket_backtest_run table
-- Stores historical backtest run results for factor-residual baskets
-- (FactorBacktestEngine), mirroring backtest_run but FK'd to basket_registry
-- instead of pair_registry, since basket ids are not pair ids.

BEGIN;

CREATE TABLE IF NOT EXISTS strategy_engine.basket_backtest_run (
    id          SERIAL PRIMARY KEY,
    basket_id   INTEGER     NOT NULL
                REFERENCES strategy_engine.basket_registry(id) ON DELETE CASCADE,

    run_date    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    start_date  DATE        NOT NULL,
    end_date    DATE        NOT NULL,

    -- Parameters used
    entry_threshold      NUMERIC(5,2)  NOT NULL,
    exit_threshold        NUMERIC(5,2) NOT NULL,
    stop_loss_threshold  NUMERIC(5,2)  NOT NULL,
    z_score_window        INTEGER      NOT NULL,
    initial_capital       NUMERIC(15,2) NOT NULL,
    slippage_bps          NUMERIC(6,2)  DEFAULT 5.0,
    commission_per_trade  NUMERIC(8,2)  DEFAULT 0.0,

    -- Performance metrics
    total_return          NUMERIC(10,4) NOT NULL,
    annualized_return     NUMERIC(10,4) NOT NULL,
    sharpe_ratio          NUMERIC(10,4) NOT NULL,
    max_drawdown          NUMERIC(10,4) NOT NULL,
    win_rate               NUMERIC(6,2) NOT NULL,
    profit_factor         NUMERIC(10,4) NOT NULL,
    total_trades           INTEGER      NOT NULL,
    avg_hold_time_hours   NUMERIC(10,2) NOT NULL,
    kelly_fraction          NUMERIC(6,4) NOT NULL,
    passed_gate                BOOLEAN  NOT NULL,

    -- Full detail for UI rendering
    equity_curve   JSONB,
    trade_log      JSONB,
    notes          TEXT
);

CREATE INDEX IF NOT EXISTS idx_basket_backtest_run_basket_date
    ON strategy_engine.basket_backtest_run (basket_id, run_date);

CREATE INDEX IF NOT EXISTS idx_basket_backtest_run_passed
    ON strategy_engine.basket_backtest_run (passed_gate);

COMMIT;
