---
layout: single
title: "Project Spec"
permalink: /project-spec/
toc: true
toc_sticky: true
toc_label: "Contents"
sidebar:
  nav: "docs"
---

# factor-stat-arb

Explainable factor residual statistical arbitrage. A standalone repo, forked from
`github.com/nishantnayar/trading-system` for its data, execution, and risk
infrastructure, then trimmed down and extended with a new discovery method and an
explainability layer that don't exist in the original codebase.

This is a Claude Code project spec. Implement in the order under **Milestones**.

## Repository and data setup

This repo starts as a trimmed clone of `trading-system`, not a fresh scaffold —
most of the infrastructure below (`src/shared`, `src/services/alpaca`,
`src/services/risk_management`, `src/services/strategy_engine/{pairs,baskets,backtesting}`,
`streamlit_ui`) was copied over as-is and should not be rebuilt from scratch.

1. Clone `trading-system`, strip the git history, and push to the new
   `factor-stat-arb` remote. Drop `src/services/strategy_engine/harmonic`,
   `src/web`, and `src/services/polygon` (Yahoo-only here) during the trim.
2. Provision a new, separate Postgres database (`factor_stat_arb`, not the
   original `trading_system` database) to recreate the schema. **Note:** the
   numbered `scripts/*.sql` migrations don't replay cleanly (see TODO 7), so the
   schema was instead cloned from the live `trading_system` DB via
   `scripts/clone_schema.py` (`pg_dump --schema-only` → `pg_restore`). A separate
   `factor_stat_arb_prefect` DB is also provisioned for Prefect. `scripts/provision_db.py`
   creates the databases + schemas.
3. Seed it with historical data from the original database's
   `data_ingestion.symbols`, `data_ingestion.market_data`,
   `analytics.technical_indicators`, and `analytics.technical_indicators_latest`
   tables via `pg_dump --data-only` / `pg_restore` (schema-only tables, not the
   pairs/baskets trade history — this repo starts its own).
4. Bring over `src/shared/prefect/flows/data_ingestion/yahoo_flows.py` so this
   repo keeps refreshing `market_data` on its own schedule rather than relying on
   manual re-syncs from `trading-system` going forward. **Source coherence:**
   `get_price_series()` reads `data_source='yahoo_adjusted'` (full universe, ~2.5yr
   hourly; the trading-system code had drifted to a thin, half-backfilled
   `yahoo_adjusted_1h` — reverted in `src/shared/market_data.py`). The refresh flow
   must write to the **same** `yahoo_adjusted` source, or `get_price_series` won't
   see fresh bars.
5. Point `.env` at the new database, and use a **separate Alpaca paper API key**
   from `trading-system`'s — running two strategy engines against the same paper
   account makes P&L attribution ambiguous.
6. **TODO — re-enable CI.** `.github/workflows/ci.yml` and `security.yml` were
   disabled during the trim (renamed `*.disabled`); they still target the old
   pip/`requirements.txt`/`flake8`/`trading_system_test` setup. Rewrite them for
   `uv sync`, `ruff`, and the `factor_stat_arb` DB, then rename back to `*.yml`.
7. **Migrations — replay is fixed and testable.** `03_create_indexes.sql` used to
   index `logging.system_logs(log_id)`, a column `02` never creates (verified
   absent in the live schema); that line was removed. `scripts/test_migrations.py`
   replays `02`→`25` in order on a throwaway DB and now reports PASS — run it after
   any `.sql` change. The harmonic migrations `26`/`27` remain skipped (dropped
   module). The live schema in `factor_stat_arb` was built via
   `scripts/clone_schema.py` (`pg_dump`); the numbered scripts are now a validated
   alternative path. Remaining TODO: reconcile the two so there's one documented
   source of truth (either drop `clone_schema.py` in favour of the migrations, or
   vice versa).

## Why this, and not another pair/basket search

Two discovery mechanisms already exist in `trading-system`:

- `scripts/discover_pairs.py` + `pair_discovery_flow.py` — Engle-Granger cointegration
  over the symbol universe, filtered to `min_correlation=0.70`, `max_pvalue=0.05`,
  half-life 5-72h, keeping only the top 5 candidates.
- `scripts/discover_baskets.py` — the same idea generalized to N-stock baskets via
  Johansen cointegration, searched combinatorially (`itertools.combinations`) within
  a sector.

Both are, at their core, a combinatorial search over discrete tuples of tickers,
filtered by a strict statistical test. On real data that search comes up sparse and
unstable more often than not — which matches exactly the problem already run into.

