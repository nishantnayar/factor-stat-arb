"""Serve the Yahoo market-data flow on a schedule against the isolated Prefect server.

Uses flow.serve() (Prefect 3): registers a scheduled deployment AND runs the
worker in this one long-lived process - ideal for a single machine, no separate
work pool needed. Applies this repo's isolated Prefect env (port 4201,
factor_stat_arb_prefect) before importing the flow.

The Prefect server must already be running (uv run main.py up prefect).

Usage:
    uv run scripts/serve_flows.py          # serve on the default schedule (blocks)
    uv run scripts/serve_flows.py --now     # trigger one run immediately, then exit
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.run_prefect import build_env  # noqa: E402

# Apply the isolated Prefect env BEFORE importing the flow (so the client and any
# scheduled runs target this repo's server/DB, not the machine-global profile).
for _k, _v in build_env().items():
    if _k.startswith(("PREFECT", "PYTHON")):
        os.environ[_k] = _v

import asyncio  # noqa: E402

from src.shared.prefect.flows.data_ingestion.yahoo_flows import (  # noqa: E402
    yahoo_market_data_flow,
)

# 22:15 UTC Mon-Fri, shortly after the US cash close. Adjust in the Prefect UI.
MARKET_DATA_CRON = "15 22 * * 1-5"


def main() -> int:
    if "--now" in sys.argv:
        print("Triggering one Yahoo market-data run now (interval=1h)...")
        res = asyncio.run(yahoo_market_data_flow(interval="1h"))
        n = res.get("total_records") if isinstance(res, dict) else res
        print(f"Done. total_records={n}")
        return 0

    print(f"Serving 'daily-market-data' on cron '{MARKET_DATA_CRON}' "
          f"(Ctrl+C to stop). Deployment visible in the Prefect UI.")
    yahoo_market_data_flow.serve(
        name="daily-market-data",
        cron=MARKET_DATA_CRON,
        parameters={"interval": "1h"},
        tags=["data-ingestion", "yahoo", "market-data"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
