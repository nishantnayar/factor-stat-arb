"""Verify the uv-managed environment is installed correctly.

Run with `uv run scripts/check_env.py`.
"""

import sys
from pathlib import Path

REQUIRED_PYTHON = (3, 11)

# distribution name -> import name, where they differ
PACKAGES = {
    "numpy": "numpy",
    "scipy": "scipy",
    "pandas": "pandas",
    "scikit-learn": "sklearn",
    "statsmodels": "statsmodels",
    "lightgbm": "lightgbm",
    "shap": "shap",
    "sqlalchemy": "sqlalchemy",
    "psycopg2-binary": "psycopg2",
    "alpaca-py": "alpaca",
    "prefect": "prefect",
    "streamlit": "streamlit",
    "python-dotenv": "dotenv",
    "pydantic": "pydantic",
    "pydantic-settings": "pydantic_settings",
    "yfinance": "yfinance",
}


def check_python_version() -> bool:
    ok = sys.version_info[:2] == REQUIRED_PYTHON
    status = "OK" if ok else "FAIL"
    print(
        f"[{status}] Python {sys.version.split()[0]} (expected {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}.x)"
    )
    return ok


def check_venv() -> bool:
    project_root = Path(__file__).resolve().parent.parent
    expected_venv = project_root / ".venv"
    in_expected_venv = Path(sys.prefix).resolve() == expected_venv.resolve()
    status = "OK" if in_expected_venv else "FAIL"
    print(f"[{status}] Interpreter: {sys.executable}")
    if not in_expected_venv:
        print(
            f"       Expected to run inside {expected_venv} - use `uv run` or activate .venv"
        )
    return in_expected_venv


def check_packages() -> bool:
    all_ok = True
    for dist_name, import_name in PACKAGES.items():
        try:
            module = __import__(import_name)
            version = getattr(module, "__version__", "unknown")
            print(f"[OK] {dist_name:<20} {version}")
        except ImportError as exc:
            print(f"[FAIL] {dist_name:<20} import error: {exc}")
            all_ok = False
    return all_ok


def main() -> int:
    print("Checking factor-stat-arb environment\n")
    results = [check_python_version(), check_venv(), check_packages()]
    print()
    if all(results):
        print("Environment OK.")
        return 0
    print("Environment check FAILED - see above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
