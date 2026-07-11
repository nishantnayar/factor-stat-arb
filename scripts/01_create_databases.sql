-- Database Setup Script for Trading System
-- Run this script as a PostgreSQL superuser (postgres)

-- Create Trading System Database
CREATE DATABASE trading_system;

-- Create Prefect Database
CREATE DATABASE "prefect";

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE trading_system TO postgres;
GRANT ALL PRIVILEGES ON DATABASE "prefect" TO postgres;

-- Connect to trading_system database and create schemas
\c trading_system;

-- Create service-specific schemas
CREATE SCHEMA IF NOT EXISTS data_ingestion;
CREATE SCHEMA IF NOT EXISTS strategy_engine;
CREATE SCHEMA IF NOT EXISTS execution;
CREATE SCHEMA IF NOT EXISTS risk_management;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS notification;
CREATE SCHEMA IF NOT EXISTS logging;
CREATE SCHEMA IF NOT EXISTS shared;

-- Grant permissions on schemas
GRANT ALL PRIVILEGES ON SCHEMA data_ingestion TO postgres;
GRANT ALL PRIVILEGES ON SCHEMA strategy_engine TO postgres;
GRANT ALL PRIVILEGES ON SCHEMA execution TO postgres;
GRANT ALL PRIVILEGES ON SCHEMA risk_management TO postgres;
GRANT ALL PRIVILEGES ON SCHEMA analytics TO postgres;
GRANT ALL PRIVILEGES ON SCHEMA notification TO postgres;
GRANT ALL PRIVILEGES ON SCHEMA logging TO postgres;
GRANT ALL PRIVILEGES ON SCHEMA shared TO postgres;

-- Verify schemas were created
SELECT schema_name 
FROM information_schema.schemata 
WHERE schema_name IN (
    'data_ingestion', 'strategy_engine', 'execution', 
    'risk_management', 'analytics', 'notification', 
    'logging', 'shared'
) 
ORDER BY schema_name;
