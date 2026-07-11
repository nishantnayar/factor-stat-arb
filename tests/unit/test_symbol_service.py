"""
Unit tests for Symbol Service
"""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.orm import Session

from src.services.data_ingestion.symbols import SymbolService
from src.services.polygon.exceptions import PolygonDataError
from src.shared.database.models.symbols import DelistedSymbol, Symbol, SymbolDataStatus


class TestSymbolService:
    """Test cases for SymbolService"""

    @pytest.fixture
    def mock_polygon_client(self):
        """Mock PolygonClient for testing"""
        with patch("src.services.data_ingestion.symbols.PolygonClient") as mock_client:
            yield mock_client.return_value

    @pytest.fixture
    def symbol_service(self, mock_polygon_client):
        """Create SymbolService instance for testing"""
        return SymbolService()

    @pytest.fixture
    def mock_symbol(self):
        """Mock Symbol instance"""
        symbol = Mock(spec=Symbol)
        symbol.symbol = "AAPL"
        symbol.name = "Apple Inc."
        symbol.exchange = "NASDAQ"
        symbol.sector = "Technology"
        symbol.market_cap = 3000000000000
        symbol.status = "active"
        symbol.added_date = datetime.now(timezone.utc)
        symbol.last_updated = datetime.now(timezone.utc)
        return symbol

    @pytest.fixture
    def mock_delisted_symbol(self):
        """Mock DelistedSymbol instance"""
        delisted = Mock(spec=DelistedSymbol)
        delisted.symbol = "OLD"
        delisted.delist_date = date.today()
        delisted.last_price = 10.50
        delisted.notes = "Delisted"
        delisted.created_at = datetime.now(timezone.utc)
        return delisted

    @pytest.mark.asyncio
    async def test_get_active_symbols_success(self, symbol_service):
        """Test successful retrieval of active symbols"""
        mock_symbols = [Mock(spec=Symbol), Mock(spec=Symbol)]

        with patch(
            "src.services.data_ingestion.symbols.db_transaction"
        ) as mock_transaction:
            mock_session = Mock(spec=Session)
            mock_result = Mock()
            mock_result.scalars.return_value.all.return_value = mock_symbols
            mock_session.execute.return_value = mock_result
            mock_transaction.return_value.__enter__.return_value = mock_session

            result = await symbol_service.get_active_symbols()

            assert len(result) == 2
            assert result == mock_symbols

    @pytest.mark.asyncio
    async def test_get_symbol_by_ticker_success(self, symbol_service):
        """Test successful retrieval of symbol by ticker"""
        mock_symbol = Mock(spec=Symbol)

        with patch(
            "src.services.data_ingestion.symbols.db_transaction"
        ) as mock_transaction:
            mock_session = Mock(spec=Session)
            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = mock_symbol
            mock_session.execute.return_value = mock_result
            mock_transaction.return_value.__enter__.return_value = mock_session

            result = await symbol_service.get_symbol_by_ticker("AAPL")

            assert result == mock_symbol

    @pytest.mark.asyncio
    async def test_get_symbol_by_ticker_not_found(self, symbol_service):
        """Test symbol retrieval when symbol not found"""
        with patch(
            "src.services.data_ingestion.symbols.db_transaction"
        ) as mock_transaction:
            mock_session = Mock(spec=Session)
            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result
            mock_transaction.return_value.__enter__.return_value = mock_session

            result = await symbol_service.get_symbol_by_ticker("INVALID")

            assert result is None

    @pytest.mark.asyncio
    async def test_add_symbol_new(self, symbol_service):
        """Test adding a new symbol"""
        with patch(
            "src.services.data_ingestion.symbols.db_transaction"
        ) as mock_transaction:
            mock_session = Mock(spec=Session)
            mock_transaction.return_value.__enter__.return_value = mock_session

            # Mock get_symbol_by_ticker to return None (symbol doesn't exist)
            with patch.object(
                symbol_service, "get_symbol_by_ticker", return_value=None
            ):
                result = await symbol_service.add_symbol(
                    symbol="AAPL",
                    name="Apple Inc.",
                    exchange="NASDAQ",
                    sector="Technology",
                    market_cap=3000000000000,
                )

                assert isinstance(result, Symbol)
                mock_session.add.assert_called_once()
                mock_session.commit.assert_called_once()
                mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_symbol_existing(self, symbol_service, mock_symbol):
        """Test adding an existing symbol"""
        with patch.object(
            symbol_service, "get_symbol_by_ticker", return_value=mock_symbol
        ):
            result = await symbol_service.add_symbol("AAPL")

            assert result == mock_symbol

    @pytest.mark.asyncio
    async def test_mark_symbol_delisted_success(self, symbol_service, mock_symbol):
        """Test successful symbol delisting"""
        with patch(
            "src.services.data_ingestion.symbols.db_transaction"
        ) as mock_transaction:
            mock_session = Mock(spec=Session)
            
            # First execute call: Symbol query (returns mock_symbol)
            # Second execute call: DelistedSymbol query (returns None - not already delisted)
            mock_result_symbol = Mock()
            mock_result_symbol.scalar_one_or_none.return_value = mock_symbol
            
            mock_result_delisted = Mock()
            mock_result_delisted.scalar_one_or_none.return_value = None
            
            # Mock execute to return different results for different calls
            mock_session.execute.side_effect = [mock_result_symbol, mock_result_delisted]
            mock_transaction.return_value.__enter__.return_value = mock_session

            result = await symbol_service.mark_symbol_delisted(
                symbol="AAPL",
                last_price=150.0,
                notes="Test delisting",
            )

            assert result is True
            assert mock_symbol.status == "delisted"
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_symbol_delisted_not_found(self, symbol_service):
        """Test delisting a symbol that doesn't exist"""
        with patch(
            "src.services.data_ingestion.symbols.db_transaction"
        ) as mock_transaction:
            mock_session = Mock(spec=Session)
            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result
            mock_transaction.return_value.__enter__.return_value = mock_session

            result = await symbol_service.mark_symbol_delisted("INVALID")

            assert result is False

    @pytest.mark.asyncio
    async def test_check_symbol_health_success(
        self, symbol_service, mock_polygon_client
    ):
        """Test successful symbol health check"""
        mock_polygon_client.get_ticker_details = AsyncMock()

        result = await symbol_service.check_symbol_health("AAPL")

        assert result is True
        mock_polygon_client.get_ticker_details.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_check_symbol_health_delisted(
        self, symbol_service, mock_polygon_client
    ):
        """Test symbol health check for delisted symbol"""
        mock_polygon_client.get_ticker_details = AsyncMock(
            side_effect=PolygonDataError("Symbol not found")
        )

        result = await symbol_service.check_symbol_health("DELISTED")

        assert result is False

    @pytest.mark.asyncio
    async def test_check_symbol_health_other_error(
        self, symbol_service, mock_polygon_client
    ):
        """Test symbol health check with other error"""
        mock_polygon_client.get_ticker_details = AsyncMock(
            side_effect=PolygonDataError("Rate limit exceeded")
        )

        result = await symbol_service.check_symbol_health("AAPL")

        assert result is True  # Other errors are treated as healthy

    @pytest.mark.asyncio
    async def test_detect_delisted_symbols(self, symbol_service):
        """Test delisting detection"""
        mock_symbols = [Mock(spec=Symbol), Mock(spec=Symbol)]
        mock_symbols[0].symbol = "HEALTHY"
        mock_symbols[1].symbol = "DELISTED"

        with patch.object(
            symbol_service, "get_active_symbols", return_value=mock_symbols
        ):
            with patch.object(
                symbol_service,
                "get_active_symbol_strings",
                return_value=["HEALTHY", "DELISTED"],
            ):
                with patch.object(
                    symbol_service, "check_symbol_health"
                ) as mock_health_check:
                    mock_health_check.side_effect = [
                        True,
                        False,
                    ]  # First healthy, second delisted

                    with patch.object(
                        symbol_service, "mark_symbol_delisted"
                    ) as mock_mark_delisted:
                        mock_mark_delisted.side_effect = [
                            True
                        ]  # Only second symbol gets delisted

                        result = await symbol_service.detect_delisted_symbols()

                        assert len(result) == 1
                        assert result[0] == "DELISTED"

    @pytest.mark.asyncio
    async def test_get_symbol_data_status(self, symbol_service):
        """Test retrieval of symbol data status"""
        mock_status = Mock(spec=SymbolDataStatus)

        with patch(
            "src.services.data_ingestion.symbols.db_transaction"
        ) as mock_transaction:
            mock_session = Mock(spec=Session)
            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = mock_status
            mock_session.execute.return_value = mock_result
            mock_transaction.return_value.__enter__.return_value = mock_session

            result = await symbol_service.get_symbol_data_status(
                symbol="AAPL",
                date=date.today(),
                data_source="polygon",
            )

            assert result == mock_status

    @pytest.mark.asyncio
    async def test_update_symbol_data_status_existing(self, symbol_service):
        """Test updating existing symbol data status"""
        mock_existing = Mock(spec=SymbolDataStatus)

        with patch(
            "src.services.data_ingestion.symbols.db_transaction"
        ) as mock_transaction:
            mock_session = Mock(spec=Session)
            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = mock_existing
            mock_session.execute.return_value = mock_result
            mock_transaction.return_value.__enter__.return_value = mock_session

            result = await symbol_service.update_symbol_data_status(
                symbol="AAPL",
                date=date.today(),
                data_source="polygon",
                status="success",
                error_message=None,
            )

            assert result == mock_existing
            assert mock_existing.status == "success"
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_symbol_data_status_new(self, symbol_service):
        """Test creating new symbol data status"""
        with patch(
            "src.services.data_ingestion.symbols.db_transaction"
        ) as mock_transaction:
            mock_session = Mock(spec=Session)
            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = None  # No existing status
            mock_session.execute.return_value = mock_result
            mock_transaction.return_value.__enter__.return_value = mock_session

            # Create a real SymbolDataStatus instance instead of mocking the class
            from src.shared.database.models.symbols import SymbolDataStatus

            test_date = date.today()

            result = await symbol_service.update_symbol_data_status(
                symbol="AAPL",
                date=test_date,
                data_source="polygon",
                status="success",
            )

            # Check that a new status was created and returned
            assert isinstance(result, SymbolDataStatus)
            assert result.symbol == "AAPL"
            assert result.date == test_date
            assert result.data_source == "polygon"
            assert result.status == "success"
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_symbols_needing_data(self, symbol_service):
        """Test retrieval of symbols needing data"""
        mock_symbols = [Mock(spec=Symbol), Mock(spec=Symbol)]

        with patch(
            "src.services.data_ingestion.symbols.db_transaction"
        ) as mock_transaction:
            mock_session = Mock(spec=Session)
            mock_result = Mock()
            mock_result.scalars.return_value.all.return_value = mock_symbols
            mock_session.execute.return_value = mock_result
            mock_transaction.return_value.__enter__.return_value = mock_session

            result = await symbol_service.get_symbols_needing_data(
                target_date=date.today(),
                data_source="polygon",
            )

            assert len(result) == 2
            assert result == mock_symbols

    @pytest.mark.asyncio
    async def test_get_delisted_symbols(self, symbol_service, mock_delisted_symbol):
        """Test retrieval of delisted symbols"""
        mock_delisted_symbols = [mock_delisted_symbol]

        with patch(
            "src.services.data_ingestion.symbols.db_transaction"
        ) as mock_transaction:
            mock_session = Mock(spec=Session)
            mock_result = Mock()
            mock_result.scalars.return_value.all.return_value = mock_delisted_symbols
            mock_session.execute.return_value = mock_result
            mock_transaction.return_value.__enter__.return_value = mock_session

            result = await symbol_service.get_delisted_symbols()

            assert len(result) == 1
            assert result == mock_delisted_symbols

    @pytest.mark.asyncio
    async def test_get_symbol_statistics(self, symbol_service):
        """Test retrieval of symbol statistics"""
        with patch(
            "src.services.data_ingestion.symbols.db_transaction"
        ) as mock_transaction:
            mock_session = Mock(spec=Session)
            mock_session.scalar.side_effect = [100, 5]  # active_count, delisted_count
            mock_session.execute.return_value.all.return_value = [
                ("NASDAQ", 80),
                ("NYSE", 20),
            ]
            mock_transaction.return_value.__enter__.return_value = mock_session

            result = await symbol_service.get_symbol_statistics()

            assert result["active_symbols"] == 100
            assert result["delisted_symbols"] == 5
            assert result["total_symbols"] == 105
            assert result["by_exchange"] == {"NASDAQ": 80, "NYSE": 20}
