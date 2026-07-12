"""
Weekly Factor Basket Discovery Flow

Scheduled 45 3 * * 6 (03:45 UTC Saturday) - after weekly pair discovery
(03:30 UTC Saturday), so both discovery jobs share the same fresh-data window
without competing for DB/CPU at the same instant.

Each run:
    1. Load universe symbols + sectors from DB
    2. Regress each stock's returns on tradable ETF proxies (SPY + sector ETF)
    3. Fit an OU process on the drift-free residual level
    4. Screen on proxy fit quality + OU half-life, rank the survivors
    5. Upsert top candidates to basket_registry (is_active=False)

Newly found baskets are NOT auto-activated. Run
scripts/backtest_factor_baskets.py against the candidates, inspect the gate
verdict in strategy_engine.basket_backtest_run, and activate manually
(UPDATE ... SET is_active=true) after reviewing the results - same
manual-review convention as pair discovery.

Deploy:
    python src/shared/prefect/flows/strategy_engine/factor_discovery_flow.py --deploy

Dry-run (one immediate run):
    python src/shared/prefect/flows/strategy_engine/factor_discovery_flow.py
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Optional, cast

# Add project root to path when running directly
if __file__ and Path(__file__).exists():
    project_root = Path(__file__).parent.parent.parent.parent.parent.parent
    if project_root.exists() and str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from loguru import logger
from prefect import flow, task

from src.services.notification.email_notifier import get_notifier


def _flow_run_name() -> str:
    return f"Factor Basket Discovery - {datetime.now().strftime('%Y-%m-%d')}"


# ---------------------------------------------------------------------------
# Discovery task
# ---------------------------------------------------------------------------


def _load_discover_factor_baskets_module() -> Any:
    """Dynamically load scripts/discover_factor_baskets.py (scripts/ isn't a package)."""
    import importlib.util

    script = (
        Path(__file__).parent.parent.parent.parent.parent.parent
        / "scripts"
        / "discover_factor_baskets.py"
    )
    spec = importlib.util.spec_from_file_location("discover_factor_baskets", script)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@task(
    name="run-factor-basket-discovery",
    retries=1,
    retry_delay_seconds=60,
    log_prints=True,
    timeout_seconds=3600,  # discovery can be slow on large symbol universes
)
async def run_factor_discovery_task(
    min_proxy_r2: float = 0.30,
    min_half_life: float = 48.0,
    max_half_life: float = 400.0,
    max_allocation_pct: float = 0.05,
    top_n: int = 50,
    limit: Optional[int] = None,
) -> list:
    """
    Run factor-basket discovery and upsert results to basket_registry.

    Returns:
        List of dicts with basket_id/name for upserted baskets.
    """
    mod = _load_discover_factor_baskets_module()

    logger.info(
        f"Starting factor basket discovery: min_proxy_r2={min_proxy_r2}, "
        f"half_life={min_half_life}-{max_half_life}h, top_n={top_n}"
    )

    df = mod.discover(
        min_proxy_r2=min_proxy_r2,
        min_half_life=min_half_life,
        max_half_life=max_half_life,
        max_allocation_pct=max_allocation_pct,
        top_n=top_n,
        limit=limit,
    )

    if df.empty:
        logger.info("No candidates passed the screen.")
        return []

    ids = mod.upsert(df)
    upserted = [
        {"basket_id": bid, "name": name} for bid, name in zip(ids, df["name"].tolist())
    ]
    logger.info(
        f"Discovery complete: {len(upserted)} basket(s) upserted to basket_registry"
    )
    return upserted


# ---------------------------------------------------------------------------
# Flow
# ---------------------------------------------------------------------------


@flow(
    name="weekly-factor-basket-discovery",
    flow_run_name=_flow_run_name,
    log_prints=True,
    retries=1,
    retry_delay_seconds=120,
    timeout_seconds=7200,
)
async def weekly_factor_discovery_flow(
    min_proxy_r2: float = 0.30,
    min_half_life: float = 48.0,
    max_half_life: float = 400.0,
    max_allocation_pct: float = 0.05,
    top_n: int = 50,
    limit: Optional[int] = None,
) -> dict:
    """
    Weekly factor-residual basket discovery flow.

    Discovers proxy-hedged, mean-reverting stock residuals, upserts them to
    basket_registry (is_active=False), and returns a summary.

    Args:
        min_proxy_r2:        Minimum proxy-regression fit quality (R^2).
        min_half_life:       Minimum OU half-life in hours.
        max_half_life:       Maximum OU half-life in hours.
        max_allocation_pct:  Max portfolio allocation per basket.
        top_n:                Maximum baskets to keep per run.
        limit:                Optional universe size cap (testing).

    Returns:
        Summary dict with baskets_found and the basket list.
    """
    logger.info("Starting weekly factor basket discovery flow")

    try:
        upserted = await run_factor_discovery_task(
            min_proxy_r2=min_proxy_r2,
            min_half_life=min_half_life,
            max_half_life=max_half_life,
            max_allocation_pct=max_allocation_pct,
            top_n=top_n,
            limit=limit,
        )
    except Exception as exc:
        err_msg = str(exc)
        logger.error(f"Factor basket discovery failed: {err_msg}")
        await get_notifier().send_flow_error(
            error=err_msg,
            flow_name="weekly-factor-basket-discovery",
        )
        raise

    logger.info(f"Discovery flow complete: {len(upserted)} basket(s) saved")
    return {
        "status": "OK",
        "baskets_found": len(upserted),
        "baskets": upserted,
    }


# ---------------------------------------------------------------------------
# Deployment helper (run from CLI)
# ---------------------------------------------------------------------------


async def deploy_factor_discovery_flow() -> None:
    """Register the weekly factor basket discovery flow as a Prefect deployment."""
    project_root = Path(__file__).parent.parent.parent.parent.parent.parent
    source_path = str(project_root)
    flow_file = "src/shared/prefect/flows/strategy_engine/factor_discovery_flow.py"

    from src.shared.prefect.config import PrefectConfig

    deployment = await cast(
        Awaitable,
        weekly_factor_discovery_flow.from_source(
            source=source_path,
            entrypoint=f"{flow_file}:weekly_factor_discovery_flow",
        ),
    )
    await deployment.deploy(
        name="Weekly Factor Basket Discovery",
        work_pool_name=PrefectConfig.get_work_pool_name(),
        cron="45 3 * * 6",  # 03:45 UTC Saturday (15 min after weekly pair discovery)
        parameters={
            "min_proxy_r2": 0.30,
            "min_half_life": 48.0,
            "max_half_life": 400.0,
            "max_allocation_pct": 0.05,
            "top_n": 50,
        },
        tags=["strategy-engine", "factor-stat-arb", "discovery", "scheduled"],
        description="Weekly factor-residual basket discovery - PCA/proxy regression + OU screening, upserts candidates to basket_registry",
        ignore_warnings=True,
    )
    logger.info("Factor basket discovery flow deployed successfully!")


if __name__ == "__main__":
    """
    Modes:
        Dry-run (one immediate run):
            python src/shared/prefect/flows/strategy_engine/factor_discovery_flow.py

        Register deployment in Prefect (creates weekly scheduled job):
            python src/shared/prefect/flows/strategy_engine/factor_discovery_flow.py --deploy
    """
    import asyncio
    import sys as _sys

    if "--deploy" in _sys.argv:
        asyncio.run(deploy_factor_discovery_flow())
    else:

        async def _run() -> None:
            await weekly_factor_discovery_flow()

        asyncio.run(_run())
