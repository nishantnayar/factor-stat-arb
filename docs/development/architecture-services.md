# Trading System Services Architecture

> **Status**: ✅ Core Services Implemented (v1.2.0) | Paper trading live with Pairs + Gartley strategies | v1.3.0 Ops Monitor Agent live (2026-05-01)

## Overview

The Trading System is built on a microservices architecture with six core services, each responsible for a specific aspect of the trading system. All services are orchestrated by Prefect and communicate through REST APIs, Redis pub/sub, and shared PostgreSQL databases.

## Microservices Architecture

### 1. Data Ingestion Service ✅
**Purpose**: Collect market data from multiple sources (Polygon.io, Yahoo Finance, Alpaca API)

**Components**:
- Polygon.io API client
- Yahoo Finance API client (via yfinance)
- Alpaca API client
- Data validation (Pydantic models)
- Prefect flows for scheduled ingestion
- Data quality checks
- Error handling and retry logic

**Responsibilities**:
- Fetch hourly market data (OHLCV)
- Fetch company fundamentals and financials
- Validate data integrity
- Store raw data in PostgreSQL
- Cache frequently accessed data in Redis
- Publish data events to message queue

**Prefect Flows**:
- `fetch_market_data`: Hourly data collection
- `validate_data_quality`: Data validation pipeline
- `archive_old_data`: Data lifecycle management

**Status**: ✅ Fully implemented (v1.0.0)

### 2. Strategy Engine Service ✅
**Purpose**: Execute trading strategies and generate signals

**Components**:
- Pairs trading engine (`src/services/strategy_engine/pairs/`) — spread calculator, signal generator, position sizer, pair executor
- Gartley harmonic pattern engine (`src/services/strategy_engine/harmonic/`) — Gartley detector and executor
- Backtesting engine with slippage/commission modeling
- `BacktestSignalGenerator` (stateless, no DB) for unit-testable signal logic

**Responsibilities**:
- Discover cointegrated pairs from historical `yahoo_adjusted` price data
- Run hourly pairs trading cycle: fetch `yahoo_adjusted_1h` bars, compute z-score, generate signals
- Detect Gartley XABCD harmonic patterns in price series
- Execute paper trades via Alpaca API (orders only; price data from Yahoo Finance)
- Manage pair registry, activation state, and backtest run history
- Position sizing via Half-Kelly (bootstrap: 2% fixed for first 20 trades; hard cap 12% per leg)

**Prefect Flows**:
- `pairs_flow.py`: Hourly cycle — refresh prices, run signal generation, execute trades
- `pair_discovery_flow.py`: Discover and rank new candidate pairs

**Key Files**:
- `src/services/strategy_engine/pairs/strategy.py` — orchestrator
- `src/services/strategy_engine/pairs/signal_generator.py` — `BacktestSignalGenerator` (stateless)
- `src/services/strategy_engine/pairs/position_sizer.py` — `KellySizer`
- `src/services/strategy_engine/harmonic/gartley_detector.py`

**Status**: ✅ Live (v1.2.0) — CFG/KEY, NWS/NWSA, BK/STT active in paper trading (as of 2026-06-24)

### 3. Execution Service ✅
**Purpose**: Execute trades and manage orders

**Components**:
- Alpaca trading API client
- Order management system
- Position tracking
- Trade execution logic

**Responsibilities**:
- Place buy/sell orders
- Manage order lifecycle
- Track positions and P&L
- Handle order fills and partial fills
- Implement order types (market, limit, stop)

**Prefect Flows**:
- `execute_trades`: Process trading signals
- `manage_orders`: Order lifecycle management
- `update_positions`: Position tracking
- `reconcile_trades`: Trade reconciliation

**Status**: ✅ Core functionality implemented (v1.0.0)

### 4. Risk Management Service ✅ (Partial)
**Purpose**: Monitor and control trading risks

**Components**:
- Half-Kelly position sizing (live in strategy engine)
- Per-pair allocation cap (`max_allocation_pct`, hard cap 12% per leg)
- Circuit breaker: stop-loss at ±3.0 sigma, expiry at 3x half-life
- Risk API endpoints (FastAPI) for position risk queries

**Responsibilities**:
- Calculate position sizes using Half-Kelly criterion
- Enforce per-pair and per-leg allocation caps
- Trigger stop-loss and expiry exits automatically
- Expose risk metrics via REST API

**Status**: ✅ Core risk controls live (v1.2.0); advanced portfolio-level risk analytics planned

### 5. Analytics Service ✅
**Purpose**: Performance analysis and reporting

**Components**:
- Performance calculation engine
- Backtesting framework
- Reporting generation
- Data visualization

