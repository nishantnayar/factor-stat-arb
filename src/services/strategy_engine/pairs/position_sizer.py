"""
Position Sizer - Kelly Criterion

Determines the number of shares to trade for each leg of a pair.

Two-phase approach:
    Bootstrap (< 20 closed trades): Fixed 2% of portfolio per leg
    Full Kelly  (>= 20 closed trades): Half-Kelly based on historical win rate

Half-Kelly formula:
    win_rate  = winning_trades / total_trades
    avg_win   = mean(pnl_pct) across winning trades
    avg_loss  = mean(|pnl_pct|) across losing trades
    kelly_f   = win_rate - (1 - win_rate) / (avg_win / avg_loss)
    half_kelly = kelly_f / 2

    per_leg_capital = half_kelly * portfolio_equity / 2  (split across 2 legs)
    qty = floor(per_leg_capital / current_price)

Hard limits (always enforced):
    - Minimum: 1 share per leg
    - Maximum: 12% of portfolio per leg
"""

import math
from typing import Tuple

from loguru import logger

from src.shared.database.base import db_readonly_session
from src.shared.database.models.strategy_models import PairRegistry, PairTrade

# Bootstrap threshold
BOOTSTRAP_TRADES = 20

# Fixed fraction during bootstrap
BOOTSTRAP_FRACTION = 0.02   # 2% per leg

# Hard cap per leg
MAX_LEG_FRACTION = 0.12     # 12% per leg


class KellySizer:
    """
    Calculates position size for a pair trade using Kelly criterion.

    Usage:
        sizer = KellySizer(pair)
        qty1, qty2 = sizer.calculate_size(
            portfolio_equity=100_000,
            price1=150.25,
            price2=200.10,
        )
    """

    def __init__(self, pair: PairRegistry):
        self.pair = pair

    def calculate_size(
        self,
        portfolio_equity: float,
        price1: float,
        price2: float,
    ) -> Tuple[int, int]:
        """
        Calculate integer share quantities for both legs.

        Args:
            portfolio_equity: Total portfolio value in USD
            price1:           Current price of symbol1
            price2:           Current price of symbol2

        Returns:
            (qty1, qty2) - integer share counts, each >= 1
        """
        fraction = self._compute_fraction()
        per_leg_capital = fraction * portfolio_equity / 2

        qty1 = max(1, math.floor(per_leg_capital / price1))
        qty2 = max(1, math.floor(per_leg_capital / price2))

        # Hard cap: no more than MAX_LEG_FRACTION of portfolio per leg
        max_qty1 = max(1, math.floor(MAX_LEG_FRACTION * portfolio_equity / price1))
        max_qty2 = max(1, math.floor(MAX_LEG_FRACTION * portfolio_equity / price2))

        qty1 = min(qty1, max_qty1)
        qty2 = min(qty2, max_qty2)

        logger.debug(
            f"KellySizer [{self.pair.symbol1}/{self.pair.symbol2}]: "
            f"fraction={fraction:.4f}, qty1={qty1}, qty2={qty2}"
        )
        return qty1, qty2

    # ------------------------------------------------------------------

    def _compute_fraction(self) -> float:
        """
        Determine the Kelly fraction based on trade history.

        Returns 2% (bootstrap) if fewer than BOOTSTRAP_TRADES completed trades,
        otherwise Half-Kelly clamped to [0.01, MAX_LEG_FRACTION * 2].
        """
        trades = self._load_closed_trades()
        total = len(trades)

        if total < BOOTSTRAP_TRADES:
            logger.debug(
                f"Bootstrap mode: {total}/{BOOTSTRAP_TRADES} trades - "
                f"using fixed {BOOTSTRAP_FRACTION*100:.0f}%"
            )
            return BOOTSTRAP_FRACTION

        wins = [t for t in trades if (t.pnl_pct or 0) > 0]
        losses = [t for t in trades if (t.pnl_pct or 0) <= 0]

        if not wins or not losses:
            logger.debug("No wins or losses yet - using bootstrap fraction")
            return BOOTSTRAP_FRACTION

        win_rate = len(wins) / total
        avg_win = sum(t.pnl_pct for t in wins) / len(wins)
        avg_loss = abs(sum(t.pnl_pct for t in losses) / len(losses))

        if avg_loss == 0:
            return BOOTSTRAP_FRACTION

        kelly = win_rate - (1 - win_rate) / (avg_win / avg_loss)
        half_kelly = kelly / 2

        # Apply per-pair allocation cap if configured (Control C)
        if (
            hasattr(self.pair, "max_allocation_pct")
            and self.pair.max_allocation_pct is not None
        ):
            cap = float(self.pair.max_allocation_pct)
            if half_kelly > cap:
                logger.debug(
                    f"Per-pair allocation cap applied: "
                    f"half_kelly={half_kelly:.4f} -> {cap:.4f}"
                )
                half_kelly = cap

        # Clamp: minimum 1%, maximum (2 x MAX_LEG_FRACTION) across both legs combined
        half_kelly = max(0.01, min(MAX_LEG_FRACTION * 2, half_kelly))

        logger.debug(
            f"Full Kelly mode: win_rate={win_rate:.2f}, "
            f"avg_win={avg_win:.2f}%, avg_loss={avg_loss:.2f}%, "
            f"kelly={kelly:.4f}, half_kelly={half_kelly:.4f}"
        )
        return float(half_kelly)

    def _load_closed_trades(self) -> list:
        """Load completed trades for this pair from the DB."""
        with db_readonly_session() as session:
            trades = (
                session.query(PairTrade)
                .filter(
                    PairTrade.pair_id == self.pair.id,
                    PairTrade.status.in_(["CLOSED", "STOPPED"]),
                    PairTrade.pnl_pct.isnot(None),
                )
                .order_by(PairTrade.exit_time.desc())
                .limit(100)  # Use most recent 100 trades for Kelly calc
                .all()
            )
            for t in trades:
                session.expunge(t)
            return trades
