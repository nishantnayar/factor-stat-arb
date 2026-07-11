# Trading System Database Architecture

> **📊 Detailed Database Analysis**: For a comprehensive review of database schema design, performance considerations, and implementation strategies, see [Database Architecture Detailed Review](database.md).

## Database Connectivity Strategy

### Separate Database Architecture with Prefect 3.4.14

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

### Trading System Database (Service-Specific Schemas)
- **Data Ingestion**: `market_data`, `data_quality_logs`, `ingestion_status`
- **Strategy Engine**: `strategies`, `strategy_signals`, `strategy_configs`
- **Execution**: `orders`, `trades`, `positions`, `execution_logs`
- **Risk Management**: `risk_limits`, `risk_events`, `position_limits`
- **Analytics**: `performance_metrics`, `reports`, `analytics_cache`
- **Notification**: `alert_configs`, `notification_logs`
- **Logging**: `system_logs`, `trading_logs`, `performance_logs`

### Prefect Database (Orchestration)
- **Flow Management**: `flow_runs`, `task_runs`, `deployments`
- **Work Pools**: `work_pools`, `workers`
- **Blocks**: `blocks`, `block_documents`
- **UI State**: `ui_settings`, `saved_searches`

### Why Separate Databases:
- **Prefect Compatibility**: Works exactly as Prefect 3.4.14 expects
- **Clean Architecture**: Clear separation of orchestration and trading data
- **No Workarounds**: No hacks or unsupported configurations
- **Future-Proof**: Compatible with Prefect updates
- **Operational Simplicity**: Independent management and monitoring

## Database Schema

### Core Trading Tables
```sql
-- Market Data Storage (Enhanced Design)
CREATE TABLE market_data (
    id BIGSERIAL,
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    open DECIMAL(15,4),
    high DECIMAL(15,4),
    low DECIMAL(15,4),
    close DECIMAL(15,4),
    volume BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    data_source VARCHAR(20) NOT NULL DEFAULT 'polygon',  -- yahoo, yahoo_adjusted, alpaca, etc.
    -- Constraints: (symbol, timestamp, data_source) for multi-source and yahoo vs yahoo_adjusted
    CONSTRAINT unique_symbol_timestamp_source UNIQUE (symbol, timestamp, data_source),
    CONSTRAINT valid_data_source CHECK (data_source IN ('polygon', 'yahoo', 'yahoo_adjusted', 'alpaca', ...))
);

-- Trading Operations (Enhanced Design)
CREATE TYPE order_side AS ENUM ('buy', 'sell');
CREATE TYPE order_type AS ENUM ('market', 'limit', 'stop', 'stop_limit');
CREATE TYPE order_status AS ENUM ('pending', 'submitted', 'filled', 'partially_filled', 'cancelled', 'rejected');

CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    order_id VARCHAR(100) UNIQUE NOT NULL,
    account_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side order_side NOT NULL,
    order_type order_type NOT NULL,
    quantity DECIMAL(15,4) NOT NULL,
    price DECIMAL(15,4),
    status order_status NOT NULL DEFAULT 'pending',
    strategy VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE trades (
    id BIGSERIAL PRIMARY KEY,
    trade_id VARCHAR(100) UNIQUE NOT NULL,
    order_id VARCHAR(100) REFERENCES orders(order_id),
    account_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    quantity DECIMAL(15,4) NOT NULL,
    price DECIMAL(15,4) NOT NULL,
    commission DECIMAL(10,4) DEFAULT 0,
    executed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    strategy VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE positions (
    id BIGSERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    quantity DECIMAL(15,4) NOT NULL,
    avg_price DECIMAL(15,4) NOT NULL,
    market_value DECIMAL(15,4),
    unrealized_pnl DECIMAL(15,4),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT unique_account_symbol UNIQUE (account_id, symbol)
);
```

### Strategy Management Tables
```sql
-- Strategy Configuration
CREATE TABLE strategies (
    id SERIAL PRIMARY KEY,
    strategy_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    parameters JSONB,
    status VARCHAR(20) DEFAULT 'inactive', -- 'active', 'inactive', 'paused'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Strategy Signals
CREATE TABLE strategy_signals (
    id SERIAL PRIMARY KEY,
    signal_id VARCHAR(100) UNIQUE NOT NULL,
    strategy_id VARCHAR(100) REFERENCES strategies(strategy_id),
    symbol VARCHAR(20) NOT NULL,
    signal VARCHAR(20) NOT NULL, -- 'buy', 'sell', 'hold'
    strength DECIMAL(5,2), -- Signal strength 0-1
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Strategy Performance
CREATE TABLE strategy_performance (
    id SERIAL PRIMARY KEY,
    strategy_id VARCHAR(100) REFERENCES strategies(strategy_id),
    date DATE NOT NULL,
    returns DECIMAL(10,4),
    sharpe_ratio DECIMAL(8,4),
    max_drawdown DECIMAL(8,4),
    total_trades INTEGER,
    win_rate DECIMAL(5,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Logging Tables
```sql
-- System Logs
CREATE TABLE system_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    service VARCHAR(50) NOT NULL,
    level VARCHAR(10) NOT NULL,
    event_type VARCHAR(100),
    message TEXT,
    correlation_id VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Trading Logs
CREATE TABLE trading_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    trade_id VARCHAR(100),
    symbol VARCHAR(20),
    side VARCHAR(10),
    quantity DECIMAL(10,2),
    price DECIMAL(10,2),
    strategy VARCHAR(100),
    execution_time_ms INTEGER,
    status VARCHAR(50),
    error_message TEXT,
    correlation_id VARCHAR(100)
);

-- Performance Logs
CREATE TABLE performance_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    service VARCHAR(50),
    operation VARCHAR(100),
    execution_time_ms INTEGER,
    memory_usage_mb INTEGER,
    cpu_usage_percent DECIMAL(5,2),
    metadata JSONB
);
```

## Concurrent Database Access

### Connection Pooling Strategy
```python
# Service-specific connection pools
class ServiceConnectionPool:
    def __init__(self, service_name: str, postgres_url: str):
        self.service_name = service_name
        self.engine = create_engine(
            postgres_url,
            poolclass=QueuePool,
            pool_size=10,           # Base connections per service
            max_overflow=20,        # Additional connections when needed
            pool_pre_ping=True,     # Validate connections
            pool_recycle=3600,      # Recycle connections hourly
            echo=False
        )
```

### Event-Driven Data Synchronization
```python
# Data synchronization between services
class DataSyncEventBus:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
    
    def publish_data_event(self, event_type: str, service: str, data: Dict[Any, Any]):
        """Publish data change event"""
        event = {
            'type': event_type,
            'service': service,
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        }
        self.redis.publish(f'data_sync:{event_type}', json.dumps(event))
```

---

**See Also**:
- [Database Architecture Detailed Review](database.md) - Comprehensive database documentation
- [Architecture Overview](architecture-overview.md) - System overview
- [Services Architecture](architecture-services.md) - Service-specific schemas
- [Prefect Architecture](architecture-prefect.md) - Prefect database configuration

