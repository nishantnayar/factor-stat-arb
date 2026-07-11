# Database Architecture Overview

## Overview

This document provides a high-level overview of the database architecture for the trading system, including distribution strategy, setup options, and implementation approach. For detailed schema definitions, see [Database Schema](database-schema.md). For performance optimization and ORM patterns, see [Database Optimization](database-optimization.md).

**Last Updated**: 4/3/2026  
**Status**: ✅ Core Architecture Implemented (v1.0.0)  
**Author**: Nishant Nayar

## Database Architecture Diagram

```mermaid
graph TB
    subgraph "PostgreSQL Instance"
        TradingDB[(trading_system<br/>Database)]
        PrefectDB[(prefect<br/>Database)]
    end
    
    subgraph "Trading System Schemas"
        DataIngestion[data_ingestion<br/>Schema]
        Strategy[strategy_engine<br/>Schema]
        Execution[execution<br/>Schema]
        Risk[risk_management<br/>Schema]
        Analytics[analytics<br/>Schema]
        Logging[logging<br/>Schema]
    end
    
    subgraph "Prefect Schema"
        PrefectSchema[public<br/>Schema]
    end
    
    TradingDB --> DataIngestion
    TradingDB --> Strategy
    TradingDB --> Execution
    TradingDB --> Risk
    TradingDB --> Analytics
    TradingDB --> Logging
    
    PrefectDB --> PrefectSchema
    
    style TradingDB fill:#00A86B
    style PrefectDB fill:#009688
    style DataIngestion fill:#e8f5e9
    style Analytics fill:#e8f5e9
    style Logging fill:#e8f5e9
```

## Database Distribution Strategy

### Selected Approach: Separate Databases with Prefect 3.4.14

```
Trading System Database + Prefect Database (Separate)
```

**Benefits:**
- Prefect compatibility with version 3.4.14
- Clean separation of orchestration and trading data
- No workarounds or unsupported configurations
- Future-proof against Prefect updates
- Independent management and monitoring

### Database Architecture Decision: Separate Databases

#### **Prefect 3.4.14 Integration**
Given Prefect 3.4.14's limitations with custom schemas, we're implementing a **separate database strategy**:

```
┌─────────────────────────────────────────────────────────┐
│                PostgreSQL Instance                      │
├─────────────────────────────────────────────────────────┤
│  trading_system database  │  prefect database          │
│  ├── data_ingestion       │  ├── public schema         │
│  ├── strategy_engine      │  │   ├── flow_runs         │
│  ├── execution            │  │   ├── task_runs         │
│  ├── risk_management      │  │   ├── deployments       │
│  ├── analytics            │  │   ├── work_pools        │
│  ├── notification         │  │   ├── blocks            │
│  └── logging              │  │   └── (other Prefect)   │
└─────────────────────────────────────────────────────────┘
```

#### **Why Separate Databases:**
- **Prefect Compatibility**: Works exactly as Prefect 3.4.14 expects
- **Clean Architecture**: Clear separation of orchestration and trading data
- **No Workarounds**: No hacks or unsupported configurations
- **Future-Proof**: Compatible with Prefect updates
- **Operational Simplicity**: Independent management and monitoring

## Database Setup Options

### Option 1: Python Script (Automated)
Run the database setup script:

```bash
python scripts/setup_databases.py
```

This script will:
- Create the `Prefect` database
- Create service-specific schemas in `trading_system`
- Configure Prefect to use PostgreSQL
- Note: Prefect will automatically initialize its tables when the server starts

### Option 2: SQL Scripts (Manual)
For more control or if you prefer SQL, run the scripts manually:

```bash
# 1. Create databases and schemas
psql -U postgres -h localhost -p 5432 -f scripts/01_create_databases.sql

# 2. Create core tables
psql -U postgres -h localhost -p 5432 -d trading_system -f scripts/02_create_core_tables.sql

# 3. Create indexes
psql -U postgres -h localhost -p 5432 -d trading_system -f scripts/03_create_indexes.sql

# 4. Verify setup
psql -U postgres -h localhost -p 5432 -d trading_system -f scripts/04_verify_setup.sql
```

The SQL scripts provide:
- Simple, transparent database setup
- Easy to modify and customize
- Clear error messages
- Step-by-step verification

### What Gets Created

#### Databases
- `trading_system` - Main trading database
- `Prefect` - Prefect orchestration database

#### Schemas in trading_system
- `data_ingestion` - Market data and quality logs
- `strategy_engine` - Strategies, signals, and performance
- `execution` - Orders, trades, and positions
- `risk_management` - Risk limits and events
- `analytics` - Portfolio and performance analytics
- `notification` - Alert configurations and logs
- `logging` - System and performance logs
- `shared` - Common utilities and configuration

#### Core Tables
- **Market Data**: `market_data`, `key_statistics`, `institutional_holders`, `data_quality_logs`
- **Trading**: `orders`, `trades`, `positions`
- **Strategy**: `strategies`, `strategy_signals`, `strategy_performance`
- **Risk**: `risk_limits`, `risk_events`
- **Analytics**: `portfolio_summary`, `performance_metrics`
- **Notification**: `notification_configs`, `notification_logs`
- **Logging**: `system_logs`, `performance_logs`
- **Shared**: `audit_log`, `system_config`

#### Backup

