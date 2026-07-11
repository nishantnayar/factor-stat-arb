# Database Optimization and ORM Patterns

## Overview

This document covers database performance optimization, indexing strategies, partitioning, data consistency patterns, monitoring, maintenance, security, and SQLAlchemy ORM usage patterns. For schema definitions, see [Database Schema](database-schema.md). For architecture overview, see [Database Overview](database-overview.md).

**Last Updated**: 4/3/2026  
**Status**: ✅ Core Patterns Implemented (v1.0.0)  
**Author**: Nishant Nayar

## Database Performance Considerations

### Indexing Strategy

#### Comprehensive Indexing Design
```sql
-- Market Data Indexes
CREATE INDEX idx_market_data_symbol_timestamp ON market_data(symbol, timestamp DESC);
CREATE INDEX idx_market_data_timestamp ON market_data(timestamp DESC);
CREATE INDEX idx_market_data_symbol ON market_data(symbol);

-- Trading Indexes
CREATE INDEX idx_orders_symbol_status ON orders(symbol, status);
CREATE INDEX idx_orders_strategy ON orders(strategy);
CREATE INDEX idx_orders_created_at ON orders(created_at DESC);
CREATE INDEX idx_orders_account_id ON orders(account_id);

CREATE INDEX idx_trades_symbol_executed_at ON trades(symbol, executed_at DESC);
CREATE INDEX idx_trades_strategy ON trades(strategy);
CREATE INDEX idx_trades_account_id ON trades(account_id);

-- Position Indexes
CREATE INDEX idx_positions_account_id ON positions(account_id);
CREATE INDEX idx_positions_symbol ON positions(symbol);

-- Logging Indexes
CREATE INDEX idx_system_logs_timestamp ON system_logs(timestamp DESC);
CREATE INDEX idx_system_logs_service_timestamp ON system_logs(service, timestamp DESC);
CREATE INDEX idx_system_logs_level_timestamp ON system_logs(level, timestamp DESC);
CREATE INDEX idx_system_logs_correlation ON system_logs(correlation_id);
CREATE INDEX idx_system_logs_event_type ON system_logs(event_type);

-- Performance Logs Indexes
CREATE INDEX idx_performance_logs_service_timestamp ON performance_logs(service, timestamp DESC);
CREATE INDEX idx_performance_logs_operation ON performance_logs(operation);
```

### Partitioning Strategy

#### Time-Based Partitioning for Large Tables
```sql
-- Partition market_data by year
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
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Create partitions for each year
CREATE TABLE market_data_y2024 PARTITION OF market_data
FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');

CREATE TABLE market_data_y2025 PARTITION OF market_data
FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');

-- Auto-create future partitions
CREATE OR REPLACE FUNCTION create_monthly_partition(table_name text, start_date date)
RETURNS void AS $$
DECLARE
    partition_name text;
    end_date date;
BEGIN
    partition_name := table_name || '_' || to_char(start_date, 'YYYY_MM');
    end_date := start_date + interval '1 month';
    
    EXECUTE format('CREATE TABLE %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
                   partition_name, table_name, start_date, end_date);
END;
$$ LANGUAGE plpgsql;
```

## Data Consistency and Concurrency

### Transaction Management

#### Transaction Strategy Design
```python
# src/shared/database/transaction_manager.py
from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy import text

class TransactionManager:
    def __init__(self, engine):
        self.engine = engine
    
    @contextmanager
    def transaction(self, isolation_level='READ_COMMITTED'):
        """Context manager for database transactions"""
        connection = self.engine.connect()
        transaction = connection.begin()
        
        try:
            # Set isolation level
            connection.execute(text(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}"))
            
            session = Session(bind=connection)
            yield session
            
            transaction.commit()
        except Exception as e:
            transaction.rollback()
            raise e
        finally:
            session.close()
            connection.close()
    
    @contextmanager
    def read_only_transaction(self):
        """Read-only transaction for analytics queries"""
        with self.transaction('READ_COMMITTED') as session:
            yield session
```

#### Optimistic Locking Implementation
```python
# src/shared/database/optimistic_locking.py
from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class OptimisticLockingMixin:
    version = Column(Integer, default=1, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def update_with_version(self, session, **kwargs):
        """Update with optimistic locking"""
        current_version = self.version
        self.version += 1
        
        result = session.query(self.__class__).filter(
            self.__class__.id == self.id,
            self.__class__.version == current_version
        ).update(kwargs)
        
        if result == 0:
            raise OptimisticLockingError("Record was modified by another process")
        
        return result
```

