"""
Factor Backtest Report

Formats FactorBacktestEngine results for console output and persists them to
the BasketBacktestRun table in the database.

Usage:
    from src.services.strategy_engine.factor_stat_arb.report import (
        FactorBacktestReport,
    )

    report = FactorBacktestReport()
    run_id = report.save(result, metrics, notes="Testing tighter entry threshold")
    report.print_summary(result, metrics)
"""

from typing import Optional

from loguru import logger

from src.services.strategy_engine.backtesting.metrics import BacktestMetrics
from src.services.strategy_engine.factor_stat_arb.backtest_engine import (
    FactorBacktestResult,
)
from src.shared.database.base import db_transaction
from src.shared.database.models.basket_models import BasketBacktestRun


class FactorBacktestReport:
    """
    Saves a FactorBacktestResult + BacktestMetrics to the BasketBacktestRun
    table and prints a formatted summary to the console.
    """

    def save(
        self,
        result: FactorBacktestResult,
        metrics: BacktestMetrics,
        notes: Optional[str] = None,
    ) -> int:
        """
        Persist the backtest run to the database.

        Args:
            result:  Raw FactorBacktestResult from FactorBacktestEngine.run()
            metrics: Computed BacktestMetrics from MetricsCalculator.compute()
            notes:   Optional free-text annotation

        Returns:
            Database ID of the new BasketBacktestRun row.
        """
        trade_log = [
            {
                "side": t.side,
                "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                "entry_z": t.entry_z,
                "exit_z": t.exit_z,
                "entry_prices": t.entry_prices,
                "exit_prices": t.exit_prices,
                "qty": t.qty,
                "pnl": t.pnl,
                "pnl_pct": t.pnl_pct,
                "hold_hours": t.hold_hours,
                "exit_reason": t.exit_reason,
            }
            for t in result.trades
        ]

        run = BasketBacktestRun(
            basket_id=result.basket_id,
            start_date=result.start_date,
            end_date=result.end_date,
            entry_threshold=result.entry_threshold,
            exit_threshold=result.exit_threshold,
            stop_loss_threshold=result.stop_loss_threshold,
            z_score_window=result.z_score_window,
            initial_capital=result.initial_capital,
            slippage_bps=result.slippage_bps,
            commission_per_trade=result.commission_per_trade,
            total_return=metrics.total_return_pct,
            annualized_return=metrics.annualized_return_pct,
            sharpe_ratio=metrics.sharpe_ratio,
            max_drawdown=metrics.max_drawdown_pct,
            win_rate=metrics.win_rate_pct,
            profit_factor=(
                metrics.profit_factor
                if metrics.profit_factor != float("inf")
                else 999.0
            ),
            total_trades=metrics.total_trades,
            avg_hold_time_hours=metrics.avg_hold_hours,
            kelly_fraction=metrics.kelly_fraction,
            passed_gate=metrics.passed_gate,
            equity_curve=result.equity_curve,
            trade_log=trade_log,
            notes=notes,
        )

        with db_transaction() as session:
            session.add(run)
            session.flush()
            run_id = run.id

        logger.info(
            f"Factor backtest run saved: id={run_id}, passed_gate={metrics.passed_gate}"
        )
        return run_id

    def print_summary(
        self,
        result: FactorBacktestResult,
        metrics: BacktestMetrics,
        run_id: Optional[int] = None,
    ) -> None:
        """
        Print a formatted summary table to the console.
        """
        gate_icon = "PASS" if metrics.passed_gate else "FAIL"
        sep = "=" * 62
        weights_str = ", ".join(
            f"{s}={w:.2f}" for s, w in zip(result.symbols, result.hedge_weights)
        )

        lines = [
            "",
            sep,
            f"  FACTOR BACKTEST RESULTS - {result.basket_name}",
            sep,
            f"  Symbols        : {result.symbols}",
            f"  Hedge weights  : {weights_str}",
            f"  Period         : {result.start_date} -> {result.end_date}",
            f"  Bars processed : {result.bars_processed}",
            f"  Entry threshold: +/-{result.entry_threshold}",
            f"  Exit threshold : +/-{result.exit_threshold}",
            f"  Stop loss      : +/-{result.stop_loss_threshold}",
            f"  Z-score window : {result.z_score_window} bars",
            f"  Slippage       : {result.slippage_bps:.1f} bps/fill",
            f"  Commission     : ${result.commission_per_trade:.2f}/trade",
            "",
            "  PERFORMANCE",
            f"  {'Total return':<22}: {metrics.total_return_pct:+.2f}%",
            f"  {'Annualized return':<22}: {metrics.annualized_return_pct:+.2f}%",
            f"  {'Final equity':<22}: ${metrics.final_equity:,.2f}",
            f"  {'Sharpe ratio':<22}: {metrics.sharpe_ratio:.3f}",
            f"  {'Max drawdown':<22}: {metrics.max_drawdown_pct:.2f}%",
            "",
            "  TRADES",
            f"  {'Total trades':<22}: {metrics.total_trades}",
            f"  {'Win rate':<22}: {metrics.win_rate_pct:.1f}%"
            f"  ({metrics.winning_trades}W / {metrics.losing_trades}L)",
            f"  {'Avg win':<22}: {metrics.avg_win_pct:+.2f}%",
            f"  {'Avg loss':<22}: {metrics.avg_loss_pct:+.2f}%",
            f"  {'Profit factor':<22}: {metrics.profit_factor:.2f}",
            f"  {'Avg hold time':<22}: {metrics.avg_hold_hours:.1f}h",
            f"  {'Kelly fraction':<22}: {metrics.kelly_fraction:.3f}",
            "",
            "  GATE THRESHOLDS",
            f"  Sharpe > {metrics.gate_sharpe_threshold}    : "
            f"{'OK' if metrics.sharpe_ratio >= metrics.gate_sharpe_threshold else 'FAIL'}"
            f"  ({metrics.sharpe_ratio:.3f})",
            f"  Win rate > {metrics.gate_win_rate_threshold}%  : "
            f"{'OK' if metrics.win_rate_pct >= metrics.gate_win_rate_threshold else 'FAIL'}"
            f"  ({metrics.win_rate_pct:.1f}%)",
            f"  Drawdown < {metrics.gate_drawdown_threshold}%  : "
            f"{'OK' if metrics.max_drawdown_pct <= metrics.gate_drawdown_threshold else 'FAIL'}"
            f"  ({metrics.max_drawdown_pct:.2f}%)",
            "",
            f"  VERDICT: [{gate_icon}]" + (f"  (run_id={run_id})" if run_id else ""),
            sep,
            "",
        ]

        for line in lines:
            print(line)
