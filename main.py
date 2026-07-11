"""factor-stat-arb entry point.

A single command to (1) validate the environment/data/services this project needs
and (2) start the long-running services (Prefect server, optional Streamlit UI).

    uv run main.py check          # run all preflight checks, exit non-zero on failure
    uv run main.py up             # checks, then start Prefect server
    uv run main.py up --with-ui   # also start the Streamlit dashboard
    uv run main.py up --skip-checks

Services are started with this repo's isolated Prefect config (port 4201,
factor_stat_arb_prefect) and shut down cleanly on Ctrl+C.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

REQUIRED_PY = (3, 11)


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    critical: bool = True


# -- Preflight checks ----------------------------------------------------------

def check_python() -> Check:
    ok = sys.version_info[:2] == REQUIRED_PY
    return Check("python version", ok,
                 f"{sys.version.split()[0]} (need {REQUIRED_PY[0]}.{REQUIRED_PY[1]}.x)")


def check_venv() -> Check:
    expected = (PROJECT_ROOT / ".venv").resolve()
    ok = Path(sys.prefix).resolve() == expected
    return Check("virtualenv", ok, sys.prefix if ok else f"{sys.prefix} (expected {expected})")


def check_imports() -> Check:
    pkgs = ["numpy", "pandas", "sklearn", "statsmodels", "lightgbm", "shap",
            "sqlalchemy", "psycopg2", "alpaca", "prefect", "streamlit"]
    missing = []
    for p in pkgs:
        try:
            __import__(p)
        except ImportError:
            missing.append(p)
    return Check("core dependencies", not missing,
                 "all import OK" if not missing else f"missing: {', '.join(missing)}")


def check_config() -> Check:
    from src.config.settings import get_settings
    s = get_settings()
    ok = s.postgres_password not in ("", "your_password_here")
    return Check("config (.env)", ok,
                 "POSTGRES_PASSWORD set" if ok else "POSTGRES_PASSWORD missing/placeholder")


def check_database() -> Check:
    from sqlalchemy import text
    from src.config.database import get_engine
    schemas = ["data_ingestion", "strategy_engine", "analytics", "risk_management"]
    try:
        eng = get_engine("trading")
        with eng.connect() as conn:
            db = conn.execute(text("select current_database()")).scalar()
            found = conn.execute(text(
                "select count(*) from information_schema.schemata where schema_name = any(:s)"
            ), {"s": schemas}).scalar()
        ok = db == "factor_stat_arb" and found == len(schemas)
        return Check("database", ok, f"connected to {db}, {found}/{len(schemas)} core schemas")
    except Exception as e:  # noqa: BLE001
        return Check("database", False, f"{type(e).__name__}: {e}")


def check_seed_data() -> Check:
    from sqlalchemy import text
    from src.config.database import get_engine
    try:
        eng = get_engine("trading")
        with eng.connect() as conn:
            md = conn.execute(text("select count(*) from data_ingestion.market_data")).scalar()
            sym = conn.execute(text("select count(*) from data_ingestion.symbols")).scalar()
        ok = md > 0 and sym > 0
        return Check("seed data", ok, f"market_data={md:,} rows, symbols={sym:,}")
    except Exception as e:  # noqa: BLE001
        return Check("seed data", False, f"{type(e).__name__}: {e}")


def check_price_series() -> Check:
    from sqlalchemy import text
    from src.config.database import get_engine
    from src.shared.market_data import get_price_series
    try:
        eng = get_engine("trading")
        with eng.connect() as conn:
            sym = conn.execute(text(
                "select symbol from data_ingestion.market_data "
                "where data_source='yahoo_adjusted' limit 1"
            )).scalar()
        s = get_price_series(sym, limit=10) if sym else []
        ok = len(s) > 0
        return Check("get_price_series", ok,
                     f"{sym}: {len(s)} bars" if ok else f"no data for {sym}")
    except Exception as e:  # noqa: BLE001
        return Check("get_price_series", False, f"{type(e).__name__}: {e}")


def check_prefect_config() -> Check:
    from src.config.settings import get_settings
    s = get_settings()
    ok = ":4201" in s.prefect_api_url and s.prefect_db_connection_url.endswith(
        "/factor_stat_arb_prefect")
    return Check("prefect config", ok,
                 f"{s.prefect_api_url} -> factor_stat_arb_prefect (isolated)")


def check_alpaca() -> Check:
    from src.config.settings import get_settings
    s = get_settings()
    is_paper = "paper" in s.alpaca_base_url
    have_keys = bool(s.alpaca_api_key and s.alpaca_secret_key)
    if not is_paper:
        return Check("alpaca (paper)", False, f"base_url not paper: {s.alpaca_base_url}")
    detail = "paper endpoint, keys set" if have_keys else "paper endpoint, KEYS MISSING (set to trade)"
    return Check("alpaca (paper)", True, detail, critical=False)


PREFLIGHT = [
    check_python, check_venv, check_imports, check_config, check_database,
    check_seed_data, check_price_series, check_prefect_config, check_alpaca,
]


def run_checks() -> bool:
    print("factor-stat-arb preflight\n" + "-" * 60)
    results = []
    for fn in PREFLIGHT:
        try:
            r = fn()
        except Exception as e:  # noqa: BLE001
            r = Check(fn.__name__, False, f"{type(e).__name__}: {e}")
        results.append(r)
        mark = "OK  " if r.ok else ("WARN" if not r.critical else "FAIL")
        print(f"[{mark}] {r.name:<20} {r.detail}")
    print("-" * 60)
    critical_ok = all(r.ok for r in results if r.critical)
    warns = [r for r in results if not r.ok and not r.critical]
    if critical_ok:
        msg = "PASS" + (f" ({len(warns)} warning(s))" if warns else "")
        print(f"Preflight: {msg}")
    else:
        print("Preflight: FAILED - fix the [FAIL] items above.")
    return critical_ok


# -- Services ------------------------------------------------------------------

def _prefect_healthy(api_url: str) -> bool:
    try:
        urllib.request.urlopen(api_url.rstrip("/") + "/health", timeout=2)
        return True
    except Exception:  # noqa: BLE001
        return False


# Known services and how to start them. `up` with no names starts all of these.
SERVICES = ("prefect", "streamlit")


def _start_prefect(env, s) -> "subprocess.Popen | None":  # noqa: F821
    import subprocess
    if _prefect_healthy(s.prefect_api_url):
        print(f"[skip] Prefect already healthy at {s.prefect_api_url}")
        return None
    print(f"[start] Prefect server -> {s.prefect_api_url}")
    p = subprocess.Popen(["prefect", "server", "start"], env=env)
    for _ in range(40):
        if _prefect_healthy(s.prefect_api_url):
            print("[ok] Prefect server healthy")
            break
        time.sleep(3)
    else:
        print("[warn] Prefect server did not report healthy in time")
    return p


def _start_streamlit(env, s) -> "subprocess.Popen | None":  # noqa: F821
    import subprocess
    print("[start] Streamlit dashboard -> http://localhost:8501")
    return subprocess.Popen(
        ["streamlit", "run", "streamlit_ui/streamlit_app.py"], env=env)


def start_services(services: list[str]) -> int:
    import subprocess

    from scripts.run_prefect import build_env
    from src.config.settings import get_settings

    names = services or list(SERVICES)  # empty -> all
    unknown = [n for n in names if n not in SERVICES]
    if unknown:
        print(f"Unknown service(s): {', '.join(unknown)}. Known: {', '.join(SERVICES)}")
        return 2

    s = get_settings()
    env = build_env()
    starters = {"prefect": _start_prefect, "streamlit": _start_streamlit}
    procs: list[tuple[str, subprocess.Popen]] = []
    for name in names:
        p = starters[name](env, s)
        if p is not None:
            procs.append((name, p))

    if not procs:
        print("All requested services already running. Nothing to start.")
        return 0

    print("\nServices running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down services...")
        for name, p in procs:
            p.terminate()
        for name, p in procs:
            try:
                p.wait(timeout=15)
            except subprocess.TimeoutExpired:
                p.kill()
            print(f"[stopped] {name}")
    return 0


# -- CLI -----------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="factor-stat-arb entry point")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("check", help="run preflight validation checks only")
    up = sub.add_parser("up", help="run checks, then start services (all by default)")
    up.add_argument("services", nargs="*", metavar="SERVICE",
                    help=f"which services to start (default: all - {', '.join(SERVICES)})")
    up.add_argument("--skip-checks", action="store_true", help="skip preflight checks")
    args = parser.parse_args()

    command = args.command or "check"

    if command == "check":
        return 0 if run_checks() else 1

    if command == "up":
        if not args.skip_checks:
            if not run_checks():
                print("\nAborting service start (preflight failed). "
                      "Use --skip-checks to override.")
                return 1
            print()
        return start_services(args.services)

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
