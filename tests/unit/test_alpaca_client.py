"""
Unit tests for Alpaca Trading API Client
"""

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from alpaca.common.exceptions import APIError
from alpaca.trading.enums import QueryOrderStatus

from src.services.alpaca.client import AlpacaClient
from src.services.alpaca.exceptions import (
    AlpacaAPIError,
    AlpacaAuthenticationError,
    AlpacaConnectionError,
)


class TestAlpacaClientInitialization:
    """Test cases for AlpacaClient initialization"""

    @pytest.fixture
    def mock_env_vars(self):
        """Mock environment variables for testing"""
        with patch.dict(
            "os.environ",
            {
                "ALPACA_API_KEY": "test_api_key",
                "ALPACA_SECRET_KEY": "test_secret_key",
            },
        ):
            yield

    def test_client_initialization_success_paper_trading(self, mock_env_vars):
        """Test successful client initialization for paper trading"""
        with (
            patch("src.services.alpaca.client.TradingClient") as mock_trading,
            patch("src.services.alpaca.client.StockHistoricalDataClient"),
        ):
            mock_client = Mock()
            mock_trading.return_value = mock_client

            client = AlpacaClient()

            assert client.api_key == "test_api_key"
            assert client.secret_key == "test_secret_key"
            assert client.is_paper is True
            assert client.base_url == "https://paper-api.alpaca.markets"
            mock_trading.assert_called_once_with(
                api_key="test_api_key",
                secret_key="test_secret_key",
                paper=True,
            )

    def test_client_initialization_success_live_trading(self, mock_env_vars):
        """Test successful client initialization for live trading"""
        with (
            patch("src.services.alpaca.client.TradingClient") as mock_trading,
            patch("src.services.alpaca.client.StockHistoricalDataClient"),
        ):
            mock_client = Mock()
            mock_trading.return_value = mock_client

            client = AlpacaClient(is_paper=False)

            assert client.is_paper is False
            assert client.base_url == "https://api.alpaca.markets"

    def test_client_initialization_with_custom_credentials(self):
        """Test client initialization with custom credentials"""
        with (
            patch("src.services.alpaca.client.TradingClient") as mock_trading,
            patch("src.services.alpaca.client.StockHistoricalDataClient"),
        ):
            mock_client = Mock()
            mock_trading.return_value = mock_client

            client = AlpacaClient(
                api_key="custom_key",
                secret_key="custom_secret",
                base_url="https://custom.url",
            )

            assert client.api_key == "custom_key"
            assert client.secret_key == "custom_secret"
            assert client.base_url == "https://custom.url"

    def test_client_initialization_no_api_key(self):
        """Test client initialization without API key"""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(AlpacaAuthenticationError) as exc_info:
                AlpacaClient()
            assert "credentials not provided" in str(exc_info.value).lower()

    def test_client_initialization_no_secret_key(self):
        """Test client initialization without secret key"""
        with patch.dict("os.environ", {"ALPACA_API_KEY": "test_key"}, clear=True):
            with pytest.raises(AlpacaAuthenticationError) as exc_info:
                AlpacaClient()
            assert "credentials not provided" in str(exc_info.value).lower()

    def test_client_initialization_connection_error(self, mock_env_vars):
        """Test client initialization with connection error"""
        with patch("src.services.alpaca.client.TradingClient") as mock_trading:
            mock_trading.side_effect = Exception("Connection failed")

            with pytest.raises(AlpacaConnectionError) as exc_info:
                AlpacaClient()
            assert "Failed to initialize" in str(exc_info.value)