## Data Synchronization Patterns

### Event-Driven Synchronization

#### Event Bus Design
```python
# src/shared/events/data_sync.py
import redis
import json
from typing import Dict, Any, List
from datetime import datetime

class DataSyncEventBus:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
        self.pubsub = self.redis.pubsub()
    
    def publish_trade_event(self, trade_data: Dict[str, Any]):
        """Publish trade execution event"""
        event = {
            'type': 'trade_executed',
            'service': 'execution',
            'data': trade_data,
            'timestamp': datetime.utcnow().isoformat(),
            'correlation_id': trade_data.get('trade_id')
        }
        
        self.redis.publish('data_sync:trades', json.dumps(event))
    
    def publish_market_data_event(self, market_data: Dict[str, Any]):
        """Publish market data update event"""
        event = {
            'type': 'market_data_updated',
            'service': 'data_ingestion',
            'data': market_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.redis.publish('data_sync:market_data', json.dumps(event))
    
    def subscribe_to_events(self, event_types: List[str], callback):
        """Subscribe to data sync events"""
        for event_type in event_types:
            self.pubsub.subscribe(f'data_sync:{event_type}')
        
        for message in self.pubsub.listen():
            if message['type'] == 'message':
                event = json.loads(message['data'])
                callback(event)
```

#### Data Synchronization Service
```python
# src/shared/data_sync/synchronizer.py
class DataSynchronizer:
    def __init__(self, event_bus: DataSyncEventBus, analytics_db: Engine):
        self.event_bus = event_bus
        self.analytics_db = analytics_db
        self.setup_event_handlers()
    
    def setup_event_handlers(self):
        """Setup event handlers for data synchronization"""
        self.event_bus.subscribe_to_events(
            ['trades', 'market_data', 'positions'],
            self.handle_data_event
        )
    
    def handle_data_event(self, event: Dict[str, Any]):
        """Handle incoming data synchronization events"""
        event_type = event['type']
        
        if event_type == 'trade_executed':
            self.sync_trade_data(event['data'])
        elif event_type == 'market_data_updated':
            self.sync_market_data(event['data'])
        elif event_type == 'position_updated':
            self.sync_position_data(event['data'])
    
    def sync_trade_data(self, trade_data: Dict[str, Any]):
        """Sync trade data to analytics database"""
        with self.analytics_db.connect() as conn:
            # Update portfolio summary
            conn.execute(text("""
                INSERT INTO portfolio_summary (account_id, symbol, total_value, realized_pnl)
                VALUES (:account_id, :symbol, :total_value, :realized_pnl)
                ON CONFLICT (account_id, symbol) 
                DO UPDATE SET 
                    total_value = portfolio_summary.total_value + :total_value,
                    realized_pnl = portfolio_summary.realized_pnl + :realized_pnl,
                    last_updated = NOW()
            """), trade_data)
            
            # Update performance metrics
            conn.execute(text("""
                INSERT INTO performance_metrics (strategy, date, total_trades, win_rate)
                VALUES (:strategy, CURRENT_DATE, 1, :win_rate)
                ON CONFLICT (strategy, date)
                DO UPDATE SET 
                    total_trades = performance_metrics.total_trades + 1,
                    win_rate = (performance_metrics.win_rate * performance_metrics.total_trades + :win_rate) / (performance_metrics.total_trades + 1)
            """), trade_data)
```

## Database Monitoring and Maintenance

### Performance Monitoring
```python
# src/shared/monitoring/db_monitoring.py
class DatabaseMonitoring:
    def __init__(self, db_connections: Dict[str, Engine]):
        self.connections = db_connections
        self.metrics = {}
    
    def track_query_performance(self, service: str, query: str, execution_time: float):
        """Track query performance metrics"""
        if service not in self.metrics:
            self.metrics[service] = {
                'query_count': 0,
                'total_time': 0,
                'slow_queries': []
            }
        
        self.metrics[service]['query_count'] += 1
        self.metrics[service]['total_time'] += execution_time
        
        if execution_time > 1.0:  # 1 second threshold
            self.metrics[service]['slow_queries'].append({
                'query': query,
                'execution_time': execution_time,
                'timestamp': datetime.utcnow()
            })
    
    def get_performance_summary(self):
        """Get database performance summary"""
        summary = {}
        for service, metrics in self.metrics.items():
            summary[service] = {
                'avg_query_time': metrics['total_time'] / metrics['query_count'] if metrics['query_count'] > 0 else 0,
                'total_queries': metrics['query_count'],
                'slow_query_count': len(metrics['slow_queries'])
            }
        return summary
```

