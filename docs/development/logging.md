# Trading System Logging Architecture

## Overview

This document outlines the logging architecture for the trading system, including design decisions, implementation strategy, and configuration management.

**Last Updated**: 4/3/2026  
**Status**: ✅ Implemented  
**Author**: Nishant Nayar

## Design Decisions

### 1. Logging Framework
- **Primary**: Loguru (consolidated logging across all services)
- **Secondary**: PostgreSQL tables for structured log storage
- **Rationale**: Loguru provides excellent performance and features, PostgreSQL enables queryable log analysis

### 2. Log Retention Strategy
- **Approach**: Simple two-tier retention
- **Active Logs**: 30 days (real-time monitoring, hot queries)
- **Archived Logs**: 30-90 days (historical analysis, reports)
- **Cleanup**: Automatic daily cleanup at 2 AM
- **Storage**: Same database, different tables

### 3. Compliance Requirements
- **Status**: No compliance requirements
- **Focus**: Debugging, performance monitoring, system health
- **Audit Trail**: Basic audit logging for system operations

### 4. Log Aggregation
- **Method**: PostgreSQL tables for structured log storage
- **Benefits**: SQL queries, indexing, correlation with trading data
- **Integration**: Seamless with existing database infrastructure

## Architecture Components

### 1. Log Categories
```
📊 Trading Logs:     Trade executions, orders, positions
🔧 System Logs:      Service health, errors, startup/shutdown
⚡ Performance Logs: Execution times, memory usage
🧠 Strategy Logs:    Signal generation, backtesting results
⚠️  Risk Logs:       Risk calculations, violations, alerts
```

### 2. Log Levels
```
ERROR:   System failures, API errors, trading failures
WARNING: Risk violations, performance issues, retries
INFO:    Normal operations, trade executions, data flow
DEBUG:   Detailed execution (development only)
```

### 3. Service-Specific Logging
| Service | Log Level | Focus Area |
|---------|-----------|------------|
| Data Ingestion | INFO | Market data fetch, validation |
| Strategy Engine | DEBUG | Signal generation, calculations |
| Execution | INFO | Order placement, trade execution |
| Risk Management | WARNING | Risk calculations, violations |
| Analytics | INFO | Performance calculations, reports |
| Notification | INFO | Alert delivery, communication |

## Implementation Architecture

### 1. Dual Logging System

```
┌─────────────────────────────────────────────────────────┐
│                  Application Code                       │
├─────────────────────────────────────────────────────────┤
│              Logging Module (src/shared/logging/)       │
│  ├── logger.py              # Main logger setup        │
│  ├── database_handler.py    # Async queue-based DB     │
│  ├── database_sink.py        # Loguru sink for DB       │
│  ├── formatters.py          # Log formatting           │
│  ├── config.py               # Configuration loader     │
│  └── correlation.py         # Correlation ID tracking  │
├─────────────────────────────────────────────────────────┤
│         Loguru (File)           PostgreSQL (DB)        │
│  ├── logs/errors.log         ├── logging.system_logs   │
│  (minimal fallback)           └── logging.performance  │
│                                _logs                    │
└─────────────────────────────────────────────────────────┘
```

### 2. Key Features

#### Feature 1: Automatic Service Detection
```python
# Automatically detects which service is logging
from src.shared.logging import get_logger

logger = get_logger(__name__)  # Detects service from module name
logger.info("Data ingestion started")
# → Logs to: logs/data_ingestion.log AND logging.system_logs
```

#### Feature 2: Dual Output (File + Database)
```python
# Single log statement goes to BOTH:
logger.info("Order created", order_id="ORD123", symbol="AAPL")

# File output (logs/execution.log):
# 2025-10-01 10:30:45.123 | INFO | execution:create_order:42 | Order created

# Database output (logging.system_logs):
# {
#   timestamp: 2025-10-01 10:30:45.123,
#   service: 'execution',
#   level: 'INFO',
#   message: 'Order created',
#   metadata: {'order_id': 'ORD123', 'symbol': 'AAPL'}
# }
```

#### Feature 3: Correlation ID Tracking
```python
# Track related operations across services
with correlation_context("trade-12345"):
    logger.info("Order placed")
    # ... order execution ...
    logger.info("Position updated")
    # ... position update ...
    
# All logs have correlation_id='trade-12345'
# Easy to trace complete flow!
```

#### Feature 4: Performance Tracking
```python
from src.shared.logging import log_performance

@log_performance
def execute_trade(order_id):
    # Your code here
    pass
    
# Automatically logs:
# - Execution time
# - Memory usage (optional)
# - Function arguments (optional)
# Stored in logging.performance_logs
```

