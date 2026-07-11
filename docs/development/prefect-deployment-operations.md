# Prefect Deployment Operations

> **📋 Implementation Status**: 🚧 In Progress  
> **Prefect Version**: 3.4.14

This document is the runbook for running and operating Prefect: server, worker, deploy, verify, monitor, troubleshoot, migration, and best practices.

## Prerequisites

1. **Prefect server** running
2. **Work pool** created (default: `data-ingestion-pool`)
3. **Worker** running for that pool
4. **Environment variables** set (see [Configuration](prefect-deployment-configuration.md))

## Step-by-Step Deployment

### Step 1: Start Prefect Server

```bash
prefect server start --host 0.0.0.0 --port 4200
```

- **UI**: http://localhost:4200  
- **API**: http://localhost:4200/api  

Keep this terminal open.

**Alternative (when script exists):** `python scripts/prefect/start_server.py`

### Step 2: Create Work Pool (one-time)

```bash
prefect work-pool ls
prefect work-pool create data-ingestion-pool --type process
```

Or from YAML: `prefect work-pool create --file deployment/prefect/work-pools/data-ingestion-pool.yaml`

### Step 3: Start Worker

```bash
prefect worker start --pool data-ingestion-pool
```

Keep this terminal open.

**Alternative:** `python scripts/prefect/start_worker.py --pool data-ingestion-pool`

### Step 4: Verify Configuration

```bash
# PowerShell
echo $env:PREFECT_API_URL
$env:PREFECT_API_URL = "http://localhost:4200/api"
```

Or in `.env`:

```bash
PREFECT_API_URL=http://localhost:4200/api
PREFECT_WORK_POOL_DATA_INGESTION=data-ingestion-pool
```

### Step 5: Deploy Flows

```bash
# Yahoo flows (current)
python src/shared/prefect/flows/data_ingestion/yahoo_flows.py
# or
python -m src.shared.prefect.flows.data_ingestion.yahoo_flows
```

When available: `python scripts/prefect/deploy_all.py`

### Step 6: Verify Deployments

```bash
prefect deployment ls
prefect deployment inspect "Daily Market Data Update/Daily Market Data Update"
```

Also check the Prefect UI at http://localhost:4200.

### Step 7: Test a Flow (optional)

```bash
prefect deployment run "Daily Market Data Update/Daily Market Data Update"
prefect deployment run "Daily Market Data Update/Daily Market Data Update" --param days_back=7 --param interval=1h
```

## What Gets Deployed (Yahoo)

- **Daily Market Data Update** — 22:15 UTC Mon–Fri; fetches 7 days of **unadjusted and adjusted** hourly data from Yahoo (`data_source='yahoo'` and `data_source='yahoo_adjusted'`), then triggers **Technical Indicators** as a sub-flow (`days_back=300` from DB). Indicators are not deployed as a standalone cron to avoid race conditions when Prefect restarts. Task returns `records_count` and `records_count_adjusted`.
- **Weekly Company Information** — 11 PM UTC Friday (after US close and daily Yahoo).
- **Weekly Key Statistics** — Prefer combined weekly flow; standalone not deployed by default.
- **Weekly Company Data Update** — Combined, 1:30 AM UTC Saturday (Fri evening US), staggered from company-only job.
- **Weekly Pair Discovery** — 3:30 AM UTC Saturday (after weekly Yahoo batch).
- **Weekly Database Backup** — 5 AM UTC Saturday; backs up `data_ingestion` and `analytics` schemas to `backups/trading_backup_YYYYMMDD.dump` via pg_dump. Run manually: `python scripts/backup_trading_db.py`.

**Note:** If you previously had "Daily Technical Indicators" deployed as a standalone cron, remove it to avoid duplicate runs: `prefect deployment delete "Daily Technical Indicators Calculation/Daily Technical Indicators Calculation"` (or delete via Prefect UI).

## Deployment Scripts (Phase 7)

These are created after flows are implemented and tested.

### deploy_all.py

```python
#!/usr/bin/env python3
"""Deploy all Prefect flows. Usage: python scripts/prefect/deploy_all.py"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from loguru import logger
from src.shared.prefect.deployments.deployments import create_deployments

def main():
    logger.info("🚀 Deploying Prefect flows...")
    try:
        create_deployments()
        logger.info("✅ All flows deployed successfully")
        return 0
    except Exception as e:
        logger.error(f"❌ Deployment failed: {e}")
        return 1
if __name__ == "__main__":
    exit(main())
```

