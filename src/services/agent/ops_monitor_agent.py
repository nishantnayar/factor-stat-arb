"""
Ops Monitor Agent

Runs after each pairs trading cycle. Reads Redis cycle state and DB trade
counts, then asks a local Ollama LLM to reason over the data and flag
anomalies. Sends an email alert if anything warrants attention.

Never raises -- all errors are caught so the agent never blocks the flow.
"""

import asyncio
import json
from typing import Optional

import ollama
from loguru import logger

from src.config.settings import get_settings
from src.shared.redis.client import get_redis

# Anomaly thresholds
_MAX_ZERO_ZSCORE_PAIRS = 1  # alert if this many pairs have |z| < 0.1
_MAX_STALE_BAR_HOURS = 3  # alert if last bar is older than this many hours
_LOW_BAR_COUNT = 20  # alert if a symbol has fewer bars than this


_SYSTEM_PROMPT = (
    "You are an anomaly detection assistant for a pairs trading system.\n\n"
    "You will receive a JSON snapshot of the current cycle state. Your job is to:\n"
    "1. Identify any operational anomalies that warrant human attention.\n"
    "2. Return a JSON object with two fields:\n"
    '   - "anomalies": a list of short strings (empty list if none)\n'
    '   - "summary": one short sentence (under 15 words) on overall cycle health\n\n'
    "A pair simply appearing in the snapshot is NOT an anomaly. NO_SIGNAL and OK\n"
    "are normal, expected statuses -- most cycles produce no trading signal.\n"
    "Only flag a SPECIFIC pair or symbol if ITS OWN data shows one of:\n"
    "- z_score near zero (|z| < 0.1) -- spread may have collapsed\n"
    "- bar_count < 20 for that symbol -- data ingestion failing\n"
    "- last_bar_hours_ago > 3 during market hours -- stale data\n"
    "- that pair's status is ERROR\n"
    "Also flag cycle-level issues only when actually present:\n"
    "- cycle_summary.errors > 0\n"
    "- cycle_summary.total_pairs == 0 (no active pairs evaluated)\n\n"
    "Each anomaly string must name the specific pair/symbol and the specific\n"
    "condition observed. Do not list a pair as an anomaly without a reason\n"
    "drawn directly from its data fields.\n"
    "Respond with valid JSON only. No explanation outside the JSON object."
)


def _build_context(cycle_summary: dict) -> dict:
    """Pull Redis state and merge with cycle summary into one snapshot."""
    r = get_redis()
    pairs_state = []

    if r is not None:
        try:
            keys = r.keys("pairs:cycle:*")
            for key in keys:
                raw = r.get(key)
                if raw:
                    try:
                        pairs_state.append(json.loads(raw))
                    except Exception:
                        pass
        except Exception as exc:
            logger.debug("ops_monitor: redis scan failed: %s", exc)

    bars_state = []
    if r is not None:
        try:
            bar_keys = r.keys("pairs:bars:*")
            for key in bar_keys:
                raw = r.get(key)
                if raw:
                    try:
                        bars_state.append(json.loads(raw))
                    except Exception:
                        pass
        except Exception as exc:
            logger.debug("ops_monitor: redis bars scan failed: %s", exc)

    # Compact redis data to key fields only to keep prompt small
    pairs_compact = [
        {
            "pair": p.get("pair", p.get("symbol1", "") + "/" + p.get("symbol2", "")),
            "status": p.get("status"),
            "z_score": p.get("z_score"),
            "signal": p.get("signal"),
        }
        for p in pairs_state
    ]
    bars_compact = [
        {
            "symbol": b.get("symbol"),
            "count": b.get("count"),
            "last_close": b.get("last_close"),
        }
        for b in bars_state
    ]

    cycle_summary_compact = {
        k: v for k, v in cycle_summary.items() if k not in ("details", "basket_summary")
    }

    return {
        "cycle_summary": cycle_summary_compact,
        "pairs_cycle_state": pairs_compact,
        "bars_state": bars_compact,
    }


def _call_ollama(context: dict) -> Optional[dict]:
    """Call local Ollama and return parsed JSON response."""
    settings = get_settings()
    prompt = json.dumps(context, default=str, indent=2)
    # Trim prompt to avoid truncated JSON responses on small-context models
    if len(prompt) > 2000:
        prompt = prompt[:2000] + "\n... (truncated)"

    try:
        response = ollama.chat(
            model=settings.ollama_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            format="json",
            options={"temperature": 0.0, "num_predict": 512, "num_ctx": 4096},
        )
        msg = response.message if hasattr(response, "message") else response["message"]
        raw = msg.content if hasattr(msg, "content") else msg["content"]
        content = (raw or "").strip()
        # Strip markdown code fences (with or without language tag)
        if content.startswith("```"):
            parts = content.split("```")
            content = parts[1] if len(parts) >= 2 else content
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        return dict(json.loads(content))
    except json.JSONDecodeError as exc:
        logger.warning("ops_monitor: LLM returned non-JSON: %s", exc)
        return None
    except Exception as exc:
        logger.warning("ops_monitor: Ollama call failed: %s", exc)
        return None


async def run(cycle_summary: dict) -> Optional[dict]:
    """
    Entry point called from the Prefect task.

    Returns the agent result dict, or None if the agent was skipped/errored.
    """
    settings = get_settings()
    if not settings.agent_enabled:
        logger.debug("ops_monitor: agent disabled, skipping")
        return None

    try:
        context = _build_context(cycle_summary)
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_call_ollama, context),
                timeout=settings.agent_timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "ops_monitor: Ollama call exceeded %ds timeout, skipping",
                settings.agent_timeout_seconds,
            )
            return None

        if result is None:
            return None

        anomalies: list = result.get("anomalies", [])
        summary: str = result.get("summary", "")

        logger.info("ops_monitor: %d anomaly(s) detected. %s", len(anomalies), summary)

        if anomalies:
            from src.services.notification.email_notifier import get_notifier

            await get_notifier().send_ops_alert(
                anomalies=anomalies,
                summary=summary,
                cycle_summary=cycle_summary,
            )

        return result

    except Exception as exc:
        logger.warning("ops_monitor: unhandled error, skipping: %s", exc)
        return None
