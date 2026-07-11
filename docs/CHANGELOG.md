# Changelog

All notable changes to the Trading System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added (2026-05-01) - Agentic AI Layer v1.3.0

- **Ops Monitor Agent** (`src/services/agent/ops_monitor_agent.py`):
  - Runs as a post-cycle Prefect task after every `intraday-pairs-trading` execution
  - Reads Redis `pairs:cycle:*` and `pairs:bars:*` keys and the cycle summary dict
  - Calls a local Ollama LLM (`llama3.2:3b` default) with `format="json"` to guarantee
    valid JSON output and `num_ctx=4096` to handle full context
  - Detects anomalies: z_score near zero, low bar counts, cycle errors, no active pairs
  - Sends an email alert via `EmailNotifier.send_ops_alert` when anomalies are found
  - Never raises -- all errors are caught so the agent never blocks the flow
  - Controlled by `AGENT_ENABLED` env var (default `True`)

- **EmailNotifier** (`src/services/notification/email_notifier.py`):
  - Added `send_ops_alert(anomalies, summary, cycle_summary)` public method
  - Added `_ops_alert_html` HTML template for ops alert emails
  - Subject format: `[PAPER] [WARN] Ops Monitor - N anomaly(s)`

- **Prefect flow** (`src/shared/prefect/flows/strategy_engine/pairs_flow.py`):
  - Added `run_ops_monitor_task` Prefect task (retries=0, never blocks flow on error)
  - Wired as the final step of `intraday_pairs_flow` after deactivation check

- **Settings** (`src/config/settings.py`):
  - Added `OLLAMA_BASE_URL` (default `http://localhost:11434`)
  - Added `OLLAMA_MODEL` (default `llama3.2:3b`)
  - Added `AGENT_ENABLED` (default `True`)

- **Architecture docs** updated:
  - `docs/development/architecture-overview.md`: Phase 2 section with full agent design
  - `docs/development/architecture-services.md`: Service #7 Agent Layer entry

### Documentation (2026-04-29)
- Updated `streamlit_ui/README.md`, `docs/development/architecture-ui.md`, `docs/user-guide/dashboard.md`, `CHANGELOG.md`, and `docs/CHANGELOG.md` to reflect the UI consolidation from 11 pages to 7.
- Page reference table, navigation tree, and page architecture sections all updated with new page names, file paths, and tab descriptions.
- Session state table updated: `selected_symbol` and `selected_timeframe` are now set by the Ops page, not Settings.

### Changed (2026-04-29)
- **UI Consolidation**: Streamlit sidebar reduced from 11 pages to 7 by merging related pages into tabbed views:
  - `4_Strategy_Monitor.py` — Pairs Trading + Basket Trading
  - `6_Pair_Lab.py` — Pair Scanner + Backtest Review
  - `7_Ops.py` — Settings + Data Quality Monitor
  - `11_About.py` deleted (not a trader workflow)

### Fixed (2026-04-29)
- **mypy** — 0 errors across 107 source files (was 8 errors in 4 files):
  - `pairs/strategy.py`: `Dict[str, Any]` annotation on first `result` assignment fixes all dict-item errors
  - `pairs_flow.py`, `pair_discovery_flow.py`: `# type: ignore[arg-type]` on Prefect `asyncio.run()` calls
  - `indicator_calculator.py`: split chained float cast to give mypy a checkable intermediate type

### Documentation (2026-04-03)
- Aligned `CLAUDE.md`, `README.md`, `docs/development/architecture-ui.md`, `docs/CONTRIBUTING.md`, and `docs/streamlit-ui-utilities.md` with current Streamlit page numbering (through page 9), ASCII-only policy for Python outside `streamlit_ui/pages/`, and pairs risk API/circuit breaker behavior.
- Standardized documentation **Last Updated** metadata to **4/3/2026** (ISO `2026-04-03` in MkDocs frontmatter where present).

### Changed
- README feature list: risk management and paper-vs-live wording updated to match implemented strategy and API behavior.

### Planned
- Broader REST surface for advanced risk metrics (where not yet exposed)
- Additional analytics and reporting

## [1.0.0] - 2025-12-XX

### Added
- ✅ **Paper Trading Integration**: Alpaca Markets API integration for paper trading
- ✅ **Multi-Source Data Ingestion**: 
  - Polygon.io integration for historical data
  - Yahoo Finance integration (10 data types: market data, company info, key statistics, dividends, splits, institutional holders, financial statements, company officers, analyst recommendations, ESG scores)
  - Alpaca integration for real-time trading data
- ✅ **Streamlit Web Dashboard**: 
  - Portfolio management page
  - Market analysis page with interactive Plotly charts
  - AI-powered stock screener with Ollama integration
  - Settings and system information pages
- ✅ **Database-First Logging**: Structured logging with PostgreSQL storage
- ✅ **Technical Indicators**: Automated calculation and storage (SMA, EMA, RSI, MACD, Bollinger Bands)
- ✅ **Prefect Workflow Orchestration**: 
  - Daily market data updates
  - Weekly company information updates
  - Weekly key statistics updates
- ✅ **Timezone Management**: UTC storage with Central Time display
- ✅ **FastAPI REST API**: Comprehensive API endpoints for trading operations
- ✅ **Database Architecture**: 
  - Separate `trading_system` and `prefect` databases
  - Service-specific schemas
  - Comprehensive table structure
- ✅ **Code Quality Tools**: Black, isort, Flake8, mypy integration
- ✅ **Testing Infrastructure**: Comprehensive test suite with pytest
- ✅ **Documentation**: Complete MkDocs documentation

### Changed
- Improved database schema with enhanced constraints and indexing
- Enhanced error handling across all services
- Optimized data ingestion workflows

### Fixed
- Database connection pooling issues
- Timezone handling in data storage
- Session state management in Streamlit UI

## [0.9.0] - 2025-11-XX

### Added
- Initial Yahoo Finance integration
- Basic Streamlit UI
- Database logging foundation

### Changed
- Refactored data ingestion architecture
- Improved error handling

## [0.8.0] - 2025-10-XX

### Added
- Polygon.io data integration
- Basic FastAPI endpoints
- Initial database schema

### Changed
- Migrated to modular architecture

## [0.7.0] - 2025-09-XX

### Added
- Initial project structure
- Basic Alpaca integration
- Core database models

---

## Version History

- **v1.0.0** (Current): Core features implemented, production-ready for paper trading
- **v1.1.0** (Planned): Strategy engine, backtesting, risk management
- **v1.2.0** (Planned): Advanced workflows, analytics, data validation
- **v1.3.0** (Future): Microservices architecture, cloud deployment

## Status Indicators

- ✅ **Implemented**: Feature is complete and working
- 🚧 **In Progress**: Feature is being developed
- 📋 **Planned**: Feature is planned for future release
- 🔮 **Future**: Feature is under consideration

---

For detailed release notes, see [GitHub Releases](https://github.com/nishantnayar/trading-system/releases).

