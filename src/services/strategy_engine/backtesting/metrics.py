"""
Backtest Metrics Calculator

Computes performance statistics from a BacktestResult.

Metrics:
    - Total return (%)
    - Annualized return (%)
    - Sharpe ratio (annualized, risk-free = 0)
    - Max drawdown (peak-to-trough on equity curve)
    - Win rate (%)
    - Avg win / avg loss
    - Profit factor (gross profit / gross loss)
    - Total trades, avg hold time (hours)
    - Kelly fraction (implied by win rate and win/loss ratio)

Gate thresholds (defaults match plan):
    - Sharpe  > 0.5
    - Win rate > 45%
    - Max drawdown < 15%
"""

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

import numpy as np

from src.services.strategy_engine.backtesting.engine import (
    BacktestResult,
    SimulatedTrade,
)

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class BacktestMetrics:
    """
    Computed performance metrics for a backtest run.

    All percentage values are expressed as floats (e.g. 12.5 means 12.5%).
    """
    # Returns
    total_return_pct: float
    annualized_return_pct: float
    initial_capital: float
    final_equity: float

    # Risk-adjusted
    sharpe_ratio: float
    max_drawdown_pct: float

    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    avg_win_pct: float
    avg_loss_pct: float
    profit_factor: float
    avg_hold_hours: float

    # Kelly
    kelly_fraction: float

    # Gate result
    passed_gate: bool
    gate_sharpe_threshold: float
    gate_win_rate_threshold: float
    gate_drawdown_threshold: float

    def to_dict(self) -> dict:
        return {
            "total_return_pct": round(self.total_return_pct, 4),
            "annualized_return_pct": round(self.annualized_return_pct, 4),
            "initial_capital": self.initial_capital,
            "final_equity": round(self.final_equity, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate_pct": round(self.win_rate_pct, 2),
            "avg_win_pct": round(self.avg_win_pct, 4),
            "avg_loss_pct": round(self.avg_loss_pct, 4),
            "profit_factor": round(self.profit_factor, 4),
            "avg_hold_hours": round(self.avg_hold_hours, 2),
            "kelly_fraction": round(self.kelly_fraction, 4),
            "passed_gate": self.passed_gate,
        }


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

class MetricsCalculator:
    """
    Computes BacktestMetrics from a BacktestResult.

    Usage:
        calc = MetricsCalculator()
        metrics = calc.compute(result)
    """

    GATE_SHARPE = 0.5
    GATE_WIN_RATE = 45.0     # %
    GATE_DRAWDOWN = 15.0     # %

    def compute(self, result: BacktestResult) -> BacktestMetrics:
        """
        Compute all metrics from a BacktestResult.

        Args:
            result: Output of BacktestEngine.run()

        Returns:
            BacktestMetrics dataclass
        """
        trades = result.trades
        equity_curve = result.equity_curve
        initial = result.initial_capital

        final_equity = equity_curve[-1]["equity"] if equity_curve else initial
        total_return_pct = ((final_equity - initial) / initial) * 100 if initial > 0 else 0.0

        # Annualized return: (1 + r)^(252/trading_days) - 1
        trading_days = _count_trading_days(result.start_date, result.end_date)
        if trading_days > 0 and total_return_pct > -100:
            ann_factor = 252.0 / trading_days
            annualized_return_pct = ((1 + total_return_pct / 100) ** ann_factor - 1) * 100
        else:
            annualized_return_pct = 0.0

        sharpe = _sharpe_ratio(equity_curve)
        max_dd = _max_drawdown(equity_curve)

        # Trade stats
        total_trades = len(trades)
        wins = [t for t in trades if (t.pnl or 0) > 0]
        losses = [t for t in trades if (t.pnl or 0) <= 0]
        winning_trades = len(wins)
        losing_trades = len(losses)
        win_rate_pct = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

        avg_win_pct = (
            float(np.mean([t.pnl_pct for t in wins if t.pnl_pct is not None]))
            if wins else 0.0
        )
        avg_loss_pct = (
            float(np.mean([abs(t.pnl_pct) for t in losses if t.pnl_pct is not None]))
            if losses else 0.0
        )

        gross_profit = sum(t.pnl for t in wins if t.pnl is not None) if wins else 0.0
        gross_loss = abs(sum(t.pnl for t in losses if t.pnl is not None)) if losses else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

        hold_times = [t.hold_hours for t in trades if t.hold_hours is not None]
        avg_hold_hours = float(np.mean(hold_times)) if hold_times else 0.0

        kelly = _kelly_fraction(win_rate_pct / 100, avg_win_pct, avg_loss_pct)

        passed_gate = (
            sharpe >= self.GATE_SHARPE
            and win_rate_pct >= self.GATE_WIN_RATE
            and max_dd <= self.GATE_DRAWDOWN
        )

        return BacktestMetrics(
            total_return_pct=total_return_pct,
            annualized_return_pct=annualized_return_pct,
            initial_capital=initial,
            final_equity=final_equity,
            sharpe_ratio=sharpe,
            max_drawdown_pct=max_dd,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate_pct=win_rate_pct,
            avg_win_pct=avg_win_pct,
            avg_loss_pct=avg_loss_pct,
            profit_factor=profit_factor,
            avg_hold_hours=avg_hold_hours,
            kelly_fraction=kelly,
            passed_gate=passed_gate,
            gate_sharpe_threshold=self.GATE_SHARPE,
            gate_win_rate_threshold=self.GATE_WIN_RATE,
            gate_drawdown_threshold=self.GATE_DRAWDOWN,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sharpe_ratio(equity_curve: List[dict]) -> float:
    """
    Annualized Sharpe ratio from equity curve (risk-free = 0).
    Uses hourly bar returns, annualized assuming ~6.5 trading hours/day x 252 days.
    """
    if len(equity_curve) < 2:
        return 0.0

    equities = np.array([e["equity"] for e in equity_curve], dtype=float)
    returns = np.diff(equities) / equities[:-1]

    if len(returns) == 0 or np.std(returns) == 0:
        return 0.0

    # Annualize: sqrt(trading hours per year) = sqrt(252 * 6.5) ~ sqrt(1638)
    ann_factor = np.sqrt(252 * 6.5)
    return float(np.mean(returns) / np.std(returns) * ann_factor)


def _max_drawdown(equity_curve: List[dict]) -> float:
    """
    Maximum peak-to-trough drawdown as a positive percentage.
    Returns 0.0 if no drawdown.
    """
    if not equity_curve:
        return 0.0

    equities = np.array([e["equity"] for e in equity_curve], dtype=float)
    running_max = np.maximum.accumulate(equities)
    drawdowns = (running_max - equities) / running_max * 100
    return float(np.max(drawdowns))


def _kelly_fraction(win_rate: float, avg_win_pct: float, avg_loss_pct: float) -> float:
    """
    Kelly fraction: f = W - (1-W)/R
    where W = win rate, R = avg_win / avg_loss

    Clamped to [0, 1]. Returns 0 if insufficient data.
    """
    if win_rate <= 0 or avg_loss_pct == 0:
        return 0.0
    r = avg_win_pct / avg_loss_pct if avg_loss_pct > 0 else 0.0
    if r == 0:
        return 0.0
    kelly = win_rate - (1 - win_rate) / r
    return float(max(0.0, min(1.0, kelly)))


def _count_trading_days(start_date: date, end_date: date) -> int:
    """Approximate trading days (weekdays only) in date range."""
    from datetime import timedelta
    delta = (end_date - start_date).days + 1
    total_weeks = delta // 7
    remaining = delta % 7
    # Count weekdays in remaining days
    from datetime import date as date_type
    start_weekday = start_date.weekday() if hasattr(start_date, "weekday") else 0
    extra = sum(
        1 for i in range(remaining)
        if (start_weekday + i) % 7 < 5
    )
    return int(total_weeks * 5 + extra)
