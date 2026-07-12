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

**Factor Stat Arb** is an open-source research project exploring explainable
factor-residual statistical arbitrage on US equities. It is built on top of a
prior pairs/baskets trading system and extends it with a new discovery layer:

- **PCA factor decomposition** extracts common return structure from 1,000+ symbols
  in one pass, rather than searching combinatorially for cointegrated pairs.
- **Tradable ETF proxy regression** maps each stock to liquid ETFs, making the
  residual spread both directly executable and interpretable.
- **Ornstein-Uhlenbeck residual fitting** screens for names with clean,
  bounded mean-reversion over a half-life appropriate for hourly bars.
- **LightGBM + SHAP explainability** scores and explains every signal candidate
  before any capital is committed.

All execution is paper-only via Alpaca. Nothing here constitutes investment advice.

## Tech stack

| Layer | Tools |
|---|---|
| Language | Python 3.11, managed with [uv](https://github.com/astral-sh/uv) |
| Data / modeling | pandas, NumPy, scikit-learn, statsmodels, LightGBM, SHAP |
| Storage | PostgreSQL (SQLAlchemy ORM), ~8.7M hourly adjusted bars |
| Orchestration | Prefect (scheduled discovery and data refresh) |
| Execution | Alpaca paper trading API |
| Dashboard | Streamlit |
| Docs | Jekyll + Minimal Mistakes (this site) |

## Repository

Source code, scripts, tests, and the Streamlit dashboard live at
[github.com/nishantnayar/factor-stat-arb](https://github.com/nishantnayar/factor-stat-arb).

Contributions, bug reports, and questions are welcome via
[GitHub Issues](https://github.com/nishantnayar/factor-stat-arb/issues).

## Disclaimer

This is a **technical and educational project**, not investment advice.
It runs against Alpaca's **paper** endpoint only and has not been validated
over a meaningful out-of-sample period. Nothing here is a recommendation to
trade any security.
{: .notice--warning}
