"""
Run discover_baskets.py for every active sector in the DB.

Usage:
    python scripts/run_discover_baskets_all_sectors.py
    python scripts/run_discover_baskets_all_sectors.py --top 5
    python scripts/run_discover_baskets_all_sectors.py --top 3 --max-pvalue 0.05
    python scripts/run_discover_baskets_all_sectors.py --dry-run   # print sectors only

Any extra flags are forwarded verbatim to discover_baskets.py.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Fetch sectors from DB
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))


def _get_sectors() -> list:
    from sqlalchemy import text

    from src.shared.database.base import db_readonly_session

    with db_readonly_session() as session:
        rows = session.execute(
            text(
                "SELECT DISTINCT sector FROM data_ingestion.symbols "
                "WHERE sector IS NOT NULL ORDER BY sector"
            )
        ).fetchall()
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--top", type=int, default=3, help="--top N passed to discover_baskets"
    )
    parser.add_argument(
        "--max-basket-size", type=int, default=3, help="max basket size (3 recommended)"
    )
    parser.add_argument(
        "--max-symbols",
        type=int,
        default=25,
        help="symbols kept after correlation pre-filter",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print sectors and commands without running them",
    )
    # Capture any remaining args to forward (e.g. --max-pvalue, --min-basket-size)
    args, extra = parser.parse_known_args()

    sectors = _get_sectors()
    print(f"\nFound {len(sectors)} sectors: {', '.join(sectors)}\n")

    discover_script = str(_PROJECT_ROOT / "scripts" / "discover_baskets.py")
    python = sys.executable

    results = []
    for i, sector in enumerate(sectors, 1):
        cmd = [
            python,
            discover_script,
            "--sector",
            sector,
            "--top",
            str(args.top),
            "--max-basket-size",
            str(args.max_basket_size),
            "--max-symbols",
            str(args.max_symbols),
        ] + extra
        print(f"[{i}/{len(sectors)}] Sector: {sector}")
        print(f"  CMD: {' '.join(cmd)}")

        if args.dry_run:
            results.append({"sector": sector, "status": "DRY_RUN"})
            continue

        t0 = time.time()
        result = subprocess.run(cmd, cwd=str(_PROJECT_ROOT))
        elapsed = round(time.time() - t0, 1)

        status = "OK" if result.returncode == 0 else f"FAILED (rc={result.returncode})"
        results.append({"sector": sector, "status": status, "elapsed_s": elapsed})
        print(f"  => {status} in {elapsed}s\n")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for r in results:
        elapsed_str = f"  ({r.get('elapsed_s')}s)" if "elapsed_s" in r else ""
        print(f"  {r['sector']:<30} {r['status']}{elapsed_str}")

    failed = [r for r in results if "FAILED" in r.get("status", "")]
    if failed:
        print(f"\n{len(failed)} sector(s) failed.")
        sys.exit(1)
    else:
        print(f"\nAll {len(results)} sectors completed successfully.")


if __name__ == "__main__":
    main()
