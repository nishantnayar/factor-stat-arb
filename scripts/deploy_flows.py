"""Register the Yahoo market-data deployment against a Prefect work pool.

Work-pool model (matches the repo's deploy_all_flows convention): creates a
'process' work pool if missing, then deploys the market-data flow to it on a
schedule. A worker (uv run scripts/run_prefect.py worker start --pool <name>,
or `main.py up worker`) executes the scheduled runs.

The Prefect server must already be running (uv run main.py up prefect).

Usage:
    uv run scripts/deploy_flows.py
"""

import asyncio
import inspect
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.run_prefect import build_env  # noqa: E402

# Apply the isolated Prefect env BEFORE importing prefect/the flow.
for _k, _v in build_env().items():
    if _k.startswith(("PREFECT", "PYTHON")):
        os.environ[_k] = _v

from prefect.client.orchestration import get_client  # noqa: E402
from prefect.client.schemas.actions import WorkPoolCreate  # noqa: E402
from prefect.exceptions import ObjectNotFound  # noqa: E402

from src.config.settings import get_settings  # noqa: E402
from src.shared.prefect.flows.data_ingestion.yahoo_flows import (  # noqa: E402
    yahoo_market_data_flow,
)

settings = get_settings()
POOL = settings.prefect_work_pool_data_ingestion  # data-ingestion-pool
FLOW_FILE = "src/shared/prefect/flows/data_ingestion/yahoo_flows.py"
CRON = "15 22 * * 1-5"  # 22:15 UTC weekdays, after US close


async def ensure_work_pool() -> None:
    async with get_client() as client:
        try:
            await client.read_work_pool(POOL)
            print(f"[skip] work pool '{POOL}' already exists")
        except ObjectNotFound:
            await client.create_work_pool(WorkPoolCreate(name=POOL, type="process"))
            print(f"[ok]   created work pool '{POOL}' (type=process)")


async def deploy() -> None:
    dep = yahoo_market_data_flow.from_source(
        source=str(ROOT),
        entrypoint=f"{FLOW_FILE}:yahoo_market_data_flow",
    )
    if inspect.iscoroutine(dep):
        dep = await dep
    dep_id = await dep.deploy(
        name="Daily Market Data Update",
        work_pool_name=POOL,
        cron=CRON,
        parameters={"days_back": 7, "interval": "1h"},
        tags=["data-ingestion", "yahoo", "market-data", "scheduled"],
        description="Daily end-of-day market data ingestion from Yahoo Finance (hourly bars)",
        ignore_warnings=True,
    )
    print(
        f"[ok]   deployed 'Daily Market Data Update' to pool '{POOL}' "
        f"on cron '{CRON}' (id={dep_id})"
    )


async def ensure_deployment() -> None:
    """Idempotently ensure the work pool and market-data deployment exist.

    Safe to call repeatedly (e.g. from main.py before starting the worker)."""
    await ensure_work_pool()
    await deploy()


def main() -> int:
    if settings.postgres_password in ("", "your_password_here"):
        print("ERROR: POSTGRES_PASSWORD not set in .env.")
        return 1
    asyncio.run(ensure_deployment())
    print("\nStart a worker to run it:  uv run main.py up worker")
    return 0


if __name__ == "__main__":
    sys.exit(main())
