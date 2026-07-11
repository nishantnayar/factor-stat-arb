"""
Database Backup Flow

Runs pg_dump for data_ingestion and analytics schemas.
Scheduled Saturday morning UTC after weekly Yahoo flows and pair discovery.
"""

import sys
from pathlib import Path

if __file__ and Path(__file__).exists():
    project_root = Path(__file__).parent.parent.parent.parent.parent.parent
    if project_root.exists() and str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from loguru import logger
from prefect import flow


def _backup_run_name() -> str:
    from datetime import datetime

    return f"DB Backup - {datetime.now().strftime('%Y-%m-%d')}"


@flow(
    name="Weekly Database Backup",
    flow_run_name=_backup_run_name,
    log_prints=True,
    retries=1,
    retry_delay_seconds=60,
    timeout_seconds=1800,
)
async def backup_trading_db_flow() -> dict:
    """
    Backup data_ingestion and analytics schemas via pg_dump.

    Runs after weekend data ingestion jobs (company info, key statistics).
    """
    import importlib.util

    _script = (
        Path(__file__).parent.parent.parent.parent.parent.parent
        / "scripts"
        / "backup_trading_db.py"
    )
    _spec = importlib.util.spec_from_file_location("backup_trading_db", _script)
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    run_backup = _mod.run_backup

    logger.info("Starting database backup (data_ingestion, analytics)")
    path = run_backup()
    logger.info(f"Backup completed: {path}")
    return {"backup_path": str(path), "success": True}
