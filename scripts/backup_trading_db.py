#!/usr/bin/env python3
"""
Backup key trading database schemas (data_ingestion, analytics).

Run manually or via Prefect. Uses pg_dump; requires PostgreSQL bin in PATH
or PGDMP_PATH env var set.
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Add project root for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(project_root / ".env")

# Default pg_dump path for Windows (PostgreSQL 18)
_DEFAULT_PGDMP = r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"
PG_DUMP_PATH = os.getenv("PGDMP_PATH", _DEFAULT_PGDMP)


def run_backup(output_dir: Path | None = None) -> Path:
    """
    Run pg_dump for data_ingestion and analytics schemas.

    Returns:
        Path to the created backup file.
    """
    if output_dir is None:
        output_dir = project_root / "backups"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d")
    output_file = output_dir / f"trading_backup_{timestamp}.dump"

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    db = os.getenv("TRADING_DB_NAME", "trading_system")
    password = os.getenv("POSTGRES_PASSWORD", "")

    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password

    cmd = [
        PG_DUMP_PATH,
        "-h", host,
        "-p", port,
        "-U", user,
        "-d", db,
        "-n", "data_ingestion",
        "-n", "analytics",
        "-F", "c",
        "-f", str(output_file),
    ]

    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr}")

    return output_file


if __name__ == "__main__":
    try:
        path = run_backup()
        print(f"Backup created: {path}")
    except Exception as e:
        print(f"Backup failed: {e}", file=sys.stderr)
        sys.exit(1)