class TestAlpacaClientAccountMethods:
    """Test cases for account-related methods"""

    @pytest.fixture
    def alpaca_client(self):
        """Create AlpacaClient instance for testing"""
        with patch.dict(
            "os.environ",
            {
                "ALPACA_API_KEY": "test_api_key",
                "ALPACA_SECRET_KEY": "test_secret_key",
            },
        ):
            with (
                patch("src.services.alpaca.client.TradingClient"),
                patch("src.services.alpaca.client.StockHistoricalDataClient"),
            ):
                return AlpacaClient()

    @pytest.mark.asyncio
    async def test_get_account_success(self, alpaca_client):
        """Test successful account retrieval"""
        mock_account = Mock()
        mock_account.id = "acc123"
        mock_account.account_number = "123456789"
        mock_account.status = "ACTIVE"
        mock_account.currency = "USD"
        mock_account.buying_power = 100000.0
        mock_account.cash = 50000.0
        mock_account.portfolio_value = 150000.0
        mock_account.equity = 150000.0
        mock_account.last_equity = 145000.0
        mock_account.created_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        mock_account.trading_blocked = False
        mock_account.transfers_blocked = False
        mock_account.account_blocked = False
        mock_account.shorting_enabled = True
        mock_account.multiplier = 2.0
        mock_account.long_market_value = 100000.0
        mock_account.short_market_value = 0.0
        mock_account.initial_margin = 25000.0
        mock_account.maintenance_margin = 20000.0
        mock_account.daytrade_count = 0
        mock_account.pattern_day_trader = False

        with patch.object(alpaca_client, "client") as mock_client:
            mock_client.get_account.return_value = mock_account

            result = await alpaca_client.get_account()

            assert result["id"] == "acc123"
            assert result["account_number"] == "123456789"
            assert result["status"] == "ACTIVE"
            assert result["currency"] == "USD"
            assert result["buying_power"] == 100000.0
            assert result["cash"] == 50000.0
            assert result["portfolio_value"] == 150000.0
            assert result["equity"] == 150000.0
            assert result["trading_blocked"] is False
            assert result["pattern_day_trader"] is False
            mock_client.get_account.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_account_api_error(self, alpaca_client):
        """Test account retrieval with API error"""
        with patch.object(alpaca_client, "client") as mock_client:
            mock_client.get_account.side_effect = APIError("API Error")

            with pytest.raises(AlpacaAPIError) as exc_info:
                await alpaca_client.get_account()
            assert "Failed to get account" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_account_connection_error(self, alpaca_client):
        """Test account retrieval with connection error"""
        with patch.object(alpaca_client, "client") as mock_client:
            mock_client.get_account.side_effect = Exception("Connection lost")

            with pytest.raises(AlpacaConnectionError) as exc_info:
                await alpaca_client.get_account()
            assert "Connection error" in str(exc_info.value)


class TestAlpacaClientPositionMethods:
    """Test cases for position-related methods"""

    @pytest.fixture
    def alpaca_client(self):
        """Create AlpacaClient instance for testing"""
        with patch.dict(
            "os.environ",
            {
                "ALPACA_API_KEY": "test_api_key",
                "ALPACA_SECRET_KEY": "test_secret_key",
            },
        ):
            with (
                patch("src.services.alpaca.client.TradingClient"),
                patch("src.services.alpaca.client.StockHistoricalDataClient"),
            ):
                return AlpacaClient()

    @pytest.mark.asyncio
    async def test_get_positions_success(self, alpaca_client):
        """Test successful positions retrieval"""
        mock_position = Mock()
        mock_position.asset_id = "asset123"
        mock_position.symbol = "AAPL"
        mock_position.exchange = "NASDAQ"
        mock_position.asset_class = "us_equity"
        mock_position.qty = 100.0
        mock_position.side = "long"
        mock_position.market_value = 15000.0
        mock_position.cost_basis = 14000.0
        mock_position.unrealized_pl = 1000.0
        mock_position.unrealized_plpc = 0.0714
        mock_position.unrealized_intraday_pl = 500.0
        mock_position.unrealized_intraday_plpc = 0.0357
        mock_position.current_price = 150.0
        mock_position.lastday_price = 145.0
        mock_position.change_today = 0.0345
        mock_position.avg_entry_price = 140.0

        with patch.object(alpaca_client, "client") as mock_client:
            mock_client.get_all_positions.return_value = [mock_position]

            result = await alpaca_client.get_positions()

            assert len(result) == 1
            assert result[0]["symbol"] == "AAPL"
            assert result[0]["qty"] == 100.0
            assert result[0]["market_value"] == 15000.0
            assert result[0]["unrealized_pl"] == 1000.0
            mock_client.get_all_positions.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_positions_empty(self, alpaca_client):
        """Test positions retrieval with no positions"""
        with patch.object(alpaca_client, "client") as mock_client:
            mock_client.get_all_positions.return_value = []

            result = await alpaca_client.get_positions()

            assert result == []

    @pytest.mark.asyncio
    async def test_get_positions_api_error(self, alpaca_client):
        """Test positions retrieval with API error"""
        with patch.object(alpaca_client, "client") as mock_client:
            mock_client.get_all_positions.side_effect = APIError("API Error")

            with pytest.raises(AlpacaAPIError) as exc_info:
                await alpaca_client.get_positions()
            assert "Failed to get positions" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_close_position_success(self, alpaca_client):
        """Test successful position closing"""
        mock_result = Mock()
        mock_result.id = "order123"
        mock_result.client_order_id = "client123"
        mock_result.created_at = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        mock_result.symbol = "AAPL"
        mock_result.qty = 100.0
        mock_result.side = "sell"
        mock_result.status = "filled"

        with patch.object(alpaca_client, "client") as mock_client:
            mock_client.close_position.return_value = mock_result

            result = await alpaca_client.close_position("AAPL")

            assert result["id"] == "order123"
            assert result["symbol"] == "AAPL"
            assert result["qty"] == 100.0
            assert result["side"] == "sell"
            assert result["status"] == "filled"
            mock_client.close_position.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_close_position_api_error(self, alpaca_client):
        """Test position closing with API error"""
        with patch.object(alpaca_client, "client") as mock_client:
            mock_client.close_position.side_effect = APIError("Position not found")

            with pytest.raises(AlpacaAPIError) as exc_info:
                await alpaca_client.close_position("INVALID")
            assert "Failed to close position" in str(exc_info.value)


