"""
Alpaca WebSocket bar streamer.

Runs as a long-lived process during market hours.  Subscribes to 1-minute
bars for every symbol that appears in an active PairRegistry row and stores
each bar as a JSON-encoded entry in a Redis list:

    Key   : pairs:ws:{SYMBOL}
    Value : JSON list of bar dicts, newest appended at right (RPUSH)
    TTL   : 26 hours (reset on each write) - survives overnight, gone before
            next open if the process is not restarted

Each bar dict has the keys:
    t  - ISO-8601 timestamp (bar open time, UTC)
    o  - open
    h  - high
    l  - low
    c  - close
    v  - volume

Usage (run directly or via Prefect deployment):
    python -m src.services.alpaca.websocket
"""

import json
import logging
import os
import signal
import sys
import types
from pathlib import Path
from typing import Any, List, Optional

# ---------------------------------------------------------------------------
# Path bootstrap so this runs as __main__ from the project root
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from alpaca.data.live import StockDataStream

from src.config.settings import get_settings
from src.shared.database.base import db_readonly_session
from src.shared.database.models.strategy_models import PairRegistry
from src.shared.redis.client import get_redis

# NOTE: requires alpaca-py (pip install alpaca-py).  This module is a
# standalone script and is NOT imported by the main strategy pipeline.

logger = logging.getLogger(__name__)

# Keep at most 26 h of 1-min bars per symbol (26 * 60 = 1560 entries)
_MAX_BARS_PER_SYMBOL = 1560
_TTL_SECONDS = 26 * 3600

# Redis key prefix
_KEY_PREFIX = "pairs:ws:"


def _active_symbols() -> List[str]:
    """Return the unique set of symbols from all active PairRegistry rows."""
    with db_readonly_session() as session:
        pairs = (
            session.query(PairRegistry).filter(PairRegistry.is_active.is_(True)).all()
        )
        symbols = set()
        for p in pairs:
            symbols.add(p.symbol1)
            symbols.add(p.symbol2)
    return sorted(symbols)


def _push_bar(r: Any, symbol: str, bar_dict: dict[str, Any]) -> None:
    """Append one bar to the Redis list for symbol, trim to max length."""
    key = f"{_KEY_PREFIX}{symbol}"
    pipe = r.pipeline()
    pipe.rpush(key, json.dumps(bar_dict))
    pipe.ltrim(key, -_MAX_BARS_PER_SYMBOL, -1)
    pipe.expire(key, _TTL_SECONDS)
    pipe.execute()


async def _bar_handler(bar: Any) -> None:
    """Called by StockDataStream for every 1-min bar received."""
    r = get_redis()
    if r is None:
        return
    bar_dict = {
        "t": bar.timestamp.isoformat(),
        "o": float(bar.open),
        "h": float(bar.high),
        "l": float(bar.low),
        "c": float(bar.close),
        "v": int(bar.volume),
    }
    _push_bar(r, bar.symbol, bar_dict)
    logger.debug("WS bar %s @ %s close=%.4f", bar.symbol, bar.timestamp, bar.close)


def run() -> None:
    """Start the WebSocket stream and block until interrupted."""
    settings = get_settings()
    api_key = settings.alpaca_api_key or os.getenv("ALPACA_API_KEY", "")
    secret_key = settings.alpaca_secret_key or os.getenv("ALPACA_SECRET_KEY", "")

    if not api_key or not secret_key:
        logger.error("ALPACA_API_KEY / ALPACA_SECRET_KEY not set - aborting")
        return

    symbols = _active_symbols()
    if not symbols:
        logger.warning(
            "No active pairs found in PairRegistry - nothing to subscribe to"
        )
        return

    logger.info("Starting Alpaca WS stream for %d symbols: %s", len(symbols), symbols)

    stream = StockDataStream(api_key, secret_key)

    # Register handler for every active symbol
    stream.subscribe_bars(_bar_handler, *symbols)

    # Graceful shutdown on SIGINT / SIGTERM
    def _stop(signum: int, frame: Optional[types.FrameType]) -> None:
        logger.info("Received signal %s - shutting down WebSocket stream", signum)
        stream.stop()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    logger.info("WebSocket stream running - press Ctrl+C to stop")
    stream.run()
    logger.info("WebSocket stream stopped")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    run()