PCA factor decomposition sidesteps the combinatorics entirely. Instead of asking
"which pair or triple of tickers happens to cointegrate," it extracts statistical
factors from the full universe's return covariance in one pass, then asks a simpler
question per stock: "after removing the common structure, does what's left mean-revert
fast and cleanly?" Every stock in the universe gets evaluated, not just the
combinatorially lucky tuples.

## The architectural shortcut that makes this cheap to build

`BasketSpreadCalculator` already computes `spread = sum(w_i * log(P_i))` across N legs
and z-scores it — that is exactly the operation a factor-residual trade needs, if the
weights `w_i` come from a regression against tradable proxies instead of a Johansen
eigenvector. Once the weights exist, everything downstream — signal generation,
position sizing, DB storage, execution, risk controls — is identical to what a basket
trade already does. So the actual new work is narrow: a new *discovery* method that
writes into the same `BasketRegistry` table, plus the explainability layer, which
doesn't exist anywhere in the codebase yet.

## Reuse table (verified against the actual repo, not assumed)

| Existing code | Reused as |
|---|---|
| `src/shared/market_data.py` → `get_price_series()` | Hourly closes already cached in Postgres by the existing Yahoo ingestion flow. No new data fetching code at all. |
| `src/services/strategy_engine/baskets/spread_calculator.py` → `BasketSpreadCalculator` | Reused unmodified — log-spread + rolling z-score across N legs, regardless of whether the weights came from Johansen or a factor regression. |
| `src/services/strategy_engine/pairs/signal_generator.py` → `SignalGenerator` / `BacktestSignalGenerator` | Reused unmodified via the same `SimpleNamespace` shim pattern `baskets/strategy.py` already uses (`_make_fake_pair`) to expose `entry_threshold` / `exit_threshold` / `stop_loss_threshold` / `max_hold_hours`. |
| `src/services/strategy_engine/pairs/position_sizer.py` → `KellySizer`, or the proportional-to-weight sizing already in `BasketStrategy._run_basket_cycle` | Reused for position sizing. |
| `src/services/strategy_engine/backtesting/engine.py` (`BacktestEngine`, `SimulatedTrade`, `BacktestResult`) | Mirrored for a `FactorBacktestEngine` — same look-ahead-safe fill logic, swap in `BasketSpreadCalculator` and the new weights. |
| `src/services/risk_management/portfolio_risk_manager.py` → `PortfolioRiskManager` | Reused unmodified. Correlation guard and drawdown circuit breaker apply the same way no matter how the basket was discovered. |
| `src/services/alpaca/client.py` → `AlpacaClient` | Reused unmodified. `alpaca_base_url` already defaults to `https://paper-api.alpaca.markets` and `paper_trading=True` is already the default in `src/config/settings.py` — paper-only requires zero new code. |
| `src/shared/database/models/basket_models.py` (`BasketRegistry`, `BasketSpread`, `BasketTrade`) | Reused unmodified as the storage layer. Discovery writes into these same tables. |
| `src/shared/prefect/flows/strategy_engine/pair_discovery_flow.py` | Mirrored structurally for a new `factor_discovery_flow.py` — same `@flow`/`@task` shape, same email summary via `src/services/notification/email_notifier.py`, same `--deploy` CLI convention. |
| `config/strategies.yaml` | Add a new block alongside the existing `pairs_trading_strategy` entry. |
| `streamlit_ui/pages/` (existing: `6_Pair_Lab.py`, `4_Strategy_Monitor.py`, etc.) | Add a new page here — `8_Factor_Lab.py` — rather than a separate app. |

## What's genuinely new

Nothing above needs to be written from scratch. What doesn't exist yet:

- `scripts/discover_factor_baskets.py` — the new discovery script (see Methodology).
- `src/shared/prefect/flows/strategy_engine/factor_discovery_flow.py` — scheduled flow calling it.
- `src/services/strategy_engine/factor_stat_arb/factor_model.py` — PCA fit across the universe.
- `src/services/strategy_engine/factor_stat_arb/proxy_mapper.py` — maps PCA factors to a small set of tradable ETF proxies via regression.
- `src/services/strategy_engine/factor_stat_arb/residual_ou.py` — OU/AR(1) fit, half-life, R^2 on the resulting spread.
- `src/services/strategy_engine/factor_stat_arb/explainability/` — **genuinely new, no equivalent exists anywhere in the repo today**:
  - `confidence_model.py` — LightGBM classifier trained on closed `BasketTrade` history, predicting whether a signal is worth trusting.
  - `shap_explainer.py`, `visualizer.py` — SHAP explanation per open or candidate signal.
- `streamlit_ui/pages/8_Factor_Lab.py` — factor structure, active signals, SHAP panel.
- A new `config/strategies.yaml` block: `factor_stat_arb_strategy`.

