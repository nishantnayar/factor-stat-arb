# Trading System Deployment Architecture

> **Status**: ✅ Core Deployment Strategy Documented (v1.0.0)

## Deployment Architecture

### Local Deployment Strategy

#### **Deployment Overview**
The trading system is designed for local deployment on Windows 10, providing a complete self-contained trading environment with all services running on a single machine.

#### **System Architecture**
```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                    Local Machine                        â”‚
â”‚                  (Windows 10)                          â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚  Infrastructure Layer                                   â”‚
â”‚  â”œâ”€â”€ PostgreSQL (Port 5432)                            â”‚
â”‚  â”œâ”€â”€ Redis (Port 6379)                                 â”‚
â”‚  â””â”€â”€ Prefect Server (Port 4200)                        â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚  Microservices Layer                                    â”‚
â”‚  â”œâ”€â”€ Data Ingestion    â”‚  Strategy Engine              â”‚
â”‚  â”œâ”€â”€ Execution Service â”‚  Risk Management              â”‚
â”‚  â””â”€â”€ Analytics Service â”‚  Notification Service         â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚  Web Layer                                              â”‚
â”‚  â”œâ”€â”€ FastAPI Web Server (Port 8000)                    â”‚
â”‚  â””â”€â”€ Frontend (Streamlit + Plotly + Custom CSS)       â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Service Deployment Strategy

#### **1. Infrastructure Services**
```yaml
# Infrastructure deployment order
infrastructure:
  - postgresql:     # Database server
    port: 5432
    databases: [trading_system, prefect]
    schemas: [data_ingestion, strategy_engine, execution, risk_management, analytics, notification, logging]
  
  - redis:          # Cache and message queue
    port: 6379
    databases: [0, 1, 2, 3, 4, 5]
  
  - prefect:        # Workflow orchestration
    port: 4200
    database: prefect
    ui_enabled: true
```

#### **2. Microservices Deployment**
```yaml
# Microservices deployment configuration
microservices:
  data_ingestion:
    port: 8001
    database_schema: data_ingestion
    dependencies: [postgresql, redis]
    prefect_flows: [fetch_market_data, validate_data_quality, archive_old_data]
  
  strategy_engine:
    port: 8002
    database_schema: strategy_engine
    dependencies: [postgresql, redis]
    prefect_flows: [run_strategy, calculate_indicators, generate_signals, backtest_strategy]
  
  execution:
    port: 8003
    database_schema: execution
    dependencies: [postgresql, redis, alpaca_api]
    prefect_flows: [execute_trades, manage_orders, update_positions, reconcile_trades]
  
  risk_management:
    port: 8004
    database_schema: risk_management
    dependencies: [postgresql, redis]
    prefect_flows: [calculate_position_size, validate_risk_limits, monitor_portfolio_risk, generate_risk_alerts]
  
  analytics:
    port: 8005
    database_schema: analytics
    dependencies: [postgresql, redis]
    prefect_flows: [calculate_performance, generate_reports, run_backtest, analyze_trades]
  
  notification:
    port: 8006
    database_schema: notification
    dependencies: [postgresql, redis, email_service]
    prefect_flows: [send_trade_alerts, monitor_system_health, aggregate_logs, send_daily_summary]
```

#### **3. Web Layer Deployment**
```yaml
# Web layer deployment
web_layer:
  fastapi_server:
    port: 8000
    dependencies: [all_microservices, postgresql, redis]
    endpoints: [api, health, metrics, logs]
  
  frontend:
    technology: [streamlit, plotly, custom_css]
    pages: [portfolio, analysis, screener, author, settings]
    api_integration: fastapi_server
    session_state: enabled
```

### Deployment Phases

#### **Phase 1: Infrastructure Setup**
```bash
# 1. Start PostgreSQL
pg_ctl start -D "C:\Program Files\PostgreSQL\15\data"

# 2. Start Redis
redis-server

# 3. Initialize Prefect
prefect server start
```

#### **Phase 2: Database Initialization**
```bash
# 1. Create databases
createdb trading_system
createdb prefect

# 2. Run database migrations
alembic upgrade head

# 3. Initialize Prefect database
prefect database upgrade
```

#### **Phase 3: Microservices Deployment**
```bash
# 1. Start microservices in parallel
python -m src.services.data_ingestion.main &
python -m src.services.strategy_engine.main &
python -m src.services.execution.main &
python -m src.services.risk_management.main &
python -m src.services.analytics.main &
python -m src.services.notification.main &

# 2. Verify service health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
curl http://localhost:8005/health
curl http://localhost:8006/health
```

#### **Phase 4: Web Layer Deployment**
```bash
# 1. Start FastAPI server
python -m src.web.main

# 2. Verify web server
curl http://localhost:8000/health
```

### Service Startup Order
1. **Infrastructure**: PostgreSQL â†’ Redis â†’ Prefect Server
2. **Database**: Create databases â†’ Run migrations â†’ Initialize Prefect
3. **Microservices**: Start all services in parallel
4. **Web Layer**: FastAPI server â†’ Frontend
5. **Verification**: Health checks â†’ Service discovery â†’ Flow deployment

### Deployment Configuration

#### **Environment Variables**
```env
# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
TRADING_DB_NAME=trading_system
PREFECT_DB_NAME=prefect
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password_here

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_URL=redis://localhost:6379/0