### start_server.py

Sets `PREFECT_API_DATABASE_CONNECTION_URL` from settings, then runs:

`prefect server start --host 0.0.0.0 --port 4200`

### start_worker.py

Accepts `--pool` and runs: `prefect worker start --pool <pool>`

## Monitoring & Commands

- **UI**: http://localhost:4200 → Deployments / Flow Runs
- **CLI**:

```bash
prefect deployment ls
prefect flow-run ls
prefect flow-run inspect <flow-run-id>
prefect flow-run logs <flow-run-id>
prefect deployment pause "Daily Market Data Update/Daily Market Data Update"
prefect deployment resume "Daily Market Data Update/Daily Market Data Update"
```

## Troubleshooting

| Issue | Action |
|-------|--------|
| Work pool not found | `prefect work-pool create data-ingestion-pool --type process` |
| Cannot connect to Prefect API | Ensure server is running; set `PREFECT_API_URL=http://localhost:4200/api` |
| No worker available | `prefect worker start --pool data-ingestion-pool` |
| Deployments exist but flows don’t run | Check deployment not paused, schedule correct, worker running; check UI for errors |
| `alembic.util.exc.CommandError: Can't locate revision identified by '<hash>'` on server startup | See [Alembic revision mismatch after a Prefect upgrade/downgrade](#alembic-revision-mismatch-after-a-prefect-upgradedowngrade) below |
| `ERROR: Cannot install ... websockets ... conflicting dependencies` during `pip install -r requirements.txt` | See [websockets version conflict](#websockets-version-conflict-prefect-vs-alpaca) below |

### Alembic revision mismatch after a Prefect upgrade/downgrade

**Symptom**: `prefect server start` fails during startup with a traceback ending in
`alembic.util.exc.CommandError: Can't locate revision identified by '<hash>'`. This can
happen either as an upgrade (current DB revision unknown to the installed package) or
mid-way through a downgrade.

**Root cause**: The Prefect Postgres database's `alembic_version` table is stamped with a
migration revision that the currently installed `prefect` package doesn't recognize -- most
often because a *different* Prefect version was installed against this same database at some
point (e.g. `pip` silently resolved a different `prefect` version to satisfy another
package's dependency, such as `streamlit` or `alpaca-py`/`alpaca-trade-api` pulling in a
different `websockets` range). Each Prefect minor version ships its own alembic migration
chain; a revision stamped by 3.4.14 will not exist in 3.2.7's chain and vice versa.

**Diagnosis**:
1. Confirm which database Prefect is actually using -- do not assume the profile file is
   authoritative; check the resolved setting directly:
   ```python
   from prefect.settings import PREFECT_API_DATABASE_CONNECTION_URL
   print(PREFECT_API_DATABASE_CONNECTION_URL.value())
   ```
   (An env var can silently override `~/.prefect/profiles.toml`.)
2. Connect to that exact database/host/user and check the stamped revision:
   ```sql
   SELECT * FROM alembic_version;
   ```
3. Check the installed Prefect version: `pip show prefect`.

**Fix**:
- If the DB's tables are otherwise fine and only `alembic_version` is stale (e.g. after a
  Prefect version was reinstalled to the *correct* version): `DELETE FROM alembic_version;`
  then start the server again -- Prefect will re-run migrations against the existing tables
  and re-stamp correctly.
- If that fails with `DuplicateTableError` (tables already exist from a different schema
  version), the safest fix is to fully reset: drop and recreate the database, then start the
  server so it builds the schema from scratch. This loses local flow-run/deployment history
  but does not touch your trading-system Postgres databases (they are separate).
- `prefect server database reset -y` does **not** help here -- it also goes through alembic
  (downgrade to base first), so it fails with the exact same `ResolutionError` if the current
  stamp is unresolvable.

**Prevention**: Pin `prefect>=3.4.14` (or whatever version your Prefect DB is currently
stamped for) in `requirements.txt` with an explicit lower bound, not just `prefect>=2.14.0`.
Without a floor, `pip`'s resolver can silently downgrade Prefect to satisfy an unrelated
conflict (see below), which reintroduces this exact failure the next time the server starts.

### websockets version conflict (Prefect vs Alpaca)

**Symptom**: `pip install -r requirements.txt` fails with
`ResolutionImpossible: ... websockets ... conflicting dependencies` naming
`alpaca-trade-api` and `prefect` (or `streamlit`).

**Root cause**: `alpaca-trade-api==3.2.0` (latest release, package is unmaintained) hard-pins
`websockets<11`. `prefect>=3.4.14` requires `websockets>=15.0.1`. `streamlit>=1.57.0` also
requires `websockets>=12.0.0` unconditionally (earlier 1.5x releases only needed it for an
optional `starlette` extra). There is no single `websockets` version that satisfies
`alpaca-trade-api` and a modern `prefect`/`streamlit` simultaneously.

**Fix**: The project uses `alpaca-py` instead of `alpaca-trade-api` specifically to avoid
this (see [Alpaca Integration](../api/data-ingestion-alpaca.md#sdk-alpaca-py-not-alpaca-trade-api)
for the full migration notes). If `alpaca-trade-api` ever gets reintroduced as a dependency,
this conflict will return -- resolve it by migrating that usage to `alpaca-py` again rather
than downgrading `prefect`/`streamlit`, since downgrading Prefect against an
already-migrated database re-triggers the alembic revision mismatch above.

## Updating Deployments

After changing flow code, redeploy:

```bash
python src/shared/prefect/flows/data_ingestion/yahoo_flows.py
# or
python scripts/prefect/deploy_all.py
```

## Understanding days_back

`days_back` has different meanings by context.

### Data ingestion (e.g. yahoo_market_data_flow)

- **Meaning**: How many days of **new** data to fetch from the API.
- **Typical**: `7` (hourly) or `30` (daily).
- **Example**: `yahoo_market_data_flow(days_back=7, interval="1h")` fetches 7 days from Yahoo.

### Indicator calculation (e.g. calculate_daily_indicators)

- **Meaning**: How many days of **historical** data to read from the **database**.
- **Typical**: `300` (needed for SMA_200, RSI_14, MACD, etc.).
- **Example**: `calculate_daily_indicators(days_back=300)` reads 300 days from DB.
- **Note**: Reads from DB, not API, so 300 days is acceptable.

**Summary**: Ingest might use `days_back=7` from the API; indicator calculation still uses `days_back=300` from the DB so all indicators have enough history.

## Architecture (high level)

```
Prefect Server → Deployments (schedules) → Work Pool → Worker (executes flows)
```

Flow run: schedule → queue → worker runs flow (e.g. load data → calculate indicators) → results in Prefect DB and UI.

## Migration Strategy

1. **Parallel run**: Keep existing scripts; run Prefect alongside; compare results (1–2 weeks).
2. **Validation**: Run both; verify consistency; document discrepancies (1–2 weeks).
3. **Cutover**: Make Prefect primary; keep scripts as fallback; document deprecation.
4. **Cleanup**: Optionally remove old scripts; update docs; train on Prefect UI.

## Best Practices

- **Incremental**: One flow at a time; test before adding more.
- **Errors**: Use retries, structured logging, timeouts, and graceful partial failure handling.
- **Monitoring**: Use Prefect UI and alerts for critical flows; track success rates and resources.
- **Testing**: Unit tests for tasks; integration tests for flows; test with limited data first.
- **Docs**: Document flow purpose, keep config examples current, maintain troubleshooting notes.

## Testing

- **Unit**: e.g. `tests/unit/test_prefect_tasks.py` for task behavior (mocked deps).
- **Integration**: e.g. `tests/integration/test_prefect_flows.py` for flows against test DB with limited symbols.

## Related Documentation

- [Prefect Deployment](prefect-deployment.md) — Overview and index
- [Configuration](prefect-deployment-configuration.md) — YAML, env, settings
- [Code Patterns](prefect-deployment-code-patterns.md) — Tasks, flows, deployments
- [Advanced Topics](prefect-deployment-advanced.md) — Design decisions

---

**Last Updated**: 4/3/2026  
**Status**: 🚧 In Progress
