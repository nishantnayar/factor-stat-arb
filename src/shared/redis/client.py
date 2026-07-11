"""
Redis client singleton for the trading system.

Provides a no-op fallback when Redis is unavailable so callers never
need to guard against connection errors.
"""

import json
import logging
import time
from typing import Any, Optional

import redis

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

# TTL for all debug keys - 48 hours
_TTL_SECONDS = 48 * 3600

# How long to wait before retrying a connection after a failure
_RETRY_COOLDOWN_SECONDS = 60

_client: Optional[Any] = None
_last_failure_time: float = 0.0


def get_redis() -> Optional[Any]:
    """
    Return a shared Redis connection, or None if Redis is unreachable.

    The connection is created once and reused.  If Redis is down, the
    failure is cached for _RETRY_COOLDOWN_SECONDS so callers don't pay
    the connection timeout cost on every call - only retry after the
    cooldown elapses.
    """
    global _client, _last_failure_time
    if _client is not None:
        return _client

    now = time.monotonic()
    if now - _last_failure_time < _RETRY_COOLDOWN_SECONDS:
        return None

    settings = get_settings()
    try:
        r = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        r.ping()
        _client = r
        logger.info(
            "Redis connected at %s:%s", settings.redis_host, settings.redis_port
        )
    except Exception as exc:
        logger.warning("Redis unavailable - debug caching disabled: %s", exc)
        _last_failure_time = now
        return None

    return _client


def set_json(key: str, value: Any, ttl: int = _TTL_SECONDS) -> None:
    """Serialize value to JSON and store it in Redis.  No-op if Redis is down."""
    r = get_redis()
    if r is None:
        return
    try:
        r.setex(key, ttl, json.dumps(value))
    except Exception as exc:
        logger.debug("Redis write failed for key %s: %s", key, exc)


def get_json(key: str) -> Optional[Any]:
    """Fetch and deserialize a JSON value from Redis.  Returns None on any error."""
    r = get_redis()
    if r is None:
        return None
    try:
        raw = r.get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as exc:
        logger.debug("Redis read failed for key %s: %s", key, exc)
        return None
