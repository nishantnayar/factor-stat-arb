"""
Weekly Pair Discovery Flow

Scheduled 03:30 UTC Saturday (late Friday US) - after US cash close, daily
market ingestion (22:15 UTC Fri), indicators (22:30 UTC Fri), and weekly
company Yahoo jobs, so the DB has fresh bars before discovery.

Each run:
    1. Load active symbols from DB
    2. Fetch 252 days of hourly closes from market_data
    3. Run Engle-Granger cointegration + half-life filters
    4. Upsert top candidates to pair_registry (is_active=False)
    5. Email a discovery summary

Newly found pairs are NOT auto-activated.  Open the Pair Scanner /
Backtest Review pages in Streamlit, run backtests, and activate
manually after reviewing the results.

Deploy:
    python src/shared/prefect/flows/strategy_engine/pair_discovery_flow.py --deploy

Dry-run (one immediate run):
    python src/shared/prefect/flows/strategy_engine/pair_discovery_flow.py
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Awaitable, List, Tuple, cast

# Add project root to path when running directly
if __file__ and Path(__file__).exists():
    project_root = Path(__file__).parent.parent.parent.parent.parent.parent
    if project_root.exists() and str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from loguru import logger
from prefect import flow, task

from src.services.notification.email_notifier import get_notifier


def _flow_run_name() -> str:
    return f"Pair Discovery - {datetime.now().strftime('%Y-%m-%d')}"


# ---------------------------------------------------------------------------
# Discovery task
# ---------------------------------------------------------------------------


@task(
    name="run-pair-discovery",
    retries=1,
    retry_delay_seconds=60,
    log_prints=True,
    timeout_seconds=3600,  # discovery can be slow on large symbol universes
)
async def run_pair_discovery_task(
    days_back: int = 252,
    min_correlation: float = 0.70,
    max_pvalue: float = 0.05,
    min_half_life: float = 5.0,
    max_half_life: float = 72.0,
    top_n: int = 5,
) -> List[Tuple[int, str, str]]:
    """
    Run pair discovery and upsert results to pair_registry.

    Returns:
        List of (pair_id, symbol1, symbol2) for upserted pairs.
    """
    import asyncio

    # Import the discovery logic from the scripts module.
    # run_discovery handles all DB I/O, filtering, and upsert.
    import importlib.util

    _script = (
        Path(__file__).parent.parent.parent.parent.parent.parent
        / "scripts"
        / "discover_pairs.py"
    )
    _spec = importlib.util.spec_from_file_location("discover_pairs", _script)
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    run_discovery = _mod.run_discovery

    logger.info(
        f"Starting pair discovery: days_back={days_back}, "
        f"min_corr={min_correlation}, max_pvalue={max_pvalue}, "
        f"half_life={min_half_life}-{max_half_life}h, top_n={top_n}"
    )

    upserted = await run_discovery(
        min_correlation=min_correlation,
        max_pvalue=max_pvalue,
        min_half_life=min_half_life,
        max_half_life=max_half_life,
        sector_filter=None,
        top_n=top_n,
        days_back=days_back,
        data_source="yahoo_adjusted",
    )

    upserted = upserted or []
    logger.info(
        f"Discovery complete: {len(upserted)} pair(s) upserted to pair_registry"
    )
    return upserted


# ---------------------------------------------------------------------------
# Flow
# ---------------------------------------------------------------------------


@flow(
    name="weekly-pair-discovery",
    flow_run_name=_flow_run_name,
    log_prints=True,
    retries=1,
    retry_delay_seconds=120,
    timeout_seconds=7200,
)
async def weekly_pair_discovery_flow(
    days_back: int = 252,
    min_correlation: float = 0.70,
    max_pvalue: float = 0.05,
    min_half_life: float = 5.0,
    max_half_life: float = 72.0,
    top_n: int = 5,
) -> dict:
    """
    Weekly pair discovery flow.

    Discovers statistically valid pairs, upserts them to pair_registry
    (is_active=False), and emails a summary.

    Args:
        days_back:        Days of hourly history to use (default 252 = 1 year).
        min_correlation:  Minimum Pearson correlation on log returns.
        max_pvalue:       Maximum Engle-Granger cointegration p-value.
        min_half_life:    Minimum mean-reversion half-life in hours.
        max_half_life:    Maximum mean-reversion half-life in hours.
        top_n:            Maximum pairs to keep per run.

    Returns:
        Summary dict with pairs_found and the pair list.
    """
    logger.info("Starting weekly pair discovery flow")

    try:
        upserted = await run_pair_discovery_task(
            days_back=days_back,
            min_correlation=min_correlation,
            max_pvalue=max_pvalue,
            min_half_life=min_half_life,
            max_half_life=max_half_life,
            top_n=top_n,
        )
    except Exception as exc:
        err_msg = str(exc)
        logger.error(f"Pair discovery failed: {err_msg}")
        await get_notifier().send_flow_error(
            error=err_msg,
            flow_name="weekly-pair-discovery",
        )
        raise

    await get_notifier().send_discovery_summary(
        pairs_found=len(upserted),
        pairs_upserted=upserted,
    )

    logger.info(f"Discovery flow complete: {len(upserted)} pair(s) saved")
    return {
        "status": "OK",
        "pairs_found": len(upserted),
        "pairs": [
            {"id": pid, "symbol1": s1, "symbol2": s2} for pid, s1, s2 in upserted
        ],
    }


# ---------------------------------------------------------------------------
# Deployment helper (run from CLI)
# ---------------------------------------------------------------------------


async def deploy_pair_discovery_flow() -> None:
    """Register the weekly pair discovery flow as a Prefect deployment."""
    project_root = Path(__file__).parent.parent.parent.parent.parent.parent
    source_path = str(project_root)
    flow_file = "src/shared/prefect/flows/strategy_engine/pair_discovery_flow.py"

    from src.shared.prefect.config import PrefectConfig

    deployment = await cast(
        Awaitable,
        weekly_pair_discovery_flow.from_source(
            source=source_path,
            entrypoint=f"{flow_file}:weekly_pair_discovery_flow",
        ),
    )
    await deployment.deploy(
        name="Weekly Pair Discovery",
        work_pool_name=PrefectConfig.get_work_pool_name(),
        cron="30 3 * * 6",  # 03:30 UTC Saturday (Fri evening US; after weekly Yahoo batch)
        parameters={
            "days_back": 252,
            "min_correlation": 0.70,
            "max_pvalue": 0.05,
            "min_half_life": 5.0,
            "max_half_life": 72.0,
            "top_n": 5,
        },
        tags=["strategy-engine", "pairs-trading", "discovery", "scheduled"],
        description="Weekly pair discovery - runs Engle-Granger cointegration on the full symbol universe and upserts candidates to pair_registry",
        ignore_warnings=True,
    )
    logger.info("Pair discovery flow deployed successfully!")


if __name__ == "__main__":
    """
    Modes:
        Dry-run (one immediate run):
            python src/shared/prefect/flows/strategy_engine/pair_discovery_flow.py

        Register deployment in Prefect (creates weekly scheduled job):
            python src/shared/prefect/flows/strategy_engine/pair_discovery_flow.py --deploy
    """
    import asyncio
    import sys as _sys

    if "--deploy" in _sys.argv:
        asyncio.run(deploy_pair_discovery_flow())
    else:

        async def _run() -> None:
            await weekly_pair_discovery_flow()

        asyncio.run(_run())
