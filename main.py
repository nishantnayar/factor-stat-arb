"""factor-stat-arb entry point.

A single command to (1) validate the environment/data/services this project needs
and (2) start the long-running services (Prefect server, Streamlit UI, and the
Prefect worker that runs scheduled data-ingestion flows).

    uv run main.py check              # run all preflight checks, exit non-zero on failure
    uv run main.py up                 # checks, then start the running system
    uv run main.py up prefect         # start only the named service(s)
    uv run main.py up docs            # opt-in: serve the mkdocs site (not in default up)
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


# Services bare `up` starts (the running system). `docs` is opt-in - a docs
# authoring server, only started when named explicitly (`up docs`).
DEFAULT_SERVICES = ("prefect", "streamlit", "worker")
ALL_SERVICES = (*DEFAULT_SERVICES, "docs")
DOCS_PORT = "8000"


def _start_prefect(env, s) -> "subprocess.Popen | None":  # noqa: F821
    import subprocess

    from scripts.run_prefect import normalize_api_url
    api = normalize_api_url(s.prefect_api_url)
    if _prefect_healthy(api):
        print(f"[skip] Prefect already healthy at {api}")
        return None
    print(f"[start] Prefect server -> {api}")
    # Write a repo-local Prefect profile with PREFECT_API_URL set, so
    # `prefect server start`'s prestart_check doesn't prompt (it prompts when the
    # active profile lacks PREFECT_API_URL). stdin=DEVNULL is a further guard.
    from scripts.run_prefect import ensure_profile
    ensure_profile()
    p = subprocess.Popen(["prefect", "server", "start"], env=env,
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
        "docs": f"http://localhost:{DOCS_PORT}",
    }


def _start_worker(env, s) -> "subprocess.Popen | None":  # noqa: F821
    import subprocess

    pool = s.prefect_work_pool_data_ingestion
    # `--type process` auto-creates the pool if missing (non-interactive). The
    # deployment itself is registered once via `uv run scripts/deploy_flows.py`
    # (a one-time activity), not here - `up` only runs services.
    print(f"[start] Prefect worker -> pool '{pool}'")
    return subprocess.Popen(
        ["prefect", "worker", "start", "--pool", pool, "--type", "process"],
        env=env, stdin=subprocess.DEVNULL)


def _start_streamlit(env, s) -> "subprocess.Popen | None":  # noqa: F821
    import subprocess
    print(f"[start] Streamlit dashboard -> http://localhost:{STREAMLIT_PORT}")
    return subprocess.Popen(
        ["streamlit", "run", "streamlit_ui/streamlit_app.py",
         "--server.port", STREAMLIT_PORT, "--server.address", "localhost"],
        env=env)


def _start_docs(env, s) -> "subprocess.Popen | None":  # noqa: F821
    import subprocess
    print(f"[start] mkdocs (docs authoring) -> http://localhost:{DOCS_PORT}")
    return subprocess.Popen(
        ["mkdocs", "serve", "-a", f"localhost:{DOCS_PORT}"], env=env)


def start_services(services: list[str]) -> int:
    import subprocess

    from scripts.run_prefect import build_env
    from src.config.settings import get_settings

    names = services or list(DEFAULT_SERVICES)  # empty -> default running system
    unknown = [n for n in names if n not in ALL_SERVICES]
    if unknown:
        print(f"Unknown service(s): {', '.join(unknown)}. Known: {', '.join(ALL_SERVICES)}")
        return 2

    s = get_settings()
    env = build_env()
    starters = {"prefect": _start_prefect, "streamlit": _start_streamlit,
                "worker": _start_worker, "docs": _start_docs}
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
    up = sub.add_parser("up", help="run checks, then start services")
    up.add_argument("services", nargs="*", metavar="SERVICE",
                    help=f"services to start (default: {', '.join(DEFAULT_SERVICES)}; "
                         f"also available: {', '.join(set(ALL_SERVICES) - set(DEFAULT_SERVICES))})")
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