#### Feature 5: Structured Logging
```python
# Pass structured data
logger.info(
    "Trade executed",
    trade_id="TRD123",
    symbol="AAPL",
    quantity=100,
    price=150.25,
    commission=1.50
)

# Stored as JSONB in database
# Easy to query and analyze!
```

### 3. Logger Setup Options

#### Option A: Simple Setup (Recommended)
```python
from src.shared.logging import setup_logging

# Setup once at application startup
setup_logging()

# Use everywhere
from loguru import logger
logger.info("Application started")
```

**Pros:**
- Simple to use
- One-time setup
- Works everywhere
- No boilerplate

**Cons:**
- Less control per module
- Global configuration

#### Option B: Service-Specific Setup
```python
from src.shared.logging import get_service_logger

# Each service gets its own logger
logger = get_service_logger("data_ingestion")
logger.info("Market data fetched")
# → Logs to logs/data_ingestion.log
```

**Pros:**
- Service-specific configuration
- Isolated log files
- Different log levels per service

**Cons:**
- More setup code
- Need to specify service name

#### Option C: Context-Aware Logger (Advanced)
```python
from src.shared.logging import get_logger

# Automatically detects service from module name
logger = get_logger(__name__)  
# __name__ = 'src.services.execution.order_manager'
# → Detected service: 'execution'
# → Logs to: logs/execution.log
```

**Pros:**
- Automatic service detection
- No hardcoding service names
- Clean code
- Recommended approach!

**Cons:**
- Relies on module structure

### 4. Database Handler Design

#### Implementation Details
The database logging system uses an async queue-based architecture:

- **Queue Manager** (`LogQueueManager`): Manages background thread for async log processing
- **Database Sink** (`DatabaseSink`): Loguru sink that receives log records and enqueues them
- **Batch Processing**: Logs are batched for efficient database writes
- **Thread Safety**: All operations are thread-safe using locks

#### Batching Strategy
- **Method**: Async queue-based batching with background worker thread
- **Batch Size**: 100 records (configurable via `batch_size`)
- **Batch Timeout**: 10 seconds (configurable via `batch_timeout`)
- **Queue Size**: Maximum 10,000 logs before blocking
- **Fallback**: Write to file if database fails
- **Benefits**: Non-blocking writes, efficient bulk inserts, graceful degradation

#### Log Levels for Database
- **Files**: ERROR only (minimal fallback for critical failures)
- **Database**: INFO+ (all logs INFO and above stored in database)
- **Rationale**: Database is primary storage, files are minimal fallback only

#### Error Handling
```python
# Graceful degradation strategy
try:
    write_to_database(log)
except DatabaseError:
    try:
        write_to_fallback_file(log)
    except IOError:
        print(f"CRITICAL: Failed to log: {log}", file=sys.stderr)
        # Never fail the application due to logging!
```

## Database Schema

The logging schema is located in the `logging` schema of the PostgreSQL database. Tables are created automatically via SQLAlchemy models or SQL scripts.

### 1. System Logs Table
```sql
CREATE TABLE logging.system_logs (
    id BIGSERIAL PRIMARY KEY,
    service VARCHAR(50) NOT NULL,
    level VARCHAR(20) NOT NULL,  -- 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    message TEXT NOT NULL,
    data JSONB,                  -- Structured metadata
    correlation_id VARCHAR(100), -- For request tracking
    event_type VARCHAR(50),      -- Event classification
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_system_logs_timestamp ON logging.system_logs(timestamp);
CREATE INDEX idx_system_logs_service ON logging.system_logs(service);
CREATE INDEX idx_system_logs_level ON logging.system_logs(level);
CREATE INDEX idx_system_logs_correlation ON logging.system_logs(correlation_id);
CREATE INDEX idx_system_logs_event_type ON logging.system_logs(event_type);
CREATE INDEX idx_system_logs_service_timestamp ON logging.system_logs(service, timestamp);
```

### 2. Performance Logs Table
```sql
CREATE TABLE logging.performance_logs (
    id BIGSERIAL PRIMARY KEY,
    service VARCHAR(50) NOT NULL,
    operation VARCHAR(100) NOT NULL,
    execution_time_ms DECIMAL(10,3) NOT NULL,
    memory_usage_mb DECIMAL(10,3),
    cpu_usage_percent DECIMAL(5,2),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_performance_logs_timestamp ON logging.performance_logs(timestamp);
CREATE INDEX idx_performance_logs_service ON logging.performance_logs(service);
CREATE INDEX idx_performance_logs_operation ON logging.performance_logs(operation);
CREATE INDEX idx_performance_logs_service_timestamp ON logging.performance_logs(service, timestamp);
```

