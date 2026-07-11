-- Indexes and Performance Optimization Script
-- Run this script in the trading_system database after creating tables

\c trading_system;

-- Set search path to include all schemas
SET search_path TO public, data_ingestion, strategy_engine, execution, risk_management, analytics, notification, logging, shared;

-- =============================================
-- DATA INGESTION INDEXES
-- =============================================

-- Market Data Indexes
CREATE INDEX idx_market_data_symbol_timestamp ON data_ingestion.market_data(symbol, timestamp DESC);
CREATE INDEX idx_market_data_timestamp ON data_ingestion.market_data(timestamp DESC);
CREATE INDEX idx_market_data_symbol ON data_ingestion.market_data(symbol);

-- Data Quality Logs Indexes
CREATE INDEX idx_data_quality_logs_symbol_timestamp ON data_ingestion.data_quality_logs(symbol, timestamp DESC);
CREATE INDEX idx_data_quality_logs_timestamp ON data_ingestion.data_quality_logs(timestamp DESC);
CREATE INDEX idx_data_quality_logs_status ON data_ingestion.data_quality_logs(status);

-- =============================================
-- EXECUTION INDEXES
-- =============================================

-- Orders Indexes
CREATE INDEX idx_orders_symbol_status ON execution.orders(symbol, status);
CREATE INDEX idx_orders_strategy ON execution.orders(strategy);
CREATE INDEX idx_orders_created_at ON execution.orders(created_at DESC);
CREATE INDEX idx_orders_account_id ON execution.orders(account_id);
CREATE INDEX idx_orders_status ON execution.orders(status);
CREATE INDEX idx_orders_order_id ON execution.orders(order_id);

-- Trades Indexes
CREATE INDEX idx_trades_symbol_executed_at ON execution.trades(symbol, executed_at DESC);
CREATE INDEX idx_trades_strategy ON execution.trades(strategy);
CREATE INDEX idx_trades_account_id ON execution.trades(account_id);
CREATE INDEX idx_trades_executed_at ON execution.trades(executed_at DESC);
CREATE INDEX idx_trades_trade_id ON execution.trades(trade_id);
CREATE INDEX idx_trades_order_id ON execution.trades(order_id);

-- Positions Indexes
CREATE INDEX idx_positions_account_id ON execution.positions(account_id);
CREATE INDEX idx_positions_symbol ON execution.positions(symbol);
CREATE INDEX idx_positions_last_updated ON execution.positions(last_updated DESC);

-- =============================================
-- STRATEGY ENGINE INDEXES
-- =============================================

-- Strategies Indexes
CREATE INDEX idx_strategies_strategy_id ON strategy_engine.strategies(strategy_id);
CREATE INDEX idx_strategies_status ON strategy_engine.strategies(status);
CREATE INDEX idx_strategies_created_at ON strategy_engine.strategies(created_at DESC);

-- Strategy Signals Indexes
CREATE INDEX idx_strategy_signals_strategy_id ON strategy_engine.strategy_signals(strategy_id);
CREATE INDEX idx_strategy_signals_symbol ON strategy_engine.strategy_signals(symbol);
CREATE INDEX idx_strategy_signals_timestamp ON strategy_engine.strategy_signals(timestamp DESC);
CREATE INDEX idx_strategy_signals_signal_type ON strategy_engine.strategy_signals(signal_type);
CREATE INDEX idx_strategy_signals_signal_id ON strategy_engine.strategy_signals(signal_id);

-- Strategy Performance Indexes
CREATE INDEX idx_strategy_performance_strategy_id ON strategy_engine.strategy_performance(strategy_id);
CREATE INDEX idx_strategy_performance_date ON strategy_engine.strategy_performance(date DESC);
CREATE INDEX idx_strategy_performance_strategy_date ON strategy_engine.strategy_performance(strategy_id, date DESC);

-- =============================================
-- RISK MANAGEMENT INDEXES
-- =============================================

-- Risk Limits Indexes
CREATE INDEX idx_risk_limits_account_id ON risk_management.risk_limits(account_id);
CREATE INDEX idx_risk_limits_limit_type ON risk_management.risk_limits(limit_type);
CREATE INDEX idx_risk_limits_is_active ON risk_management.risk_limits(is_active);

-- Risk Events Indexes
CREATE INDEX idx_risk_events_account_id ON risk_management.risk_events(account_id);
CREATE INDEX idx_risk_events_event_type ON risk_management.risk_events(event_type);
CREATE INDEX idx_risk_events_severity ON risk_management.risk_events(severity);
CREATE INDEX idx_risk_events_timestamp ON risk_management.risk_events(timestamp DESC);
CREATE INDEX idx_risk_events_is_resolved ON risk_management.risk_events(is_resolved);
CREATE INDEX idx_risk_events_event_id ON risk_management.risk_events(event_id);

-- =============================================
-- ANALYTICS INDEXES
-- =============================================

