"""Tradable ETF proxies and the stock universe.

The factor residual strategy regresses each stock onto a small set of liquid,
tradable ETFs (a broad-market ETF plus SPDR sector ETFs) so the resulting hedge
is executable. This module defines that proxy set, the sector -> ETF map, and a
helper to load the stock universe (so ETFs stored in market_data are not swept
into the stock-only PCA).
"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.config.database import get_engine

# Broad-market proxy.
BROAD_ETF = "SPY"

# data_ingestion.symbols.sector -> SPDR sector ETF.
SECTOR_ETFS = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Health Care": "XLV",
    "Healthcare": "XLV",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Basic Materials": "XLB",
    "Communication Services": "XLC",
}

# All proxy ETFs to ingest / regress against (deduplicated, sorted).
PROXY_ETFS: list[str] = sorted({BROAD_ETF, *SECTOR_ETFS.values()})


def sector_etf(sector: Optional[str]) -> Optional[str]:
    """SPDR sector ETF for a symbol's sector, or None if unmapped."""
    if not sector:
        return None
    return SECTOR_ETFS.get(sector)


def load_universe_symbols(
    engine: Optional[Engine] = None,
    statuses: Sequence[str] = ("active",),
) -> list[str]:
    """Stock symbols that make up the discovery universe (excludes ETF proxies)."""
    engine = engine or get_engine("trading")
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT symbol FROM data_ingestion.symbols "
                "WHERE status = ANY(:statuses) ORDER BY symbol"
            ),
            {"statuses": list(statuses)},
        ).fetchall()
    universe = [r[0] for r in rows]
    proxies = set(PROXY_ETFS)
    return [s for s in universe if s not in proxies]


def load_symbol_sectors(engine: Optional[Engine] = None) -> dict[str, str]:
    """Map of symbol -> sector for the universe."""
    engine = engine or get_engine("trading")
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT symbol, sector FROM data_ingestion.symbols WHERE sector IS NOT NULL"
            )
        ).fetchall()
    return {r[0]: r[1] for r in rows}
