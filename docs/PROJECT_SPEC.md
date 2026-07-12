---
layout: single
title: "Architecture"
permalink: /project-spec/
toc: true
toc_sticky: true
toc_label: "Contents"
read_time: true
sidebar:
  nav: "docs"
---

# Architecture

Factor Statistical Arbitrage is a modular Python system for explainable factor-residual
statistical arbitrage on US equities. This page covers the system design,
component breakdown, and milestone roadmap.

## System overview

```
Yahoo Finance (hourly bars)
        |
        v
  PostgreSQL ─── market_data (~8.7M rows, 1,000+ symbols, 2.5yr)
        |
        v
  Factor Discovery Pipeline
  ┌──────────────────────────────────┐
  │  PCA factor model                │
  │  -> ETF proxy regression (OLS)   │
  │  -> OU residual fit + screen     │
  │  -> Rank & store in registry     │
  └──────────────────────────────────┘
        |
        v
  BasketRegistry (PostgreSQL)
        |
   ┌────┴────┐
   v         v
Backtest   Live signal (z-score)
engine         |
               v
         Confidence model + SHAP
               |
               v
         Alpaca paper execution
         + Portfolio risk guards
               |
               v
         Streamlit Factor Lab
```

## Why factor decomposition

Statistical arbitrage typically searches for pairs or baskets of tickers that
cointegrate -- a combinatorial search filtered by a strict statistical test.
On real data that search is sparse: most combinations fail, and the ones that
pass tend to be regime-dependent.

PCA factor decomposition sidesteps the combinatorics. It extracts the common
return structure from the full universe in one pass, then asks a simpler
question of every stock: *does what's left after removing the common structure
mean-revert cleanly?*

Because the residual is computed against **tradable ETF proxies** (e.g. SPY +
a sector ETF), the hedge is directly executable and carries a plain-English
interpretation: "XOM trades like 0.85 XLE + 0.15 SPY." Every stock in the
universe is evaluated, not just the combinatorially lucky tuples.

## Data

| Source | Detail |
|---|---|
| Market data | Yahoo Finance hourly bars, split/dividend-adjusted |
| Storage | PostgreSQL `data_ingestion.market_data` (partitioned by `data_source`) |
| Active source | `yahoo_adjusted` -- ~1,038 symbols, ~2.5 years of hourly bars |
| Refresh | Prefect-scheduled `yahoo_market_data_flow`, runs nightly on weekdays |
| Access | `get_price_series(symbol, limit)` in `src/shared/market_data.py` |

ETF proxies (SPY, SPDR sector ETFs) are stored in the same table but kept
separate from the stock universe so they never contaminate the PCA.

## Database schema

Two PostgreSQL databases run independently:

| Database | Purpose |
|---|---|
| `factor_stat_arb` | Application DB: market data, models, strategy tables |
| `factor_stat_arb_prefect` | Prefect orchestration metadata (isolated) |

The application DB has 8 schemas. Key tables for the factor strategy:

| Table | Content |
|---|---|
| `data_ingestion.symbols` | Symbol universe with sector mappings |
| `data_ingestion.market_data` | Hourly OHLCV bars (all sources) |
| `analytics.technical_indicators` | Pre-computed RSI, ATR, Bollinger bands |
| `strategy_engine.basket_registry` | Discovered factor baskets (hedge weights, OU stats, rank score) |
| `strategy_engine.basket_trades` | Trade history (paper) |

## Factor discovery pipeline

The pipeline runs in `scripts/discover_factor_baskets.py` and is scheduled
via `factor_discovery_flow.py`.

### 1. Data (`src/.../factor_stat_arb/data.py`)

Pulls hourly adjusted closes into a wide `time x symbol` matrix, converts to
log returns, and cleans: sparse symbols and outlier ticks are dropped so
downstream steps receive a dense matrix.

### 2. Factor model (`factor_model.py`)

`FactorModel` standardizes cross-sectional returns and fits PCA, retaining the
smallest number of components that explain a target variance share (default
~60%). On the live universe, ~22 components explain 60% of variance (PC1, the
market factor, accounts for ~20%).

The factor model characterises common structure. The actual hedge comes from
the proxy mapper because PCA factors are not directly tradable.

### 3. Proxy mapper (`proxy_mapper.py`)

Each stock's returns are regressed (OLS) on a small set of liquid ETFs -- SPY
plus the stock's SPDR sector ETF. The fitted betas become the hedge weights of
a log-price spread basket:

```
spread = log(P_stock) - beta_sector * log(P_sector_etf) - beta_spy * log(P_spy)
```

This makes the residual both executable and interpretable:

> "JPM trades like 1.23 XLF, roughly SPY-neutral, R2 = 0.72."

Two residual objects are computed:

