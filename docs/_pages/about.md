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

**Factor Statistical Arbitrage** is an open-source research project that looks
for stocks whose price has drifted a little out of step with their market and
sector, on the idea that the gap tends to close again. It's built so the
reasoning behind every trade idea can actually be read and understood, not
just trusted blindly.

The classic way to look for this ("pairs trading") is to search through
thousands of pairs of tickers looking for two that have historically moved
together, then wait for one of those pairs to drift apart. It's a slow,
brute-force search, and pairs that worked in the past often quietly stop
working.

This project takes a different angle: instead of searching for pairs, it
looks at the whole market at once, mathematically separates "what moved
because of the broad market and sector" from "what's left over for this
specific stock," and checks every stock for the same thing -- is the leftover
part currently stretched away from normal, and does it reliably come back?

Four things make this approach distinct:

- **Looks at everything at once.** Every stock in the universe (~1,000
  names) is checked in a single pass -- no combing through pairs one at a
  time, no cherry-picking.
- **Hedges with things you can actually trade.** Each stock's market/sector
  exposure is measured against a couple of liquid, real ETFs (an S&P 500 fund
  plus its sector fund), not an abstract number -- so the hedge is something
  you could really buy or sell.
- **Explains itself in plain English.** The result reads like "this stock
  trades like 85% its energy-sector ETF plus 15% the S&P 500" -- a label a
  non-specialist can understand, attached to every candidate before any money
  (paper money) moves.
- **Grades its own confidence.** A separate scoring model looks at each
  candidate trade against how similar setups have played out historically,
  and explains -- feature by feature -- why it's more or less confident in
  this one.

All execution is paper-only via Alpaca -- no real money is ever at risk.
Nothing here constitutes investment advice.

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