Key schemas (`data_ingestion`, `analytics`) are backed up weekly via Prefect (5 AM UTC Saturday) and on demand via `python scripts/backup_trading_db.py`. Backups are stored in `backups/`. See [Prefect Architecture](architecture-prefect.md#prefect-backup-and-recovery).

## Implementation Strategy

### Phase 1: Database Foundation & Setup

#### **1.1 Environment Setup**
- **PostgreSQL Installation**: Local PostgreSQL server setup
- **Database Creation**: Create `trading_system` and `prefect` databases
- **Connection Configuration**: Environment variables, connection strings
- **Database User Setup**: Service-specific users with appropriate permissions

#### **1.2 Prefect Database Setup**
```sql
-- Create Prefect database
CREATE DATABASE prefect;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE prefect TO postgres;
```

**Prefect Configuration:**
```bash
# Configure Prefect to use PostgreSQL
prefect config set PREFECT_API_DATABASE_CONNECTION_URL="postgresql+asyncpg://postgres:password@localhost:5432/prefect"

# Initialize Prefect database
prefect database upgrade
```

#### **1.3 Trading System Database Setup**
```sql
-- Create trading system database
CREATE DATABASE trading_system;

-- Create service-specific schemas
CREATE SCHEMA data_ingestion;
CREATE SCHEMA strategy_engine;
CREATE SCHEMA execution;
CREATE SCHEMA risk_management;
CREATE SCHEMA analytics;
CREATE SCHEMA notification;
CREATE SCHEMA logging;
CREATE SCHEMA shared;
```

#### **1.4 Environment Configuration**
```env
# Trading System Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
TRADING_DB_NAME=trading_system
TRADING_DB_USER=postgres
TRADING_DB_PASSWORD=your_password_here

# Prefect Database
PREFECT_DB_NAME=prefect
PREFECT_DB_USER=postgres
PREFECT_DB_PASSWORD=your_password_here

# Prefect Configuration
PREFECT_API_DATABASE_CONNECTION_URL=postgresql+asyncpg://postgres:password@localhost:5432/prefect

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_URL=redis://localhost:6379/0
```

### Phase 2: Schema Implementation

#### **2.1 Core Trading Tables**
- **Market Data Tables**: Enhanced with constraints and partitioning
- **Trading Operations**: Orders, trades, positions with proper relationships
- **Strategy Management**: Strategy configuration and performance tracking
- **System Logging**: Structured log storage

#### **2.2 Service-Specific Schemas**
- **data_ingestion**: Market data, symbols management, key statistics, institutional holders, company info, data quality logs, ingestion status
  - Symbol tables: `symbols`, `delisted_symbols`, `symbol_data_status` (see [SymbolService API](../api/data-ingestion-yahoo.md#symbolservice-api) section)
- **strategy_engine**: Strategies, signals, performance metrics
- **execution**: Orders, trades, positions, execution logs
- **risk_management**: Risk limits, events, position limits
- **analytics**: Performance calculations, reports, analytics
- **notification**: Alert configurations, notification logs
- **logging**: Centralized system logs from all services

### Phase 3: Connection Management

#### **3.1 Database Connection Strategy**
```python
# src/config/database.py
class DatabaseConfig:
    # Trading System Database
    TRADING_DB_URL = "postgresql://postgres:password@localhost:5432/trading_system"
    
    # Prefect Database
    PREFECT_DB_URL = "postgresql://postgres:password@localhost:5432/prefect"
    
    # Service-specific schemas
    SCHEMAS = {
        'data_ingestion': 'data_ingestion',
        'strategy_engine': 'strategy_engine',
        'execution': 'execution',
        'risk_management': 'risk_management',
        'analytics': 'analytics',
        'notification': 'notification',
        'logging': 'logging',
        'shared': 'shared'
    }
```

#### **3.2 Connection Pooling**
- **Trading System**: Service-specific connection pools
- **Prefect**: Dedicated connection pool
- **Redis**: Shared cache and message queue
- **Monitoring**: Connection health and performance tracking

### Phase 4: Data Synchronization

#### **4.1 Event-Driven Synchronization**
- **Redis Pub/Sub**: Cross-service data synchronization
- **Analytics Database**: Real-time updates to shared analytics
- **Log Aggregation**: Centralized logging from all services
- **Performance Metrics**: Real-time performance tracking

#### **4.2 Data Consistency**
- **Eventual Consistency**: Event-driven updates between services
- **Conflict Resolution**: Handling concurrent updates
- **Data Validation**: Multi-level data validation
- **Audit Trails**: Complete data lineage tracking

## Implementation Recommendations

### Phase 1: Schema Improvements
1. **Update Core Tables** with improved constraints and data types
2. **Implement Comprehensive Indexing** strategy
3. **Add Partitioning** for large tables
4. **Create Audit Tables** for compliance

### Phase 2: Performance Optimization
1. **Implement Connection Pooling** with proper configuration
2. **Add Query Performance Monitoring**
3. **Create Automated Maintenance** procedures
4. **Implement Caching** strategies

### Phase 3: Advanced Features
1. **Add Row-Level Security** for multi-tenancy
2. **Implement Data Encryption** for sensitive data
3. **Create Backup and Recovery** procedures
4. **Add Real-time Monitoring** dashboards

## Key Benefits of Enhanced Architecture

### 1. Performance
- Optimized queries with proper indexing
- Partitioned tables for large datasets
- Connection pooling for concurrent access
- Query performance monitoring

### 2. Reliability
- Data consistency with proper constraints
- Optimistic locking for concurrent updates
- Automated maintenance procedures
- Comprehensive error handling

### 3. Security
- Row-level security for data isolation
- Audit logging for compliance
- Data encryption for sensitive information
- Access control and monitoring

### 4. Maintainability
- Clear schema documentation
- Automated maintenance procedures
- Performance monitoring and alerting
- Comprehensive testing strategies

This enhanced database architecture provides a solid foundation for a production-grade trading system with proper performance, reliability, and security characteristics.

---

**See Also**:
- [Database Schema](database-schema.md) - Detailed schema definitions
- [Database Optimization](database-optimization.md) - Performance tuning and ORM patterns
- [System Architecture Index](architecture.md) - Overall system architecture

