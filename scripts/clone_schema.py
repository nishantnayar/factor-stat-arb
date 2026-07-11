"""Clone the factor_stat_arb schema from the live trading_system database.

The numbered scripts/*.sql migrations drifted out of sync with the real DB and
don't replay cleanly (e.g. 03 indexes a nonexistent system_logs.log_id). The
authoritative schema is the running trading_system DB, so we pg_dump its schema
(structure only, no data) and restore it into a freshly created factor_stat_arb.

Data seeding (symbols, market_data, technical_indicators) is a separate step.

Usage:
    uv run scripts/clone_schema.py            # drop+recreate factor_stat_arb, clone schema
    uv run scripts/clone_schema.py --verify   # report tables per schema
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import psycopg2
from psycopg2 import sql

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))

from src.config.settings import get_settings  # noqa: E402

settings = get_settings()

SOURCE_DB = "trading_system"
TARGET_DB = settings.trading_db_name  # factor_stat_arb
SCHEMAS = [
    "data_ingestion", "strategy_engine", "execution", "risk_management",
    "analytics", "notification", "logging", "shared",
]

PG_BIN = Path(os.getenv("PG_BIN", r"C:\Program Files\PostgreSQL\18\bin"))
PG_DUMP = PG_BIN / "pg_dump.exe"
PG_RESTORE = PG_BIN / "pg_restore.exe"


def _conn(dbname: str):
    c = psycopg2.connect(
        host=settings.postgres_host, port=settings.postgres_port,
        user=settings.postgres_user, password=settings.postgres_password,
        dbname=dbname,
    )
    c.autocommit = True
    return c


def _pg_env() -> dict:
    env = os.environ.copy()
    env["PGPASSWORD"] = settings.postgres_password
    return env


def _common_conn_args() -> list[str]:
    return [
        "-h", settings.postgres_host,
        "-p", str(settings.postgres_port),
        "-U", settings.postgres_user,
    ]


def recreate_target() -> None:
    c = _conn("postgres")
    try:
        with c.cursor() as cur:
            # Terminate any open connections to the target before dropping.
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()", (TARGET_DB,)
            )
            cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(TARGET_DB)))
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TARGET_DB)))
            print(f"[ok]   recreated empty database {TARGET_DB}")
    finally:
        c.close()


def clone_schema() -> None:
    with tempfile.TemporaryDirectory() as td:
        dump = Path(td) / "schema.dump"
        dump_cmd = [
            str(PG_DUMP), *_common_conn_args(),
            "--schema-only", "--no-owner", "--no-privileges",
            "-Fc", "-d", SOURCE_DB, "-f", str(dump),
        ]
        print(f"[..]   pg_dump --schema-only from {SOURCE_DB}")
        subprocess.run(dump_cmd, env=_pg_env(), check=True)

        restore_cmd = [
            str(PG_RESTORE), *_common_conn_args(),
            "--no-owner", "--no-privileges",
            "-d", TARGET_DB, str(dump),
        ]
        print(f"[..]   pg_restore into {TARGET_DB}")
        # pg_restore may emit non-fatal warnings; check=False, inspect returncode.
        r = subprocess.run(restore_cmd, env=_pg_env())
        if r.returncode != 0:
            print(f"[warn] pg_restore exited {r.returncode} (often non-fatal warnings)")
        else:
            print("[ok]   schema restored")


def verify() -> None:
    c = _conn(TARGET_DB)
    try:
        with c.cursor() as cur:
            cur.execute(
                "SELECT table_schema, count(*) FROM information_schema.tables "
                "WHERE table_schema = ANY(%s) GROUP BY table_schema ORDER BY table_schema",
                (SCHEMAS,),
            )
            rows = cur.fetchall()
            total = sum(n for _, n in rows)
            print(f"\n{TARGET_DB}: {total} tables across {len(rows)} schemas")
            for schema, n in rows:
                print(f"  {schema}: {n} tables")
    finally:
        c.close()


def main() -> int:
    if settings.postgres_password in ("", "your_password_here"):
        print("ERROR: POSTGRES_PASSWORD not set in .env - fill it in first.")
        return 1
    if not PG_DUMP.exists():
        print(f"ERROR: pg_dump not found at {PG_DUMP}. Set PG_BIN env var.")
        return 1
    if "--verify" in sys.argv:
        verify()
        return 0
    recreate_target()
    clone_schema()
    verify()
    return 0


if __name__ == "__main__":
    sys.exit(main())