### 3. SQLAlchemy Models

The database models are defined in `src/shared/database/models/logging_models.py`:

- **SystemLog**: Represents general system logs with structured data
- **PerformanceLog**: Represents performance metrics with execution times and resource usage

Both models use:
- Timezone-aware timestamps (UTC)
- Proper indexing for query performance
- JSONB for flexible metadata storage
- Automatic timestamp defaults

## Configuration

### 1. Logging Configuration (config/logging.yaml)
```yaml
logging:
  # Log Levels
  level: "INFO"
  root_level: "INFO"
  
  # Log Rotation (for minimal file fallback)
  rotation:
    size: "10 MB"
    time: "daily"
    retention: "30 days"
    compression: false
    
  # Log Format
  format: "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}"
  
  # Log Files (minimal - only for error fallback)
  files:
    main: "logs/trading.log"
    errors: "logs/errors.log"
    system: "logs/system.log"
    trades: "logs/trades.log"
    performance: "logs/performance.log"
    
  # Service-specific Logging
  services:
    data_ingestion:
      level: "INFO"
      file: "logs/data_ingestion.log"
    strategy_engine:
      level: "DEBUG"
      file: "logs/strategy_engine.log"
    execution:
      level: "INFO"
      file: "logs/execution.log"
    risk_management:
      level: "WARNING"
      file: "logs/risk_management.log"
    analytics:
      level: "INFO"
      file: "logs/analytics.log"
    notification:
      level: "INFO"
      file: "logs/notification.log"
      
  # Structured Logging
  structured: true
  json_format: false
  
  # Performance Logging
  performance:
    enabled: true
    log_execution_time: true
    log_memory_usage: true
    log_database_queries: false
  
  # Database Logging (Primary Storage)
  database:
    enabled: true
    active_table: "system_logs"
    archive_table: "archived_system_logs"
    batch_size: 100              # Write when 100 logs are queued
    batch_timeout: 10             # Write every 10 seconds (or when batch is full)
    async_logging: true           # Use async queue-based processing
    fallback_to_file: true        # Fallback to file if database fails
```

### 2. Environment Settings
```python
# src/config/settings.py
class LoggingSettings(BaseSettings):
    # File retention
    file_retention_days: int = 30
    file_archive_after_days: int = 7
    
    # Database retention
    database_retention_days: int = 30
    database_archive_after_days: int = 7
    
    # Cleanup schedule
    cleanup_schedule: str = "0 2 * * *"
    cleanup_batch_size: int = 1000
    
    # Retention policies
    trading_logs_retention: int = 90
    performance_logs_retention: int = 30
    system_logs_retention: int = 30
    error_logs_retention: int = 90
```

## Usage Patterns

### Pattern 1: Simple Logging
```python
from loguru import logger

logger.info("Application started")
logger.error("Failed to connect to API", error=str(e))
```

### Pattern 2: Structured Logging
```python
logger.info(
    "Order executed",
    order_id="ORD123",
    symbol="AAPL",
    quantity=100,
    price=150.25,
    execution_time_ms=45
)
```

### Pattern 3: Performance Tracking
```python
from src.shared.logging import log_performance

@log_performance
def calculate_indicators(symbol: str, period: int):
    # Heavy calculation
    pass
```

### Pattern 4: Correlation Tracking
```python
from src.shared.logging import correlation_context

async def process_trade_flow(trade_id):
    with correlation_context(trade_id):
        await validate_risk()      # Logged with trade_id
        await execute_order()      # Logged with trade_id
        await update_position()    # Logged with trade_id
```

## Implementation Strategy

### 1. Dual Logging Approach
```
Service → Loguru → File + PostgreSQL
                ↓
        Structured Data → Database
                ↓
        SQL Queries → Analysis
```

### 2. Automatic Cleanup Process
- **Schedule**: Daily at 2 AM via Prefect flows
- **Process**: 
  1. Archive logs older than 30 days
  2. Delete archived logs older than 90 days
  3. Log cleanup results
- **Monitoring**: Cleanup operation logs (future enhancement)

### 3. Log Analysis Capabilities
```sql
-- Find all logs related to a specific trade
SELECT * FROM system_logs 
WHERE correlation_id = 'trade_12345'
ORDER BY timestamp;

-- Link trading logs with system logs
SELECT t.*, s.message, s.level
FROM trading_logs t
JOIN system_logs s ON t.trade_id = s.correlation_id
WHERE t.symbol = 'AAPL';

-- Performance analysis
SELECT service, AVG(execution_time_ms) as avg_time
FROM performance_logs 
WHERE timestamp > NOW() - INTERVAL '1 day'
GROUP BY service;
```