| Object | Definition | Use |
|---|---|---|
| **Traded spread** | `log P_stock - sum(beta * log P_proxy)` | What's executed; z-scored with a rolling window |
| **Residual level** | Cumulative idiosyncratic returns (Avellaneda-Lee) | OU half-life is fit here -- drift-free, so half-life is meaningful |

The distinction matters: the traded spread carries regression alpha as a linear
drift, which would inflate the OU half-life estimate. The residual level
removes it.

### 4. OU fit (`residual_ou.py`)

The residual level is fit as an AR(1): `s_t = a + b*s_{t-1} + eps`. From `b`:

- Mean-reversion speed: `theta = -ln(b)`
- **Half-life**: `ln(2) / theta` (in hours)
- Long-run mean and equilibrium standard deviation

A candidate passes the screen if `0 < b < 1` (mean-reverting) and its
half-life falls in the configured window.

**Half-life calibration:** Factor residuals mean-revert more slowly than
cointegrated pairs. Across the live universe (drift-free residual):

| p25 | Median | p75 |
|---|---|---|
| 166h | **263h (~38 trading days)** | 393h |

The default screen is **48--400h**, dropping microstructure noise (< 48h) and
near-random-walk names (> 400h).

### 5. Ranking and storage

Survivors are ranked by `proxy_r2 * z_score_abs_mean` (fit quality x
tradability) and upserted into `strategy_engine.basket_registry` with
`is_active=False` pending manual review.

```bash
uv run scripts/discover_factor_baskets.py --dry-run      # preview only
uv run scripts/discover_factor_baskets.py --top-n 50     # discover + store
```

A recent run produced 50 candidates; Energy and Financials dominate (tight
sector-ETF tracking yields the cleanest residuals). Example: `FSA_XOM` = XOM
hedged with SPY + XLE, half-life 192h, proxy R2 0.83.

## Signal and execution

Once a basket is activated in the registry, the live signal loop:

1. Computes the log-price spread using stored hedge weights.
2. Z-scores against a rolling window (default 30-day).
3. Fires entry / exit signals at configurable sigma thresholds (entry 2.0,
   exit 0.5, stop-loss 3.0 by default).
4. Sizes positions using Half-Kelly after 20 bootstrap trades (2% fixed
   fraction for the first 20); hard cap 12% per leg.
5. Submits paper orders via the Alpaca API.

Portfolio risk guards run at every cycle: a correlation guard prevents
over-concentration among correlated open positions, and a drawdown circuit
breaker halts trading if portfolio drawdown exceeds the configured threshold.

## Explainability layer (planned)

Before any basket is activated, a confidence model assigns a probability that
the signal will be profitable:

- **Training data:** closed `basket_trades` history (label: profitable yes/no).
- **Features:** OU half-life, OU R2, proxy loading stability over time, recent
  volume regime, sector momentum.
- **Model:** LightGBM classifier.
- **Explanation:** SHAP values per candidate signal, surfaced in the Streamlit
  Factor Lab.

## Streamlit dashboard

`uv run main.py up` starts three services:

| Service | Port | Purpose |
|---|---|---|
| Prefect server | 4201 | Orchestration UI, flow run history |
| Streamlit | 8502 | Factor Lab dashboard |
| Prefect worker | -- | Executes scheduled flows |

## Tech stack

| Layer | Tools |
|---|---|
| Language | Python 3.11, [uv](https://github.com/astral-sh/uv) |
| Data / modeling | pandas, NumPy, scikit-learn, statsmodels, LightGBM, SHAP |
| Storage | PostgreSQL with SQLAlchemy ORM |
| Orchestration | Prefect |
| Execution | Alpaca paper trading API |
| Dashboard | Streamlit |

## Milestones

| Weeks | Milestone |
|---|---|
| 0 | Environment, databases, data seeded |
| 1--2 | `discover_factor_baskets.py` -- PCA + proxy regression + OU screening |
| 3 | `FactorBacktestEngine` -- Sharpe, drawdown, hit rate gates |
| 4 | `factor_discovery_flow.py` + `strategies.yaml` entry + manual review |
| 5 | Explainability layer -- confidence model + SHAP |
| 6 | Multi-proxy hedge comparison; tighten proxy mapping |
| 7 | End-to-end paper trading validation against Alpaca |
| 8 | Streamlit Factor Lab; write-up |

## Risk notes

- **Factor instability.** PCA structure shifts over time. Discovery should
  re-run weekly; backtests should show what happens to performance when
  loadings change between refits.
- **Paper only.** All execution targets Alpaca's paper endpoint. The system
  has not been validated over a meaningful out-of-sample period.
- **Correlation guard.** The portfolio risk manager checks that a new basket
  entry is not highly correlated with existing open positions. Verify this
  applies correctly to factor baskets during integration testing.
