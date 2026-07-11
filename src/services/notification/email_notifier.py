"""
Email Notification Service

Sends email alerts for key pairs trading events:
  - Trade opened (LONG_SPREAD / SHORT_SPREAD)
  - Trade closed with P&L (EXIT / EXPIRE)
  - Stop-loss triggered (STOP_LOSS)
  - Trade execution failures
  - Prefect flow errors

Uses stdlib smtplib (no extra dependencies).
Gracefully no-ops when SMTP settings are not configured.
"""

import asyncio
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from loguru import logger

from src.config.settings import get_settings


class EmailNotifier:
    """
    Thin email wrapper for trading event notifications.

    All public methods are async - SMTP is dispatched via asyncio.to_thread
    so it never blocks the Prefect event loop.
    """

    def __init__(self) -> None:
        s = get_settings()
        self._host: Optional[str] = s.smtp_host
        self._port: Optional[int] = s.smtp_port
        self._username: Optional[str] = s.smtp_username
        self._password: Optional[str] = s.smtp_password
        self._from_email: Optional[str] = s.smtp_from_email
        self._to_email: Optional[str] = s.smtp_to_email
        self._paper: bool = s.paper_trading

    @property
    def _configured(self) -> bool:
        return all(
            [
                self._host,
                self._port,
                self._username,
                self._password,
                self._from_email,
                self._to_email,
            ]
        )

    # ------------------------------------------------------------------
    # Public event methods
    # ------------------------------------------------------------------

    async def send_trade_opened(
        self,
        pair: str,
        signal_type: str,
        z_score: float,
        qty1: float,
        qty2: float,
        price1: float,
        price2: float,
        sym1: str,
        sym2: str,
    ) -> None:
        direction = "LONG" if signal_type == "LONG_SPREAD" else "SHORT"
        subject = f"[{self._mode}] Trade Opened - {pair} ({direction})"
        body = self._trade_opened_html(
            pair,
            signal_type,
            direction,
            z_score,
            qty1,
            qty2,
            price1,
            price2,
            sym1,
            sym2,
        )
        await self._send(subject, body)

    async def send_trade_closed(
        self,
        pair: str,
        exit_reason: str,
        z_score: float,
        pnl: float,
        pnl_pct: float,
        hold_hours: float,
        strategy: str = "Pairs Trading",
    ) -> None:
        pnl_tag = "[+PNL]" if pnl >= 0 else "[-PNL]"
        subject = f"[{self._mode}] Trade Closed - {pair} {pnl_tag} ${pnl:+.2f}"
        body = self._trade_closed_html(
            pair, exit_reason, z_score, pnl, pnl_pct, hold_hours, strategy
        )
        await self._send(subject, body)

    async def send_stop_loss(
        self,
        pair: str,
        z_score: float,
        pnl: float,
        pnl_pct: float,
        strategy: str = "Pairs Trading",
    ) -> None:
        subject = f"[{self._mode}] [WARN] STOP-LOSS - {pair} ${pnl:+.2f}"
        body = self._stop_loss_html(pair, z_score, pnl, pnl_pct, strategy)
        await self._send(subject, body)

    async def send_trade_failed(
        self,
        pair: str,
        action: str,
        reason: str,
    ) -> None:
        subject = f"[{self._mode}] [WARN] Trade Failed - {pair} ({action})"
        body = self._trade_failed_html(pair, action, reason)
        await self._send(subject, body)

    async def send_flow_error(
        self,
        error: str,
        flow_name: str = "intraday-pairs-trading",
    ) -> None:
        subject = f"[{self._mode}] [ALERT] Flow Error - {flow_name}"
        body = self._flow_error_html(flow_name, error)
        await self._send(subject, body)

    async def send_pair_deactivated(
        self,
        pair: str,
        reason: str,
        win_rate: float,
        avg_pnl: float,
        total_trades: int,
    ) -> None:
        subject = f"[{self._mode}] Pair Deactivated - {pair}"
        body = self._pair_deactivated_html(
            pair, reason, win_rate, avg_pnl, total_trades
        )
        await self._send(subject, body)

    async def send_ops_alert(
        self,
        anomalies: list,
        summary: str,
        cycle_summary: dict,
    ) -> None:
        subject = f"[{self._mode}] [WARN] Ops Monitor - {len(anomalies)} anomaly(s)"
        body = self._ops_alert_html(anomalies, summary, cycle_summary)
        await self._send(subject, body)

    async def send_discovery_summary(
        self,
        pairs_found: int,
        pairs_upserted: list,
    ) -> None:
        subject = f"[{self._mode}] Weekly Discovery - {pairs_found} pair(s) found"
        body = self._discovery_summary_html(pairs_found, pairs_upserted)
        await self._send(subject, body)

    # ------------------------------------------------------------------
    # HTML templates
    # ------------------------------------------------------------------

    @property
    def _mode(self) -> str:
        return "PAPER" if self._paper else "LIVE"

    def _base_html(self, title: str, content: str) -> str:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return f"""
<html><body style="font-family:monospace;background:#f9f9f9;padding:24px">
<div style="max-width:560px;margin:auto;background:#fff;border:1px solid #ddd;border-radius:6px;padding:24px">
  <h2 style="margin-top:0;border-bottom:2px solid #111;padding-bottom:8px">{title}</h2>
  {content}
  <p style="color:#888;font-size:11px;margin-top:24px;border-top:1px solid #eee;padding-top:8px">
    Trading System &nbsp;|&nbsp; {now} &nbsp;|&nbsp; {'Paper Trading' if self._paper else 'Live Trading'}
  </p>
</div>
</body></html>"""

    def _row(self, label: str, value: str, color: str = "#111") -> str:
        return (
            f'<tr><td style="color:#666;padding:4px 8px 4px 0">{label}</td>'
            f'<td style="color:{color};font-weight:bold;padding:4px 0">{value}</td></tr>'
        )

    def _table(self, rows: str) -> str:
        return f'<table style="width:100%;border-collapse:collapse;margin:12px 0">{rows}</table>'

    def _trade_opened_html(
        self,
        pair: str,
        signal_type: str,
        direction: str,
        z_score: float,
        qty1: float,
        qty2: float,
        price1: float,
        price2: float,
        sym1: str,
        sym2: str,
    ) -> str:
        color = "#1a6e3c" if direction == "LONG" else "#8b1a1a"
        notional = qty1 * price1 + qty2 * price2
        rows = (
            self._row("Pair", pair)
            + self._row("Direction", f"{direction} SPREAD", color)
            + self._row("Z-Score (entry)", f"{z_score:+.4f}")
            + self._row(f"{sym1} qty / price", f"{qty1} @ ${price1:.2f}")
            + self._row(f"{sym2} qty / price", f"{qty2} @ ${price2:.2f}")
            + self._row("Est. Notional", f"${notional:,.2f}")
        )
        return self._base_html(
            f"Trade Opened - {pair}",
            f"<p>A <strong>{direction} SPREAD</strong> signal was generated and a two-legged trade was submitted to Alpaca.</p>"
            + self._table(rows),
        )

    def _trade_closed_html(
        self,
        pair: str,
        exit_reason: str,
        z_score: float,
        pnl: float,
        pnl_pct: float,
        hold_hours: float,
        strategy: str = "Pairs Trading",
    ) -> str:
        pnl_color = "#1a6e3c" if pnl >= 0 else "#8b1a1a"
        rows = (
            self._row("Strategy", strategy)
            + self._row("Pair", pair)
            + self._row("Exit Reason", exit_reason)
            + self._row("Z-Score (exit)", f"{z_score:+.4f}")
            + self._row("Hold Time", f"{hold_hours:.1f} hours")
            + self._row("P&L", f"${pnl:+.2f}  ({pnl_pct:+.2f}%)", pnl_color)
        )
        return self._base_html(
            f"Trade Closed - {pair}",
            "<p>The open pair trade was closed.</p>" + self._table(rows),
        )

    def _stop_loss_html(
        self,
        pair: str,
        z_score: float,
        pnl: float,
        pnl_pct: float,
        strategy: str = "Pairs Trading",
    ) -> str:
        rows = (
            self._row("Strategy", strategy)
            + self._row("Pair", pair)
            + self._row("Trigger", "STOP_LOSS", "#8b1a1a")
            + self._row("Z-Score (exit)", f"{z_score:+.4f}")
            + self._row("Realised P&L", f"${pnl:+.2f}  ({pnl_pct:+.2f}%)", "#8b1a1a")
        )
        return self._base_html(
            f"[WARN] Stop-Loss Triggered - {pair}",
            "<p><strong>The z-score exceeded the stop-loss threshold.</strong> Both legs were market-closed immediately.</p>"
            + self._table(rows),
        )

    def _trade_failed_html(self, pair: str, action: str, reason: str) -> str:
        rows = (
            self._row("Pair", pair)
            + self._row("Failed Action", action, "#8b1a1a")
            + self._row("Reason", reason)
        )
        return self._base_html(
            f"[WARN] Trade Execution Failed - {pair}",
            "<p>An Alpaca order submission failed. Manual review may be required.</p>"
            + self._table(rows),
        )

    def _pair_deactivated_html(
        self,
        pair: str,
        reason: str,
        win_rate: float,
        avg_pnl: float,
        total_trades: int,
    ) -> str:
        rows = (
            self._row("Pair", pair)
            + self._row("Deactivation Reason", reason, "#8b1a1a")
            + self._row("Trades Evaluated", str(total_trades))
            + self._row("Win Rate", f"{win_rate:.1%}", "#8b1a1a")
            + self._row("Avg P&L per Trade", f"${avg_pnl:+.2f}", "#8b1a1a")
        )
        return self._base_html(
            f"Pair Deactivated - {pair}",
            "<p>This pair was automatically deactivated due to sustained poor performance. "
            "It remains in the registry with <code>is_active=False</code>. "
            "Run a fresh backtest before reactivating.</p>" + self._table(rows),
        )

    def _ops_alert_html(
        self, anomalies: list, summary: str, cycle_summary: dict
    ) -> str:
        anomaly_rows = "".join(
            self._row(f"#{i + 1}", a, "#8b1a1a") for i, a in enumerate(anomalies)
        )
        meta_rows = (
            self._row("Pairs evaluated", str(cycle_summary.get("total_pairs", "-")))
            + self._row("Signals", str(cycle_summary.get("with_signal", "-")))
            + self._row("Errors", str(cycle_summary.get("errors", "-")))
        )
        return self._base_html(
            "[WARN] Ops Monitor Alert",
            f"<p>{summary}</p>"
            + "<h3>Anomalies</h3>"
            + self._table(anomaly_rows)
            + "<h3>Cycle Snapshot</h3>"
            + self._table(meta_rows),
        )

    def _discovery_summary_html(self, pairs_found: int, pairs_upserted: list) -> str:
        if not pairs_upserted:
            content = "<p>No pairs matched discovery criteria this week.</p>"
        else:
            pair_rows = "".join(
                self._row(f"#{i + 1}", f"{s1}/{s2}  (id={pid})")
                for i, (pid, s1, s2) in enumerate(pairs_upserted)
            )
            content = (
                f"<p>{pairs_found} pair(s) upserted to the registry with "
                f"<code>is_active=False</code>. Run backtests before activating.</p>"
                + self._table(pair_rows)
            )
        return self._base_html("Weekly Pair Discovery Summary", content)

    def _flow_error_html(self, flow_name: str, error: str) -> str:
        rows = (
            self._row("Flow", flow_name)
            + self._row(
                "Time (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            )
            + self._row("Error", f"<code>{error[:500]}</code>")
        )
        return self._base_html(
            f"[ALERT] Prefect Flow Error - {flow_name}",
            "<p>The pairs trading Prefect flow encountered an unhandled error.</p>"
            + self._table(rows),
        )

    # ------------------------------------------------------------------
    # SMTP dispatch
    # ------------------------------------------------------------------

    async def _send(self, subject: str, html_body: str) -> None:
        if not self._configured:
            logger.debug("Email not configured - skipping notification: {}", subject)
            return
        try:
            await asyncio.to_thread(self._send_sync, subject, html_body)
            logger.info("Email sent: {}", subject)
        except Exception as exc:
            logger.error("Failed to send email '{}': {}", subject, exc)

    def _send_sync(self, subject: str, html_body: str) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._from_email  # type: ignore[assignment]
        msg["To"] = self._to_email  # type: ignore[assignment]
        msg.attach(MIMEText(html_body, "html"))

        context = ssl.create_default_context()
        with smtplib.SMTP(self._host, self._port) as server:  # type: ignore[arg-type]
            server.ehlo()
            server.starttls(context=context)
            server.login(self._username, self._password)  # type: ignore[arg-type]
            server.sendmail(self._from_email, self._to_email, msg.as_string())  # type: ignore[arg-type]


# Module-level singleton - imported by strategy and flow
_notifier: Optional[EmailNotifier] = None


def get_notifier() -> EmailNotifier:
    global _notifier
    if _notifier is None:
        _notifier = EmailNotifier()
    return _notifier
