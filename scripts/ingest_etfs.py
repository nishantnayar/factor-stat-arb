"""Ingest tradable ETF proxies (SPY + SPDR sector ETFs) into market_data.

The seeded universe has stocks only; the factor strategy needs ETF proxy prices to
regress against. This fetches ~2 years of hourly adjusted bars (Yahoo's intraday
history limit is ~730 days) for each proxy ETF and stores them as
data_source='yahoo_adjusted', the same source get_price_series/discovery read.

Usage:
    uv run scripts/ingest_etfs.py            # fetch all proxy ETFs
    uv run scripts/ingest_etfs.py --verify   # report bar counts per ETF
"""

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from src.config.database import get_engine  # noqa: E402
from src.services.strategy_engine.factor_stat_arb.proxies import PROXY_ETFS  # noqa: E402
from src.services.yahoo.loader import YahooDataLoader  # noqa: E402

# Yahoo caps 1h history at ~730 days; stay just under.
LOOKBACK_DAYS = 725


async def ingest() -> None:
    loader = YahooDataLoader(delay_between_requests=0.5)
    end = date.today()
    start = end - timedelta(days=LOOKBACK_DAYS)
    for etf in PROXY_ETFS:
        try:
            n = await loader.load_market_data(
                symbol=etf,
                start_date=start,
                end_date=end,
                interval="1h",
                auto_adjust=True,
            )
            print(f"[ok]   {etf}: {n} adjusted bars")
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] {etf}: {type(e).__name__}: {e}")


def verify() -> None:
    eng = get_engine("trading")
    with eng.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT symbol, count(*), min(timestamp), max(timestamp) "
                "FROM data_ingestion.market_data "
                "WHERE data_source='yahoo_adjusted' AND symbol = ANY(:e) "
                "GROUP BY symbol ORDER BY symbol"
            ),
            {"e": PROXY_ETFS},
        ).fetchall()
    have = {r[0] for r in rows}
    for r in rows:
        print(f"  {r[0]}: {r[1]:,} bars  {r[2].date()}..{r[3].date()}")
    missing = sorted(set(PROXY_ETFS) - have)
    print(
        f"present {len(have)}/{len(PROXY_ETFS)}"
        + (f", MISSING {missing}" if missing else "")
    )


def main() -> int:
    if "--verify" in sys.argv:
        verify()
        return 0
    asyncio.run(ingest())
    print("\n--- verification ---")
    verify()
    return 0


if __name__ == "__main__":
    sys.exit(main())