# Prefect Configuration
PREFECT_API_URL=http://localhost:4200/api
PREFECT_API_DATABASE_CONNECTION_URL=postgresql+asyncpg://postgres:password@localhost:5432/prefect

# Service Configuration
DATA_INGESTION_PORT=8001
STRATEGY_ENGINE_PORT=8002
EXECUTION_PORT=8003
RISK_MANAGEMENT_PORT=8004
ANALYTICS_PORT=8005
NOTIFICATION_PORT=8006
WEB_SERVER_PORT=8000

# Alpaca API Configuration
ALPACA_API_KEY=your_api_key
ALPACA_SECRET_KEY=your_secret_key
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Logging Configuration
LOG_LEVEL=INFO
LOG_RETENTION_DAYS=30
```


### Deployment Scripts

#### **Startup Script**
```bash
#!/bin/bash
# start_trading_system.sh

echo "Starting Trading System..."

# Phase 1: Infrastructure
echo "Starting infrastructure services..."
pg_ctl start -D "C:\Program Files\PostgreSQL\15\data"
redis-server --daemonize yes
prefect server start --host 0.0.0.0 --port 4200 &

# Wait for services to be ready
sleep 10

# Phase 2: Database initialization
echo "Initializing databases..."
createdb trading_system
createdb prefect
alembic upgrade head
prefect database upgrade

# Phase 3: Start microservices
echo "Starting microservices..."
python -m src.services.data_ingestion.main &
python -m src.services.strategy_engine.main &
python -m src.services.execution.main &
python -m src.services.risk_management.main &
python -m src.services.analytics.main &
python -m src.services.notification.main &

# Wait for services to be ready
sleep 15

# Phase 4: Start web server
echo "Starting web server..."
python -m src.web.main &

echo "Trading system started successfully!"
echo "Web UI: http://localhost:8000"
echo "Prefect UI: http://localhost:4200"
```

#### **Shutdown Script**
```bash
#!/bin/bash
# stop_trading_system.sh

echo "Stopping Trading System..."

# Stop web server
pkill -f "src.web.main"

# Stop microservices
pkill -f "src.services"

# Stop Prefect
pkill -f "prefect server"

# Stop Redis
redis-cli shutdown

# Stop PostgreSQL
pg_ctl stop -D "C:\Program Files\PostgreSQL\15\data"

echo "Trading system stopped successfully!"
```

### Health Monitoring

#### **Service Health Checks**
```python
# src/shared/health/health_checker.py
class HealthChecker:
    def __init__(self):
        self.services = {
            'postgresql': 'localhost:5432',
            'redis': 'localhost:6379',
            'prefect': 'localhost:4200',
            'data_ingestion': 'localhost:8001',
            'strategy_engine': 'localhost:8002',
            'execution': 'localhost:8003',
            'risk_management': 'localhost:8004',
            'analytics': 'localhost:8005',
            'notification': 'localhost:8006',
            'web_server': 'localhost:8000'
        }
    
    def check_all_services(self):
        """Check health of all services"""
        health_status = {}
        for service, endpoint in self.services.items():
            try:
                response = requests.get(f"http://{endpoint}/health", timeout=5)
                health_status[service] = response.status_code == 200
            except:
                health_status[service] = False
        return health_status
```

#### **Deployment Verification**
```python
# src/scripts/verify_deployment.py
def verify_deployment():
    """Verify all services are running correctly"""
    health_checker = HealthChecker()
    health_status = health_checker.check_all_services()
    
    all_healthy = all(health_status.values())
    
    if all_healthy:
        print("âœ… All services are healthy!")
        return True
    else:
        print("âŒ Some services are unhealthy:")
        for service, status in health_status.items():
            print(f"  {service}: {'âœ…' if status else 'âŒ'}")
        return False
```

### Production Considerations

#### **Performance Optimization**
- **Connection Pooling**: Optimize database connections
- **Caching Strategy**: Implement Redis caching
- **Resource Monitoring**: Monitor CPU, memory, disk usage
- **Log Rotation**: Implement log rotation and cleanup

#### **Security Hardening**
- **API Keys**: Secure storage of Alpaca API keys
- **Database Security**: Proper user permissions
- **Network Security**: Firewall configuration
- **Audit Logging**: Complete audit trail

#### **Backup Strategy**
- **Database Backups**: Daily automated backups
- **Configuration Backups**: Version control for configurations
- **Log Backups**: Centralized log storage
- **Disaster Recovery**: Recovery procedures and testing

### Deployment Checklist

#### **Pre-Deployment**
- [ ] PostgreSQL installed and configured
- [ ] Redis installed and configured
- [ ] Python environment set up
- [ ] Dependencies installed
- [ ] Environment variables configured
- [ ] Alpaca API keys obtained

#### **Deployment**
- [ ] Infrastructure services started
- [ ] Databases created and migrated
- [ ] Microservices deployed
- [ ] Web server started
- [ ] Health checks passed
- [ ] Prefect flows deployed

#### **Post-Deployment**
- [ ] All services responding
- [ ] Database connections working
- [ ] Prefect UI accessible
- [ ] Trading system functional
- [ ] Monitoring configured
- [ ] Backup procedures tested

---

**See Also**:
- [Architecture Overview](architecture-overview.md) - System overview
- [Services Architecture](architecture-services.md) - Service deployment details
- [Prefect Architecture](architecture-prefect.md) - Prefect orchestration
- [Database Architecture](architecture-database.md) - Database setup
