---
layout: splash
title: "Factor Statistical Arbitrage"
permalink: /
toc: false
sidebar: false
header:
  overlay_color: "#1a1a2e"
  overlay_filter: 0.55
  actions:
    - label: '<i class="fab fa-github"></i>&nbsp; View on GitHub'
      url: "https://github.com/nishantnayar/factor-stat-arb"
excerpt: >
  Explainable factor-residual statistical arbitrage on US equities.
  PCA decomposition &rarr; tradable ETF proxy mapping &rarr; OU residual mean-reversion &rarr; SHAP explainability.

feature_row:
  - title: "Methodology"
    excerpt: "The factor pipeline stage by stage: PCA decomposition, ETF proxy mapping, OU residual fit, and discovery ranking."
    url: "/factor-stat-arb/methodology/"
    btn_label: "Read more"
    btn_class: "btn--primary"
  - title: "Project Spec"
    excerpt: "Full design and milestone plan -- from data ingestion to paper execution and explainability."
    url: "/factor-stat-arb/project-spec/"
    btn_label: "Read more"
    btn_class: "btn--primary"
  - title: "Source Code"
    excerpt: "Python 3.11, uv-managed environment, PostgreSQL, Prefect, Streamlit, Alpaca paper trading."
    url: "https://github.com/nishantnayar/factor-stat-arb"
    btn_label: "View repository"
    btn_class: "btn--inverse"
---

{% include feature_row %}

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![uv](https://img.shields.io/badge/deps-uv-7c3aed.svg)](https://github.com/astral-sh/uv)
[![PostgreSQL](https://img.shields.io/badge/storage-PostgreSQL-336791.svg)](https://www.postgresql.org/)
[![Prefect](https://img.shields.io/badge/orchestration-Prefect-024dfd.svg)](https://www.prefect.io/)
[![Alpaca](https://img.shields.io/badge/execution-Alpaca%20paper-ffb86c.svg)](https://alpaca.markets/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/nishantnayar/factor-stat-arb/blob/main/LICENSE)
[![Status: WIP](https://img.shields.io/badge/status-work--in--progress-orange.svg)](#project-status)

---

## The idea

Classic pairs and basket strategies hunt for a *pair* or *tuple* of tickers that happen
to cointegrate -- a combinatorial search over discrete ticker sets, filtered by a strict
statistical test. On real data that search tends to come back sparse and unstable.

**Factor Stat Arb sidesteps the combinatorics.** It decomposes the entire universe's
return covariance with PCA in a single pass, then asks one question of *every* stock:

> After removing the common market/sector structure, does what's left mean-revert
> quickly and cleanly?

Each stock is regressed onto a small set of **tradable ETF proxies** (e.g. sector ETF +
SPY), so the residual spread is directly executable -- and the loadings double as a
plain-English explanation ("this name trades like 70% XLF, 20% SPY"). A confidence model
and SHAP layer then score and explain each candidate signal before any capital is
committed.

## At a glance

| | |
|---|---|
| **Data** | PostgreSQL, ~2.5 years of hourly adjusted bars for 1,000+ symbols |
| **Discovery** | PCA &rarr; tradable ETF proxy regression &rarr; OU residual screen &rarr; ranked candidates |
| **Execution** | Alpaca **paper** only, behind portfolio risk guards |
| **Tooling** | [uv](https://github.com/astral-sh/uv)-managed; `uv run main.py up` starts Prefect + dashboard + worker |

## Project status

The data foundation, factor discovery pipeline (PCA, proxy mapping, OU screen), and
services are in place. The backtest engine and explainability layer are the active build.

- [x] Reproducible environment (uv, pinned Python 3.11, locked deps)
- [x] PostgreSQL provisioned, schema built, ~8.7M market-data rows seeded
- [x] PCA factor model + tradable-proxy mapping
- [x] OU residual fit + discovery script
- [ ] Factor backtest engine
- [ ] Prefect discovery flow
- [ ] Confidence model + SHAP explainability
- [ ] Streamlit Factor Lab

See the [Project Spec](/factor-stat-arb/project-spec/) for the full design and milestone plan.

## Pipeline

```mermaid
flowchart LR
    A[Hourly adjusted\nprices, full universe] --> B[PCA factor\ndecomposition]
    B --> C[Map factors to\ntradable ETF proxies]
    C --> D[Residual spread\n+ OU half-life fit]
    D --> E[Signal\nz-score thresholds]
    E --> F[Backtest\nSharpe / DD / hit-rate]
    E --> G[Confidence model\n+ SHAP explanation]
    F --> H[Paper execution\n+ portfolio risk guards]
    G --> H
```

---

**Disclaimer:** This is a technical and educational project, not investment advice.
It runs against Alpaca's paper endpoint only and has not been validated over a meaningful
out-of-sample period.
{: .notice--warning}
