"""factor-stat-arb entry point.

A single command to (1) validate the environment/data/services this project needs
and (2) start the long-running services (Prefect server, Streamlit UI, and the
Prefect worker that runs scheduled data-ingestion flows).

    uv run main.py check              # run all preflight checks, exit non-zero on failure
    uv run main.py up                 # checks, then start ALL services
    uv run main.py up prefect         # start only the named service(s)
    uv run main.py up worker          # ensure the work pool + deployment, run the worker
    uv run main.py up --skip-checks

Services use this repo's isolated Prefect config (port 4201,
factor_stat_arb_prefect, work pool fsa-data-ingestion) and shut down cleanly on
Ctrl+C.
"""

from __future__ import annotations

import argparse
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


def _quiet_logs() -> None:
    """Suppress DEBUG/INFO chatter (loguru + stdlib) so preflight output is clean."""
    import logging
    logging.getLogger().setLevel(logging.WARNING)
    try:
        from loguru import logger as _lg
        _lg.remove()
        _lg.add(sys.stderr, level="WARNING")
    except Exception:  # noqa: BLE001
        pass


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
    import asyncio

    from src.config.settings import get_settings
    s = get_settings()
    if "paper" not in s.alpaca_base_url:
        return Check("alpaca (paper)", False, f"base_url not paper: {s.alpaca_base_url}")
    if not (s.alpaca_api_key and s.alpaca_secret_key):
        return Check("alpaca (paper)", True,
                     "paper endpoint, KEYS MISSING (set to trade)", critical=False)

    from src.services.alpaca.client import AlpacaClient

    async def _acct():
        c = AlpacaClient(api_key=s.alpaca_api_key, secret_key=s.alpaca_secret_key,
                         base_url=s.alpaca_base_url, is_paper=True)
        return await c.get_account()

    try:
        a = asyncio.run(_acct())
        cash = float(a.get("cash", 0) or 0)
        status = str(a.get("status", "")).replace("AccountStatus.", "")
        label = f"{s.alpaca_account_label} - " if s.alpaca_account_label else ""
        return Check("alpaca (paper)", True,
                     f"{label}acct {a['account_number']} {status} cash=${cash:,.0f}")
    except Exception as e:  # noqa: BLE001
        return Check("alpaca (paper)", False,
                     f"auth failed: {type(e).__name__}: {e}", critical=False)


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
SERVICES = ("prefect", "streamlit", "worker")


def _start_prefect(env, s) -> "subprocess.Popen | None":  # noqa: F821
    import subprocess

    from scripts.run_prefect import normalize_api_url
    api = normalize_api_url(s.prefect_api_url)
    if _prefect_healthy(api):
        print(f"[skip] Prefect already healthy at {api}")
        return None
    print(f"[start] Prefect server -> {api}")
    # Start the server WITHOUT PREFECT_API_URL in its env. That var is for
    # clients; when it's set, `prefect server start` runs a client/server address
    # check and, in an interactive terminal, blocks on a "profile mismatch"
    # prompt. The server binds via PREFECT_SERVER_API_HOST/PORT (still set).
    server_env = dict(env)
    server_env.pop("PREFECT_API_URL", None)
    # No stdin either, as a belt-and-suspenders against any other prompt.
    p = subprocess.Popen(["prefect", "server", "start"], env=server_env,
                         stdin=subprocess.DEVNULL)
    for _ in range(40):
        if _prefect_healthy(api):
            print("[ok] Prefect server healthy")
            break
        time.sleep(3)
    else:
        print("[warn] Prefect server did not report healthy in time")
    return p


STREAMLIT_PORT = "8502"  # isolated from trading-system's default 8501


def _service_urls(s) -> dict:
    prefect_ui = s.prefect_api_url.rstrip("/")
    if prefect_ui.endswith("/api"):
        prefect_ui = prefect_ui[:-4]
    return {
        "prefect": prefect_ui,
        "streamlit": f"http://localhost:{STREAMLIT_PORT}",
        "worker": f"pool '{s.prefect_work_pool_data_ingestion}'",
    }


def _start_worker(env, s) -> "subprocess.Popen | None":  # noqa: F821
    import asyncio
    import subprocess

    pool = s.prefect_work_pool_data_ingestion
    # Ensure the work pool + market-data deployment exist before the worker starts
    # (idempotent) so `up` is fully self-contained - no separate deploy step.
    print(f"[..]    ensuring work pool '{pool}' + deployment")
    try:
        from scripts.deploy_flows import ensure_deployment
        asyncio.run(ensure_deployment())
    except Exception as e:  # noqa: BLE001
        print(f"[warn] could not ensure deployment ({type(e).__name__}: {e}); "
              f"worker will still start")
    print(f"[start] Prefect worker -> pool '{pool}'")
    return subprocess.Popen(
        ["prefect", "worker", "start", "--pool", pool], env=env)


def _start_streamlit(env, s) -> "subprocess.Popen | None":  # noqa: F821
    import subprocess
    print(f"[start] Streamlit dashboard -> http://localhost:{STREAMLIT_PORT}")
    return subprocess.Popen(
        ["streamlit", "run", "streamlit_ui/streamlit_app.py",
         "--server.port", STREAMLIT_PORT, "--server.address", "localhost"],
        env=env)


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
    starters = {"prefect": _start_prefect, "streamlit": _start_streamlit,
                "worker": _start_worker}
    procs: list[tuple[str, subprocess.Popen]] = []
    for name in names:
        p = starters[name](env, s)
        if p is not None:
            procs.append((name, p))

    urls = _service_urls(s)
    print("\nRunning services:")
    for name in names:
        print(f"  {name:<10} {urls[name]}")

    if not procs:
        print("\nAll requested services were already running.")
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
    _quiet_logs()

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
