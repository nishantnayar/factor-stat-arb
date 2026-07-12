# CLAUDE.md - Factor Statistical Arbitrage

## Project

Explainable factor-residual statistical arbitrage on US equities. PCA factor
decomposition -> tradable ETF proxy mapping -> OU residual mean-reversion ->
signal -> backtest -> explainability -> paper execution. Forked from
`trading-system` for its data/execution/risk infrastructure, then trimmed and
extended. Paper trading only via Alpaca. PostgreSQL + Prefect + Streamlit.

**Author**: Nishant Nayar
**Repo**: https://github.com/nishantnayar/factor-stat-arb
**Full design + build plan**: `docs/PROJECT_SPEC.md`

---

## Environment

- Managed entirely with **uv** (Python 3.11, pinned via `.python-version`).
- Install / sync: `uv sync`. Run anything: `uv run <cmd>`.
- Do NOT use pip/conda/venv directly. `uv.lock` is committed - keep it in sync.
- Verify the environment: `uv run scripts/check_env.py`.

---

## Entry Point

`main.py` is the single entry point:

```bash
uv run main.py check          # run all preflight validation checks
uv run main.py up             # checks, then start ALL services (Prefect + Streamlit + worker)
uv run main.py up prefect     # start only the named service(s)
uv run main.py up --skip-checks
```

---

## Encoding Rules

- All `.py` files must be **ASCII-only** - no Unicode curly quotes, en/em dash
  characters, or any byte > 0x7F in source code or docstrings.
- Use plain ASCII substitutes: `-` for en/em dashes, `->` for arrows,
  `"` / `'` for typographic quotes. No emoji in `.py`.
- **Exception**: page modules under `streamlit_ui/pages/` (if reintroduced) may
  use Unicode for display text. `streamlit_ui/streamlit_app.py` and everything
  else under `streamlit_ui/` must stay ASCII-only, same as `src/`.
- Verify: `python -c "open('file.py','r',encoding='ascii').read()"`.

---

## Before Marking Any Code Change Done

