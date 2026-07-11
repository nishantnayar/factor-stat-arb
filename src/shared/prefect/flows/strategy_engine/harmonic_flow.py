"""
Intraday Harmonic Pattern Trading Flow

Scheduled to run daily at market open:
    Cron: 30 14 * * 1-5  (UTC = 9:30 AM ET, Mon-Fri)

Each run:
    1. Check market is open (Alpaca clock)
    2. Load price series for configured symbol universe from DB (yahoo_adjusted EOD)
    3. Scan for Gartley patterns
    4. For each open HarmonicTrade: check exit conditions and close if triggered
    5. For each new pattern: size position and open trade at point D
    6. Log summary

Deploy alongside the pairs flow in the same Prefect work pool.

Symbol universe is configured via the HARMONIC_UNIVERSE env var (comma-separated).
Defaults to a small liquid set if not set.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Awaitable, List, Optional, cast


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

if __file__ and Path(__file__).exists():
    project_root = Path(__file__).parent.parent.parent.parent.parent.parent
    if project_root.exists() and str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from loguru import logger
from prefect import flow, task

from src.config.settings import get_settings
from src.services.alpaca.client import AlpacaClient
from src.services.strategy_engine.harmonic.gartley_detector import (
    GartleyDetector,
    GartleyPattern,
    scan_universe,
)
from src.services.strategy_engine.harmonic.harmonic_executor import (
    HarmonicExecutor,
    compute_qty,
)
from src.shared.database.base import db_readonly_session
from src.shared.database.models.strategy_models import HarmonicTrade
from src.shared.market_data import get_price_series

# ---------------------------------------------------------------------------
# Universe defaults (override with HARMONIC_UNIVERSE env var)
# ---------------------------------------------------------------------------

_DEFAULT_UNIVERSE = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "META",
    "JPM",
    "BAC",
    "GS",
    "MS",
    "WFC",
    "XOM",
    "CVX",
    "COP",
    "SLB",
    "EOG",
    "NVDA",
    "AMD",
    "TSLA",
    "WMT",
    "JNJ",
]

_EOD_BARS = 252  # ~1 year of daily bars for pattern detection
_SWING_ORDER = 5  # bars on each side to confirm a swing point
_MAX_OPEN_TRADES = 5  # cap concurrent harmonic positions


def _flow_run_name() -> str:
    return f"Harmonic Pattern Cycle - {datetime.now().strftime('%Y-%m-%d %H:%M')}"


def _load_universe() -> List[str]:
    """Return symbol list from HARMONIC_UNIVERSE env var or the default set."""
    import os

    raw = os.environ.get("HARMONIC_UNIVERSE", "")
    if raw.strip():
        return [s.strip().upper() for s in raw.split(",") if s.strip()]
    return _DEFAULT_UNIVERSE


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@task(
    name="check-market-open-harmonic",
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
        logger.info("Market is OPEN  -  proceeding with harmonic scan")
    else:
        logger.info("Market is CLOSED  -  next open: {}", next_open)
    return bool(is_open)


@task(
    name="load-harmonic-prices",
    retries=2,
    retry_delay_seconds=30,
    log_prints=True,
)
def load_prices_task(symbols: List[str]) -> dict:
    """
    Fetch EOD daily close series for each symbol from the DB (yahoo_adjusted).

    Returns {symbol: pd.Series} for symbols that have sufficient data.
    Symbols with fewer than 2*_SWING_ORDER+1 bars are dropped with a warning.
    """
    from sqlalchemy import text

    from src.shared.market_data import get_price_series as _gps

    # Harmonic patterns work best on daily bars; reuse the yahoo_adjusted source.
    min_bars = 2 * _SWING_ORDER + 1
    result = {}

    for symbol in symbols:
        # Query EOD bars directly (yahoo_adjusted, not yahoo_adjusted_1h)
        sql = text(
            """
            SELECT timestamp, close
            FROM data_ingestion.market_data
            WHERE symbol      = :symbol
              AND data_source  = 'yahoo_adjusted'
              AND close IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT :lim
            """
        )
        try:
            import pandas as pd

            with db_readonly_session() as session:
                rows = session.execute(
                    sql, {"symbol": symbol, "lim": _EOD_BARS}
                ).fetchall()

            if not rows:
                logger.warning("No yahoo_adjusted bars in DB for {}", symbol)
                continue

            timestamps = [r[0] for r in reversed(rows)]
            closes = [float(r[1]) for r in reversed(rows)]
            idx = pd.DatetimeIndex(
                pd.to_datetime(timestamps, utc=True), name="timestamp"
            )
            series = pd.Series(closes, index=idx, name=symbol, dtype=float)

            if len(series) < min_bars:
                logger.warning(
                    "{}: only {} bars, need {} - skipping",
                    symbol,
                    len(series),
                    min_bars,
                )
                continue

            result[symbol] = series
            logger.debug("{}: {} EOD bars loaded", symbol, len(series))

        except Exception as exc:
            logger.warning("Failed to load prices for {}: {}", symbol, exc)

    logger.info(
        "load-harmonic-prices: {}/{} symbols have sufficient data",
        len(result),
        len(symbols),
    )
    return result


@task(
    name="scan-harmonic-patterns",
    retries=1,
    retry_delay_seconds=15,
    log_prints=True,
)
def scan_patterns_task(symbol_prices: dict) -> List[GartleyPattern]:
    """
    Run GartleyDetector across the symbol universe.

    Returns a flat list of GartleyPattern objects with symbol set,
    limited to the single most-recent pattern per symbol (to avoid
    opening multiple trades on the same ticker from one scan).
    """
    raw = scan_universe(symbol_prices, swing_order=_SWING_ORDER)

    patterns: List[GartleyPattern] = []
    for symbol, found in raw.items():
        best = found[0]  # most-recent D point first (already sorted)
        best.symbol = symbol
        patterns.append(best)
        logger.info(
            "Pattern: {} {} {} | D={:.4f} SL={:.4f} T1={:.4f} T2={:.4f}",
            symbol,
            best.direction,
            "gartley",
            best.d_price,
            best.stop_loss,
            best.targets[0],
            best.targets[1],
        )

    logger.info(
        "scan-harmonic-patterns: {} pattern(s) found across {} symbol(s)",
        len(patterns),
        len(symbol_prices),
    )
    return patterns


@task(
    name="check-harmonic-exits",
    retries=1,
    retry_delay_seconds=15,
    log_prints=True,
)
async def check_exits_task(alpaca: AlpacaClient, symbol_prices: dict) -> dict:
    """
    Evaluate exit conditions for all open HarmonicTrades.

    Closes any trade whose current price has hit TARGET_1, TARGET_2, or STOP_LOSS.
    Returns a summary dict.
    """
    with db_readonly_session() as session:
        open_trades = (
            session.query(HarmonicTrade).filter(HarmonicTrade.status == "OPEN").all()
        )
        for t in open_trades:
            session.expunge(t)

    if not open_trades:
        logger.info("check-harmonic-exits: no open trades")
        return {"checked": 0, "closed": 0}

    executor = HarmonicExecutor(alpaca)
    closed = 0

    for trade in open_trades:
        series = symbol_prices.get(trade.symbol)
        if series is None or series.empty:
            logger.warning(
                "No price data for open trade id={} ({}), skipping exit check",
                trade.id,
                trade.symbol,
            )
            continue

        current_price = float(series.iloc[-1])
        signal = HarmonicExecutor.check_exit(trade, current_price)

        if signal:
            logger.info(
                "Exit signal {} for trade id={} ({}) @ {:.4f}",
                signal,
                trade.id,
                trade.symbol,
                current_price,
            )
            ok = await executor.close_trade(
                trade,
                exit_price=current_price,
                exit_reason=signal,
            )
            if ok:
                closed += 1

    logger.info("check-harmonic-exits: checked={} closed={}", len(open_trades), closed)
    return {"checked": len(open_trades), "closed": closed}


@task(
    name="open-harmonic-trades",
    retries=1,
    retry_delay_seconds=30,
    log_prints=True,
)
async def open_trades_task(
    alpaca: AlpacaClient,
    patterns: List[GartleyPattern],
    symbol_prices: dict,
) -> dict:
    """
    Open new harmonic trades for detected patterns.

    Guards:
      - Skip if a trade for this symbol is already OPEN.
      - Skip if total open harmonic trades >= _MAX_OPEN_TRADES.
      - Skip if qty rounds to 0 (position too small for equity).
    """
    with db_readonly_session() as session:
        open_trades = (
            session.query(HarmonicTrade).filter(HarmonicTrade.status == "OPEN").all()
        )
        open_symbols = {t.symbol for t in open_trades}
        open_count = len(open_trades)

    if open_count >= _MAX_OPEN_TRADES:
        logger.info(
            "open-harmonic-trades: already at max open trades ({}), skipping",
            _MAX_OPEN_TRADES,
        )
        return {"attempted": 0, "opened": 0, "skipped": len(patterns)}

    try:
        account = await alpaca.get_account()
        portfolio_equity = float(account.get("equity", 0))
    except Exception as exc:
        logger.error("Failed to fetch account equity: {}", exc)
        return {
            "attempted": 0,
            "opened": 0,
            "skipped": len(patterns),
            "error": str(exc),
        }

    executor = HarmonicExecutor(alpaca)
    attempted = opened = skipped = 0

    for pattern in patterns:
        if open_count >= _MAX_OPEN_TRADES:
            skipped += 1
            continue

        symbol = pattern.symbol

        if symbol in open_symbols:
            logger.info(
                "open-harmonic-trades: {} already has an open trade, skipping",
                symbol,
            )
            skipped += 1
            continue

        series = symbol_prices.get(symbol)
        current_price = (
            float(series.iloc[-1])
            if series is not None and not series.empty
            else pattern.d_price
        )

        qty = compute_qty(portfolio_equity, current_price)
        if qty == 0:
            logger.warning(
                "open-harmonic-trades: qty=0 for {} @ {:.4f}, skipping",
                symbol,
                current_price,
            )
            skipped += 1
            continue

        attempted += 1
        trade = await executor.open_trade(
            pattern,
            qty=qty,
            current_price=current_price,
        )
        if trade:
            opened += 1
            open_count += 1
            open_symbols.add(symbol)

    logger.info(
        "open-harmonic-trades: attempted={} opened={} skipped={}",
        attempted,
        opened,
        skipped,
    )
    return {"attempted": attempted, "opened": opened, "skipped": skipped}


# ---------------------------------------------------------------------------
# Flow
# ---------------------------------------------------------------------------


@flow(
    name="intraday-harmonic-trading",
    flow_run_name=_flow_run_name,
    log_prints=True,
    retries=1,
    retry_delay_seconds=60,
    timeout_seconds=300,
)
async def intraday_harmonic_flow(skip_market_check: bool = False) -> dict:
    """
    Daily harmonic pattern trading flow.

    Args:
        skip_market_check: Set True to run even when market is closed
                           (useful for testing / manual runs).

    Returns:
        Summary dict with scan and trade results.
    """
    logger.info("Starting intraday harmonic trading flow")

    settings = get_settings()
    alpaca = AlpacaClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
        is_paper=True,
    )

    if not skip_market_check:
        is_open = await check_market_open_task(alpaca)
        if not is_open:
            return {"status": "MARKET_CLOSED"}

    symbols = _load_universe()
    logger.info("Harmonic universe: {} symbols", len(symbols))

    try:
        symbol_prices = load_prices_task(symbols)

        if not symbol_prices:
            logger.warning("No price data available, aborting harmonic flow")
            return {"status": "NO_DATA"}

        exit_summary = await check_exits_task(alpaca, symbol_prices)

        patterns = scan_patterns_task(symbol_prices)

        if settings.harmonic_long_only:
            before = len(patterns)
            patterns = [p for p in patterns if p.direction == "bullish"]
            skipped = before - len(patterns)
            if skipped:
                logger.info(
                    "HARMONIC_LONG_ONLY: dropped {} bearish pattern(s)", skipped
                )

        if patterns:
            entry_summary = await open_trades_task(alpaca, patterns, symbol_prices)
        else:
            entry_summary = {"attempted": 0, "opened": 0, "skipped": 0}

    except Exception as exc:
        err_msg = str(exc)
        logger.error("Unhandled harmonic flow error: {}", err_msg)
        raise

    summary = {
        "status": "OK",
        "symbols_scanned": len(symbol_prices),
        "patterns_found": len(patterns),
        "exits": exit_summary,
        "entries": entry_summary,
    }
    logger.info(
        "Harmonic flow complete: symbols={} patterns={} exits_closed={} entries_opened={}",
        summary["symbols_scanned"],
        summary["patterns_found"],
        exit_summary["closed"],
        entry_summary["opened"],
    )
    return summary


# ---------------------------------------------------------------------------
# Deployment helper
# ---------------------------------------------------------------------------


async def deploy_harmonic_flow() -> None:
    """Register the harmonic trading flow as a Prefect deployment."""
    project_root = Path(__file__).parent.parent.parent.parent.parent.parent
    flow_file = "src/shared/prefect/flows/strategy_engine/harmonic_flow.py"

    from src.shared.prefect.config import PrefectConfig

    deployment = await cast(
        Awaitable,
        intraday_harmonic_flow.from_source(
            source=str(project_root),
            entrypoint=f"{flow_file}:intraday_harmonic_flow",
        ),
    )
    await deployment.deploy(
        name="Intraday Harmonic Trading",
        work_pool_name=PrefectConfig.get_work_pool_name(),
        cron="30 14 * * 1-5",  # 9:30 AM ET daily, Mon-Fri
        parameters={"skip_market_check": False},
        tags=["strategy-engine", "harmonic-trading", "scheduled"],
        description="Daily harmonic pattern scan - detects Gartley patterns and places paper orders via Alpaca",
        ignore_warnings=True,
    )
    logger.info("Harmonic trading flow deployed successfully!")


if __name__ == "__main__":
    """
    Modes:
        Dry-run (one cycle now, market check skipped):
            python src/shared/prefect/flows/strategy_engine/harmonic_flow.py

        Register deployment in Prefect:
            python src/shared/prefect/flows/strategy_engine/harmonic_flow.py --deploy
    """
    import asyncio
    import sys as _sys

    if "--deploy" in _sys.argv:
        asyncio.run(deploy_harmonic_flow())
    else:

        async def _run() -> None:
            await intraday_harmonic_flow(skip_market_check=True)

        asyncio.run(_run())