-- Portfolio Summary Indexes
CREATE INDEX idx_portfolio_summary_account_id ON analytics.portfolio_summary(account_id);
CREATE INDEX idx_portfolio_summary_symbol ON analytics.portfolio_summary(symbol);
CREATE INDEX idx_portfolio_summary_last_updated ON analytics.portfolio_summary(last_updated DESC);

-- Performance Metrics Indexes
CREATE INDEX idx_performance_metrics_strategy ON analytics.performance_metrics(strategy);
CREATE INDEX idx_performance_metrics_date ON analytics.performance_metrics(date DESC);
CREATE INDEX idx_performance_metrics_strategy_date ON analytics.performance_metrics(strategy, date DESC);

-- =============================================
-- NOTIFICATION INDEXES
-- =============================================

-- Notification Configs Indexes
CREATE INDEX idx_notification_configs_user_id ON notification.notification_configs(user_id);
CREATE INDEX idx_notification_configs_notification_type ON notification.notification_configs(notification_type);
CREATE INDEX idx_notification_configs_is_active ON notification.notification_configs(is_active);
CREATE INDEX idx_notification_configs_config_id ON notification.notification_configs(config_id);

-- Notification Logs Indexes
CREATE INDEX idx_notification_logs_user_id ON notification.notification_logs(user_id);
CREATE INDEX idx_notification_logs_notification_type ON notification.notification_logs(notification_type);
CREATE INDEX idx_notification_logs_status ON notification.notification_logs(status);
CREATE INDEX idx_notification_logs_timestamp ON notification.notification_logs(timestamp DESC);
CREATE INDEX idx_notification_logs_log_id ON notification.notification_logs(log_id);

-- =============================================
-- LOGGING INDEXES
-- =============================================

-- System Logs Indexes
CREATE INDEX idx_system_logs_timestamp ON logging.system_logs(timestamp DESC);
CREATE INDEX idx_system_logs_service_timestamp ON logging.system_logs(service, timestamp DESC);
CREATE INDEX idx_system_logs_level_timestamp ON logging.system_logs(level, timestamp DESC);
CREATE INDEX idx_system_logs_correlation ON logging.system_logs(correlation_id);
CREATE INDEX idx_system_logs_event_type ON logging.system_logs(event_type);
-- Removed: idx_system_logs_log_id — logging.system_logs has no log_id column
-- (never existed in the live schema; this index was drift/aspirational).

-- Performance Logs Indexes
CREATE INDEX idx_performance_logs_service_timestamp ON logging.performance_logs(service, timestamp DESC);
CREATE INDEX idx_performance_logs_operation ON logging.performance_logs(operation);
CREATE INDEX idx_performance_logs_execution_time ON logging.performance_logs(execution_time_ms DESC);

-- =============================================
-- SHARED INDEXES
-- =============================================

-- Audit Log Indexes
CREATE INDEX idx_audit_log_user_id ON shared.audit_log(user_id);
CREATE INDEX idx_audit_log_table_name ON shared.audit_log(table_name);
CREATE INDEX idx_audit_log_operation ON shared.audit_log(operation);
CREATE INDEX idx_audit_log_timestamp ON shared.audit_log(timestamp DESC);

-- System Config Indexes
CREATE INDEX idx_system_config_config_key ON shared.system_config(config_key);
CREATE INDEX idx_system_config_is_active ON shared.system_config(is_active);

-- =============================================
-- COMPOSITE INDEXES FOR COMMON QUERIES
-- =============================================

-- Market data by symbol and time range (without date restriction)
CREATE INDEX idx_market_data_symbol_time_range ON data_ingestion.market_data(symbol, timestamp);

-- Recent trades by account (without date restriction)
CREATE INDEX idx_trades_account_recent ON execution.trades(account_id, executed_at DESC);

-- Active orders by symbol (without date restriction)
CREATE INDEX idx_orders_symbol_active ON execution.orders(symbol, created_at DESC);

-- Recent system logs by service (without date restriction)
CREATE INDEX idx_system_logs_service_recent ON logging.system_logs(service, timestamp DESC);

-- =============================================
-- PARTIAL INDEXES FOR PERFORMANCE
-- =============================================

-- Only index filled trades
CREATE INDEX idx_trades_filled ON execution.trades(executed_at DESC) 
WHERE trade_id IS NOT NULL;

-- Only index error logs
CREATE INDEX idx_system_logs_errors ON logging.system_logs(timestamp DESC) 
WHERE level IN ('ERROR', 'CRITICAL');

-- Only index active strategies
CREATE INDEX idx_strategies_active ON strategy_engine.strategies(created_at DESC) 
WHERE status = 'active';

-- Only index unresolved risk events
CREATE INDEX idx_risk_events_unresolved ON risk_management.risk_events(timestamp DESC) 
WHERE is_resolved = FALSE;