All must pass (run via uv):

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src/ --ignore-missing-imports
```

Auto-fix formatting/lint:
```bash
uv run ruff format . && uv run ruff check --fix .
```

Note: CI (`.github/workflows/*.disabled`) is currently disabled and still
targets the old pip/black/isort setup - see setup TODOs in `docs/PROJECT_SPEC.md`.

---

## Testing Rules

- Unit tests in `tests/unit/`, integration in `tests/integration/`.
- **No DB or network in unit tests** - mock everything with `unittest.mock`.
- `asyncio_mode = auto` in `pytest.ini` - do NOT add `@pytest.mark.asyncio` to
  individual methods, only to classes if needed.
- **BacktestSignalGenerator** is stateless (no DB) - use it in tests, not
  `SignalGenerator`.

Run unit tests (no DB): `uv run pytest tests/unit -v`

---

## Databases

Two Postgres databases on the local server:

| DB | Purpose |
|---|---|
| `factor_stat_arb` | Application DB: market data, models, strategy tables (8 schemas) |
| `factor_stat_arb_prefect` | Prefect orchestration metadata (isolated from trading-system's) |

Setup / maintenance scripts (all `uv run scripts/<x>.py`):

| Script | Does |
|---|---|
| `provision_db.py` | Create both DBs + the 8 schemas (idempotent; skips migrations if already populated) |
| `clone_schema.py` | Build the app schema via `pg_dump --schema-only` from the live `trading_system` DB (how the schema was actually built) |
| `seed_data.py` | Seed `symbols`, `market_data`, `technical_indicators` from `trading_system` (data only) |
| `test_migrations.py` | Replay the numbered `scripts/*.sql` migrations on a throwaway DB to verify a clean in-order replay |

### Database Safety
- Never drop `factor_stat_arb` - it holds ~8.7M seeded `market_data` rows.
- If running DB-backed tests, use a database whose name ends in `_test`.
- The numbered `scripts/*.sql` migrations are validated by `test_migrations.py`
  but are NOT the source of truth for the live schema (that was `clone_schema.py`).

---

## Services (isolated from trading-system)

`main.py up` starts all three; narrow with names (`up prefect`, `up worker`, ...):

- **Prefect** - server on port **4201**, metadata in `factor_stat_arb_prefect`.
  For raw CLI use `uv run scripts/run_prefect.py <args>` (sets a repo-local
  `PREFECT_HOME` + port + DB URL so it never touches the machine-global Prefect
  profile / shared DB on 4200). UI: http://localhost:4201
- **Streamlit** - bare-bones dashboard on port **8502** (trading-system uses the
  default 8501). Entry: `streamlit_ui/streamlit_app.py` (single tabbed app:
  Overview wired to the DB, plus milestone placeholders).
- **worker** - Prefect process worker on the **`fsa-data-ingestion`** work pool
  (distinct name so it never collides with trading-system's). Starts with
  `--type process` (auto-creates the pool). `up` runs services only.

### Data-ingestion flow
- `src/shared/prefect/flows/data_ingestion/yahoo_flows.py:yahoo_market_data_flow`
  fetches hourly Yahoo bars and writes both `yahoo` and **`yahoo_adjusted`**
  (the source `get_price_series` reads - keep them coherent). It also chains the
  technical-indicator calc.
- **Registering the deployment is a one-time step**, kept separate from running
  services: `uv run scripts/deploy_flows.py` creates the pool + the
  `Daily Market Data Update` deployment (cron `15 22 * * 1-5`). It persists in the
  Prefect DB. Scheduled runs then fire whenever a worker is up (`up` / `up worker`).

### Prefect prompt gotcha
`prefect server start` prompts (in a TTY) when the active profile lacks
PREFECT_API_URL. `run_prefect.ensure_profile()` writes a repo-local
`.prefect/profiles.toml` with it set before starting the server - do not remove
that call.

Config for all services is derived from `.env` via `src/config/settings.py`. The
Prefect DB URL is DERIVED from `POSTGRES_PASSWORD` (single source of truth) - do
not re-introduce a duplicated password in `PREFECT_API_DATABASE_CONNECTION_URL`.

---

## Trading Safety

- **Paper trading only** (`PAPER_TRADING=true`; `alpaca_base_url` defaults to the
  paper endpoint). Use a SEPARATE Alpaca paper key from trading-system's.
- Never submit real Alpaca orders. Execution reuses `BasketStrategy` /
  `pair_executor.py` - do not add order-submission code elsewhere.

---

## Key File Locations

| What | Where |
|---|---|
| Settings (all env vars) | `src/config/settings.py` |
| Entry point (checks + services) | `main.py` |
| Price series accessor | `src/shared/market_data.py` - `get_price_series()` |
| Basket spread + z-score (reused) | `src/services/strategy_engine/baskets/spread_calculator.py` |
| Basket strategy / execution (reused) | `src/services/strategy_engine/baskets/strategy.py` |
| Signal logic (stateless) | `src/services/strategy_engine/pairs/signal_generator.py` |
| Position sizing | `src/services/strategy_engine/pairs/position_sizer.py` |
| Backtest engine (reused) | `src/services/strategy_engine/backtesting/engine.py` |
| Portfolio risk guards | `src/services/risk_management/portfolio_risk_manager.py` |
| ORM models (baskets) | `src/shared/database/models/basket_models.py` |
| Factor strategy (NEW, planned) | `src/services/strategy_engine/factor_stat_arb/` |
| Dashboard | `streamlit_ui/streamlit_app.py` |

---

## Data Source Architecture

**Alpaca is used for order execution only. All price data comes from Yahoo Finance.**

`market_data.data_source` values in `factor_stat_arb`:

| Value | Coverage | Used by |
|---|---|---|
| `yahoo_adjusted` | ~1,038 symbols, ~2.5yr **hourly** split/dividend-adjusted | `get_price_series()` - the primary source |
| `yahoo` | same coverage, unadjusted | general market data |
| `yahoo_adjusted_1h` | thin (~19 symbols, few months) | legacy; NOT used here |

- `get_price_series(symbol, limit)` reads `data_source='yahoo_adjusted'`
  (`_DATA_SOURCE` in `src/shared/market_data.py`). The trading-system code had
  drifted to the thin `yahoo_adjusted_1h`; this repo reverted it to the full
  source. Any ongoing Yahoo refresh flow must write to `yahoo_adjusted` to stay
  coherent with reads.

---

## Reused Primitives (conventions carried from trading-system)

The factor strategy reuses these unchanged via `SimpleNamespace` shims (see the
reuse table in `docs/PROJECT_SPEC.md`):

- **Spread formula**: `sum(w_i * log(P_i))`, then rolling z-score (BasketSpreadCalculator).
- **Signal thresholds**: entry 2.0 sigma, exit 0.5 sigma, stop-loss 3.0 sigma,
  expire 3x half-life hours (defaults).
- **Position sizing**: bootstrap 2% fixed for first 20 trades, then Half-Kelly;
  hard cap 12% per leg (`MAX_LEG_FRACTION` in `position_sizer.py`).
- **Risk guards**: `PortfolioRiskManager` correlation guard + drawdown circuit
  breaker apply to factor baskets exactly as to pairs/baskets.

---

## Dropped from the trading-system base

Not present in this repo (do not reference or re-add): `src/web` (FastAPI),
`src/services/polygon`, `src/services/strategy_engine/harmonic`, the 7-page
trading-system Streamlit UI, and the ollama/LLM chat + market-banner UI modules.
The harmonic `scripts/26`/`27` SQL and a couple of harmonic tests still linger and
are inert (skipped by `test_migrations.py`); prune when convenient.
