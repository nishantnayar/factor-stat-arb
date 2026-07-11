# CLAUDE.md - Trading System

## Project

Algorithmic pairs trading platform. Paper trading via Alpaca. PostgreSQL + Redis + Prefect + Streamlit + FastAPI.

**Author**: Nishant Nayar
**Repo**: https://github.com/nishantnayar/trading-system

---

## Encoding Rules

- All `.py` files must be **ASCII-only** - no Unicode curly quotes, en/em dash characters, or any byte > 0x7F in source code or docstrings
- Use plain ASCII substitutes: `-` for en-dash, ` - ` for em-dash, `"` / `'` for typographic quotes
- **Exception**: Streamlit UI pages only (`streamlit_ui/pages/`) may use Unicode for display text
- All other Python under `streamlit_ui/` (e.g. `api_client.py`, `utils.py`, `css_config.py`, `streamlit_app.py`) must stay **ASCII-only**, same as `src/`
- Verify before committing: `python -c "open('file.py','r',encoding='ascii').read()"`

---

## Before Marking Any Code Change Done

Always run these three checks - all must pass:

```bash
black --check .
isort --check-only .
mypy src/ --ignore-missing-imports
```

Auto-fix formatting:
```bash
black . && isort .
```

---

## Testing Rules

- Unit tests live in `tests/unit/`, integration tests in `tests/integration/`
- **No DB or network in unit tests** - mock everything with `unittest.mock`
- Use `patch.object(instance, "_method", ...)` to mock private DB calls (e.g. `_load_closed_trades`)
- Patch SMTP at `smtplib.SMTP`, not at the import site
- `asyncio_mode = auto` is set in `pytest.ini` - do NOT add `@pytest.mark.asyncio` to individual methods, only to classes if needed
- Markers in use: `@pytest.mark.unit`, `@pytest.mark.trading`, `@pytest.mark.integration`, `@pytest.mark.database`
- Reset `src.services.notification.email_notifier._notifier = None` before and after tests that call `get_notifier()`

Run new unit tests (no DB needed):
```bash
pytest -m "unit and trading" -v
```

Run full suite (requires DB ending in `_test`):
```bash
python scripts/run_tests.py all
```

---

## Database Safety

- **Never run tests against a DB unless its name ends with `_test`** - conftest.py enforces this but don't bypass it
- The test DB is `trading_system_test` (set via `TRADING_DB_NAME` env var)
- Never drop tables if `market_data` has > 1000 rows - production guard

---

## Trading Safety

- The system runs **paper trading only** (`IS_PAPER_TRADING=True` in `.env`)
- Never write code that submits real Alpaca orders outside of `pair_executor.py`
- `get_notifier()` returns a module-level singleton - instantiated once at import time from `get_settings()`

---

## Key File Locations

| What | Where |
|---|---|
| Settings (all env vars) | `src/config/settings.py` |
| Pairs strategy orchestrator | `src/services/strategy_engine/pairs/strategy.py` |
| Signal logic (stateless) | `src/services/strategy_engine/pairs/signal_generator.py` - use `BacktestSignalGenerator` in tests |
| Position sizing | `src/services/strategy_engine/pairs/position_sizer.py` |
| Email notifications | `src/services/notification/email_notifier.py` |
| Prefect hourly flow | `src/shared/prefect/flows/strategy_engine/pairs_flow.py` |
| P&L report UI | `streamlit_ui/pages/5_PnL_Report.py` |
| Strategy monitor UI (Pairs + Baskets tabs) | `streamlit_ui/pages/4_Strategy_Monitor.py` |
| Pair Lab UI (Scanner + Backtest tabs) | `streamlit_ui/pages/6_Pair_Lab.py` |
| Ops UI (Connections + Data Quality tabs) | `streamlit_ui/pages/7_Ops.py` |
| ORM models | `src/shared/database/models/strategy_models.py` |
| Persisted UI prefs | `config/scanner_prefs.json`, `config/analysis_prefs.json` (gitignored) |
| Redis debug client | `src/shared/redis/client.py` - `set_json` / `get_json` helpers, no-op if Redis is down |
| Ops Monitor Agent | `src/services/agent/ops_monitor_agent.py` - post-cycle anomaly detection via Ollama LLM |

---

## CI Pipeline (GitHub Actions)

Runs on push/PR to `main` and `develop`. All must pass:

1. `black --check .`
2. `isort --check-only .`
3. `flake8 . --select=E9,F63,F7,F82` (syntax errors + undefined names only)
4. `mypy src/ --ignore-missing-imports`
5. Unit + integration + database tests (against `trading_system_test` DB)

---

## Architecture Notes

