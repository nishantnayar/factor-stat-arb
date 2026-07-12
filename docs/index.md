---
title: "Factor Stat Arb"
description: "Explainable factor-residual statistical arbitrage on US equities"
---

# Factor Statistical Arbitrage

Explainable factor-residual statistical arbitrage on US equities. Instead of
searching combinatorially for pairs or baskets that cointegrate, Factor Stat Arb
decomposes the whole universe's return covariance with PCA, maps each stock to a
small set of **tradable ETF proxies**, and trades the idiosyncratic residual when
it mean-reverts cleanly - explaining every signal along the way.

## Start here

- **[Methodology](methodology.md)** - the factor pipeline stage by stage.
- **[Project spec](PROJECT_SPEC.md)** - full design and milestone plan.
- **Development** - infrastructure reference (database, Prefect, logging, testing).

## At a glance

- **Data**: PostgreSQL, ~2.5 years of hourly adjusted bars for 1,000+ symbols.
- **Discovery**: PCA -> tradable ETF proxy regression -> OU residual screen ->
  ranked candidates in `BasketRegistry`.
- **Execution**: Alpaca **paper** only, behind the reused portfolio risk guards.
- **Tooling**: managed end-to-end with [uv](https://github.com/astral-sh/uv);
  `uv run main.py up` starts Prefect, the dashboard, and the data-ingestion worker.

## Status

The data foundation, factor discovery pipeline (PCA, proxy mapping, OU screen,
`discover_factor_baskets.py`), and services are in place. The backtest engine and
explainability layer are the active build. See the
[project spec](PROJECT_SPEC.md) for the milestone checklist.

!!! warning "Not investment advice"
    This is a technical and educational project. It runs against Alpaca's paper
    endpoint only and has not been validated out-of-sample.
