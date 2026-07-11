"""
Pairs Strategy Orchestrator

Main entry point called by the Prefect intraday flow.

Each call to PairsStrategy.run_cycle() performs one full evaluation loop:
    1. Load active pairs from PairRegistry
    2. For each pair:
        a. Fetch latest N hourly bars from data_ingestion.market_data
           (data_source='yahoo_adjusted', refreshed by pairs_flow before cycle)
        b. SpreadCalculator.calculate() -> spread, z_score
        c. Store spread/z-score to PairSpread table
        d. SignalGenerator.generate() -> signal or None
        e. If entry signal: KellySizer.calculate_size() -> qty1, qty2
        f. PairExecutor.open_pair_trade() or close_pair_trade() / emergency_stop()
    3. Update PairPerformance table

The strategy reads prices from data_ingestion.market_data (yahoo_adjusted
hourly bars).  Alpaca is used only for order execution and account info.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from loguru import logger

from src.services.alpaca.client import AlpacaClient
from src.services.notification.email_notifier import get_notifier
from src.services.risk_management.portfolio_risk_manager import PortfolioRiskManager
from src.services.strategy_engine.pairs.pair_executor import PairExecutor
from src.services.strategy_engine.pairs.position_sizer import KellySizer
from src.services.strategy_engine.pairs.signal_generator import SignalGenerator
from src.services.strategy_engine.pairs.spread_calculator import SpreadCalculator
from src.shared.database.base import db_readonly_session, db_transaction
from src.shared.database.models.strategy_models import (
    PairPerformance,
    PairRegistry,
    PairSpread,
    PairTrade,
)
from src.shared.market_data import get_price_series
from src.shared.redis.client import set_json


def _cache_bars(symbol: str, prices: "pd.Series", ts: str) -> None:
    """Store bar fetch metadata in Redis under pairs:bars:{symbol}."""
    if prices.empty:
        set_json(f"pairs:bars:{symbol}", {"symbol": symbol, "ts": ts, "count": 0})
        return
    set_json(
        f"pairs:bars:{symbol}",
        {
            "symbol": symbol,
            "ts": ts,
            "count": len(prices),
            "first": str(prices.index[0]),
            "last": str(prices.index[-1]),
            "last_close": round(float(prices.iloc[-1]), 4),
        },
    )


class PairsStrategy:
    """
    Orchestrates the full pairs trading evaluation cycle.

    Usage:
        strategy = PairsStrategy(alpaca_client)
        results = await strategy.run_cycle()
    """

    # How many hourly bars to fetch for spread calculation
    # Needs to be at least z_score_window; we use 3x for buffer
    PRICE_LOOKBACK_BARS = 500

    def __init__(self, alpaca: AlpacaClient):
        self.alpaca = alpaca

    # ------------------------------------------------------------------
    # Main cycle
    # ------------------------------------------------------------------

    async def run_cycle(self) -> List[Dict]:
        """
        Run one full evaluation cycle across all active pairs.

        Returns:
            List of per-pair result dicts with signal, action taken, etc.
        """
        pairs = self._load_active_pairs()
        if not pairs:
            logger.warning("No active pairs found in PairRegistry")
            return []

        account = await self.alpaca.get_account()
        portfolio_equity = float(account.get("equity", 0))

        # Pre-fetch all price series once so the risk manager can compute
        # cross-pair correlations without a second round of Alpaca calls.
        prices_cache: Dict[str, pd.Series] = {}
        for pair in pairs:
            try:
                p1, p2 = await self._fetch_prices(pair)
                prices_cache[pair.symbol1] = p1
                prices_cache[pair.symbol2] = p2
            except Exception as e:
                logger.warning(
                    f"Price prefetch failed for {pair.symbol1}/{pair.symbol2}: {e}"
                )

        # Load open trades for all pairs (used by circuit breaker P&L and
        # correlation guard's active-pair list).
        open_trades = self._load_all_open_trades(pairs)

        # Reconcile: void any DB-open trades whose Alpaca positions never filled.
        await self._reconcile_open_trades(open_trades, pairs)
        # Reload after reconciliation in case any were voided.
        open_trades = self._load_all_open_trades(pairs)

        active_open_pairs = [p for p in pairs if open_trades.get(p.id)]

        # Portfolio risk controls - run once per cycle
        risk_mgr = PortfolioRiskManager()
        unrealized_pnl = PortfolioRiskManager.compute_unrealized_pnl(
            list(open_trades.values()),
            prices_cache,
            pair_lookup={p.id: p for p in pairs},
        )
        total_equity = portfolio_equity + unrealized_pnl
        circuit_breaker_active = risk_mgr.update_and_check_drawdown(total_equity)

        if circuit_breaker_active:
            logger.warning("Circuit breaker ACTIVE - new entries blocked this cycle")

        results = []
        for pair in pairs:
            try:
                result = await self._run_pair_cycle(
                    pair,
                    portfolio_equity,
                    prices_cache,
                    active_open_pairs,
                    circuit_breaker_active,
                    risk_mgr,
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Error in pair cycle {pair.symbol1}/{pair.symbol2}: {e}")
                results.append(
                    {
                        "pair": f"{pair.symbol1}/{pair.symbol2}",
                        "status": "ERROR",
                        "error": str(e),
                    }
                )

        return results

    # ------------------------------------------------------------------
    # Single pair cycle
    # ------------------------------------------------------------------

    async def _run_pair_cycle(
        self,
        pair: PairRegistry,
        portfolio_equity: float,
        prices_cache: Dict[str, pd.Series],
        active_open_pairs: List[PairRegistry],
        circuit_breaker_active: bool,
        risk_mgr: PortfolioRiskManager,
    ) -> Dict[str, Any]:
        sym1, sym2 = pair.symbol1, pair.symbol2
        pair_label = f"{sym1}/{sym2}"
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        logger.info(f"Evaluating pair: {pair_label}")
        # 1. Use pre-fetched prices from cache (avoids duplicate Alpaca calls)
        prices1 = prices_cache.get(sym1, pd.Series(dtype=float))
        prices2 = prices_cache.get(sym2, pd.Series(dtype=float))

        # Cache bar fetch metadata for debugging
        _cache_bars(sym1, prices1, now_str)
        _cache_bars(sym2, prices2, now_str)

        if prices1.empty or prices2.empty:
            logger.warning(f"No price data for {pair_label} - skipping")
            result: Dict[str, Any] = {"pair": pair_label, "status": "NO_DATA"}
            set_json(f"pairs:cycle:{sym1}_{sym2}", {**result, "ts": now_str})
            return result

        # 2. Calculate spread + z-score
        calc = SpreadCalculator(
            hedge_ratio=float(pair.hedge_ratio),
            z_score_window=int(pair.z_score_window),
        )
        spread_series, z_series, current_z = calc.calculate(prices1, prices2)

        if current_z is None:
            logger.warning(f"Insufficient data for z-score: {pair_label}")
            result = {
                "pair": pair_label,
                "status": "INSUFFICIENT_DATA",
                "bar_count_1": len(prices1),
                "bar_count_2": len(prices2),
                "z_score_window": int(pair.z_score_window),
            }
            set_json(f"pairs:cycle:{sym1}_{sym2}", {**result, "ts": now_str})
            return result

        p1, p2 = calc.current_prices(prices1, prices2)

        # 3. Persist spread/z-score
        self._store_spread(pair, spread_series, z_series, prices1, prices2)

        # 4. Generate signal
        sig_gen = SignalGenerator(pair)
        signal = sig_gen.generate(current_z, persist=True)

        if signal is None:
            result = {
                "pair": pair_label,
                "status": "NO_SIGNAL",
                "z_score": round(current_z, 4),
            }
            set_json(
                f"pairs:cycle:{sym1}_{sym2}",
                {
                    **result,
                    "ts": now_str,
                    "bar_count_1": len(prices1),
                    "bar_count_2": len(prices2),
                    "entry_threshold": float(pair.entry_threshold),
                },
            )
            return result

        logger.info(
            f"Signal [{signal.signal_type}] for {sym1}/{sym2} z={current_z:.3f}"
        )

        # 5. Execute
        executor = PairExecutor(pair, self.alpaca)
        notifier = get_notifier()
        action = "NONE"

        if signal.signal_type in ("LONG_SPREAD", "SHORT_SPREAD"):
            if p1 is None or p2 is None:
                return {"pair": pair_label, "status": "NO_PRICE"}

            # Control B - circuit breaker
            if circuit_breaker_active:
                logger.warning(f"Entry blocked by circuit breaker: {pair_label}")
                return {
                    "pair": pair_label,
                    "status": "BLOCKED_CIRCUIT_BREAKER",
                    "z_score": round(current_z, 4),
                    "signal": signal.signal_type,
                }

            # Control A - correlation guard
            # Exclude this pair from the active_open_pairs list so it
            # doesn't block itself (it has no open trade yet at this point).
            other_open = [p for p in active_open_pairs if p.id != pair.id]
            allowed, reason = risk_mgr.check_correlation_guard(
                pair, prices_cache, other_open
            )
            if not allowed:
                logger.warning(
                    f"Entry blocked by correlation guard: {pair_label} - {reason}"
                )
                return {
                    "pair": pair_label,
                    "status": "BLOCKED_CORRELATION",
                    "reason": reason,
                    "z_score": round(current_z, 4),
                    "signal": signal.signal_type,
                }

            sizer = KellySizer(pair)
            qty1, qty2 = sizer.calculate_size(portfolio_equity, p1, p2)
            trade = await executor.open_pair_trade(
                signal=signal,
                qty1=qty1,
                qty2=qty2,
                current_price1=p1,
                current_price2=p2,
            )
            if trade:
                action = f"OPEN ({signal.signal_type})"
                await notifier.send_trade_opened(
                    pair=pair_label,
                    signal_type=signal.signal_type,
                    z_score=current_z,
                    qty1=qty1,
                    qty2=qty2,
                    price1=p1,
                    price2=p2,
                    sym1=sym1,
                    sym2=sym2,
                )
            else:
                action = "OPEN_FAILED"
                await notifier.send_trade_failed(
                    pair=pair_label,
                    action=f"OPEN ({signal.signal_type})",
                    reason="Alpaca order submission returned no trade record",
                )

        elif signal.signal_type in ("EXIT", "STOP_LOSS", "EXPIRE"):
            open_trade = self._get_open_trade(pair)
            if open_trade:
                success, pnl, pnl_pct = await executor.close_pair_trade(
                    trade=open_trade,
                    exit_z=current_z,
                    exit_reason=signal.signal_type,
                    current_price1=p1,
                    current_price2=p2,
                )
                if success:
                    action = f"CLOSE ({signal.signal_type})"
                    hold_hours = 0.0
                    if open_trade.entry_time:
                        hold_hours = (
                            datetime.now(timezone.utc) - open_trade.entry_time
                        ).total_seconds() / 3600
                    if signal.signal_type == "STOP_LOSS":
                        await notifier.send_stop_loss(
                            pair=pair_label,
                            z_score=current_z,
                            pnl=pnl,
                            pnl_pct=pnl_pct,
                        )
                    else:
                        await notifier.send_trade_closed(
                            pair=pair_label,
                            exit_reason=signal.signal_type,
                            z_score=current_z,
                            pnl=pnl,
                            pnl_pct=pnl_pct,
                            hold_hours=hold_hours,
                        )
                else:
                    action = "CLOSE_FAILED"
                    await notifier.send_trade_failed(
                        pair=pair_label,
                        action=f"CLOSE ({signal.signal_type})",
                        reason="Alpaca close order returned failure",
                    )

        # 6. Update performance metrics
        self._update_performance(pair)

        result = {
            "pair": pair_label,
            "status": "OK",
            "z_score": round(current_z, 4),
            "signal": signal.signal_type,
            "action": action,
        }
        set_json(
            f"pairs:cycle:{sym1}_{sym2}",
            {
                **result,
                "ts": now_str,
                "bar_count_1": len(prices1),
                "bar_count_2": len(prices2),
                "entry_threshold": float(pair.entry_threshold),
            },
        )
        return result

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _load_active_pairs(self) -> List[PairRegistry]:
        with db_readonly_session() as session:
            pairs = (
                session.query(PairRegistry)
                .filter(PairRegistry.is_active.is_(True))
                .all()
            )
            for p in pairs:
                session.expunge(p)
            return pairs

    async def _fetch_prices(self, pair: PairRegistry) -> Tuple[pd.Series, pd.Series]:
        """
        Fetch the last PRICE_LOOKBACK_BARS hourly adjusted closes from the DB.

        Data source: data_ingestion.market_data (data_source='yahoo_adjusted').
        The pairs_flow refreshes these bars from Yahoo Finance before calling
        run_cycle(), so the DB always has bars up to the current hour.
        Alpaca is used only for order execution, not for price data.
        """
        sym1, sym2 = pair.symbol1, pair.symbol2
        p1 = get_price_series(sym1, limit=self.PRICE_LOOKBACK_BARS)
        p2 = get_price_series(sym2, limit=self.PRICE_LOOKBACK_BARS)
        return p1, p2

    def _load_all_open_trades(self, pairs: List[PairRegistry]) -> Dict[int, PairTrade]:
        """Return {pair_id: PairTrade} for all pairs that currently have an open trade."""
        pair_ids = [p.id for p in pairs]
        with db_readonly_session() as session:
            trades = (
                session.query(PairTrade)
                .filter(
                    PairTrade.pair_id.in_(pair_ids),
                    PairTrade.status == "OPEN",
                )
                .all()
            )
            # Keep the most recent open trade per pair (there should only be one)
            result: Dict[int, PairTrade] = {}
            for t in trades:
                if (
                    t.pair_id not in result
                    or t.entry_time > result[t.pair_id].entry_time
                ):
                    session.expunge(t)
                    result[t.pair_id] = t
            return result

    async def _reconcile_open_trades(
        self,
        open_trades: Dict[int, PairTrade],
        pairs: List[PairRegistry],
    ) -> None:
        """
        Void DB-open trades whose legs are no longer in Alpaca.

        Happens when a day-order entry expires unfilled: the DB records the trade
        as OPEN but Alpaca has no position. Without reconciliation the next EXIT
        signal tries to close a non-existent position and generates a warn email.
        """
        if not open_trades:
            return
        try:
            positions = await self.alpaca.get_positions()
        except Exception as e:
            logger.warning(
                "_reconcile_open_trades: could not fetch Alpaca positions: {}", e
            )
            return

        alpaca_syms = {p["symbol"] for p in positions}
        pair_lookup = {p.id: p for p in pairs}
        now = datetime.now(timezone.utc)

        for pair_id, trade in open_trades.items():
            pair = pair_lookup.get(pair_id)
            if not pair:
                continue
            sym1, sym2 = pair.symbol1, pair.symbol2
            if sym1 not in alpaca_syms and sym2 not in alpaca_syms:
                logger.warning(
                    "Reconcile: trade id={} {}/{} is OPEN in DB but neither leg exists "
                    "in Alpaca -- voiding as UNFILLED",
                    trade.id,
                    sym1,
                    sym2,
                )
                with db_transaction() as session:
                    db_trade = session.query(PairTrade).filter_by(id=trade.id).first()
                    if db_trade and db_trade.status == "OPEN":
                        db_trade.status = "CLOSED"
                        db_trade.exit_time = now
                        db_trade.exit_reason = "UNFILLED"

    def _get_open_trade(self, pair: PairRegistry) -> Optional[PairTrade]:
        with db_readonly_session() as session:
            trade = (
                session.query(PairTrade)
                .filter(
                    PairTrade.pair_id == pair.id,
                    PairTrade.status == "OPEN",
                )
                .order_by(PairTrade.entry_time.desc())
                .first()
            )
            if trade:
                session.expunge(trade)
            return trade

    def _store_spread(
        self,
        pair: PairRegistry,
        spread_series: pd.Series,
        z_series: pd.Series,
        prices1: pd.Series,
        prices2: pd.Series,
    ) -> None:
        """Persist the latest spread/z-score bar to PairSpread."""
        if spread_series.empty:
            return

        last_ts = spread_series.index[-1]
        spread_val = float(spread_series.iloc[-1])
        z_val = float(z_series.iloc[-1]) if not z_series.empty else None
        p1_val = float(prices1.iloc[-1]) if not prices1.empty else None
        p2_val = float(prices2.iloc[-1]) if not prices2.empty else None

        row = PairSpread(
            pair_id=pair.id,
            timestamp=last_ts.to_pydatetime(),
            price1=p1_val,
            price2=p2_val,
            spread=spread_val,
            z_score=z_val,
            hedge_ratio=float(pair.hedge_ratio),
        )
        with db_transaction() as session:
            session.add(row)

    def _update_performance(self, pair: PairRegistry) -> None:
        """Recompute and upsert today's PairPerformance row."""
        today = datetime.now(timezone.utc).date()

        with db_readonly_session() as session:
            trades = (
                session.query(PairTrade)
                .filter(
                    PairTrade.pair_id == pair.id,
                    PairTrade.status.in_(["CLOSED", "STOPPED"]),
                )
                .all()
            )
            for t in trades:
                session.expunge(t)

        if not trades:
            return

        total = len(trades)
        wins = [t for t in trades if (t.pnl or 0) > 0]
        win_rate = len(wins) / total if total > 0 else 0.0
        avg_pnl = sum(t.pnl or 0 for t in trades) / total
        total_pnl = sum(t.pnl or 0 for t in trades)
        hold_times = [t for t in trades if t.entry_time and t.exit_time]
        avg_hold = (
            sum(
                (t.exit_time - t.entry_time).total_seconds() / 3600  # type: ignore[operator,misc]
                for t in hold_times
            )
            / len(hold_times)
            if hold_times
            else 0.0
        )

        with db_transaction() as session:
            perf = (
                session.query(PairPerformance)
                .filter(
                    PairPerformance.pair_id == pair.id, PairPerformance.date == today
                )
                .first()
            )
            if perf is None:
                perf = PairPerformance(pair_id=pair.id, date=today)
                session.add(perf)

            perf.total_trades = total
            perf.winning_trades = len(wins)
            perf.win_rate = win_rate
            perf.avg_pnl = avg_pnl
            perf.total_pnl = total_pnl
            perf.avg_hold_hours = avg_hold
