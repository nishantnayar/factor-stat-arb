"""
Unit tests for EmailNotifier.

smtplib.SMTP and get_settings() are patched so no real network
or SMTP credentials are needed.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.services.notification.email_notifier as notifier_module
from src.services.notification.email_notifier import EmailNotifier, get_notifier


def _mock_settings(configured: bool = True, paper: bool = True) -> MagicMock:
    """Build a settings mock with SMTP fields populated (or blank if not configured)."""
    s = MagicMock()
    if configured:
        s.smtp_host = "smtp.example.com"
        s.smtp_port = 587
        s.smtp_username = "user@example.com"
        s.smtp_password = "secret"
        s.smtp_from_email = "from@example.com"
        s.smtp_to_email = "to@example.com"
    else:
        s.smtp_host = None
        s.smtp_port = None
        s.smtp_username = None
        s.smtp_password = None
        s.smtp_from_email = None
        s.smtp_to_email = None
    s.paper_trading = paper
    return s


def _configured_notifier(paper: bool = True) -> EmailNotifier:
    """Return an EmailNotifier built with mocked configured settings."""
    with patch(
        "src.services.notification.email_notifier.get_settings",
        return_value=_mock_settings(configured=True, paper=paper),
    ):
        return EmailNotifier()


def _unconfigured_notifier() -> EmailNotifier:
    """Return an EmailNotifier built with missing SMTP settings."""
    with patch(
        "src.services.notification.email_notifier.get_settings",
        return_value=_mock_settings(configured=False),
    ):
        return EmailNotifier()


@pytest.mark.unit
class TestEmailNotifier:
    """Unit tests for EmailNotifier SMTP dispatch and configuration behaviour."""

    # ------------------------------------------------------------------
    # Configured notifier - each send method should trigger SMTP once
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_send_trade_opened_sends_email(self):
        """send_trade_opened() dispatches exactly one SMTP send when configured."""
        notifier = _configured_notifier()
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            await notifier.send_trade_opened(
                pair="SYM1/SYM2",
                signal_type="LONG_SPREAD",
                z_score=-2.5,
                qty1=10,
                qty2=8,
                price1=150.0,
                price2=200.0,
                sym1="SYM1",
                sym2="SYM2",
            )
        mock_server.sendmail.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_trade_closed_sends_email(self):
        """send_trade_closed() dispatches exactly one SMTP send when configured."""
        notifier = _configured_notifier()
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            await notifier.send_trade_closed(
                pair="SYM1/SYM2",
                exit_reason="EXIT",
                z_score=0.2,
                pnl=150.0,
                pnl_pct=1.5,
                hold_hours=4.0,
            )
        mock_server.sendmail.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_stop_loss_sends_email(self):
        """send_stop_loss() dispatches exactly one SMTP send when configured."""
        notifier = _configured_notifier()
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            await notifier.send_stop_loss(
                pair="SYM1/SYM2",
                z_score=3.5,
                pnl=-200.0,
                pnl_pct=-2.0,
            )
        mock_server.sendmail.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_trade_failed_sends_email(self):
        """send_trade_failed() dispatches exactly one SMTP send when configured."""
        notifier = _configured_notifier()
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            await notifier.send_trade_failed(
                pair="SYM1/SYM2",
                action="OPEN",
                reason="Insufficient buying power",
            )
        mock_server.sendmail.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_flow_error_sends_email(self):
        """send_flow_error() dispatches exactly one SMTP send when configured."""
        notifier = _configured_notifier()
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            await notifier.send_flow_error(error="Something exploded")
        mock_server.sendmail.assert_called_once()

    # ------------------------------------------------------------------
    # Unconfigured notifier - must be silent
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_unconfigured_notifier_no_ops(self):
        """Missing SMTP settings -> no SMTP call, no exception raised."""
        notifier = _unconfigured_notifier()
        with patch("smtplib.SMTP") as mock_smtp_cls:
            await notifier.send_trade_opened(
                pair="SYM1/SYM2",
                signal_type="LONG_SPREAD",
                z_score=-2.5,
                qty1=10,
                qty2=8,
                price1=150.0,
                price2=200.0,
                sym1="SYM1",
                sym2="SYM2",
            )
        mock_smtp_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_smtp_failure_logs_and_doesnt_raise(self):
        """SMTP exception is swallowed - caller must not see it."""
        notifier = _configured_notifier()
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp_cls.side_effect = ConnectionRefusedError("cannot connect")
            # Should NOT raise
            await notifier.send_flow_error(error="Test error")

    # ------------------------------------------------------------------
    # Subject line content
    # ------------------------------------------------------------------

    def test_paper_mode_in_subject(self):
        """In paper trading mode, _mode property returns 'PAPER'."""
        notifier = _configured_notifier(paper=True)
        assert notifier._mode == "PAPER"

    def test_live_mode_in_subject(self):
        """In live trading mode, _mode property returns 'LIVE'."""
        notifier = _configured_notifier(paper=False)
        assert notifier._mode == "LIVE"

    # ------------------------------------------------------------------
    # Singleton behaviour
    # ------------------------------------------------------------------

    def test_get_notifier_returns_singleton(self):
        """Two calls to get_notifier() return the same instance."""
        # Reset module-level singleton first
        notifier_module._notifier = None
        with patch(
            "src.services.notification.email_notifier.get_settings",
            return_value=_mock_settings(),
        ):
            n1 = get_notifier()
            n2 = get_notifier()
        assert n1 is n2
        # Cleanup
        notifier_module._notifier = None
