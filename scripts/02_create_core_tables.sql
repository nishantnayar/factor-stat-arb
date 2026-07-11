-- Core Trading Tables Creation Script
-- Run this script in the trading_system database

\c trading_system;

-- Set search path to include all schemas
SET search_path TO public, data_ingestion, strategy_engine, execution, risk_management, analytics, notification, logging, shared;

-- Create custom types
CREATE TYPE order_side AS ENUM ('buy', 'sell');
CREATE TYPE order_type AS ENUM ('market', 'limit', 'stop', 'stop_limit');
CREATE TYPE order_status AS ENUM ('pending', 'submitted', 'filled', 'partially_filled', 'cancelled', 'rejected');
CREATE TYPE time_in_force AS ENUM ('day', 'gtc', 'ioc', 'fok');
CREATE TYPE trade_type AS ENUM ('opening', 'closing', 'partial');

-- =============================================
-- DATA INGESTION SCHEMA
-- =============================================

-- Market Data Table
CREATE TABLE data_ingestion.market_data (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    open DECIMAL(15,4),
    high DECIMAL(15,4),
    low DECIMAL(15,4),
    close DECIMAL(15,4),
    volume BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_symbol_timestamp UNIQUE (symbol, timestamp),
    CONSTRAINT positive_prices CHECK (open > 0 AND high > 0 AND low > 0 AND close > 0),
    CONSTRAINT valid_ohlc CHECK (high >= GREATEST(open, close) AND low <= LEAST(open, close))
);