**Responsibilities**:
- Calculate strategy performance metrics
- Generate performance reports
- Create backtesting results
- Analyze trade patterns
- Generate portfolio analytics
- Calculate technical indicators

**Prefect Flows**:
- `calculate_performance`: Performance metrics
- `generate_reports`: Report generation
- `run_backtest`: Historical testing
- `analyze_trades`: Trade analysis

**Status**: ✅ Core functionality implemented (v1.0.0)

### 6. Notification Service ✅
**Purpose**: Handle alerts and communications

**Components**:
- `EmailNotifier` singleton (`src/services/notification/email_notifier.py`)
- Five event methods: trade opened, trade closed, stop-loss triggered, trade failed, flow error
- No-op silently when SMTP env vars are missing — safe to run unconfigured

**Responsibilities**:
- Send trade notifications on open, close, stop-loss, and failure events
- Alert on Prefect flow errors
- Use ASCII subject tags: `[PAPER]`/`[LIVE]` prefix, `[WARN]`, `[ALERT]`, `[+PNL]`/`[-PNL]`
- `get_notifier()` returns a module-level singleton instantiated once from `get_settings()`

**Status**: ✅ Implemented (v1.2.0)

### 7. Agent Layer (v1.3.0 — In Design)
**Purpose**: Reasoning layer that observes trading state and augments decisions with LLM-based analysis

**Components**:
- `OpsMonitorAgent` — post-cycle anomaly detection, no write access
- `StrategyReviewAgent` — shadow-mode signal reviewer; gating mode after validation
- `PairDiscoveryAgent` — candidate pair evaluation with fundamentals/news tools

**Responsibilities**:
- Read Redis cycle state (`pairs:cycle:*`, `pairs:bars:*`) and DB trade records after each Prefect cycle
- Detect operational anomalies: stale data, perpetual low z-scores, no-trade streaks, fill errors
- Reason over signal context (z-score, spread trend, earnings calendar, news) and emit a structured verdict
- Evaluate pair discovery candidates using external tool calls (news, fundamentals)
- Persist all agent decisions with inputs and reasoning for audit

**Integration Points**:
- Runs as a Prefect task inside `pairs_flow.py` (post-cycle step)
- Reads from Redis and PostgreSQL; writes only to a new `agent_decisions` audit table
- Calls `EmailNotifier` for anomaly alerts
- Tools available to agents: `get_cycle_state`, `get_open_trades`, `get_news` (external), `place_order` (gated, StrategyReviewAgent only after promotion)

**Implementation**:
- Anthropic SDK (`claude-sonnet-4-6`), prompt caching on system prompts
- Deterministic fallback: agent errors do not block rule-based execution
- Shadow mode enforced at the Prefect task level -- verdict logged, execution unaffected

**Status**: ✅ Ops Monitor Agent live (v1.3.0, 2026-05-01). Strategy Reviewer and Pair Discovery Agent planned.

## Service Communication

### Inter-Service Communication
- **REST APIs**: Synchronous communication between services
- **Redis Pub/Sub**: Asynchronous event-driven communication
- **Prefect Flows**: Orchestrated workflows across services
- **Shared Database**: PostgreSQL for data persistence

### Service Dependencies
```
Data Ingestion → Strategy Engine → Risk Management → Execution
     ↓                ↓                ↓              ↓
Analytics Service ← Notification Service ← Redis ← PostgreSQL
```

## Service Status Summary

| Service | Status | Version | Key Features |
|---------|--------|---------|--------------|
| **Data Ingestion** | ✅ Implemented | v1.0.0 | Multi-source (Yahoo/Polygon), Prefect flows, `yahoo_adjusted_1h` for intraday |
| **Strategy Engine** | ✅ Live | v1.2.0 | Pairs trading (CFG/KEY, NWS/NWSA, BK/STT), Gartley harmonic, backtest with slippage |
| **Execution** | ✅ Implemented | v1.0.0 | Alpaca order placement (paper), position tracking (price data from Yahoo Finance) |
| **Risk Management** | ✅ Partial | v1.2.0 | Half-Kelly sizing, allocation caps, stop-loss/expiry circuit breakers |
| **Analytics** | ✅ Implemented | v1.0.0 | Performance metrics, technical indicators, backtesting |
| **Notification** | ✅ Implemented | v1.2.0 | Email alerts for all trade lifecycle events |
| **Agent Layer** | ✅ Ops Monitor live | v1.3.0 | Ops Monitor Agent running post-cycle; Strategy Reviewer + Pair Discovery planned |

---

**See Also**:
- [Architecture Overview](architecture-overview.md) - System overview
- [Prefect Architecture](architecture-prefect.md) - Workflow orchestration details
- [Database Architecture](architecture-database.md) - Service-specific database schemas
- [UI Architecture](architecture-ui.md) - Frontend implementation

