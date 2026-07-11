"""
Unit tests for Yahoo Finance Client

Tests the Yahoo Finance API client functionality.
"""

from datetime import date
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from src.services.yahoo.client import YahooClient
from src.services.yahoo.exceptions import (
    YahooAPIError,
    YahooConnectionError,
    YahooDataError,
    YahooSymbolNotFoundError,
)
from src.services.yahoo.models import CompanyInfo, YahooBar, YahooHealthCheck


class TestYahooClientInitialization:
    """Test Yahoo client initialization"""

    def test_client_initialization(self):
        """Test client initialization"""
        client = YahooClient()
        assert client is not None


class TestYahooClientHistoricalData:
    """Test historical data fetching"""

    @pytest.fixture
    def client(self):
        """Create Yahoo client"""
        return YahooClient()

    @pytest.fixture
    def mock_history_data(self):
        """Create mock history data"""
        data = {
            "Open": [100.0, 101.0, 102.0],
            "High": [105.0, 106.0, 107.0],
            "Low": [99.0, 100.0, 101.0],
            "Close": [104.0, 105.0, 106.0],
            "Volume": [1000000, 1100000, 1200000],
            "Dividends": [0.0, 0.0, 0.0],
            "Stock Splits": [0.0, 0.0, 0.0],
        }
        dates = pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC")
        return pd.DataFrame(data, index=dates)

    @pytest.mark.asyncio
    @patch("src.services.yahoo.client.yf.Ticker")
    async def test_get_historical_data_with_dates(
        self, mock_ticker_class, client, mock_history_data
    ):
        """Test getting historical data with date range"""
        mock_ticker = Mock()
        mock_ticker.history.return_value = mock_history_data
        mock_ticker_class.return_value = mock_ticker

        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        bars = await client.get_historical_data("AAPL", start_date, end_date)

        assert len(bars) == 3
        assert all(isinstance(bar, YahooBar) for bar in bars)
        assert bars[0].symbol == "AAPL"
        assert bars[0].open == 100.0
        mock_ticker.history.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.services.yahoo.client.yf.Ticker")
    async def test_get_historical_data_no_dates(
        self, mock_ticker_class, client, mock_history_data
    ):
        """Test getting historical data without date range"""
        mock_ticker = Mock()
        mock_ticker.history.return_value = mock_history_data
        mock_ticker_class.return_value = mock_ticker

        bars = await client.get_historical_data("AAPL")

        assert len(bars) == 3
        mock_ticker.history.assert_called_once_with(
            period="1mo", interval="1d", auto_adjust=False
        )

    @pytest.mark.asyncio
    @patch("src.services.yahoo.client.yf.Ticker")
    async def test_get_historical_data_auto_adjust_true(
        self, mock_ticker_class, client, mock_history_data
    ):
        """Test getting historical data with auto_adjust=True (adjusted prices)"""
        mock_ticker = Mock()
        mock_ticker.history.return_value = mock_history_data
        mock_ticker_class.return_value = mock_ticker

        bars = await client.get_historical_data("AAPL", auto_adjust=True)

        assert len(bars) == 3
        mock_ticker.history.assert_called_once_with(
            period="1mo", interval="1d", auto_adjust=True
        )

    @pytest.mark.asyncio
    @patch("src.services.yahoo.client.yf.Ticker")
    async def test_get_historical_data_empty(self, mock_ticker_class, client):
        """Test handling empty historical data"""
        mock_ticker = Mock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker_class.return_value = mock_ticker

        with pytest.raises(YahooDataError):
            await client.get_historical_data("INVALID")

    @pytest.mark.asyncio
    @patch("src.services.yahoo.client.yf.Ticker")
    async def test_get_historical_data_api_error(self, mock_ticker_class, client):
        """Test handling API errors"""
        mock_ticker = Mock()
        mock_ticker.history.side_effect = Exception("API Error")
        mock_ticker_class.return_value = mock_ticker

        with pytest.raises(YahooAPIError):
            await client.get_historical_data("AAPL")


class TestYahooClientCompanyInfo:
    """Test company info fetching"""

    @pytest.fixture
    def client(self):
        """Create Yahoo client"""
        return YahooClient()

    @pytest.fixture
    def mock_info_data(self):
        """Create mock company info"""
        return {
            "symbol": "AAPL",
            "shortName": "Apple Inc.",
            "longName": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "fullTimeEmployees": 150000,
            "longBusinessSummary": "Apple designs and manufactures consumer electronics",
            "website": "https://www.apple.com",
            "phone": "408-996-1010",
            "address1": "One Apple Park Way",
            "city": "Cupertino",
            "state": "CA",
            "zip": "95014",
            "country": "United States",
            "marketCap": 3000000000000,
            "currency": "USD",
            "exchange": "NASDAQ",
            "quoteType": "EQUITY",
        }

    @pytest.mark.asyncio
    @patch("src.services.yahoo.client.yf.Ticker")
    async def test_get_company_info_success(
        self, mock_ticker_class, client, mock_info_data
    ):
        """Test getting company info successfully"""
        mock_ticker = Mock()
        mock_ticker.info = mock_info_data
        mock_ticker_class.return_value = mock_ticker

        info = await client.get_company_info("AAPL")

        assert isinstance(info, CompanyInfo)
        assert info.symbol == "AAPL"
        assert info.name == "Apple Inc."
        assert info.sector == "Technology"

    @pytest.mark.asyncio
    @patch("src.services.yahoo.client.yf.Ticker")
    async def test_get_company_info_not_found(self, mock_ticker_class, client):
        """Test handling symbol not found"""
        mock_ticker = Mock()
        mock_ticker.info = {}
        mock_ticker_class.return_value = mock_ticker

        with pytest.raises(YahooDataError):
            await client.get_company_info("INVALID")


class TestYahooClientHealthCheck:
    """Test health check"""

    @pytest.fixture
    def client(self):
        """Create Yahoo client"""
        return YahooClient()

    @pytest.mark.asyncio
    @patch("src.services.yahoo.client.yf.Ticker")
    async def test_health_check_success(self, mock_ticker_class, client):
        """Test successful health check"""
        mock_ticker = Mock()
        mock_ticker.info = {"symbol": "AAPL", "shortName": "Apple Inc."}
        mock_ticker_class.return_value = mock_ticker

        health = await client.health_check()

        assert isinstance(health, YahooHealthCheck)
        assert health.healthy is True
        assert health.data_available is True

    @pytest.mark.asyncio
    @patch("src.services.yahoo.client.yf.Ticker")
    async def test_health_check_failure(self, mock_ticker_class, client):
        """Test failed health check"""
        mock_ticker = Mock()
        mock_ticker.info = {}
        mock_ticker_class.return_value = mock_ticker

        health = await client.health_check()

        assert health.healthy is False
        assert health.data_available is False


class TestYahooExceptions:
    """Test Yahoo exception classes"""

    def test_yahoo_api_error(self):
        """Test YahooAPIError"""
        error = YahooAPIError("Test error")
        assert str(error) == "Test error"

    def test_yahoo_connection_error(self):
        """Test YahooConnectionError"""
        error = YahooConnectionError("Connection failed")
        assert str(error) == "Connection failed"

    def test_yahoo_data_error(self):
        """Test YahooDataError"""
        error = YahooDataError("No data")
        assert str(error) == "No data"

    def test_yahoo_symbol_not_found_error(self):
        """Test YahooSymbolNotFoundError"""
        error = YahooSymbolNotFoundError("Symbol not found")
        assert str(error) == "Symbol not found"