### Automated Maintenance
```python
# src/shared/maintenance/db_maintenance.py
class DatabaseMaintenance:
    def __init__(self, db_connections: Dict[str, Engine]):
        self.connections = db_connections
    
    def run_vacuum_analyze(self, service: str):
        """Run VACUUM ANALYZE on service database"""
        with self.connections[service].connect() as conn:
            conn.execute(text("VACUUM ANALYZE"))
    
    def cleanup_old_logs(self, service: str, retention_days: int = 30):
        """Clean up old log entries"""
        with self.connections[service].connect() as conn:
            # Archive old logs
            conn.execute(text("""
                INSERT INTO archived_system_logs 
                SELECT * FROM system_logs 
                WHERE created_at < NOW() - INTERVAL '%s days'
            """), (retention_days,))
            
            # Delete archived logs
            conn.execute(text("""
                DELETE FROM system_logs 
                WHERE created_at < NOW() - INTERVAL '%s days'
            """), (retention_days,))
    
    def update_statistics(self, service: str):
        """Update database statistics"""
        with self.connections[service].connect() as conn:
            conn.execute(text("ANALYZE"))
```

## Security Considerations

### Database Security Implementation
```python
# src/shared/security/db_security.py
class DatabaseSecurity:
    def __init__(self, db_connections: Dict[str, Engine]):
        self.connections = db_connections
    
    def setup_row_level_security(self, service: str):
        """Setup row-level security for multi-tenant data"""
        with self.connections[service].connect() as conn:
            # Enable RLS on sensitive tables
            conn.execute(text("ALTER TABLE trades ENABLE ROW LEVEL SECURITY"))
            conn.execute(text("ALTER TABLE positions ENABLE ROW LEVEL SECURITY"))
            conn.execute(text("ALTER TABLE orders ENABLE ROW LEVEL SECURITY"))
            
            # Create policies
            conn.execute(text("""
                CREATE POLICY trades_account_policy ON trades
                FOR ALL TO trading_app
                USING (account_id = current_setting('app.current_account_id'))
            """))
    
    def audit_data_access(self, service: str, user_id: str, table_name: str, operation: str):
        """Audit data access for compliance"""
        with self.connections[service].connect() as conn:
            conn.execute(text("""
                INSERT INTO audit_log (user_id, table_name, operation, timestamp)
                VALUES (:user_id, :table_name, :operation, NOW())
            """), {
                'user_id': user_id,
                'table_name': table_name,
                'operation': operation
            })
```

## SQLAlchemy ORM and Session Management

### Overview

The trading system uses SQLAlchemy ORM (Object-Relational Mapping) to interact with PostgreSQL. This provides a Pythonic interface to the database while maintaining type safety and preventing SQL injection attacks.

### Declarative Base

All database models inherit from a common declarative base:

```python
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# All models inherit from Base
class MarketData(Base):
    __tablename__ = "market_data"
    __table_args__ = {'schema': 'data_ingestion'}
    # ... column definitions
```

**Purpose:**
- Provides metadata registry for all tables
- Enables ORM mapping between Python classes and database tables
- Tracks relationships and foreign keys
- Provides query interface

### Session Management Design

#### Automated Session Management

The system uses **context managers** for automatic session lifecycle management:

```python
# Write operations
with db_transaction() as session:
    order = Order(symbol='AAPL', quantity=100)
    session.add(order)
    # Auto-commit on success, auto-rollback on error

# Read operations
with db_readonly_session() as session:
    results = session.query(MarketData).filter_by(symbol='AAPL').all()
```

#### Two Session Types

**1. Transaction Session (`db_transaction`)**

For write operations that modify data:

```python
@contextmanager
def db_transaction() -> Generator[Session, None, None]:
    """
    Database transaction context manager with automatic commit/rollback
    
    Features:
    - Automatic commit on success
    - Automatic rollback on error
    - Connection pooling
    - Error logging
    - Always closes session
    
    Usage:
        with db_transaction() as session:
            order = Order(symbol='AAPL', quantity=100)
            session.add(order)
    
    Use cases:
    - Creating orders, trades, positions
    - Updating risk limits
    - Recording strategy signals
    - Any data modification
    """
```

