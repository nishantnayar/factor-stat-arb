"""
Factor Backtest Engine

Replays historical hourly bars through an N-leg factor-residual basket's
spread/z-score/signal logic and simulates fills to evaluate performance.

Design (mirrors src/services/strategy_engine/backtesting/engine.py, but
generalized from 2-leg pairs to N-leg baskets):
    - Pulls hourly OHLCV from data_ingestion.market_data (DB only - no API calls)
    - Uses BasketSpreadCalculator in-memory (no DB writes during replay)
    - Uses BacktestSignalGenerator (stateless) directly against BasketRegistry,
      since BasketRegistry already exposes entry_threshold/exit_threshold/
      stop_loss_threshold/max_hold_hours under those exact names - no shim needed
    - Fills are simulated at the signal bar's price, worsened by slippage_bps
    - All results passed to MetricsCalculator; optionally saved via
      FactorBacktestReport

Usage:
    from src.services.strategy_engine.factor_stat_arb.backtest_engine import (
        FactorBacktestEngine,
    )
    from src.shared.database.models.basket_models import BasketRegistry

    engine = FactorBacktestEngine(basket, start_date, end_date)
    result = engine.run()
    # result is a FactorBacktestResult, compatible with MetricsCalculator
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
from loguru import logger

from src.services.strategy_engine.baskets.spread_calculator import (
    BasketSpreadCalculator,
)
from src.services.strategy_engine.pairs.signal_generator import BacktestSignalGenerator
from src.shared.database.base import db_readonly_session
from src.shared.database.models.basket_models import BasketRegistry
from src.shared.database.models.market_data import MarketData

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SimulatedBasketTrade:
    """A single simulated round-trip N-leg basket trade."""

    side: str  # LONG_SPREAD or SHORT_SPREAD
    entry_time: datetime
    entry_z: float
    entry_prices: Dict[str, float]
    qty: Dict[str, float]
    exit_time: Optional[datetime] = None
    exit_z: Optional[float] = None
    exit_prices: Optional[Dict[str, float]] = None
    exit_reason: Optional[str] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    hold_hours: Optional[float] = None


@dataclass
class FactorBacktestResult:
    """
    Raw output of FactorBacktestEngine.run() before metrics are computed.

    Shape-compatible with MetricsCalculator.compute(), which only reads
    trades / equity_curve / initial_capital / start_date / end_date.
    """

    basket_id: int
    basket_name: str
    symbols: List[str]
    hedge_weights: List[float]
    start_date: date
    end_date: date
    initial_capital: float
    entry_threshold: float
    exit_threshold: float
    stop_loss_threshold: float
    z_score_window: int
    slippage_bps: float = 5.0
    commission_per_trade: float = 0.0
    trades: List[SimulatedBasketTrade] = field(default_factory=list)
    equity_curve: List[dict] = field(default_factory=list)  # [{timestamp, equity}]
    bars_processed: int = 0


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class FactorBacktestEngine:
    """
    Simulates the factor-residual basket strategy on historical data.

    Args:
        basket:            BasketRegistry row (already populated with thresholds)
        start_date:        First bar date (inclusive)
        end_date:          Last bar date (inclusive)
        initial_capital:   Starting portfolio equity in USD
        data_source:       Market data source label in DB
    """

    def __init__(
        self,
        basket: BasketRegistry,
        start_date: date,
        end_date: date,
        initial_capital: float = 100_000.0,
        data_source: str = "yahoo_adjusted",
        slippage_bps: float = 5.0,
        commission_per_trade: float = 0.0,
    ):
        self.basket = basket
        self.symbols: List[str] = list(basket.symbols or [])
        weights_by_symbol: Dict[str, float] = basket.hedge_weights or {}
        self.hedge_weights: List[float] = [
            float(weights_by_symbol[s]) for s in self.symbols
        ]
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.data_source = data_source
        self.slippage_bps = slippage_bps
        self.commission_per_trade = commission_per_trade

        self._calc = BasketSpreadCalculator(
            symbols=self.symbols,
            hedge_weights=self.hedge_weights,
            z_score_window=int(basket.z_score_window),
        )
        self._sig_gen = BacktestSignalGenerator(basket)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self) -> FactorBacktestResult:
        """
        Execute the backtest and return a FactorBacktestResult.

        Returns:
            FactorBacktestResult with trades, equity curve, and metadata.
            Pass to MetricsCalculator to get performance metrics.
        """
        logger.info(
            f"Starting factor backtest: {self.basket.name} {self.symbols} "
            f"{self.start_date} -> {self.end_date}"
        )

        prices = self._load_prices()
        missing = [s for s in self.symbols if prices[s].empty]
        if missing:
            logger.warning(f"No price data for {missing} in basket {self.basket.name}")
            return self._empty_result()

        aligned = pd.concat(prices, axis=1).dropna()
        aligned.columns = pd.Index(self.symbols)

        if len(aligned) < self.basket.z_score_window:
            logger.warning(
                f"Insufficient bars: {len(aligned)} < window {self.basket.z_score_window}"
            )
            return self._empty_result()

        return self._replay(aligned)

    # ------------------------------------------------------------------
    # Price loading
    # ------------------------------------------------------------------

    def _load_prices(self) -> Dict[str, pd.Series]:
        """Fetch hourly close prices from DB for all basket symbols."""
        buffer_days = max(int(self.basket.z_score_window / 6.5) + 5, 30)
        fetch_start = self.start_date - timedelta(days=buffer_days)

        with db_readonly_session() as session:
            rows = (
                session.query(
                    MarketData.symbol,
                    MarketData.timestamp,
                    MarketData.close,
                )
                .filter(
                    MarketData.symbol.in_(self.symbols),
                    MarketData.data_source == self.data_source,
                    MarketData.timestamp
                    >= datetime.combine(fetch_start, datetime.min.time()),
                    MarketData.timestamp
                    <= datetime.combine(
                        self.end_date + timedelta(days=1), datetime.min.time()
                    ),
                    MarketData.close.isnot(None),
                )
                .order_by(MarketData.timestamp)
                .all()
            )

        if not rows:
            return {sym: pd.Series(dtype=float) for sym in self.symbols}

        df = pd.DataFrame(rows, columns=["symbol", "timestamp", "close"])
        df["close"] = df["close"].astype(float)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

        prices = {}
        for sym in self.symbols:
            s = df[df["symbol"] == sym].set_index("timestamp")["close"]
            prices[sym] = s
            logger.info(f"Loaded {len(s)} bars for {sym}")
        return prices

    # ------------------------------------------------------------------
    # Bar-by-bar replay
    # ------------------------------------------------------------------

    def _replay(self, aligned: pd.DataFrame) -> FactorBacktestResult:
        """Iterate through bars chronologically, generating signals and fills."""
        result = FactorBacktestResult(
            basket_id=self.basket.id,
            basket_name=self.basket.name,
            symbols=self.symbols,
            hedge_weights=self.hedge_weights,
            start_date=self.start_date,
            end_date=self.end_date,
            initial_capital=self.initial_capital,
            entry_threshold=float(self.basket.entry_threshold),
            exit_threshold=float(self.basket.exit_threshold),
            stop_loss_threshold=float(self.basket.stop_loss_threshold),
            z_score_window=int(self.basket.z_score_window),
            slippage_bps=self.slippage_bps,
            commission_per_trade=self.commission_per_trade,
        )

        open_trade: Optional[SimulatedBasketTrade] = None
        equity = self.initial_capital
        realized_pnl = 0.0

        prices_dict = {sym: aligned[sym] for sym in self.symbols}
        _, z_series, _ = self._calc.calculate(prices_dict)

        start_dt = pd.Timestamp(self.start_date, tz="UTC")
        end_dt = pd.Timestamp(self.end_date, tz="UTC") + pd.Timedelta(days=1)

        bars = aligned[(aligned.index >= start_dt) & (aligned.index < end_dt)]

        for ts in bars.index:
            row = bars.loc[ts]
            if ts not in z_series.index:
                continue
            z_raw = z_series.loc[ts]
            if pd.isna(z_raw):
                continue
            z = float(z_raw)
            snapshot = {sym: float(row[sym]) for sym in self.symbols}

            open_entry_time = open_trade.entry_time if open_trade else None
            signal_type, _reason = self._sig_gen.evaluate(
                z, open_entry_time, ts.to_pydatetime()
            )

            if signal_type is None:
                result.equity_curve.append(
                    {
                        "timestamp": ts.isoformat(),
                        "equity": equity
                        + realized_pnl
                        + _unrealized_pnl(open_trade, snapshot, self.hedge_weights),
                    }
                )
                result.bars_processed += 1
                continue

            if signal_type in ("LONG_SPREAD", "SHORT_SPREAD") and open_trade is None:
                entry_prices, qty = self._open_legs(signal_type, snapshot, equity)
                open_trade = SimulatedBasketTrade(
                    side=signal_type,
                    entry_time=ts.to_pydatetime(),
                    entry_z=z,
                    entry_prices=entry_prices,
                    qty=qty,
                )

            elif (
                signal_type in ("EXIT", "STOP_LOSS", "EXPIRE")
                and open_trade is not None
            ):
                exit_prices = self._close_legs(open_trade, snapshot)
                pnl, pnl_pct = _compute_pnl(
                    open_trade,
                    exit_prices,
                    self.hedge_weights,
                    self.commission_per_trade,
                )
                open_trade.exit_time = ts.to_pydatetime()
                open_trade.exit_z = z
                open_trade.exit_prices = exit_prices
                open_trade.exit_reason = signal_type
                open_trade.pnl = pnl
                open_trade.pnl_pct = pnl_pct
                hold_delta = ts.to_pydatetime() - open_trade.entry_time
                open_trade.hold_hours = hold_delta.total_seconds() / 3600

                realized_pnl += pnl
                equity += pnl
                result.trades.append(open_trade)
                open_trade = None

            result.equity_curve.append(
                {
                    "timestamp": ts.isoformat(),
                    "equity": equity
                    + _unrealized_pnl(open_trade, snapshot, self.hedge_weights),
                }
            )
            result.bars_processed += 1

        if open_trade is not None and len(bars) > 0:
            last_ts = bars.index[-1]
            last_snapshot = {sym: float(bars[sym].iloc[-1]) for sym in self.symbols}
            exit_prices = self._close_legs(open_trade, last_snapshot)
            pnl, pnl_pct = _compute_pnl(
                open_trade, exit_prices, self.hedge_weights, self.commission_per_trade
            )
            open_trade.exit_time = last_ts.to_pydatetime()
            open_trade.exit_z = (
                float(z_series.loc[last_ts]) if last_ts in z_series.index else None
            )
            open_trade.exit_prices = exit_prices
            open_trade.exit_reason = "END_OF_BACKTEST"
            open_trade.pnl = pnl
            open_trade.pnl_pct = pnl_pct
            hold_delta = last_ts.to_pydatetime() - open_trade.entry_time
            open_trade.hold_hours = hold_delta.total_seconds() / 3600
            result.trades.append(open_trade)

        logger.info(
            f"Factor backtest complete: {result.bars_processed} bars, "
            f"{len(result.trades)} trades"
        )
        return result

    # ------------------------------------------------------------------
    # Leg sizing / fills
    # ------------------------------------------------------------------

    def _open_legs(
        self, signal_type: str, snapshot: Dict[str, float], equity: float
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        Size and fill each leg proportional to |hedge_weight_i|, sharing a
        fixed 2%-of-equity total allocation (mirrors BasketStrategy's
        sizing-by-weight convention).

        Sign convention: LONG_SPREAD follows the hedge-weight sign as-is
        (positive weight = buy, negative = sell); SHORT_SPREAD flips it.
        """
        allocation = equity * 0.02
        abs_weights = [abs(w) for w in self.hedge_weights]
        total_abs_w = sum(abs_weights) or 1.0

        entry_prices: Dict[str, float] = {}
        qty: Dict[str, float] = {}
        for sym, w, abs_w in zip(self.symbols, self.hedge_weights, abs_weights):
            effective_w = -w if signal_type == "SHORT_SPREAD" else w
            is_buy = effective_w > 0
            price = self._slipped_price(snapshot[sym], is_buy=is_buy)
            entry_prices[sym] = price
            dollar_value = allocation * (abs_w / total_abs_w)
            qty[sym] = dollar_value / price
        return entry_prices, qty

    def _close_legs(
        self, trade: SimulatedBasketTrade, snapshot: Dict[str, float]
    ) -> Dict[str, float]:
        """Fill each leg at the reverse side of its entry direction."""
        exit_prices: Dict[str, float] = {}
        for sym, w in zip(self.symbols, self.hedge_weights):
            effective_w = -w if trade.side == "SHORT_SPREAD" else w
            was_buy = effective_w > 0
            exit_prices[sym] = self._slipped_price(snapshot[sym], is_buy=not was_buy)
        return exit_prices

    def _slipped_price(self, price: float, is_buy: bool) -> float:
        """Worsen a fill price by slippage_bps basis points."""
        factor = self.slippage_bps / 10_000
        return price * (1 + factor) if is_buy else price * (1 - factor)

    # ------------------------------------------------------------------

    def _empty_result(self) -> FactorBacktestResult:
        return FactorBacktestResult(
            basket_id=self.basket.id,
            basket_name=self.basket.name,
            symbols=self.symbols,
            hedge_weights=self.hedge_weights,
            start_date=self.start_date,
            end_date=self.end_date,
            initial_capital=self.initial_capital,
            entry_threshold=float(self.basket.entry_threshold),
            exit_threshold=float(self.basket.exit_threshold),
            stop_loss_threshold=float(self.basket.stop_loss_threshold),
            z_score_window=int(self.basket.z_score_window),
            slippage_bps=self.slippage_bps,
            commission_per_trade=self.commission_per_trade,
        )


