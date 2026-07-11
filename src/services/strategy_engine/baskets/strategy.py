"""
Basket Strategy Orchestrator

Each call to BasketStrategy.run_cycle() performs one full evaluation loop
across all active baskets in basket_registry:

    1. Load active baskets from BasketRegistry
    2. For each basket:
        a. Fetch latest N hourly bars for all legs from data_ingestion.market_data
        b. BasketSpreadCalculator.calculate() -> spread, z_score
        c. Store spread/z-score to BasketSpread table
        d. SignalGenerator.generate() -> signal or None  (reused from pairs)
        e. If entry signal: size each leg proportionally to |w_i|
        f. Execute N legs via PairExecutor.place_order (one call per leg)
        g. Persist BasketTrade row
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Dict, List, Optional

import pandas as pd
from loguru import logger

from src.services.alpaca.client import AlpacaClient
from src.services.strategy_engine.baskets.spread_calculator import (
    BasketSpreadCalculator,
)
from src.services.strategy_engine.pairs.signal_generator import SignalGenerator
from src.shared.database.base import db_readonly_session, db_transaction
from src.shared.database.models.strategy_models import (
    BasketRegistry,
    BasketSpread,
    BasketTrade,
)
from src.shared.market_data import get_price_series

# How many hourly bars to fetch per symbol (same as pairs strategy)
_PRICE_LOOKBACK_BARS = 500


def _make_fake_pair(basket: BasketRegistry) -> SimpleNamespace:
    """
    Build a plain namespace with only the attributes SignalGenerator reads.
    Using SimpleNamespace avoids SQLAlchemy instrumentation errors that occur
    when PairRegistry.__new__() is used (missing _sa_instance_state).
    """
    return SimpleNamespace(
        id=basket.id,
        symbol1=(basket.symbols or ["?"])[0],
        symbol2="_basket_",
        entry_threshold=basket.entry_threshold,
        exit_threshold=basket.exit_threshold,
        stop_loss_threshold=basket.stop_loss_threshold,
        max_hold_hours=basket.max_hold_hours,
    )


class BasketStrategy:
    """
    Orchestrates the basket trading evaluation cycle.

    Usage:
        strategy = BasketStrategy(alpaca_client)
        results = await strategy.run_cycle()
    """

    def __init__(self, alpaca: AlpacaClient):
        self.alpaca = alpaca

    async def run_cycle(self) -> List[Dict]:
        """Run one full evaluation cycle across all active baskets."""
        baskets = self._load_active_baskets()
        if not baskets:
            logger.info("No active baskets found in BasketRegistry")
            return []

        account = await self.alpaca.get_account()
        portfolio_equity = float(account.get("equity", 0))

        results = []
        for basket in baskets:
            try:
                result = await self._run_basket_cycle(basket, portfolio_equity)
                results.append(result)
            except Exception as exc:
                logger.error(f"Error in basket cycle {basket.name}: {exc}")
                results.append(
                    {"basket": basket.name, "status": "ERROR", "error": str(exc)}
                )

        return results

    async def _run_basket_cycle(
        self, basket: BasketRegistry, portfolio_equity: float
    ) -> Dict:
        symbols: List[str] = list(basket.symbols or [])
        weights: List[float] = list(basket.hedge_weights or [])
        name = basket.name
        logger.info(f"Evaluating basket: {name}  symbols={symbols}")

        # 1. Fetch price series for each leg
        prices: Dict[str, pd.Series] = {}
        for sym in symbols:
            s = get_price_series(sym, limit=_PRICE_LOOKBACK_BARS)
            prices[sym] = s

        missing = [s for s in symbols if prices[s].empty]
        if missing:
            logger.warning(f"No price data for {missing} in basket {name} - skipping")
            return {"basket": name, "status": "NO_DATA", "missing": missing}

        # 2. Compute spread and z-score
        calc = BasketSpreadCalculator(
            symbols=symbols,
            hedge_weights=weights,
            z_score_window=int(basket.z_score_window),
        )
        spread_series, z_series, current_z = calc.calculate(prices)

        if current_z is None:
            bar_counts = {s: len(prices[s]) for s in symbols}
            logger.warning(f"Insufficient data for basket {name}: {bar_counts}")
            return {
                "basket": name,
                "status": "INSUFFICIENT_DATA",
                "bar_counts": bar_counts,
                "z_score_window": int(basket.z_score_window),
            }

        # 3. Persist spread snapshot
        self._store_spread(basket, spread_series, z_series, prices, weights)

        # 4. Generate signal (reuse SignalGenerator with a fake PairRegistry shim).
        # persist=False: basket signals must never write to pair_signal -- its FK
        # is to pair_registry, and basket ids are not pair ids, so persisting here
        # can violate that FK. open_trade is fetched from BasketTrade directly
        # since SignalGenerator's own lookup only knows about PairTrade.
        fake_pair = _make_fake_pair(basket)
        sig_gen = SignalGenerator(fake_pair)
        open_trade = self._get_open_trade(basket)
        signal = sig_gen.generate(current_z, open_trade=open_trade, persist=False)

        if signal is None:
            return {
                "basket": name,
                "status": "NO_SIGNAL",
                "z_score": round(current_z, 4),
            }

        logger.info(
            f"Signal [{signal.signal_type}] for basket {name}  z={current_z:.3f}"
        )

        # 5. Execute
        action = "NONE"
        current_prices = calc.current_prices(prices)

        if signal.signal_type in ("LONG_SPREAD", "SHORT_SPREAD"):
            # Size each leg proportionally to |w_i|
            abs_weights = [abs(w) for w in weights]
            total_abs_w = sum(abs_weights)
            allocation = portfolio_equity * float(basket.max_allocation_pct or 0.05)

            legs = []
            for sym, w, abs_w in zip(symbols, weights, abs_weights):
                price = current_prices.get(sym)
                if price is None or price <= 0:
                    continue
                dollar_value = allocation * (abs_w / total_abs_w)
                qty = max(1, int(dollar_value / price))
                # Sign: LONG_SPREAD follows the cointegrating vector sign
                # positive weight = long, negative weight = short
                if signal.signal_type == "SHORT_SPREAD":
                    w = -w
                side = "buy" if w > 0 else "sell"
                legs.append(
                    {
                        "symbol": sym,
                        "qty": qty,
                        "side": side,
                        "entry_price": round(price, 4),
                        "order_id": None,
                    }
                )

            if legs:
                order_legs = await self._place_basket_orders(legs)
                trade = self._open_basket_trade(
                    basket, signal.signal_type, order_legs, current_z
                )
                if trade:
                    action = f"OPEN ({signal.signal_type})"
                else:
                    action = "OPEN_FAILED"

        elif signal.signal_type in ("EXIT", "STOP_LOSS", "EXPIRE"):
            if open_trade:
                closed = await self._close_basket_trade(
                    basket, open_trade, current_z, signal.signal_type, current_prices
                )
                action = f"CLOSE ({signal.signal_type})" if closed else "CLOSE_FAILED"

        return {
            "basket": name,
            "status": "OK",
            "z_score": round(current_z, 4),
            "signal": signal.signal_type,
            "action": action,
        }

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _load_active_baskets(self) -> List[BasketRegistry]:
        with db_readonly_session() as session:
            baskets = (
                session.query(BasketRegistry)
                .filter(BasketRegistry.is_active.is_(True))
                .all()
            )
            for b in baskets:
                session.expunge(b)
            return baskets

    def _get_open_trade(self, basket: BasketRegistry) -> Optional[BasketTrade]:
        with db_readonly_session() as session:
            trade = (
                session.query(BasketTrade)
                .filter(
                    BasketTrade.basket_id == basket.id,
                    BasketTrade.status == "OPEN",
                )
                .order_by(BasketTrade.entry_time.desc())
                .first()
            )
            if trade:
                session.expunge(trade)
            return trade

    def _store_spread(
        self,
        basket: BasketRegistry,
        spread_series: pd.Series,
        z_series: pd.Series,
        prices: Dict[str, pd.Series],
        weights: List[float],
    ) -> None:
        if spread_series.empty:
            return
        last_ts = spread_series.index[-1]
        prices_snapshot = {
            sym: round(float(prices[sym].iloc[-1]), 4)
            for sym in basket.symbols or []
            if sym in prices and not prices[sym].empty
        }
        ts = last_ts.to_pydatetime()
        with db_transaction() as session:
            exists = (
                session.query(BasketSpread)
                .filter(
                    BasketSpread.basket_id == basket.id,
                    BasketSpread.timestamp == ts,
                )
                .first()
            )
            if exists:
                logger.debug(
                    f"Spread for basket {basket.id} at {ts} already stored - skipping"
                )
                return
            row = BasketSpread(
                basket_id=basket.id,
                timestamp=ts,
                prices=prices_snapshot,
                spread=float(spread_series.iloc[-1]),
                z_score=(float(z_series.iloc[-1]) if not z_series.empty else None),
                hedge_weights=weights,
            )
            session.add(row)

    def _open_basket_trade(
        self,
        basket: BasketRegistry,
        side: str,
        legs: List[Dict],
        entry_z: float,
    ) -> Optional[BasketTrade]:
        trade = BasketTrade(
            basket_id=basket.id,
            entry_time=datetime.now(timezone.utc),
            entry_z_score=round(entry_z, 4),
            side=side,
            legs=legs,
            status="OPEN",
        )
        with db_transaction() as session:
            session.add(trade)
            session.flush()
            session.expunge(trade)
        return trade

    async def _place_basket_orders(self, legs: List[Dict]) -> List[Dict]:
        """Submit one Alpaca market order per leg."""
        for leg in legs:
            try:
                order = await self.alpaca.place_order(
                    symbol=leg["symbol"],
                    qty=leg["qty"],
                    side=leg["side"],
                    order_type="market",
                    time_in_force="day",
                )
                leg["order_id"] = order.get("id")
            except Exception as exc:
                logger.error(f"Order failed for {leg['symbol']}: {exc}")
                leg["order_id"] = None
        return legs

    async def _close_basket_trade(
        self,
        basket: BasketRegistry,
        trade: BasketTrade,
        exit_z: float,
        exit_reason: str,
        current_prices: Dict[str, Optional[float]],
    ) -> bool:
        exit_legs = []
        for leg in trade.legs or []:
            sym = leg["symbol"]
            close_side = "sell" if leg["side"] == "buy" else "buy"
            price = current_prices.get(sym)
            try:
                order = await self.alpaca.place_order(
                    symbol=sym,
                    qty=leg["qty"],
                    side=close_side,
                    order_type="market",
                    time_in_force="day",
                )
                exit_legs.append(
                    {
                        "symbol": sym,
                        "exit_price": round(price, 4) if price else None,
                        "order_id": order.get("id"),
                    }
                )
            except Exception as exc:
                logger.error(f"Close order failed for {sym}: {exc}")
                return False

        # Compute simple P&L: sum over legs of (exit-entry)*qty * direction
        pnl = 0.0
        for leg, el in zip(trade.legs or [], exit_legs):
            ep = leg.get("entry_price") or 0.0
            xp = el.get("exit_price") or 0.0
            qty = leg.get("qty", 0)
            sign = 1 if leg["side"] == "buy" else -1
            pnl += sign * qty * (xp - ep)

        total_invested = sum(
            (leg.get("entry_price") or 0.0) * leg.get("qty", 0)
            for leg in (trade.legs or [])
        )
        pnl_pct = pnl / total_invested if total_invested > 0 else 0.0

        now = datetime.now(timezone.utc)
        with db_transaction() as session:
            db_trade = session.get(BasketTrade, trade.id)
            if db_trade:
                db_trade.exit_time = now
                db_trade.exit_z_score = round(exit_z, 4)
                db_trade.exit_reason = exit_reason
                db_trade.exit_legs = exit_legs  # type: ignore[assignment]
                db_trade.pnl = round(pnl, 4)
                db_trade.pnl_pct = round(pnl_pct, 6)
                db_trade.status = "STOPPED" if exit_reason == "STOP_LOSS" else "CLOSED"

        return True