class TestAlpacaClientOrderMethods:
    """Test cases for order-related methods"""

    @pytest.fixture
    def alpaca_client(self):
        """Create AlpacaClient instance for testing"""
        with patch.dict(
            "os.environ",
            {
                "ALPACA_API_KEY": "test_api_key",
                "ALPACA_SECRET_KEY": "test_secret_key",
            },
        ):
            with (
                patch("src.services.alpaca.client.TradingClient"),
                patch("src.services.alpaca.client.StockHistoricalDataClient"),
            ):
                return AlpacaClient()

    @pytest.mark.asyncio
    async def test_get_orders_success(self, alpaca_client):
        """Test successful orders retrieval"""
        mock_order = Mock()
        mock_order.id = "order123"
        mock_order.client_order_id = "client123"
        mock_order.created_at = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        mock_order.updated_at = datetime(2024, 1, 1, 10, 5, 0, tzinfo=timezone.utc)
        mock_order.submitted_at = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        mock_order.filled_at = datetime(2024, 1, 1, 10, 5, 0, tzinfo=timezone.utc)
        mock_order.expired_at = None
        mock_order.canceled_at = None
        mock_order.failed_at = None
        mock_order.replaced_at = None
        mock_order.replaced_by = None
        mock_order.replaces = None
        mock_order.asset_id = "asset123"
        mock_order.symbol = "AAPL"
        mock_order.asset_class = "us_equity"
        mock_order.notional = None
        mock_order.qty = 100.0
        mock_order.filled_qty = 100.0
        mock_order.filled_avg_price = 150.0
        mock_order.order_class = "simple"
        mock_order.order_type = "market"
        mock_order.type = "market"
        mock_order.side = "buy"
        mock_order.time_in_force = "day"
        mock_order.limit_price = None
        mock_order.stop_price = None
        mock_order.status = "filled"
        mock_order.extended_hours = False
        mock_order.legs = None
        mock_order.trail_percent = None
        mock_order.trail_price = None
        mock_order.hwm = None

        with patch.object(alpaca_client, "client") as mock_client:
            mock_client.get_orders.return_value = [mock_order]

            result = await alpaca_client.get_orders(status="all", limit=50)

            assert len(result) == 1
            assert result[0]["id"] == "order123"
            assert result[0]["symbol"] == "AAPL"
            assert result[0]["side"] == "buy"
            assert result[0]["status"] == "filled"
            assert result[0]["qty"] == 100.0
            mock_client.get_orders.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_orders_empty(self, alpaca_client):
        """Test orders retrieval with no orders"""
        with patch.object(alpaca_client, "client") as mock_client:
            mock_client.get_orders.return_value = []

            result = await alpaca_client.get_orders()

            assert result == []

    @pytest.mark.asyncio
    async def test_get_orders_filtered_by_specific_status(self, alpaca_client):
        """
        Test that a specific order status (e.g. "filled") is applied as a
        client-side filter, since QueryOrderStatus only supports open/closed/all.
        """

        def make_order(order_id, status):
            order = Mock()
            order.id = order_id
            order.client_order_id = f"client-{order_id}"
            order.created_at = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
            order.updated_at = None
            order.submitted_at = None
            order.filled_at = None
            order.expired_at = None
            order.canceled_at = None
            order.failed_at = None
            order.replaced_at = None
            order.replaced_by = None
            order.replaces = None
            order.asset_id = "asset123"
            order.symbol = "AAPL"
            order.asset_class = "us_equity"
            order.notional = None
            order.qty = 100.0
            order.filled_qty = 100.0 if status == "filled" else 0.0
            order.filled_avg_price = 150.0 if status == "filled" else None
            order.order_class = "simple"
            order.order_type = "market"
            order.type = "market"
            order.side = "buy"
            order.time_in_force = "day"
            order.limit_price = None
            order.stop_price = None
            order.status = status
            order.extended_hours = False
            order.legs = None
            order.trail_percent = None
            order.trail_price = None
            order.hwm = None
            return order

        with patch.object(alpaca_client, "client") as mock_client:
            mock_client.get_orders.return_value = [
                make_order("order1", "filled"),
                make_order("order2", "canceled"),
            ]

            result = await alpaca_client.get_orders(status="filled", limit=50)

            assert len(result) == 1
            assert result[0]["id"] == "order1"
            assert result[0]["status"] == "filled"
            _, kwargs = mock_client.get_orders.call_args
            assert kwargs["filter"].status == QueryOrderStatus.ALL

    @pytest.mark.asyncio
    async def test_place_order_market_success(self, alpaca_client):
        """Test successful market order placement"""
        mock_order = Mock()
        mock_order.id = "order123"
        mock_order.client_order_id = "client123"
        mock_order.created_at = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        mock_order.symbol = "AAPL"
        mock_order.qty = 100.0
        mock_order.side = "buy"
        mock_order.order_type = "market"
        mock_order.status = "new"

        with patch.object(alpaca_client, "client") as mock_client:
            mock_client.submit_order.return_value = mock_order

            result = await alpaca_client.place_order(
                symbol="AAPL",
                qty=100,
                side="buy",
                order_type="market",
                time_in_force="day",
            )

            assert result["id"] == "order123"
            assert result["symbol"] == "AAPL"
            assert result["qty"] == 100.0
            assert result["side"] == "buy"
            assert result["status"] == "new"
            mock_client.submit_order.assert_called_once()
            _, kwargs = mock_client.submit_order.call_args
            order_request = kwargs["order_data"]
            assert order_request.symbol == "AAPL"
            assert order_request.qty == 100
            assert order_request.side == "buy"
            assert order_request.time_in_force == "day"

    @pytest.mark.asyncio
    async def test_place_order_limit_success(self, alpaca_client):
        """Test successful limit order placement"""
        mock_order = Mock()
        mock_order.id = "order123"
        mock_order.client_order_id = "client123"
        mock_order.created_at = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        mock_order.symbol = "AAPL"
        mock_order.qty = 100.0
        mock_order.side = "buy"
        mock_order.order_type = "limit"
        mock_order.status = "new"

        with patch.object(alpaca_client, "client") as mock_client:
            mock_client.submit_order.return_value = mock_order

            result = await alpaca_client.place_order(
                symbol="AAPL",
                qty=100,
                side="buy",
                order_type="limit",
                time_in_force="day",
                limit_price=150.0,
            )

            assert result["id"] == "order123"
            mock_client.submit_order.assert_called_once()
            _, kwargs = mock_client.submit_order.call_args
            assert kwargs["order_data"].limit_price == 150.0

    @pytest.mark.asyncio
    async def test_place_order_api_error(self, alpaca_client):
        """Test order placement with API error"""
        with patch.object(alpaca_client, "client") as mock_client:
            mock_client.submit_order.side_effect = APIError("Insufficient buying power")

            with pytest.raises(AlpacaAPIError) as exc_info:
                await alpaca_client.place_order(
                    symbol="AAPL", qty=100, side="buy", order_type="market"
                )
            assert "Failed to place order" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cancel_order_success(self, alpaca_client):
        """Test successful order cancellation"""
        with patch.object(alpaca_client, "client") as mock_client:
            mock_client.cancel_order_by_id.return_value = None

            result = await alpaca_client.cancel_order("order123")

            assert result is True
            mock_client.cancel_order_by_id.assert_called_once_with("order123")

    @pytest.mark.asyncio
    async def test_cancel_order_api_error(self, alpaca_client):
        """Test order cancellation with API error"""
        with patch.object(alpaca_client, "client") as mock_client:
            mock_client.cancel_order_by_id.side_effect = APIError("Order not found")

            with pytest.raises(AlpacaAPIError) as exc_info:
                await alpaca_client.cancel_order("invalid_order")
            assert "Failed to cancel order" in str(exc_info.value)


