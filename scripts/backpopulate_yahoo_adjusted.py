#!/usr/bin/env python3
"""
Backpopulate Yahoo market data (adjusted and/or unadjusted) for all stocks.

By default loads adjusted prices (data_source='yahoo_adjusted'). Use --unadjusted
to load raw prices (data_source='yahoo') only.

Usage:
    # Adjusted (default; matches scheduled flow)
    python scripts/backpopulate_yahoo_adjusted.py --all-symbols --days 365
    python scripts/backpopulate_yahoo_adjusted.py --all-symbols --from-date 2020-01-01 --to-date 2024-12-31
    # Unadjusted only (raw OHLCV)
    python scripts/backpopulate_yahoo_adjusted.py --all-symbols --days 365 --unadjusted
    # Daily
    python scripts/backpopulate_yahoo_adjusted.py --all-symbols --days 365 --interval 1d
"""

import asyncio
import os
import sys
from datetime import date, datetime, timedelta
from typing import Optional

import click

project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)

from loguru import logger  # noqa: E402

from src.services.yahoo.loader import YahooDataLoader  # noqa: E402
from src.shared.logging import setup_logging  # noqa: E402


@click.command()
@click.option("--symbol", type=str, help="Single symbol (e.g. AAPL).")
@click.option("--all-symbols", is_flag=True, help="Backpopulate for all active symbols.")
@click.option(
    "--from-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Start date (YYYY-MM-DD).",
)
@click.option(
    "--to-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="End date (YYYY-MM-DD).",
)
@click.option(
    "--days",
    type=int,
    default=365,
    help="Days back from to-date (default 365). Used if from-date not set.",
)
@click.option(
    "--interval",
    type=click.Choice(["1d", "1h", "1wk", "1mo"]),
    default="1h",
    help="Bar interval; default 1h to match scheduled Yahoo ingestion.",
)
@click.option(
    "--delay",
    type=float,
    default=0.5,
    help="Seconds between symbols (default 0.5).",
)
@click.option(
    "--max-symbols",
    type=int,
    help="Limit number of symbols (e.g. for testing).",
)
@click.option(
    "--unadjusted",
    is_flag=True,
    help="Load raw (unadjusted) prices only (data_source='yahoo'). Default is adjusted.",
)
def main(
    symbol: Optional[str],
    all_symbols: bool,
    from_date: Optional[datetime],
    to_date: Optional[datetime],
    days: int,
    interval: str,
    delay: float,
    max_symbols: Optional[int],
    unadjusted: bool,
) -> int:
    if not symbol and not all_symbols:
        logger.error("Specify --symbol or --all-symbols")
        return 1
    if symbol and all_symbols:
        logger.error("Use either --symbol or --all-symbols, not both")
        return 1

    setup_logging()

    to_date_obj = to_date.date() if to_date else date.today()
    from_date_obj = (
        from_date.date() if from_date else (to_date_obj - timedelta(days=days))
    )
    if to_date_obj == date.today():
        to_date_obj = to_date_obj + timedelta(days=1)
    logger.info(
        f"Backpopulating {'unadjusted' if unadjusted else 'adjusted'} prices: "
        f"{from_date_obj} to {to_date_obj}, interval={interval}"
    )

    return asyncio.run(
        _run(
            symbol=symbol,
            all_symbols=all_symbols,
            from_date=from_date_obj,
            to_date=to_date_obj,
            interval=interval,
            delay=delay,
            max_symbols=max_symbols,
            unadjusted=unadjusted,
        )
    )


async def _run(
    symbol: Optional[str],
    all_symbols: bool,
    from_date: date,
    to_date: date,
    interval: str,
    delay: float,
    max_symbols: Optional[int],
    unadjusted: bool = False,
) -> int:
    loader = YahooDataLoader(batch_size=100, delay_between_requests=delay)
    auto_adjust = not unadjusted

    if symbol:
        symbols = [symbol.upper().strip()]
    else:
        symbols = await loader._get_active_symbols()
        if max_symbols:
            symbols = symbols[:max_symbols]
    logger.info(f"Processing {len(symbols)} symbol(s) (auto_adjust={auto_adjust})")

    total = 0
    failed = 0
    for i, sym in enumerate(symbols, 1):
        try:
            count = await loader.load_market_data(
                symbol=sym,
                start_date=from_date,
                end_date=to_date,
                interval=interval,
                auto_adjust=auto_adjust,
            )
            total += count
            kind = "unadjusted" if unadjusted else "adjusted"
            logger.info(f"[{i}/{len(symbols)}] {sym}: {count} {kind} bars")
        except Exception as e:
            failed += 1
            logger.warning(f"[{i}/{len(symbols)}] {sym}: failed - {e!s}")
        if i < len(symbols):
            await asyncio.sleep(delay)

    kind = "unadjusted" if unadjusted else "adjusted"
    logger.info(f"Done. Total {kind} bars: {total}, failed symbols: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