**2. Read-Only Session (`db_readonly_session`)**

For read operations that don't modify data:

```python
@contextmanager
def db_readonly_session() -> Generator[Session, None, None]:
    """
    Read-only database session for analytics and reporting
    
    Features:
    - No write operations allowed
    - Optimized for read performance
    - No transaction overhead
    - Connection pooling
    
    Usage:
        with db_readonly_session() as session:
            data = session.query(MarketData).filter(...).all()
    
    Use cases:
    - Analytics queries
    - Dashboard data
    - Reporting
    - Backtesting
    """
```

**Performance Benefits of Read-Only Sessions:**
- No Write-Ahead Log (WAL) overhead
- Reduced locking overhead
- PostgreSQL can optimize query execution
- Lower resource consumption
- Can leverage read replicas (future scaling)

#### Schema Handling

Schemas are specified in model definitions using `__table_args__`:

```python
class MarketData(Base):
    __tablename__ = "market_data"
    __table_args__ = {'schema': 'data_ingestion'}  # Explicit schema
    
    id = Column(BigInteger, primary_key=True)
    symbol = Column(String(20), nullable=False)
    # ...
```

**Benefits:**
- Schema is explicit in code
- No connection string magic
- Works with automated session management
- Maintains schema isolation

#### Error Handling Strategy

The session manager implements comprehensive error handling:

```python
try:
    yield session
    session.commit()
    logger.debug("Transaction committed successfully")
    
except IntegrityError as e:
    session.rollback()
    logger.error(f"Database integrity error: {e}")
    raise  # Constraint violations, duplicate keys
    
except OperationalError as e:
    session.rollback()
    logger.error(f"Database operational error: {e}")
    raise  # Connection issues, timeouts
    
except DataError as e:
    session.rollback()
    logger.error(f"Database data error: {e}")
    raise  # Invalid data types, out of range
    
except Exception as e:
    session.rollback()
    logger.error(f"Unexpected database error: {e}")
    raise
    
finally:
    session.close()  # Always close
```

**Error Categories:**
- **IntegrityError** - Constraint violations, duplicate keys
- **OperationalError** - Connection problems, timeouts
- **DataError** - Invalid data types, out of range values
- **ProgrammingError** - SQL syntax errors

**Error Handling Benefits:**
- Centralized error logging (all DB errors captured)
- Categorized errors for different handling strategies
- Exceptions re-raised for caller to handle
- Stack traces preserved for debugging
- Monitoring and alerting ready

#### Connection Pooling

Connection pooling is configured in `src/config/database.py`:

```python
engine = create_engine(
    database_url,
    poolclass=QueuePool,
    pool_size=10,         # Keep 10 connections open
    max_overflow=20,      # Allow 20 more if needed
    pool_timeout=30,      # Wait 30s for available connection
    pool_recycle=3600     # Recycle connections after 1 hour
)
```

**Benefits:**
- Reuses existing connections (faster)
- Prevents connection exhaustion
- Automatic connection management
- Configurable pool size per workload

### Usage Examples

#### Example 1: Create Order (Write Operation)

```python
from src.services.execution.models import Order, OrderSide
from src.shared.database.base import db_transaction

def create_order(symbol: str, quantity: int, price: float):
    """Create a new trading order"""
    with db_transaction() as session:
        order = Order(
            order_id=generate_id(),
            account_id='ACC123',
            symbol=symbol,
            quantity=quantity,
            price=price,
            side=OrderSide.BUY,
            status=OrderStatus.PENDING
        )
        session.add(order)
        # Auto-commit on success
        return order.order_id
```

#### Example 2: Query Market Data (Read Operation)

```python
from src.services.data_ingestion.models import MarketData
from src.shared.database.base import db_readonly_session
from datetime import datetime, timedelta

def get_market_history(symbol: str, days: int):
    """Get historical market data"""
    with db_readonly_session() as session:
        cutoff = datetime.now() - timedelta(days=days)
        return session.query(MarketData)\
            .filter(MarketData.symbol == symbol)\
            .filter(MarketData.timestamp >= cutoff)\
            .order_by(MarketData.timestamp.desc())\
            .all()
```