- **Spread formula**: `log(P1) - hedge_ratio * log(P2)`
- **Signal thresholds**: entry (default 2.0 sigma), exit (0.5 sigma), stop-loss (3.0 sigma), expire (3x half-life hours)
- **Position sizing**: bootstrap 2% fixed for first 20 trades, then Half-Kelly; hard cap 12% per leg
- **EmailNotifier** no-ops silently when SMTP env vars are missing - safe to run unconfigured
- **Email subject lines** use ASCII tags in code: `[PAPER]`/`[LIVE]` prefix, `[WARN]`, `[ALERT]`, `[+PNL]`/`[-PNL]` for trade closed, plain `-` as separator (no emoji in `.py` outside `streamlit_ui/pages/`)
- **BacktestSignalGenerator** is stateless (no DB) - always use this in tests, not `SignalGenerator`
- **UI preferences** are persisted to JSON files in `config/` (not DB) - lightweight, gitignored, survives restarts
- **Streamlit page numbering**: 1 Portfolio, 2 Analysis, 3 Screener, 4 Strategy Monitor (Pairs tab + Baskets tab), 5 P&L Report, 6 Pair Lab (Scanner tab + Backtest tab), 7 Ops (Connections & Preferences tab + Data Quality tab)
- **Redis debug caching**: every `intraday-pairs-trading` cycle writes bar metadata and cycle results
  to Redis (TTL 48 h). No-op if Redis is down. Keys:
  - `pairs:bars:{SYMBOL}` -- count, first/last timestamp, last close for the fetched price series
  - `pairs:cycle:{SYM1}_{SYM2}` -- status, z_score, bar_counts, entry_threshold, signal (if any)
  - Quick check: `redis-cli get pairs:cycle:EWBC_FNB`
- **Ops Monitor Agent**: runs after every pairs cycle as a Prefect task. Reads Redis cycle/bar
  state, calls local Ollama (`llama3.2:3b`) with `format="json"` to detect anomalies, emails
  alert if any found. Controlled by `AGENT_ENABLED` env var. Never raises -- errors are silent.
  Requires Ollama running locally (`ollama serve`). Model: `OLLAMA_MODEL` env var (default `llama3.2:3b`).

---

## Data Source Architecture (updated 2026-04-03)

**Alpaca is used for order execution only. All price data comes from Yahoo Finance.**

### market_data `data_source` values
| Value | Written by | Used by | Notes |
|---|---|---|---|
| `yahoo_adjusted` | Daily Prefect flow, backpopulate scripts | Backtesting, indicators, pair discovery | EOD/multi-day adjusted bars - do not touch |
| `yahoo_adjusted_1h` | `refresh_pair_prices_task` in `pairs_flow.py` | `get_price_series()` in strategy | Intraday 1h bars refreshed before each cycle |
| `yahoo` | Daily Prefect flow | General market data | Unadjusted bars |

### Intraday price flow
1. `refresh_pair_prices_task` (pairs_flow) fetches 2 days of `interval='1h'` Yahoo bars via `yfinance`
2. Upserts into `data_ingestion.market_data` with `data_source='yahoo_adjusted_1h'`
3. `get_price_series(symbol, limit)` in `src/shared/market_data.py` reads these for the strategy
4. Alpaca REST (`AlpacaClient`) is called only for `place_order`, `get_positions`, `get_clock`, etc.

### DB migration required
Run `scripts/21b_add_yahoo_adjusted_1h_source.sql` to add `yahoo_adjusted_1h` to the CHECK constraint.

---

## Pair Discovery & Selection Notes

### Rank Score Formula (updated 2026-04-01)
`rank_score = (1 - coint_pvalue) x |correlation| x z_score_abs_mean`

Previously used a liquidity proxy; replaced with `z_score_abs_mean` (mean absolute z-score over
the discovery window). This directly measures tradeability -- pairs with low z_score_abs_mean are
cointegrated but their spreads barely move and never cross entry thresholds.

`z_score_window` is capped at 60 bars (was uncapped, could reach 100+ for long half-life pairs,
over-smoothing the spread and compressing z-scores further).

### Why pairs can be found but never trade
- Strong cointegration (low p-value) does not guarantee the spread is volatile enough to cross 2.0 sigma
- Long half-life + uncapped z_window = heavily smoothed spread = z-scores near zero
- Fix: rank on z_score_abs_mean, cap z_window at 60
- **Price data gotcha**: strategy reads from `yahoo_adjusted_1h` in the DB, not from Alpaca.
  If INSUFFICIENT_DATA appears in logs, check `redis-cli get pairs:bars:{SYMBOL}` -- the `count`
  field shows how many bars were fetched. Ensure `refresh_pair_prices_task` ran successfully
  and migration `21_add_yahoo_adjusted_1h_source.sql` has been applied.

### Active Pairs Policy
Active pair status is managed in the DB and visible in the Pair Lab UI -- do not track it here.
For allocation caps: `max_allocation_pct` in `PairRegistry` bounds per-pair exposure; the hard
cap is 12% per leg (`MAX_LEG_FRACTION` in `position_sizer.py`). FNB concentration risk: do not
run more than 2 FNB-leg pairs simultaneously without reducing allocation caps further.

### Backtest Window Guidance
- Default UI window is 180 days -- this is long enough to include regime changes that hurt Sharpe
- If a pair fails on 180 days but the equity curve shows recovery after month 3, try 90 days
- A pair failing harder on a shorter window means the spread divergence is recent and ongoing --
  skip it, do not adjust thresholds to compensate