-- Data Quality Logs
CREATE TABLE data_ingestion.data_quality_logs (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    check_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL, -- 'pass', 'fail', 'warning'
    message TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- EXECUTION SCHEMA
-- =============================================

-- Orders Table
CREATE TABLE execution.orders (
    id BIGSERIAL PRIMARY KEY,
    order_id VARCHAR(100) UNIQUE NOT NULL,
    account_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side order_side NOT NULL,
    order_type order_type NOT NULL,
    quantity DECIMAL(15,4) NOT NULL,
    price DECIMAL(15,4),
    stop_price DECIMAL(15,4),
    time_in_force time_in_force DEFAULT 'day',
    status order_status NOT NULL DEFAULT 'pending',
    strategy VARCHAR(100),
    session_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT positive_quantity CHECK (quantity > 0),
    CONSTRAINT valid_price CHECK (price IS NULL OR price > 0),
    CONSTRAINT valid_stop_price CHECK (stop_price IS NULL OR stop_price > 0)
);

-- Trades Table
CREATE TABLE execution.trades (
    id BIGSERIAL PRIMARY KEY,
    trade_id VARCHAR(100) UNIQUE NOT NULL,
    order_id VARCHAR(100) REFERENCES execution.orders(order_id),
    account_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    quantity DECIMAL(15,4) NOT NULL,
    price DECIMAL(15,4) NOT NULL,
    commission DECIMAL(10,4) DEFAULT 0,
    executed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    settlement_date DATE,
    strategy VARCHAR(100),
    trade_type trade_type,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT positive_quantity CHECK (quantity > 0),
    CONSTRAINT positive_price CHECK (price > 0),
    CONSTRAINT non_negative_commission CHECK (commission >= 0)
);

-- Positions Table
CREATE TABLE execution.positions (
    id BIGSERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    quantity DECIMAL(15,4) NOT NULL,
    avg_price DECIMAL(15,4) NOT NULL,
    market_value DECIMAL(15,4),
    unrealized_pnl DECIMAL(15,4),
    realized_pnl DECIMAL(15,4) DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_account_symbol UNIQUE (account_id, symbol),
    CONSTRAINT non_negative_quantity CHECK (quantity >= 0)
);

-- =============================================
-- STRATEGY ENGINE SCHEMA
-- =============================================

-- Strategies Table
CREATE TABLE strategy_engine.strategies (
    id BIGSERIAL PRIMARY KEY,
    strategy_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    parameters JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'active', -- 'active', 'inactive', 'paused'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Strategy Signals Table
CREATE TABLE strategy_engine.strategy_signals (
    id BIGSERIAL PRIMARY KEY,
    signal_id VARCHAR(100) UNIQUE NOT NULL,
    strategy_id VARCHAR(100) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    signal_type VARCHAR(20) NOT NULL, -- 'buy', 'sell', 'hold'
    confidence DECIMAL(5,4), -- 0.0 to 1.0
    price DECIMAL(15,4),
    quantity DECIMAL(15,4),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_confidence CHECK (confidence >= 0 AND confidence <= 1),
    CONSTRAINT positive_price CHECK (price IS NULL OR price > 0),
    CONSTRAINT positive_quantity CHECK (quantity IS NULL OR quantity > 0)
);

-- Strategy Performance Table
CREATE TABLE strategy_engine.strategy_performance (
    id BIGSERIAL PRIMARY KEY,
    strategy_id VARCHAR(100) NOT NULL,
    date DATE NOT NULL,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    total_return DECIMAL(10,6),
    sharpe_ratio DECIMAL(10,6),
    max_drawdown DECIMAL(10,6),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_strategy_date UNIQUE (strategy_id, date),
    CONSTRAINT non_negative_trades CHECK (total_trades >= 0 AND winning_trades >= 0 AND losing_trades >= 0)
);

-- =============================================
-- RISK MANAGEMENT SCHEMA
-- =============================================

-- Risk Limits Table
CREATE TABLE risk_management.risk_limits (
    id BIGSERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    limit_type VARCHAR(50) NOT NULL, -- 'max_position_size', 'max_daily_loss', 'max_drawdown'
    limit_value DECIMAL(15,4) NOT NULL,
    current_value DECIMAL(15,4) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT positive_limit_value CHECK (limit_value > 0)
);

-- Risk Events Table
CREATE TABLE risk_management.risk_events (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR(100) UNIQUE NOT NULL,
    account_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL, -- 'low', 'medium', 'high', 'critical'
    message TEXT NOT NULL,
    data JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE,
    is_resolved BOOLEAN DEFAULT FALSE
);

-- =============================================
-- ANALYTICS SCHEMA
-- =============================================

-- Portfolio Summary Table
CREATE TABLE analytics.portfolio_summary (
    id BIGSERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    total_value DECIMAL(15,4) NOT NULL,
    realized_pnl DECIMAL(15,4) DEFAULT 0,
    unrealized_pnl DECIMAL(15,4) DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_account_symbol UNIQUE (account_id, symbol)
);

-- Performance Metrics Table
CREATE TABLE analytics.performance_metrics (
    id BIGSERIAL PRIMARY KEY,
    strategy VARCHAR(100) NOT NULL,
    date DATE NOT NULL,
    total_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(5,4), -- 0.0 to 1.0
    total_return DECIMAL(10,6),
    sharpe_ratio DECIMAL(10,6),
    max_drawdown DECIMAL(10,6),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_strategy_date UNIQUE (strategy, date),
    CONSTRAINT valid_win_rate CHECK (win_rate IS NULL OR (win_rate >= 0 AND win_rate <= 1))
);

-- =============================================
-- NOTIFICATION SCHEMA
-- =============================================

-- Notification Configurations
CREATE TABLE notification.notification_configs (
    id BIGSERIAL PRIMARY KEY,
    config_id VARCHAR(100) UNIQUE NOT NULL,
    user_id VARCHAR(50) NOT NULL,
    notification_type VARCHAR(50) NOT NULL, -- 'email', 'sms', 'webhook'
    config JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Notification Logs
CREATE TABLE notification.notification_logs (
    id BIGSERIAL PRIMARY KEY,
    log_id VARCHAR(100) UNIQUE NOT NULL,
    user_id VARCHAR(50) NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL, -- 'sent', 'failed', 'pending'
    message TEXT,
    error_message TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- LOGGING SCHEMA
-- =============================================

-- Drop existing tables if they exist (to recreate with updated schema)
DROP TABLE IF EXISTS logging.performance_logs CASCADE;
DROP TABLE IF EXISTS logging.system_logs CASCADE;

-- System Logs Table
CREATE TABLE logging.system_logs (
    id BIGSERIAL PRIMARY KEY,
    service VARCHAR(50) NOT NULL,
    level VARCHAR(20) NOT NULL, -- 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    message TEXT NOT NULL,
    data JSONB,
    correlation_id VARCHAR(100),
    event_type VARCHAR(50),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Performance Logs Table
CREATE TABLE logging.performance_logs (
    id BIGSERIAL PRIMARY KEY,
    service VARCHAR(50) NOT NULL,
    operation VARCHAR(100) NOT NULL,
    execution_time_ms DECIMAL(10,3) NOT NULL,
    memory_usage_mb DECIMAL(10,3),
    cpu_usage_percent DECIMAL(5,2),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- SHARED SCHEMA
-- =============================================

-- Audit Log Table
CREATE TABLE shared.audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(50),
    table_name VARCHAR(100) NOT NULL,
    operation VARCHAR(20) NOT NULL, -- 'INSERT', 'UPDATE', 'DELETE', 'SELECT'
    old_values JSONB,
    new_values JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- System Configuration Table
CREATE TABLE shared.system_config (
    id BIGSERIAL PRIMARY KEY,
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default system configuration
INSERT INTO shared.system_config (config_key, config_value, description) VALUES
('system_version', '1.0.0', 'Current system version'),
('maintenance_mode', 'false', 'System maintenance mode'),
('max_concurrent_trades', '10', 'Maximum concurrent trades allowed'),
('default_risk_limit', '0.05', 'Default risk limit (5%)');
