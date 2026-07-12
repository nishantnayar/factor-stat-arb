"""Seed factor_stat_arb with market/reference data from trading_system.

Copies DATA ONLY for the four tables the factor strategy needs (README step 3):
symbols, market_data, technical_indicators, technical_indicators_latest. It does
NOT copy pairs/baskets trade history - this repo starts its own.

Schema must already exist (see clone_schema.py). Uses pg_dump -Fc --data-only and
pg_restore --disable-triggers (superuser) so FK ordering isn't a problem.

Usage:
    uv run scripts/seed_data.py            # seed the 4 tables (must be empty)
    uv run scripts/seed_data.py --force    # TRUNCATE then reseed if already populated
    uv run scripts/seed_data.py --verify   # compare row counts source vs target
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import psycopg2

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))

from src.config.settings import get_settings  # noqa: E402

settings = get_settings()

SOURCE_DB = "trading_system"
TARGET_DB = settings.trading_db_name  # factor_stat_arb

# Order matters for TRUNCATE (children before parents); restore uses
# --disable-triggers so load order is not FK-constrained.
TABLES = [
    "data_ingestion.symbols",
    "data_ingestion.market_data",
    "analytics.technical_indicators",
    "analytics.technical_indicators_latest",
]

PG_BIN = Path(os.getenv("PG_BIN", r"C:\Program Files\PostgreSQL\18\bin"))
PG_DUMP = PG_BIN / "pg_dump.exe"
PG_RESTORE = PG_BIN / "pg_restore.exe"


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


def _pg_env() -> dict:
    env = os.environ.copy()
    env["PGPASSWORD"] = settings.postgres_password
    return env


def _conn_args() -> list[str]:
    return [
        "-h",
        settings.postgres_host,
        "-p",
        str(settings.postgres_port),
        "-U",
        settings.postgres_user,
    ]


def _counts(dbname: str) -> dict[str, int]:
    c = _conn(dbname)
    out = {}
    try:
        with c.cursor() as cur:
            for t in TABLES:
                cur.execute(f"select count(*) from {t}")
                out[t] = cur.fetchone()[0]
    finally:
        c.close()
    return out


def verify() -> None:
    src, tgt = _counts(SOURCE_DB), _counts(TARGET_DB)
    print(f"{'table':<45}{'source':>12}{'target':>12}  match")
    for t in TABLES:
        ok = "OK" if src[t] == tgt[t] else "DIFF"
        print(f"{t:<45}{src[t]:>12,}{tgt[t]:>12,}  {ok}")


def _truncate_target() -> None:
    c = _conn(TARGET_DB)
    try:
        with c.cursor() as cur:
            # Reverse order (children first); CASCADE for safety.
            cur.execute("TRUNCATE " + ", ".join(reversed(TABLES)) + " CASCADE")
        print("[ok]   truncated target tables")
    finally:
        c.close()


def seed() -> None:
    with tempfile.TemporaryDirectory() as td:
        dump = Path(td) / "data.dump"
        table_flags: list[str] = []
        for t in TABLES:
            table_flags += ["-t", t]
        dump_cmd = [
            str(PG_DUMP),
            *_conn_args(),
            "--data-only",
            "-Fc",
            *table_flags,
            "-d",
            SOURCE_DB,
            "-f",
            str(dump),
        ]
        print(
            f"[..]   pg_dump --data-only ({len(TABLES)} tables) from {SOURCE_DB} - "
            f"this may take a minute for market_data"
        )
        subprocess.run(dump_cmd, env=_pg_env(), check=True)
        print(f"[ok]   dump written ({dump.stat().st_size / 1e6:.1f} MB compressed)")

        restore_cmd = [
            str(PG_RESTORE),
            *_conn_args(),
            "--data-only",
            "--disable-triggers",
            "-d",
            TARGET_DB,
            str(dump),
        ]
        print(f"[..]   pg_restore into {TARGET_DB}")
        r = subprocess.run(restore_cmd, env=_pg_env())
        if r.returncode != 0:
            print(f"[warn] pg_restore exited {r.returncode} (inspect output above)")
        else:
            print("[ok]   data restored")


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

    tgt = _counts(TARGET_DB)
    populated = {t: n for t, n in tgt.items() if n > 0}
    if populated and "--force" not in sys.argv:
        print("Target already has data:")
        for t, n in populated.items():
            print(f"  {t}: {n:,} rows")
        print(
            "Refusing to append (would duplicate). Re-run with --force to TRUNCATE + reseed."
        )
        return 1
    if populated:
        _truncate_target()

    seed()
    print("\n--- verification ---")
    verify()
    return 0


if __name__ == "__main__":
    sys.exit(main())