#### Example 3: Complex Transaction (Multiple Operations)

```python
from src.shared.database.base import db_transaction

def execute_trade(order_id: str, execution_price: float):
    """Execute a trade and update related records"""
    with db_transaction() as session:
        # 1. Get and update order
        order = session.query(Order).filter_by(order_id=order_id).first()
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        order.status = OrderStatus.FILLED
        order.updated_at = datetime.now(timezone.utc)
        
        # 2. Create trade record
        trade = Trade(
            trade_id=generate_id(),
            order_id=order_id,
            account_id=order.account_id,
            symbol=order.symbol,
            quantity=order.quantity,
            price=execution_price,
            executed_at=datetime.now(timezone.utc)
        )
        session.add(trade)
        
        # 3. Update or create position
        position = session.query(Position).filter_by(
            account_id=order.account_id,
            symbol=order.symbol
        ).first()
        
        if position:
            # Update existing position
            position.quantity += order.quantity
            position.avg_price = calculate_avg_price(position, order)
            position.last_updated = datetime.now(timezone.utc)
        else:
            # Create new position
            position = Position(
                account_id=order.account_id,
                symbol=order.symbol,
                quantity=order.quantity,
                avg_price=execution_price
            )
            session.add(position)
        
        # All operations committed together or all rolled back
        return trade.trade_id
```

#### Example 4: Analytics Query (Aggregation)

```python
from src.shared.database.base import db_readonly_session
from sqlalchemy import func

def get_portfolio_summary(account_id: str):
    """Get aggregated portfolio metrics"""
    with db_readonly_session() as session:
        summary = session.query(
            Position.symbol,
            Position.quantity,
            Position.avg_price,
            Position.unrealized_pnl,
            func.sum(Position.market_value).label('total_value')
        )\
        .filter(Position.account_id == account_id)\
        .filter(Position.quantity > 0)\
        .group_by(Position.symbol)\
        .all()
        
        return summary
```

### Design Principles

| Principle | Implementation | Benefit |
|-----------|----------------|---------|
| **Automation** | Context managers | Prevents connection leaks |
| **Separation** | Read/Write sessions | Performance optimization |
| **Explicitness** | Schema in models | Clear and maintainable |
| **Simplicity** | Single database | No distributed transactions |
| **Observability** | Error logging | Monitoring and debugging |
| **Safety** | Auto-rollback | Data consistency |
| **Efficiency** | Connection pooling | Resource optimization |

### Transaction Isolation

The system uses PostgreSQL's default isolation level:

- **Isolation Level**: READ COMMITTED
- **Behavior**: Queries see only committed data
- **Concurrency**: High (minimal locking)
- **Use Case**: Suitable for most trading operations

For operations requiring stronger guarantees:

```python
from sqlalchemy import text

with db_transaction() as session:
    # Set higher isolation level if needed
    session.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
    # Your operations here
```

### Best Practices

**DO:**
- ✅ Use `db_transaction()` for all write operations
- ✅ Use `db_readonly_session()` for analytics and reporting
- ✅ Keep transactions short and focused
- ✅ Handle exceptions at the application level
- ✅ Use connection pooling (already configured)
- ✅ Specify schema in model definitions

**DON'T:**
- ❌ Mix read and write sessions (use write session if needed)
- ❌ Keep transactions open for long periods
- ❌ Catch and ignore database errors
- ❌ Create sessions manually (use context managers)
- ❌ Use distributed transactions (not needed)
- ❌ Modify read-only session data

### Advanced Features

#### Manual Session Management (Advanced)

For cases requiring explicit control:

```python
from src.shared.database.base import get_session

def advanced_operation():
    """Advanced use case with manual session management"""
    session = get_session()
    try:
        # Your operations
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

⚠️ **Warning**: Manual session management requires careful handling. Prefer context managers.

#### Nested Transactions (Savepoints)

For complex operations requiring partial rollback:

```python
with db_transaction() as session:
    order = Order(...)
    session.add(order)
    
    # Create savepoint
    savepoint = session.begin_nested()
    try:
        # Risky operation
        risky_update()
        savepoint.commit()
    except Exception:
        # Rollback to savepoint, main transaction continues
        savepoint.rollback()
```

---

**See Also**:
- [Database Overview](database-overview.md) - Architecture overview and setup
- [Database Schema](database-schema.md) - Detailed schema definitions