## Implementation Status

### ✅ Phase 1: Core Logging (Completed)
- [x] Basic Loguru setup
- [x] File logging with rotation (minimal fallback)
- [x] Service detection
- [x] Configuration loading

### ✅ Phase 2: Database Integration (Completed)
- [x] Database handler with async queue-based processing
- [x] Database sink for loguru integration
- [x] Async batching with configurable batch size and timeout
- [x] Fallback mechanism to file logging
- [x] Structured logging with JSONB metadata
- [x] SQLAlchemy models for SystemLog and PerformanceLog
- [x] Database schema creation

### ✅ Phase 3: Advanced Features (Completed)
- [x] Correlation ID tracking
- [x] Performance logging support
- [x] Thread-safe queue management
- [x] Graceful shutdown with log flushing

### 🚧 Phase 4: Monitoring (Future)
- [ ] Real-time log streaming
- [ ] Error alerting
- [ ] Performance dashboards
- [ ] Anomaly detection
- [ ] Log retention and cleanup automation

## Future Enhancements

### 1. Phase 2 (Post-MVP)
- [ ] Real-time log monitoring dashboard
- [ ] Log analysis tools with charts
- [ ] Automated alerting based on log patterns
- [ ] Log correlation analysis tools

### 2. Phase 3 (Advanced)
- [ ] Machine learning for log pattern detection
- [ ] Predictive alerting based on log trends
- [ ] Advanced log visualization
- [ ] Integration with external monitoring tools

## Open Questions

### 1. Implementation Details
- [x] Logging implementation in shared utilities
- [x] Prefect flow for automatic cleanup
- [x] Log correlation ID generation strategy
- [x] Performance optimization for high-volume logging

### 2. Monitoring & Alerts
- [ ] Real-time log monitoring requirements
- [ ] Alert thresholds for error rates
- [ ] Performance degradation detection
- [ ] System health indicators

### 3. Development vs Production
- [ ] Different logging levels for environments
- [ ] Development debugging tools
- [ ] Production log optimization
- [ ] Testing log configurations

## Usage Examples

### Basic Logging
```python
from loguru import logger

# Simple logging - automatically goes to database
logger.info("Application started")
logger.error("Failed to connect to API", error=str(e))
```

### Structured Logging
```python
# Structured data automatically stored in JSONB
logger.info(
    "Order executed",
    order_id="ORD123",
    symbol="AAPL",
    quantity=100,
    price=150.25,
    execution_time_ms=45
)
```

### Correlation Tracking
```python
from src.shared.logging.correlation import set_correlation_id

# Set correlation ID for request tracking
set_correlation_id("trade-12345")
logger.info("Order placed")  # Automatically includes correlation_id
logger.info("Position updated")  # Same correlation_id
```

### Performance Logging
```python
from src.shared.logging import log_performance

@log_performance
def calculate_indicators(symbol: str, period: int):
    # Heavy calculation
    pass
# Automatically logs execution time to performance_logs table
```

## Querying Logs

### Find logs by correlation ID
```sql
SELECT * FROM logging.system_logs 
WHERE correlation_id = 'trade-12345'
ORDER BY timestamp;
```

### Performance analysis
```sql
SELECT 
    service, 
    operation,
    AVG(execution_time_ms) as avg_time,
    MAX(execution_time_ms) as max_time,
    COUNT(*) as call_count
FROM logging.performance_logs 
WHERE timestamp > NOW() - INTERVAL '1 day'
GROUP BY service, operation
ORDER BY avg_time DESC;
```

### Error analysis
```sql
SELECT 
    service,
    level,
    COUNT(*) as error_count,
    MAX(timestamp) as last_error
FROM logging.system_logs 
WHERE level IN ('ERROR', 'CRITICAL')
    AND timestamp > NOW() - INTERVAL '7 days'
GROUP BY service, level
ORDER BY error_count DESC;
```

## Next Steps

1. ✅ **Database Schema**: Log tables implemented in PostgreSQL
2. ✅ **Logging Utilities**: Shared logging utilities created
3. ✅ **Service Integration**: Logging integrated across services
4. 🚧 **Cleanup Automation**: Implement Prefect cleanup flows for log retention
5. ✅ **Testing**: Logging configuration tested and working

---

**Note**: This document will be updated as we make more architectural decisions and implement the logging system.
