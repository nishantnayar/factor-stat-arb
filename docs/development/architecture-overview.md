# Trading System Architecture Overview

## Overview

A production-grade algorithmic trading system designed for local deployment, focusing on equities trading through Alpaca with paper trading capabilities. The system uses a microservices architecture with Prefect orchestration, Python-based services, and a modern web interface.

**Author**: Nishant Nayar  
**Email**: nishant.nayar@hotmail.com  
**Repository**: https://github.com/nishantnayar/trading-system  
**Documentation**: https://nishantnayar.github.io/trading-system  
**Last Updated**: 5/1/2026  
**Status**: ✅ v1.2.0 — Pairs Trading and Gartley Harmonic Strategy live in paper trading | v1.3.0 Ops Monitor Agent live (2026-05-01)

## System Requirements

- **Asset Class**: Equities — paper trading via Alpaca API (order execution only)
- **Price Data**: Yahoo Finance via `yfinance` (EOD `yahoo_adjusted`, intraday `yahoo_adjusted_1h`)
- **Data Frequency**: Hourly intraday ingestion (strategy cycle); daily EOD ingestion (Prefect)
- **Trading Mode**: Paper trading (live trading planned)
- **Deployment**: Local machine (Windows 10)
- **Architecture**: Microservices with Prefect orchestration

## Technology Stack

### Core Technologies
- **Language**: Python 3.11+
- **Environment**: Anaconda
- **Database**: PostgreSQL (metadata, transactions, logs)
- **Cache/Queue**: Redis (caching, pub/sub)
- **Data Processing**: Polars (analytics, large datasets)
- **Orchestration**: Prefect (workflow management)
- **Validation**: Pydantic (data models, API validation)

### Frontend
- **Backend**: FastAPI
- **Frontend**: Streamlit + Plotly + Custom CSS
- **Charts**: Plotly for interactive financial visualizations
- **Updates**: Real-time updates via Streamlit's reactive framework

### Development & Quality
- **Linting**: Flake8 + Black + isort
- **Type Checking**: mypy
- **Documentation**: MkDocs
- **Logging**: Loguru (consolidated logging)
- **Testing**: pytest + coverage

## Architecture Components

The system is organized into the following architectural components:

- **[Services Architecture](architecture-services.md)** - Detailed breakdown of all microservices
- **[Database Architecture](architecture-database.md)** - Database design and connectivity
- **[UI Architecture](architecture-ui.md)** - Frontend and user interface design
- **[Prefect Architecture](architecture-prefect.md)** - Workflow orchestration and deployment
- **[Deployment Architecture](architecture-deployment.md)** - System deployment strategy
- **[Timezone Architecture](architecture-timezone.md)** - Timezone handling strategy

## Communication Patterns

### Service Communication
- **Synchronous**: REST APIs for real-time requests
- **Asynchronous**: Redis pub/sub for events
- **Batch Processing**: Prefect flows for scheduled tasks
- **Data Synchronization**: Event-driven updates between services

### Message Flow
```
Data Ingestion → Strategy Engine → Risk Management → Execution
     ↓                ↓                ↓              ↓
Analytics Service ← Notification Service ← Redis ← PostgreSQL
                          ↑
                    Agent Layer (v1.3.0)
                  (observes, reasons, alerts)
```

### Prefect Flow Orchestration
```
Market Data Flow → Strategy Flow → Risk Flow → Execution Flow
       ↓               ↓            ↓           ↓
   Analytics Flow ← Notification Flow ← Monitoring Flow
```

## Security Architecture

### API Security
- Alpaca API keys stored in environment variables
- Rate limiting on all API endpoints
- Input validation with Pydantic models
- SQL injection prevention with ORM

### Data Security
- Database connection encryption
- Secure credential storage
- Audit logging for all trades
- Backup and recovery procedures

## Monitoring & Observability

### Logging Strategy
- **Loguru**: Consolidated logging across all services
- **Structured Logging**: JSON format for analysis
- **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Log Rotation**: Daily rotation, 30-day retention

> **📝 Detailed Logging Analysis**: For comprehensive logging architecture, structured logging patterns, and implementation strategies, see [Logging Architecture Detailed Review](logging.md).

### Monitoring
- **System Health**: Service status, database connections
- **Trading Metrics**: P&L, trade count, execution time
- **Performance**: Memory usage, CPU utilization
- **Alerts**: Email notifications for critical events

### Dashboard
- **Real-time Portfolio**: Current positions and P&L
- **Strategy Performance**: Returns, Sharpe ratio, drawdown
- **System Status**: Service health, error rates
- **Trade History**: Recent trades and orders

## Development Workflow

### Environment Setup
```bash
# Create conda environment
conda create -n trading-system python=3.11
conda activate trading-system

# Install dependencies
conda install -c conda-forge postgresql redis
pip install -r requirements.txt

# Setup databases
createdb trading_system
redis-server
```