class TestAlpacaClientMarketMethods:
    """Test cases for market-related methods"""

    @pytest.fixture
    def alpaca_client(self):
        """Create AlpacaClient instance for testing"""
        with patch.dict(
            "os.environ",
            {
                "ALPACA_API_KEY": "test_api_key",
                "ALPACA_SECRET_KEY": "test_secret_key",
            },
        ):
            with (
                patch("src.services.alpaca.client.TradingClient"),
                patch("src.services.alpaca.client.StockHistoricalDataClient"),
            ):
                return AlpacaClient()

    @pytest.mark.asyncio
    async def test_get_clock_market_open(self, alpaca_client):
        """Test market clock when market is open"""
        mock_clock = Mock()
        mock_clock.timestamp = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        mock_clock.is_open = True
        mock_clock.next_open = datetime(2024, 1, 16, 9, 30, 0, tzinfo=timezone.utc)
        mock_clock.next_close = datetime(2024, 1, 15, 16, 0, 0, tzinfo=timezone.utc)

        with patch.object(alpaca_client, "client") as mock_client:
            mock_client.get_clock.return_value = mock_clock

            result = await alpaca_client.get_clock()

            assert result["is_open"] is True
            assert "timestamp" in result
            assert "next_open" in result
            assert "next_close" in result
            mock_client.get_clock.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_clock_market_closed(self, alpaca_client):
        """Test market clock when market is closed"""
        mock_clock = Mock()
        mock_clock.timestamp = datetime(2024, 1, 15, 2, 0, 0, tzinfo=timezone.utc)
        mock_clock.is_open = False
        mock_clock.next_open = datetime(2024, 1, 15, 9, 30, 0, tzinfo=timezone.utc)
        mock_clock.next_close = datetime(2024, 1, 15, 16, 0, 0, tzinfo=timezone.utc)

        with patch.object(alpaca_client, "client") as mock_client:
            mock_client.get_clock.return_value = mock_clock

            result = await alpaca_client.get_clock()

            assert result["is_open"] is False

    @pytest.mark.asyncio
    async def test_get_clock_api_error(self, alpaca_client):
        """Test market clock with API error"""
        with patch.object(alpaca_client, "client") as mock_client:
            mock_client.get_clock.side_effect = APIError("API Error")

            with pytest.raises(AlpacaAPIError) as exc_info:
                await alpaca_client.get_clock()
            assert "Failed to get clock" in str(exc_info.value)


class TestAlpacaExceptions:
    """Test cases for Alpaca exceptions"""

    def test_alpaca_api_error(self):
        """Test AlpacaAPIError exception"""
        error = AlpacaAPIError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_alpaca_connection_error(self):
        """Test AlpacaConnectionError exception"""
        error = AlpacaConnectionError("Connection failed")
        assert str(error) == "Connection failed"
        assert isinstance(error, AlpacaAPIError)

    def test_alpaca_authentication_error(self):
        """Test AlpacaAuthenticationError exception"""
        error = AlpacaAuthenticationError("Invalid credentials")
        assert str(error) == "Invalid credentials"
        assert isinstance(error, AlpacaAPIError)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
