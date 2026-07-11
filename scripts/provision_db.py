"""Provision the factor_stat_arb databases and run schema migrations.

Replaces scripts/01_create_databases.sql (which is psql-specific and hardcodes
trading_system). Reads DB connection from .env via src.config.settings.

Usage:
    uv run scripts/provision_db.py            # create DBs + schemas + migrations
    uv run scripts/provision_db.py --verify   # just report what exists
"""

import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))

from src.config.settings import get_settings  # noqa: E402

settings = get_settings()

MAIN_DB = settings.trading_db_name          # factor_stat_arb
PREFECT_DB = "factor_stat_arb_prefect"

SCHEMAS = [
    "data_ingestion", "strategy_engine", "execution", "risk_management",
    "analytics", "notification", "logging", "shared",
]

# Migrations to apply, in order. Skip 01 (replaced here) and 26/27 (harmonic,
# a module dropped from this repo).
SKIP = {"01", "26", "27"}


def _conn(dbname: str):
    c = psycopg2.connect(
        host=settings.postgres_host, port=settings.postgres_port,
        user=settings.postgres_user, password=settings.postgres_password,
        dbname=dbname,
    )
    c.autocommit = True
    return c


def _db_exists(cur, name: str) -> bool:
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
    return cur.fetchone() is not None


def create_databases() -> None:
    c = _conn("postgres")
    try:
        with c.cursor() as cur:
            for name in (MAIN_DB, PREFECT_DB):
                if _db_exists(cur, name):
                    print(f"[skip] database {name} already exists")
                else:
                    cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                    print(f"[ok]   created database {name}")
    finally:
        c.close()


def create_schemas() -> None:
    c = _conn(MAIN_DB)
    try:
        with c.cursor() as cur:
            for s in SCHEMAS:
                cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(s)))
            print(f"[ok]   ensured {len(SCHEMAS)} schemas in {MAIN_DB}")
    finally:
        c.close()


def migration_files() -> list[Path]:
    files = sorted(SCRIPTS_DIR.glob("[0-9][0-9]*.sql"))
    return [f for f in files if f.name[:2] not in SKIP]


def run_migrations() -> None:
    c = _conn(MAIN_DB)
    try:
        with c.cursor() as cur:
            for f in migration_files():
                sql_text = f.read_text(encoding="utf-8")
                # Drop psql meta-commands (\c, \echo, etc.) psycopg2 can't run.
                cleaned = "\n".join(
                    ln for ln in sql_text.splitlines() if not ln.strip().startswith("\\")
                )
                try:
                    cur.execute(cleaned)
                    print(f"[ok]   {f.name}")
                except Exception as e:  # noqa: BLE001
                    print(f"[FAIL] {f.name}: {type(e).__name__}: {e}")
                    raise
    finally:
        c.close()


def verify() -> None:
    c = _conn("postgres")
    try:
        with c.cursor() as cur:
            for name in (MAIN_DB, PREFECT_DB):
                print(f"database {name}: {'EXISTS' if _db_exists(cur, name) else 'MISSING'}")
    finally:
        c.close()
    c = _conn(MAIN_DB)
    try:
        with c.cursor() as cur:
            cur.execute("SELECT schema_name FROM information_schema.schemata "
                        "WHERE schema_name = ANY(%s) ORDER BY schema_name", (SCHEMAS,))
            found = [r[0] for r in cur.fetchall()]
            print(f"schemas present ({len(found)}/{len(SCHEMAS)}): {', '.join(found)}")
            cur.execute("SELECT table_schema, count(*) FROM information_schema.tables "
                        "WHERE table_schema = ANY(%s) GROUP BY table_schema ORDER BY table_schema",
                        (SCHEMAS,))
            for schema, n in cur.fetchall():
                print(f"  {schema}: {n} tables")
    finally:
        c.close()


def _already_populated() -> bool:
    """True if the target DB already has application tables (built by either
    clone_schema.py or a prior provision run). Migrations aren't idempotent, so
    replaying them onto a populated DB just collides (e.g. duplicate enum types)."""
    c = _conn(MAIN_DB)
    try:
        with c.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM information_schema.tables WHERE table_schema = ANY(%s)",
                (SCHEMAS,),
            )
            return cur.fetchone()[0] > 0
    except psycopg2.OperationalError:
        return False  # DB doesn't exist yet
    finally:
        c.close()


def main() -> int:
    if settings.postgres_password in ("", "your_password_here"):
        print("ERROR: POSTGRES_PASSWORD not set in .env - fill it in first.")
        return 1
    if "--verify" in sys.argv:
        verify()
        return 0
    create_databases()
    create_schemas()
    force = "--force" in sys.argv
    if _already_populated() and not force:
        print(f"[skip] {MAIN_DB} already has tables - migrations not replayed "
              f"(they aren't idempotent). Use scripts/test_migrations.py to test a "
              f"clean replay on a throwaway DB, or pass --force to replay anyway.")
    else:
        run_migrations()
    print("\n--- verification ---")
    verify()
    return 0


if __name__ == "__main__":
    sys.exit(main())