### Code Quality
```bash
# Pre-commit hooks
pre-commit install

# Code formatting
black .
isort .

# Linting
flake8 .

# Type checking
mypy .
```

### Testing Strategy
- **Unit Tests**: Individual service functions
- **Integration Tests**: Service interactions
- **End-to-End Tests**: Complete trading workflows
- **Strategy Tests**: Backtesting validation

## Configuration Management

### Environment Configuration
```python
# src/config/settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    postgres_url: str
    redis_url: str
    
    # Alpaca API
    alpaca_api_key: str
    alpaca_secret_key: str
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    
    # Prefect
    prefect_api_url: str = "http://localhost:4200"
    
    # Logging
    log_level: str = "INFO"
    log_retention_days: int = 30
    
    class Config:
        env_file = ".env"
```

### Strategy Configuration
```yaml
# config/strategies.yaml
strategies:
  - name: "momentum_strategy"
    enabled: true
    parameters:
      lookback_period: 20
      threshold: 0.02
      max_position_size: 0.1
    risk_limits:
      max_drawdown: 0.05
      max_daily_loss: 0.02
```

## Performance Considerations

### Data Processing
- **Polars**: Optimized for large datasets
- **Batch Processing**: Efficient data pipeline
- **Caching**: Redis for frequently accessed data
- **Indexing**: Database indexes for fast queries

### Scalability
- **Horizontal Scaling**: Multiple service instances
- **Database Optimization**: Query optimization, connection pooling
- **Memory Management**: Efficient data structures
- **Async Processing**: Non-blocking operations

## Future Enhancements

### Phase 1 ✅ Complete (v1.2.0)
- Paper trading with pairs strategy (CFG/KEY, NWS/NWSA, BK/STT) and Gartley harmonic pattern
- Email notifications, Redis caching, 7-page Streamlit UI
- Backtest engine with slippage/commission, Half-Kelly position sizing

### Phase 2 — Agentic AI Layer (v1.3.0, In Design)

The system will gain an **Agent Layer** that reasons over trading state rather than applying fixed rules.
Three agents are planned, introduced in order of increasing autonomy and risk:

#### Agent 1: Ops Monitor Agent (low risk, first to ship)
- Runs as a post-cycle Prefect task after each `pairs_flow` execution
- Reads Redis `pairs:cycle:*` keys, DB trade state, and recent logs
- Detects anomalies: data staleness, z-scores perpetually near zero, no trades in N days,
  `INSUFFICIENT_DATA` errors, single-leg fills
- Emits a structured reasoning summary via `EmailNotifier` when anomalies are found
- No write access to orders or positions — observe-only

#### Agent 2: Strategy Review Agent (shadow mode first)
- Runs alongside the deterministic signal generator — does NOT replace it initially
- Receives z-score, spread trend, Redis cycle data, and upcoming earnings/news (via tools)
- Produces a structured verdict: `AGREE`, `CAUTION`, or `SKIP` with a one-sentence rationale
- In shadow mode: verdict is logged and emailed but does not gate execution
- Promoted to gate mode (can suppress a trade) only after N weeks of shadow validation

#### Agent 3: Pair Discovery Agent (research use)
- Invoked manually or via a Prefect flow during pair discovery runs
- Reviews cointegration candidates using fundamentals and recent news via tool calls
- Rejects pairs with structural reasons for correlation (acquisitions, index rebalance, sector ETF overlap)
- Writes a brief rationale per candidate to the DB for audit trail

#### Design Principles
- **Observe before act**: all agents start in read-only / shadow mode
- **Deterministic fallback**: if an agent errors, the rule-based system runs unchanged
- **Auditable**: every agent decision is persisted with its inputs and reasoning
- **Tool-gated execution**: order placement is a named tool that requires explicit agent invocation,
  never implicit side effects
- **Claude API**: agents are implemented via the Anthropic SDK (`claude-sonnet-4-6` default);
  prompt caching enabled on system prompts to reduce cost per hourly cycle

### Phase 3 (Future)
- Live trading mode
- Additional strategy types (momentum, mean reversion)
- Advanced portfolio-level risk analytics
- Multi-asset and cross-sector strategies
- Cloud deployment options

## Getting Started

1. **Setup Environment**: Install Anaconda, PostgreSQL, Redis
2. **Clone Repository**: Get the codebase
3. **Install Dependencies**: Create conda environment
4. **Configure**: Set up API keys and database
5. **Run Services**: Start all microservices
6. **Access Dashboard**: Open web interface
7. **Deploy Strategy**: Configure and start trading

This architecture provides a solid foundation for a production-grade trading system that can scale with your needs while maintaining simplicity for local deployment.

---

**See Also**:
- [Services Architecture](architecture-services.md)
- [Database Architecture](architecture-database.md)
- [UI Architecture](architecture-ui.md)
- [Prefect Architecture](architecture-prefect.md)
- [Deployment Architecture](architecture-deployment.md)
- [Timezone Architecture](architecture-timezone.md)