# ---------------------------------------------------------------------------
# P&L helpers
# ---------------------------------------------------------------------------


def _compute_pnl(
    trade: SimulatedBasketTrade,
    exit_prices: Dict[str, float],
    hedge_weights: List[float],
    commission: float = 0.0,
) -> Tuple[float, float]:
    """
    Compute P&L for closing an N-leg trade.

    Each leg's direction follows the sign of its hedge weight (flipped for
    SHORT_SPREAD, matching _open_legs/_close_legs). A "buy" leg profits when
    price rises; a "sell" leg profits when price falls.

    commission is a flat dollar cost deducted from the gross P&L.
    """
    symbols = list(trade.entry_prices.keys())
    pnl = 0.0
    for sym, w in zip(symbols, hedge_weights):
        effective_w = -w if trade.side == "SHORT_SPREAD" else w
        sign = 1.0 if effective_w > 0 else -1.0
        d = exit_prices[sym] - trade.entry_prices[sym]
        pnl += sign * trade.qty[sym] * d

    pnl -= commission

    entry_cost = sum(trade.qty[s] * trade.entry_prices[s] for s in symbols)
    pnl_pct = (pnl / entry_cost * 100) if entry_cost > 0 else 0.0
    return pnl, pnl_pct


def _unrealized_pnl(
    trade: Optional[SimulatedBasketTrade],
    current_snapshot: Dict[str, float],
    hedge_weights: List[float],
) -> float:
    """Mark-to-market P&L for an open trade (used for equity curve)."""
    if trade is None:
        return 0.0
    pnl, _ = _compute_pnl(trade, current_snapshot, hedge_weights)
    return float(pnl)