## Methodology

1. **Universe and data.** Reuse `get_price_series()` against `data_ingestion.market_data` — already populated hourly. No new ingestion code.
2. **Factor decomposition.** PCA on standardized daily (or hourly) returns across the full universe. Keep the top-k components explaining roughly 50-70% of variance.
3. **Tradable proxy mapping.** Regress each stock's return on a small set of liquid ETFs (sector ETF + SPY, or whichever handful best track the top components) rather than the untradeable statistical factors directly. This is what makes discovery output directly executable through `BasketRegistry`, and it's a good explainability object on its own — "this stock's exposure looks like 70% XLF, 20% SPY."
4. **Spread and OU fit.** Log-spread of stock vs. weighted proxies, via `BasketSpreadCalculator`. Fit an OU process on the resulting spread for half-life and R^2, screened with bounds in the same spirit as `pair_discovery_flow.py`'s `min_half_life`/`max_half_life`, swapping Engle-Granger p-value for OU fit quality.
5. **Signal.** `SignalGenerator` via the `SimpleNamespace` shim — identical threshold logic already used for pairs and baskets.
6. **Backtest.** `FactorBacktestEngine`, mirroring `BacktestEngine` with `BasketSpreadCalculator` / `BacktestSignalGenerator` swapped in.
7. **Explainability.** Confidence classifier + SHAP over discovery-stage features: OU half-life, OU R^2, proxy-loading stability over time, recent volume/volatility regime, sector momentum.
8. **Execution.** `BasketStrategy.run_cycle()` unchanged, against the Alpaca paper endpoint (already the default). `PortfolioRiskManager` guards apply unchanged.
9. **Dashboard and content.** New Streamlit page, plus GitHub commit history, Medium write-up, LinkedIn post.

## Milestones (~5-8 hrs/week)

| Weeks | Milestone |
|---|---|
| 0 | Repo trim, new `factor_stat_arb` database provisioned and seeded, `.env` and Alpaca paper keys pointed at the new setup (see **Repository and data setup**) |
| 1-2 | `discover_factor_baskets.py` — PCA + proxy regression + OU screening, validated against a real universe already in the DB |
| 3 | `FactorBacktestEngine` — Sharpe/drawdown/hit rate, compared against the existing pair/basket backtest gate thresholds |
| 4 | `factor_discovery_flow.py` + `config/strategies.yaml` entry + manual activation review (same is_active=False-until-reviewed convention as pairs) |
| 5 | Explainability layer — confidence model + SHAP |
| 6 (stretch) | Compare 1-proxy vs. multi-proxy hedges; tighten the tradable-proxy mapping |
| 7 | Confirm `BasketStrategy.run_cycle()` runs the new registry entries correctly end to end against Alpaca paper |
| 8 | `8_Factor_Lab.py` Streamlit page; GitHub write-up; Medium article; LinkedIn post |

## Risk and honesty notes

- `PortfolioRiskManager`'s correlation guard and drawdown circuit breaker already protect
  this strategy exactly as they protect pairs and baskets — no new risk code needed,
  but worth confirming in testing that a factor-basket entry is correctly seen by the
  correlation guard against other open positions.
- PCA factor structure is not stable. Re-discovery should run on a similar cadence to
  `weekly_pair_discovery_flow` (weekly), and the backtest should show what happens to
  performance when factor loadings shift between refits.
- Paper trading only (`paper_trading=True`, `alpaca_base_url` pointed at
  `paper-api.alpaca.markets`) until independently validated over a meaningful
  out-of-sample period. This is a technical and educational project, not investment
  advice.

## Build order for Claude Code

1. `src/services/strategy_engine/factor_stat_arb/factor_model.py` (PCA) + `proxy_mapper.py`
2. `src/services/strategy_engine/factor_stat_arb/residual_ou.py`
3. `scripts/discover_factor_baskets.py` — wire 1 and 2 together, upsert to `BasketRegistry`
4. `src/services/strategy_engine/backtesting/` → `FactorBacktestEngine` (mirror `BacktestEngine`)
5. `src/shared/prefect/flows/strategy_engine/factor_discovery_flow.py`
6. `src/services/strategy_engine/factor_stat_arb/explainability/` — confidence model + SHAP
7. `streamlit_ui/pages/8_Factor_Lab.py`
8. `config/strategies.yaml` entry
9. Tests under `tests/`, mirroring existing test structure for the pairs/baskets modules

Confirm each step against the real DB schema and existing modules as you go — several
of the interfaces above (`SignalGenerator`, `BasketSpreadCalculator`) use `SimpleNamespace`
shims and duck typing rather than shared base classes, so match the existing shim pattern
exactly rather than subclassing.
