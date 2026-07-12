"""Backtest discovered factor-residual baskets and gate-check performance.

Runs FactorBacktestEngine + MetricsCalculator + FactorBacktestReport for one
or all baskets in strategy_engine.basket_registry, printing a pass/fail gate
summary useful for the manual-review step after discover_factor_baskets.py.

Usage:
    uv run scripts/backtest_factor_baskets.py                       # all baskets
    uv run scripts/backtest_factor_baskets.py --active-only
    uv run scripts/backtest_factor_baskets.py --basket-id 5
    uv run scripts/backtest_factor_baskets.py --days 180 --dry-run  # no DB writes
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.services.strategy_engine.backtesting.metrics import (  # noqa: E402
    MetricsCalculator,
)
from src.services.strategy_engine.factor_stat_arb.backtest_engine import (  # noqa: E402
    FactorBacktestEngine,
)
from src.services.strategy_engine.factor_stat_arb.report import (  # noqa: E402
    FactorBacktestReport,
)
from src.shared.database.base import db_readonly_session  # noqa: E402
from src.shared.database.models.basket_models import BasketRegistry  # noqa: E402


def load_baskets(basket_id: Optional[int], active_only: bool) -> List[BasketRegistry]:
    with db_readonly_session() as session:
        query = session.query(BasketRegistry)
        if basket_id is not None:
            query = query.filter(BasketRegistry.id == basket_id)
        elif active_only:
            query = query.filter(BasketRegistry.is_active.is_(True))
        baskets = query.all()
        for b in baskets:
            session.expunge(b)
        return baskets


def main() -> int:
    p = argparse.ArgumentParser(description="Backtest factor-residual baskets")
    p.add_argument("--basket-id", type=int, default=None, help="backtest one basket")
    p.add_argument(
        "--active-only", action="store_true", help="only is_active=True baskets"
    )
    p.add_argument("--days", type=int, default=365, help="lookback window in days")
    p.add_argument(
        "--initial-capital", type=float, default=100_000.0, help="starting equity"
    )
    p.add_argument("--dry-run", action="store_true", help="no DB writes")
    args = p.parse_args()

    baskets = load_baskets(args.basket_id, args.active_only)
    if not baskets:
        print("No baskets found matching the given filters.")
        return 0

    end_date = date.today()
    start_date = end_date - timedelta(days=args.days)

    calc = MetricsCalculator()
    report = FactorBacktestReport()

    summary_rows = []
    for basket in baskets:
        engine = FactorBacktestEngine(
            basket,
            start_date=start_date,
            end_date=end_date,
            initial_capital=args.initial_capital,
        )
        result = engine.run()
        metrics = calc.compute(result)

        run_id = None
        if not args.dry_run:
            run_id = report.save(
                result, metrics, notes="scripts/backtest_factor_baskets.py"
            )

        report.print_summary(result, metrics, run_id=run_id)
        summary_rows.append(
            (
                basket.name,
                metrics.sharpe_ratio,
                metrics.win_rate_pct,
                metrics.max_drawdown_pct,
                metrics.passed_gate,
            )
        )

    print("\nSUMMARY")
    print(f"{'basket':<30}{'sharpe':>10}{'win_rate':>12}{'drawdown':>12}{'gate':>8}")
    for name, sharpe, win_rate, dd, passed in summary_rows:
        print(
            f"{name:<30}{sharpe:>10.3f}{win_rate:>11.1f}%{dd:>11.2f}%{('PASS' if passed else 'FAIL'):>8}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
