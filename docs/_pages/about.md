---
layout: single
title: "About"
permalink: /about/
toc: false
author_profile: true
sidebar:
  nav: "docs"
---

## The project

**Factor Stat Arb** is an open-source research system for explainable
factor-residual statistical arbitrage on US equities.

Rather than searching combinatorially for pairs of tickers that happen to
cointegrate, the system decomposes the entire universe's return covariance
with PCA in a single pass and asks one question of every stock: *does what's
left after removing the common market and sector structure mean-revert cleanly
enough to trade?*

Four properties make this approach distinct:

- **Universe-wide.** Every stock is evaluated in the same PCA pass -- no
  combinatorial search, no cherry-picked pairs.
- **Tradable hedges.** Each stock is regressed onto liquid ETFs (SPY + its
  sector ETF), so the hedge portfolio is directly executable, not a synthetic
  statistical construct.
- **Interpretable.** The regression loadings read as a plain-English exposure:
  "XOM trades like 0.85 XLE + 0.15 SPY." Every candidate signal comes with
  this label before any capital is committed.
- **Explainable signals.** A LightGBM confidence model and SHAP layer score
  and explain each candidate signal against historical trade outcomes.

All execution is paper-only via Alpaca. Nothing here constitutes investment
advice.

## Tech stack

| Layer | Tools |
|---|---|
| Language | Python 3.11, managed with [uv](https://github.com/astral-sh/uv) |
| Data / modeling | pandas, NumPy, scikit-learn, statsmodels, LightGBM, SHAP |
| Storage | PostgreSQL (SQLAlchemy ORM), ~8.7M hourly adjusted bars |
| Orchestration | Prefect (scheduled discovery + data refresh) |
| Execution | Alpaca paper trading API |
| Dashboard | Streamlit |
| Docs | Jekyll + Minimal Mistakes |

## Get started

```bash
# 1. Install (uv provisions Python 3.11 itself)
uv sync

# 2. Configure
cp .env.example .env      # set POSTGRES_PASSWORD and Alpaca paper keys

# 3. Provision databases and schema
uv run scripts/provision_db.py

# 4. Seed market data
uv run scripts/seed_data.py

# 5. Start all services
uv run main.py up
```

Detailed setup and architecture are on the
[Architecture]({{ "/project-spec/" | relative_url }}) page.

## Repository

Source code, scripts, tests, and the Streamlit dashboard:
[github.com/nishantnayar/factor-stat-arb](https://github.com/nishantnayar/factor-stat-arb)

Bug reports and questions are welcome via
[GitHub Issues](https://github.com/nishantnayar/factor-stat-arb/issues).

## Disclaimer

This is a **technical and educational project**, not investment advice.
It runs against Alpaca's **paper** endpoint only and has not been validated
over a meaningful out-of-sample period. Nothing here is a recommendation to
trade any security.
{: .notice--warning}
