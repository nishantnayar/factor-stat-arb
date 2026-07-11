"""
Intraday Pairs Trading Flow

Scheduled to run hourly during market hours:
    Cron: 0 14-21 * * 1-5  (UTC = 9 AM - 5 PM ET, Mon-Fri)

Each run:
    1. Check market is open (Alpaca clock)
    2. Load active pairs from PairRegistry
    3. For each pair: run one PairsStrategy cycle
    4. Log summary

Deploy alongside existing flows in the Prefect work pool.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Optional, cast


class _IgnoreWinError10054(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if "WinError 10054" in record.getMessage():
            return False
        if record.exc_info:
            import traceback

            tb = "".join(traceback.format_exception(*record.exc_info))
            if "WinError 10054" in tb or "ConnectionResetError" in tb:
                return False
        return True


logging.getLogger("asyncio").addFilter(_IgnoreWinError10054())

# Add project root to path when running directly
if __file__ and Path(__file__).exists():
    project_root = Path(__file__).parent.parent.parent.parent.parent.parent
    if project_root.exists() and str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from loguru import logger
from prefect import flow, task

from src.config.settings import get_settings
from src.services.alpaca.client import AlpacaClient
from src.services.notification.email_notifier import get_notifier
from src.services.strategy_engine.baskets.strategy import BasketStrategy
from src.services.strategy_engine.pairs.strategy import PairsStrategy
from src.shared.database.base import db_readonly_session, db_transaction
from src.shared.database.models.market_data import MarketData
from src.shared.database.models.strategy_models import (
    BasketRegistry,
    PairRegistry,
    PairTrade,
)

# ---------------------------------------------------------------------------
# Run name helper
# ---------------------------------------------------------------------------


def _flow_run_name() -> str:
    return f"Pairs Trading Cycle - {datetime.now().strftime('%Y-%m-%d %H:%M')}"


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@task(
    name="check-market-open",
    retries=2,
    retry_delay_seconds=15,
    log_prints=True,
)
async def check_market_open_task(alpaca: AlpacaClient) -> bool:
    """Return True if the market is currently open."""
    clock = await alpaca.get_clock()
    is_open = clock.get("is_open", False)
    next_open = clock.get("next_open", "unknown")
    if is_open:
        logger.info("Market is OPEN  -  proceeding with strategy cycle")
    else:
        logger.info(f"Market is CLOSED  -  next open: {next_open}")
    return bool(is_open)


@task(
    name="run-pairs-strategy-cycle",
    retries=1,
    retry_delay_seconds=30,
    log_prints=True,
)
async def run_pairs_strategy_task(alpaca: AlpacaClient) -> dict:
    """Run one full PairsStrategy evaluation cycle across all active pairs."""
    strategy = PairsStrategy(alpaca)
    results = await strategy.run_cycle()

    ok = [r for r in results if r.get("status") == "OK"]
    no_signal = [r for r in results if r.get("status") == "NO_SIGNAL"]
    errors = [r for r in results if r.get("status") == "ERROR"]

    summary = {
        "total_pairs": len(results),
        "with_signal": len(ok),
        "no_signal": len(no_signal),
        "errors": len(errors),
        "details": results,
    }

    logger.info(
        f"Cycle complete: {len(results)} pairs evaluated, "
        f"{len(ok)} with signal, {len(errors)} errors"
    )
    return summary


@task(
    name="refresh-pair-prices",
    retries=2,
    retry_delay_seconds=30,
    log_prints=True,
)
async def refresh_pair_prices_task() -> dict:
    """
    Load today's hourly Yahoo bars into market_data for every active pair symbol.

    Runs before the strategy cycle so _fetch_prices() always sees bars up to
    the current hour.  Uses days_back=14 (2 calendar weeks) to cover the
    largest z_score_window (60 bars = ~9 trading days at 7 bars/day).
    2 days was insufficient - caused INSUFFICIENT_DATA on every cycle.
    Yahoo `end` must be strictly after ``date.today()`` or today's hourly bars
    are omitted (yfinance treats ``end`` as exclusive).
    """
    with db_readonly_session() as session:
        pairs = (
            session.query(PairRegistry).filter(PairRegistry.is_active.is_(True)).all()
        )
        pair_syms = {sym for p in pairs for sym in (p.symbol1, p.symbol2)}
        for p in pairs:
            session.expunge(p)

        baskets = (
            session.query(BasketRegistry)
            .filter(BasketRegistry.is_active.is_(True))
            .all()
        )
        basket_syms = {sym for b in baskets for sym in (b.symbols or [])}
        for b in baskets:
            session.expunge(b)

    symbols = sorted(pair_syms | basket_syms)

    if not symbols:
        logger.info("refresh-pair-prices: no active pairs or baskets, skipping")
        return {"symbols": [], "loaded": 0}

    logger.info("Refreshing hourly bars for %d symbols: %s", len(symbols), symbols)

    from datetime import date, timedelta, timezone

    import yfinance as yf
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from_date = date.today() - timedelta(days=14)
    # yfinance `end` is exclusive on the calendar day; today's 1h bars are
    # dropped if end==today. Use tomorrow so the current session is included.
    to_date = date.today() + timedelta(days=1)
    total = 0

    for symbol in symbols:
        try:
            hist = yf.Ticker(symbol).history(
                start=str(from_date),
                end=str(to_date),
                interval="1h",
                auto_adjust=True,
            )
            if hist.empty:
                logger.warning("No Yahoo bars returned for %s", symbol)
                continue

            records = []
            for ts, row in hist.iterrows():
                records.append(
                    {
                        "symbol": symbol,
                        "timestamp": ts.to_pydatetime().astimezone(timezone.utc),
                        "data_source": "yahoo_adjusted_1h",
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                        "volume": int(row["Volume"]),
                    }
                )

            with db_transaction() as session:
                stmt = pg_insert(MarketData).values(records)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["symbol", "timestamp", "data_source"],
                    set_={
                        "open": stmt.excluded.open,
                        "high": stmt.excluded.high,
                        "low": stmt.excluded.low,
                        "close": stmt.excluded.close,
                        "volume": stmt.excluded.volume,
                    },
                )
                session.execute(stmt)

            total += len(records)
            logger.info("Refreshed %d bars for %s", len(records), symbol)
        except Exception as exc:
            logger.warning("Failed to refresh bars for %s: %s", symbol, exc)

    logger.info("refresh-pair-prices: %d total records for %s", total, symbols)
    return {"symbols": symbols, "loaded": total}


@task(
    name="run-basket-strategy-cycle",
    retries=1,
    retry_delay_seconds=30,
    log_prints=True,
)
async def run_basket_strategy_task(alpaca: AlpacaClient) -> dict:
    """Run one full BasketStrategy evaluation cycle across all active baskets."""
    with db_readonly_session() as session:
        active_count = (
            session.query(BasketRegistry)
            .filter(BasketRegistry.is_active.is_(True))
            .count()
        )

    if active_count == 0:
        logger.info("No active baskets found - skipping basket cycle")
        return {"total_baskets": 0, "with_signal": 0, "errors": 0}

    strategy = BasketStrategy(alpaca)
    results = await strategy.run_cycle()

    ok = [r for r in results if r.get("status") == "OK"]
    errors = [r for r in results if r.get("status") == "ERROR"]

    summary = {
        "total_baskets": len(results),
        "with_signal": len(ok),
        "errors": len(errors),
        "details": results,
    }
    logger.info(
        f"Basket cycle complete: {len(results)} baskets evaluated, {len(ok)} with signal, {len(errors)} errors"
    )
    return summary


@task(
    name="run-ops-monitor",
    retries=0,
    log_prints=True,
)
async def run_ops_monitor_task(cycle_summary: dict) -> None:
    """Run the Ops Monitor Agent post-cycle. Never raises."""
    from src.services.agent import ops_monitor_agent

    await ops_monitor_agent.run(cycle_summary)


# Degradation thresholds for auto-disabling pairs
_MIN_TRADES_TO_EVALUATE = 5  # skip pairs with fewer closed trades
_EVAL_WINDOW = 10  # look at the most recent N closed trades
_FAIL_WIN_RATE = 0.35  # deactivate if win rate falls below this
# (also requires avg_pnl < 0 to avoid deactivating pairs on a cold streak)


@task(
    name="check-and-disable-failing-pairs",
    retries=1,
    retry_delay_seconds=15,
    log_prints=True,
)
async def check_and_disable_failing_pairs_task() -> dict:
    """
    Evaluate recent trade performance for every active pair.
    Deactivates pairs where the last _EVAL_WINDOW trades show:
      - win rate < _FAIL_WIN_RATE, AND
      - average P&L < 0
    Sends an email alert for each deactivated pair.
    """
    with db_readonly_session() as session:
        pairs = (
            session.query(PairRegistry).filter(PairRegistry.is_active.is_(True)).all()
        )
        for p in pairs:
            session.expunge(p)

    deactivated = []

    for pair in pairs:
        with db_readonly_session() as session:
            recent = (
                session.query(PairTrade)
                .filter(
                    PairTrade.pair_id == pair.id,
                    PairTrade.status.in_(["CLOSED", "STOPPED"]),
                )
                .order_by(PairTrade.exit_time.desc())
                .limit(_EVAL_WINDOW)
                .all()
            )
            for t in recent:
                session.expunge(t)

        if len(recent) < _MIN_TRADES_TO_EVALUATE:
            continue

        wins = sum(1 for t in recent if (t.pnl or 0) > 0)
        win_rate = wins / len(recent)
        avg_pnl = sum(t.pnl or 0 for t in recent) / len(recent)

        if win_rate < _FAIL_WIN_RATE and avg_pnl < 0:
            pair_label = f"{pair.symbol1}/{pair.symbol2}"
            reason = (
                f"Last {len(recent)} trades: "
                f"win_rate={win_rate:.1%} (threshold {_FAIL_WIN_RATE:.0%}), "
                f"avg_pnl=${avg_pnl:+.2f}"
            )
            logger.warning(f"Auto-deactivating {pair_label}: {reason}")

            with db_transaction() as session:
                db_pair = session.get(PairRegistry, pair.id)
                if db_pair:
                    db_pair.is_active = False
                    db_pair.notes = f"Auto-deactivated {datetime.now().strftime('%Y-%m-%d')}: {reason}"

            await get_notifier().send_pair_deactivated(
                pair=pair_label,
                reason=reason,
                win_rate=win_rate,
                avg_pnl=avg_pnl,
                total_trades=len(recent),
            )
            deactivated.append(pair_label)

    if deactivated:
        logger.info(
            f"Deactivated {len(deactivated)} failing pair(s): {', '.join(deactivated)}"
        )
    else:
        logger.info("Performance check: no failing pairs detected")

    return {"deactivated": deactivated, "count": len(deactivated)}


# ---------------------------------------------------------------------------
# Flow
# ---------------------------------------------------------------------------


@flow(
    name="intraday-pairs-trading",
    flow_run_name=_flow_run_name,
    log_prints=True,
    retries=1,
    retry_delay_seconds=60,
    timeout_seconds=600,
)
async def intraday_pairs_flow(skip_market_check: bool = False) -> dict:
    """
    Intraday pairs trading strategy flow.

    Args:
        skip_market_check: Set True to run even when market is closed
                           (useful for testing / manual runs).

    Returns:
        Summary dict with results from all pair cycles.
    """
    logger.info("Starting intraday pairs trading flow")

    settings = get_settings()
    alpaca = AlpacaClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
        is_paper=True,
    )

    if not skip_market_check:
        is_open = await check_market_open_task(alpaca)
        if not is_open:
            return {"status": "MARKET_CLOSED", "pairs_evaluated": 0}

    try:
        await refresh_pair_prices_task()
        summary = await run_pairs_strategy_task(alpaca)
        basket_summary = await run_basket_strategy_task(alpaca)
        deactivation = await check_and_disable_failing_pairs_task()
        summary["deactivated_pairs"] = deactivation["deactivated"]
        summary["basket_summary"] = basket_summary
        await run_ops_monitor_task(summary)
    except Exception as exc:
        err_msg = str(exc)
        logger.error(f"Unhandled flow error: {err_msg}")
        await get_notifier().send_flow_error(error=err_msg)
        raise

    logger.info(
        f"Flow complete: {summary['total_pairs']} pairs, "
        f"{summary['with_signal']} signals, {summary['errors']} errors, "
        f"{len(summary.get('deactivated_pairs', []))} deactivated"
    )
    return {"status": "OK", **summary}


# ---------------------------------------------------------------------------
# Deployment helper (run from CLI)
# ---------------------------------------------------------------------------


async def deploy_pairs_flow() -> None:
    """Register the intraday pairs trading flow as a Prefect deployment."""
    project_root = Path(__file__).parent.parent.parent.parent.parent.parent
    source_path = str(project_root)
    flow_file = "src/shared/prefect/flows/strategy_engine/pairs_flow.py"

    from prefect.client.schemas.schedules import CronSchedule

    from src.shared.prefect.config import PrefectConfig

    deployment = await cast(
        Awaitable,
        intraday_pairs_flow.from_source(
            source=source_path,
            entrypoint=f"{flow_file}:intraday_pairs_flow",
        ),
    )
    await deployment.deploy(
        name="Intraday Pairs Trading",
        work_pool_name=PrefectConfig.get_work_pool_name(),
        schedules=[CronSchedule(cron="0 14-21 * * 1-5")],
        parameters={"skip_market_check": False},
        tags=["strategy-engine", "pairs-trading", "scheduled"],
        description="Hourly intraday pairs trading strategy  -  evaluates z-scores and places paper orders via Alpaca",
        ignore_warnings=True,
    )
    logger.info("Pairs trading flow deployed successfully!")


if __name__ == "__main__":
    """
    Modes:
        Dry-run (one cycle now, market check skipped):
            python src/shared/prefect/flows/strategy_engine/pairs_flow.py

        Register deployment in Prefect (creates scheduled job visible in UI):
            python src/shared/prefect/flows/strategy_engine/pairs_flow.py --deploy
    """
    import asyncio
    import sys as _sys

    if "--deploy" in _sys.argv:
        asyncio.run(deploy_pairs_flow())
    else:
        # Default: run one cycle immediately (skip market check for manual testing)
        async def _run() -> None:
            await intraday_pairs_flow(skip_market_check=True)

        asyncio.run(_run())
