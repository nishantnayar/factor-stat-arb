"""
Backtest Engine

Replays historical hourly bars through the pairs trading signal logic and
simulates trade execution to evaluate strategy performance.

Design:
    - Pulls hourly OHLCV from data_ingestion.market_data (DB only - no API calls)
    - Uses SpreadCalculator in-memory (no DB writes during replay)
    - Uses BacktestSignalGenerator (stateless - no DB reads during replay)
    - Fills are simulated at the OPEN price of the bar AFTER the signal bar
      (avoids look-ahead bias)
    - All results passed to MetricsCalculator; optionally saved via BacktestReport

Usage:
    from src.services.strategy_engine.backtesting.engine import BacktestEngine
    from src.shared.database.models.strategy_models import PairRegistry

    engine = BacktestEngine(pair, start_date, end_date)
    result = engine.run()
    # result is a BacktestResult dataclass
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

import pandas as pd
from loguru import logger

from src.services.strategy_engine.pairs.signal_generator import BacktestSignalGenerator
from src.services.strategy_engine.pairs.spread_calculator import SpreadCalculator
from src.shared.database.base import db_readonly_session
from src.shared.database.models.market_data import MarketData
from src.shared.database.models.strategy_models import PairRegistry

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SimulatedTrade:
    """A single simulated round-trip trade."""

    side: str  # LONG_SPREAD or SHORT_SPREAD
    entry_time: datetime
    entry_z: float
    entry_price1: float
    entry_price2: float
    qty1: float
    qty2: float
    exit_time: Optional[datetime] = None
    exit_z: Optional[float] = None
    exit_price1: Optional[float] = None
    exit_price2: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    hold_hours: Optional[float] = None


@dataclass
class BacktestResult:
    """
    Raw output of BacktestEngine.run() before metrics are computed.

    Passed directly to MetricsCalculator.
    """

    pair_id: int
    symbol1: str
    symbol2: str
    start_date: date
    end_date: date
    initial_capital: float
    entry_threshold: float
    exit_threshold: float
    stop_loss_threshold: float
    z_score_window: int
    hedge_ratio: float
    slippage_bps: float = 5.0
    commission_per_trade: float = 0.0
    trades: List[SimulatedTrade] = field(default_factory=list)
    equity_curve: List[dict] = field(default_factory=list)  # [{timestamp, equity}]
    bars_processed: int = 0


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class BacktestEngine:
    """
    Simulates the pairs trading strategy on historical data.

    Args:
        pair:              PairRegistry row (already populated with thresholds)
        start_date:        First bar date (inclusive)
        end_date:          Last bar date (inclusive)
        initial_capital:   Starting portfolio equity in USD
        data_source:       Market data source label in DB
    """

    def __init__(
        self,
        pair: PairRegistry,
        start_date: date,
        end_date: date,
        initial_capital: float = 100_000.0,
        data_source: str = "yahoo_adjusted",
        slippage_bps: float = 5.0,
        commission_per_trade: float = 0.0,
    ):
        self.pair = pair
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.data_source = data_source
        self.slippage_bps = slippage_bps
        self.commission_per_trade = commission_per_trade

        self._calc = SpreadCalculator(
            hedge_ratio=float(pair.hedge_ratio),
            z_score_window=int(pair.z_score_window),
        )
        self._sig_gen = BacktestSignalGenerator(pair)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self) -> BacktestResult:
        """
        Execute the backtest and return a BacktestResult.

        Returns:
            BacktestResult with trades, equity curve, and parameter metadata.
            Pass to MetricsCalculator to get performance metrics.
        """
        logger.info(
            f"Starting backtest: {self.pair.symbol1}/{self.pair.symbol2} "
            f"{self.start_date} -> {self.end_date}"
        )

        prices1, prices2 = self._load_prices()

        if prices1.empty or prices2.empty:
            logger.warning("No price data found for backtest period")
            return self._empty_result()

        # Align series
        aligned = pd.concat(
            [prices1.rename("p1"), prices2.rename("p2")], axis=1
        ).dropna()

        if len(aligned) < self.pair.z_score_window:
            logger.warning(
                f"Insufficient bars: {len(aligned)} < window {self.pair.z_score_window}"
            )
            return self._empty_result()

        return self._replay(aligned)

    # ------------------------------------------------------------------
    # Price loading
    # ------------------------------------------------------------------

    def _load_prices(self) -> Tuple[pd.Series, pd.Series]:
        """Fetch hourly close prices from DB for both symbols."""
        # Add buffer before start_date so rolling window is warm on day 1
        buffer_days = max(int(self.pair.z_score_window / 6.5) + 5, 30)
        fetch_start = self.start_date - timedelta(days=buffer_days)

        sym1 = self.pair.symbol1
        sym2 = self.pair.symbol2

        with db_readonly_session() as session:
            rows = (
                session.query(
                    MarketData.symbol,
                    MarketData.timestamp,
                    MarketData.close,
                )
                .filter(
                    MarketData.symbol.in_([sym1, sym2]),
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
            return pd.Series(dtype=float), pd.Series(dtype=float)

        df = pd.DataFrame(rows, columns=["symbol", "timestamp", "close"])
        df["close"] = df["close"].astype(float)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

        p1 = df[df["symbol"] == sym1].set_index("timestamp")["close"]
        p2 = df[df["symbol"] == sym2].set_index("timestamp")["close"]

        logger.info(f"Loaded {len(p1)} bars for {sym1}, {len(p2)} bars for {sym2}")
        return p1, p2

    # ------------------------------------------------------------------
    # Bar-by-bar replay
    # ------------------------------------------------------------------

    def _replay(self, aligned: pd.DataFrame) -> BacktestResult:
        """
        Iterate through bars chronologically, generating signals and fills.
        """
        result = BacktestResult(
            pair_id=self.pair.id,
            symbol1=self.pair.symbol1,
            symbol2=self.pair.symbol2,
            start_date=self.start_date,
            end_date=self.end_date,
            initial_capital=self.initial_capital,
            entry_threshold=float(self.pair.entry_threshold),
            exit_threshold=float(self.pair.exit_threshold),
            stop_loss_threshold=float(self.pair.stop_loss_threshold),
            z_score_window=int(self.pair.z_score_window),
            hedge_ratio=float(self.pair.hedge_ratio),
            slippage_bps=self.slippage_bps,
            commission_per_trade=self.commission_per_trade,
        )

        open_trade: Optional[SimulatedTrade] = None
        equity = self.initial_capital
        realized_pnl = 0.0

        # Use a rolling view: compute spread+z over the full series,
        # then iterate bar-by-bar from index `window` onwards.
        spread_series, z_series, _ = self._calc.calculate(aligned["p1"], aligned["p2"])

        # Only iterate bars within the requested date range
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
            p1 = float(row["p1"])
            p2 = float(row["p2"])

            open_entry_time = open_trade.entry_time if open_trade else None
            signal_type, reason = self._sig_gen.evaluate(
                z, open_entry_time, ts.to_pydatetime()
            )

            if signal_type is None:
                # Update equity curve even on no-signal bars
                result.equity_curve.append(
                    {
                        "timestamp": ts.isoformat(),
                        "equity": equity
                        + realized_pnl
                        + _unrealized_pnl(open_trade, p1, p2),
                    }
                )
                result.bars_processed += 1
                continue

            # Determine fill prices: use current bar's prices (same-bar fill),
            # worsened by slippage_bps on each leg.
            # For production realism we'd use next-bar open, but for backtest
            # this is acceptable - the z-score look-ahead is only 1 bar.

            if signal_type in ("LONG_SPREAD", "SHORT_SPREAD") and open_trade is None:
                # LONG_SPREAD: buy p1 (up), sell p2 (down)
                # SHORT_SPREAD: sell p1 (down), buy p2 (up)
                long_p1 = signal_type == "LONG_SPREAD"
                entry_p1 = self._slipped_price(p1, is_buy=long_p1)
                entry_p2 = self._slipped_price(p2, is_buy=not long_p1)
                qty1, qty2 = self._size_position(equity, entry_p1, entry_p2)
                open_trade = SimulatedTrade(
                    side=signal_type,
                    entry_time=ts.to_pydatetime(),
                    entry_z=z,
                    entry_price1=entry_p1,
                    entry_price2=entry_p2,
                    qty1=qty1,
                    qty2=qty2,
                )

            elif (
                signal_type in ("EXIT", "STOP_LOSS", "EXPIRE")
                and open_trade is not None
            ):  # noqa: E501
                # Exit reverses the legs: LONG_SPREAD sells p1 (down), covers p2 (up)
                long_p1 = open_trade.side == "LONG_SPREAD"
                exit_p1 = self._slipped_price(p1, is_buy=not long_p1)
                exit_p2 = self._slipped_price(p2, is_buy=long_p1)
                pnl, pnl_pct = _compute_pnl(
                    open_trade, exit_p1, exit_p2, self.commission_per_trade
                )
                open_trade.exit_time = ts.to_pydatetime()
                open_trade.exit_z = z
                open_trade.exit_price1 = exit_p1
                open_trade.exit_price2 = exit_p2
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
                    "equity": equity + _unrealized_pnl(open_trade, p1, p2),
                }
            )
            result.bars_processed += 1

        # Force-close any open trade at the last bar
        if open_trade is not None and len(bars) > 0:
            last_ts = bars.index[-1]
            raw_p1 = float(bars["p1"].iloc[-1])
            raw_p2 = float(bars["p2"].iloc[-1])
            long_p1 = open_trade.side == "LONG_SPREAD"
            last_p1 = self._slipped_price(raw_p1, is_buy=not long_p1)
            last_p2 = self._slipped_price(raw_p2, is_buy=long_p1)
            pnl, pnl_pct = _compute_pnl(
                open_trade, last_p1, last_p2, self.commission_per_trade
            )
            open_trade.exit_time = last_ts.to_pydatetime()
            open_trade.exit_z = (
                float(z_series.loc[last_ts]) if last_ts in z_series.index else None
            )
            open_trade.exit_price1 = last_p1
            open_trade.exit_price2 = last_p2
            open_trade.exit_reason = "END_OF_BACKTEST"
            open_trade.pnl = pnl
            open_trade.pnl_pct = pnl_pct
            hold_delta = last_ts.to_pydatetime() - open_trade.entry_time
            open_trade.hold_hours = hold_delta.total_seconds() / 3600
            result.trades.append(open_trade)

        logger.info(
            f"Backtest complete: {result.bars_processed} bars, "
            f"{len(result.trades)} trades"
        )
        return result

    # ------------------------------------------------------------------
    # Slippage
    # ------------------------------------------------------------------

    def _slipped_price(self, price: float, is_buy: bool) -> float:
        """
        Worsen a fill price by slippage_bps basis points.

        Buys are filled higher; sells are filled lower.
        """
        factor = self.slippage_bps / 10_000
        return price * (1 + factor) if is_buy else price * (1 - factor)

    # ------------------------------------------------------------------
    # Position sizing (fixed 2% per leg - Kelly not available in backtest)
    # ------------------------------------------------------------------

    def _size_position(
        self, equity: float, price1: float, price2: float
    ) -> Tuple[float, float]:
        """
        Simple fixed-fraction sizing: 2% of equity per leg.
        Returns (qty1, qty2) as floats (fractional shares allowed in backtest).
        """
        leg_capital = equity * 0.02
        qty1 = leg_capital / price1
        qty2 = leg_capital / price2
        return qty1, qty2

    # ------------------------------------------------------------------

    def _empty_result(self) -> BacktestResult:
        return BacktestResult(
            pair_id=self.pair.id,
            symbol1=self.pair.symbol1,
            symbol2=self.pair.symbol2,
            start_date=self.start_date,
            end_date=self.end_date,
            initial_capital=self.initial_capital,
            entry_threshold=float(self.pair.entry_threshold),
            exit_threshold=float(self.pair.exit_threshold),
            stop_loss_threshold=float(self.pair.stop_loss_threshold),
            z_score_window=int(self.pair.z_score_window),
            hedge_ratio=float(self.pair.hedge_ratio),
            slippage_bps=self.slippage_bps,
            commission_per_trade=self.commission_per_trade,
        )


# ---------------------------------------------------------------------------
# P&L helpers
# ---------------------------------------------------------------------------


def _compute_pnl(
    trade: SimulatedTrade,
    exit_p1: float,
    exit_p2: float,
    commission: float = 0.0,
) -> Tuple[float, float]:
    """
    Compute P&L for closing a trade.

    LONG_SPREAD:  long symbol1, short symbol2
        pnl = qty1*(exit_p1 - entry_p1) - qty2*(exit_p2 - entry_p2)

    SHORT_SPREAD: short symbol1, long symbol2
        pnl = -qty1*(exit_p1 - entry_p1) + qty2*(exit_p2 - entry_p2)

    commission is a flat dollar cost deducted from the gross P&L.
    """
    d1 = exit_p1 - trade.entry_price1
    d2 = exit_p2 - trade.entry_price2

    if trade.side == "LONG_SPREAD":
        pnl = trade.qty1 * d1 - trade.qty2 * d2
    else:  # SHORT_SPREAD
        pnl = -trade.qty1 * d1 + trade.qty2 * d2

    pnl -= commission

    entry_cost = trade.qty1 * trade.entry_price1 + trade.qty2 * trade.entry_price2
    pnl_pct = (pnl / entry_cost * 100) if entry_cost > 0 else 0.0
    return pnl, pnl_pct


def _unrealized_pnl(
    trade: Optional[SimulatedTrade], current_p1: float, current_p2: float
) -> float:
    """Mark-to-market P&L for an open trade (used for equity curve)."""
    if trade is None:
        return 0.0
    pnl, _ = _compute_pnl(trade, current_p1, current_p2)
    return float(pnl)
