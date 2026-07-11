"""Run the Prefect CLI with this repo's isolated configuration.

There is a machine-global Prefect profile (~/.prefect/profiles.toml, active
'local') pointing at a shared Prefect DB on port 4200. To avoid touching it, this
wrapper sets a repo-local PREFECT_HOME plus the isolated API URL / port and the
derived factor_stat_arb_prefect connection URL (from .env via Settings), then
execs the real prefect CLI.

Usage (anything you'd pass to `prefect`):
    uv run scripts/run_prefect.py server start
    uv run scripts/run_prefect.py config view
    uv run scripts/run_prefect.py deployment ls
"""

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config.settings import get_settings  # noqa: E402


def normalize_api_url(url: str) -> str:
    """Ensure the Prefect API URL ends with '/api'.

    Prefect's server API lives under /api; if PREFECT_API_URL lacks it (a common
    .env mistake), `prefect server start` sees a client/server mismatch and blocks
    on an interactive prompt. Normalizing avoids that entirely.
    """
    url = url.rstrip("/")
    if not url.endswith("/api"):
        url += "/api"
    return url


def build_env() -> dict:
    s = get_settings()
    api_url = normalize_api_url(s.prefect_api_url)   # http://localhost:4201/api
    parsed = urlparse(api_url)
    port = str(parsed.port or 4201)
    host = parsed.hostname or "127.0.0.1"

    env = os.environ.copy()
    # Prefect's CLI prints emoji; force UTF-8 so the Windows cp1252 console
    # doesn't crash with UnicodeEncodeError.
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    # Repo-local Prefect home isolates profiles/state from the global install.
    env["PREFECT_HOME"] = str(REPO_ROOT / ".prefect")
    env["PREFECT_API_URL"] = api_url
    env["PREFECT_API_DATABASE_CONNECTION_URL"] = s.prefect_db_connection_url
    # Bind the server to this repo's port (loopback only).
    env["PREFECT_SERVER_API_HOST"] = "127.0.0.1"
    env["PREFECT_SERVER_API_PORT"] = port
    env["PREFECT_UI_API_URL"] = api_url
    # Note: server binds to 127.0.0.1; host var above is informational.
    _ = host
    return env


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: uv run scripts/run_prefect.py <prefect args...>")
        return 2
    env = build_env()
    (REPO_ROOT / ".prefect").mkdir(exist_ok=True)
    return subprocess.run(["prefect", *argv], env=env).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
