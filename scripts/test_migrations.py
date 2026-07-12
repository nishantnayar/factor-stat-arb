"""Test that scripts/*.sql migrations replay cleanly, in order, on an empty DB.

Creates a throwaway database, ensures the 8 service schemas, then runs each
numbered migration in order, stopping at the first failure and reporting the
offending file + error. Always drops the throwaway DB afterwards (unless --keep).

This is the red/green signal for the migration-fix TODO: run it, fix the file it
names, run it again, until it reports all migrations OK.

Usage:
    uv run scripts/test_migrations.py           # replay into scratch DB, report
    uv run scripts/test_migrations.py --keep     # leave the scratch DB for inspection
"""

import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))

from src.config.settings import get_settings  # noqa: E402

settings = get_settings()

SCRATCH_DB = "factor_stat_arb_migtest"
SCHEMAS = [
    "data_ingestion",
    "strategy_engine",
    "execution",
    "risk_management",
    "analytics",
    "notification",
    "logging",
    "shared",
]
# 01 creates databases (psql-specific); 26/27 are the dropped harmonic module.
SKIP = {"01", "26", "27"}


def _conn(dbname: str):
    c = psycopg2.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname=dbname,
    )
    c.autocommit = True
    return c


def _drop_scratch(cur) -> None:
    cur.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = %s AND pid <> pg_backend_pid()",
        (SCRATCH_DB,),
    )
    cur.execute(
        sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(SCRATCH_DB))
    )


def migration_files() -> list[Path]:
    files = sorted(SCRIPTS_DIR.glob("[0-9][0-9]*.sql"))
    return [f for f in files if f.name[:2] not in SKIP]


def run() -> int:
    keep = "--keep" in sys.argv
    # (Re)create a clean scratch DB.
    admin = _conn("postgres")
    try:
        with admin.cursor() as cur:
            _drop_scratch(cur)
            cur.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(SCRATCH_DB))
            )
    finally:
        admin.close()
    print(f"[ok]   created scratch DB {SCRATCH_DB}")

    failed = None
    c = _conn(SCRATCH_DB)
    try:
        with c.cursor() as cur:
            for s in SCHEMAS:
                cur.execute(
                    sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(s))
                )
            print(f"[ok]   created {len(SCHEMAS)} schemas")
            for f in migration_files():
                cleaned = "\n".join(
                    ln
                    for ln in f.read_text(encoding="utf-8").splitlines()
                    if not ln.strip().startswith("\\")
                )
                try:
                    cur.execute(cleaned)
                    print(f"[ok]   {f.name}")
                except Exception as e:  # noqa: BLE001
                    print(f"[FAIL] {f.name}: {type(e).__name__}: {e}")
                    failed = f.name
                    break
    finally:
        c.close()
        if keep:
            print(f"[keep] scratch DB {SCRATCH_DB} left in place")
        else:
            admin = _conn("postgres")
            try:
                with admin.cursor() as cur:
                    _drop_scratch(cur)
                print(f"[ok]   dropped scratch DB {SCRATCH_DB}")
            finally:
                admin.close()

    if failed:
        print(f"\nRESULT: FAILED at {failed} - fix it and re-run.")
        return 1
    print("\nRESULT: all migrations replayed cleanly. PASS")
    return 0


if __name__ == "__main__":
    sys.exit(run())
