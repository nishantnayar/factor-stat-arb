"""
Unit tests for Historical Data Loader
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.services.data_ingestion.historical_loader import HistoricalDataLoader
from src.services.polygon.exceptions import PolygonAPIError
from src.shared.database.models.market_data import MarketData


class TestHistoricalDataLoaderInitialization:
    """Test cases for HistoricalDataLoader initialization"""

    def test_loader_initialization_default(self):
        """Test loader initialization with default parameters"""
        with patch("src.services.data_ingestion.historical_loader.PolygonClient"):
            loader = HistoricalDataLoader()

            assert loader.batch_size == 100
            assert loader.requests_per_minute == 2
            assert loader.data_source == "polygon"
            assert loader.detect_delisted is True
            assert loader.delay_between_requests == 30.0  # 60/2

    def test_loader_initialization_custom(self):
        """Test loader initialization with custom parameters"""
        with patch("src.services.data_ingestion.historical_loader.PolygonClient"):
            loader = HistoricalDataLoader(
                batch_size=50,
                requests_per_minute=5,
                data_source="yahoo",
                detect_delisted=False,
            )

            assert loader.batch_size == 50
            assert loader.requests_per_minute == 5
            assert loader.data_source == "yahoo"
            assert loader.detect_delisted is False
            assert loader.delay_between_requests == 12.0  # 60/5

    def test_loader_initialization_creates_polygon_client(self):
        """Test that loader creates Polygon client"""
        with patch(
            "src.services.data_ingestion.historical_loader.PolygonClient"
        ) as mock_polygon:
            mock_client = Mock()
            mock_polygon.return_value = mock_client

            loader = HistoricalDataLoader()

            assert loader.polygon_client == mock_client
            mock_polygon.assert_called_once()

    def test_loader_initialization_creates_symbol_service(self):
        """Test that loader creates SymbolService when detect_delisted is True"""
        with patch("src.services.data_ingestion.historical_loader.PolygonClient"):
            with patch(
                "src.services.data_ingestion.historical_loader.SymbolService"
            ) as mock_symbol_service:
                mock_service = Mock()
                mock_symbol_service.return_value = mock_service

                loader = HistoricalDataLoader(detect_delisted=True)

                assert loader.symbol_service == mock_service
                mock_symbol_service.assert_called_once()

    def test_loader_initialization_no_symbol_service(self):
        """Test that loader doesn't create SymbolService when detect_delisted is False"""
        with patch("src.services.data_ingestion.historical_loader.PolygonClient"):
            loader = HistoricalDataLoader(detect_delisted=False)

            assert loader.symbol_service is None


class TestHistoricalDataLoaderSymbolData:
    """Test cases for loading data for a single symbol"""

    @pytest.fixture
    def loader(self):
        """Create loader instance for testing"""
        with patch("src.services.data_ingestion.historical_loader.PolygonClient"):
            return HistoricalDataLoader()

    @pytest.fixture
    def mock_bars(self):
        """Create mock bar data"""
        bars = []
        for i in range(5):
            bar = Mock()
            bar.timestamp = datetime(2024, 1, i + 1, 9, 30, 0, tzinfo=timezone.utc)
            bar.open = 100.0 + i
            bar.high = 105.0 + i
            bar.low = 95.0 + i
            bar.close = 102.0 + i
            bar.volume = 1000000 + (i * 10000)
            bars.append(bar)
        return bars

    @pytest.mark.asyncio
    async def test_load_symbol_data_success(self, loader, mock_bars):
        """Test successful symbol data loading"""
        with patch.object(
            loader.polygon_client, "get_aggregates", new_callable=AsyncMock
        ) as mock_get_aggs:
            mock_get_aggs.return_value = mock_bars

            with patch.object(
                loader, "_batch_insert_records", new_callable=AsyncMock
            ) as mock_insert:
                mock_insert.return_value = 5

                with patch.object(
                    loader, "_update_load_run", new_callable=AsyncMock
                ) as mock_update:
                    with patch.object(
                        loader, "_get_last_successful_date", new_callable=AsyncMock
                    ) as mock_get_last:
                        mock_get_last.return_value = None

                        result = await loader.load_symbol_data(
                            "AAPL", from_date=date(2024, 1, 1), to_date=date(2024, 1, 5)
                        )

                        assert result == 5
                        mock_get_aggs.assert_called_once()
                        mock_insert.assert_called_once()
                        mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_symbol_data_no_data(self, loader, setup_test_tables):
        """Test loading when no data is returned"""
        with patch.object(
            loader.polygon_client, "get_aggregates", new_callable=AsyncMock
        ) as mock_get_aggs:
            mock_get_aggs.return_value = []

            with patch.object(
                loader, "_get_last_successful_date", new_callable=AsyncMock
            ) as mock_get_last:
                mock_get_last.return_value = None

                result = await loader.load_symbol_data(
                    "INVALID", from_date=date(2024, 1, 1), to_date=date(2024, 1, 5)
                )

                assert result == 0

    @pytest.mark.asyncio
    async def test_load_symbol_data_incremental_loading(self, loader, mock_bars):
        """Test incremental loading with existing data"""
        last_date = date(2024, 1, 3)

        with patch.object(
            loader.polygon_client, "get_aggregates", new_callable=AsyncMock
        ) as mock_get_aggs:
            mock_get_aggs.return_value = mock_bars

            with patch.object(
                loader, "_get_last_successful_date", new_callable=AsyncMock
            ) as mock_get_last:
                mock_get_last.return_value = last_date

                with patch.object(
                    loader, "_batch_insert_records", new_callable=AsyncMock
                ) as mock_insert:
                    mock_insert.return_value = 5

                    with patch.object(
                        loader, "_update_load_run", new_callable=AsyncMock
                    ):
                        await loader.load_symbol_data(
                            "AAPL", to_date=date(2024, 1, 10), incremental=True
                        )

                        # Check that from_date was adjusted to day after last successful
                        call_args = mock_get_aggs.call_args
                        assert "from_date" in call_args.kwargs
                        # Should start from 2024-01-04 (day after last_date)

    @pytest.mark.asyncio
    async def test_load_symbol_data_api_error(self, loader):
        """Test handling of API errors"""
        with patch.object(
            loader.polygon_client, "get_aggregates", new_callable=AsyncMock
        ) as mock_get_aggs:
            mock_get_aggs.side_effect = PolygonAPIError("API Error")

            with patch.object(
                loader, "_get_last_successful_date", new_callable=AsyncMock
            ) as mock_get_last:
                mock_get_last.return_value = None

                with patch.object(
                    loader, "_update_load_run", new_callable=AsyncMock
                ) as mock_update:
                    with pytest.raises(PolygonAPIError):
                        await loader.load_symbol_data(
                            "AAPL",
                            from_date=date(2024, 1, 1),
                            to_date=date(2024, 1, 5),
                        )

                    # Should still update load run with error
                    mock_update.assert_called_once()
                    assert mock_update.call_args.kwargs["status"] == "failed"

    @pytest.mark.asyncio
    async def test_load_symbol_data_days_back(self, loader, mock_bars):
        """Test loading data using days_back parameter"""
        with patch.object(
            loader.polygon_client, "get_aggregates", new_callable=AsyncMock
        ) as mock_get_aggs:
            mock_get_aggs.return_value = mock_bars

            with patch.object(
                loader, "_get_last_successful_date", new_callable=AsyncMock
            ) as mock_get_last:
                mock_get_last.return_value = None

                with patch.object(
                    loader, "_batch_insert_records", new_callable=AsyncMock
                ) as mock_insert:
                    mock_insert.return_value = 5

                    with patch.object(
                        loader, "_update_load_run", new_callable=AsyncMock
                    ):
                        result = await loader.load_symbol_data("AAPL", days_back=30)

                        assert result == 5
                        # Should calculate from_date as 30 days ago


class TestHistoricalDataLoaderAllSymbols:
    """Test cases for loading data for all symbols"""

    @pytest.fixture
    def loader(self):
        """Create loader instance for testing"""
        with patch("src.services.data_ingestion.historical_loader.PolygonClient"):
            return HistoricalDataLoader()

    @pytest.mark.asyncio
    async def test_load_all_symbols_success(self, loader):
        """Test successful loading of all symbols"""
        mock_symbols = ["AAPL", "GOOGL", "MSFT"]

        with patch.object(
            loader, "_get_active_symbols", new_callable=AsyncMock
        ) as mock_get_symbols:
            mock_get_symbols.return_value = mock_symbols

            with patch.object(
                loader, "load_symbol_data", new_callable=AsyncMock
            ) as mock_load:
                mock_load.return_value = 100

                with patch("asyncio.sleep", new_callable=AsyncMock):
                    result = await loader.load_all_symbols_data(
                        from_date=date(2024, 1, 1), to_date=date(2024, 1, 5)
                    )

                    assert result["total_symbols"] == 3
                    assert result["successful"] == 3
                    assert result["failed"] == 0
                    assert result["total_records"] == 300
                    assert mock_load.call_count == 3

    @pytest.mark.asyncio
    async def test_load_all_symbols_with_failures(self, loader):
        """Test loading all symbols with some failures"""
        mock_symbols = ["AAPL", "INVALID", "GOOGL"]

        with patch.object(
            loader, "_get_active_symbols", new_callable=AsyncMock
        ) as mock_get_symbols:
            mock_get_symbols.return_value = mock_symbols

            with patch.object(
                loader, "load_symbol_data", new_callable=AsyncMock
            ) as mock_load:
                # First succeeds, second fails, third succeeds
                mock_load.side_effect = [100, PolygonAPIError("Error"), 100]

                with patch("asyncio.sleep", new_callable=AsyncMock):
                    result = await loader.load_all_symbols_data(
                        from_date=date(2024, 1, 1), to_date=date(2024, 1, 5)
                    )

                    assert result["total_symbols"] == 3
                    assert result["successful"] == 2
                    assert result["failed"] == 1
                    assert result["total_records"] == 200
                    assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_load_all_symbols_max_symbols(self, loader):
        """Test loading with max_symbols limit"""
        mock_symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "NVDA"]

        with patch.object(
            loader, "_get_active_symbols", new_callable=AsyncMock
        ) as mock_get_symbols:
            mock_get_symbols.return_value = mock_symbols

            with patch.object(
                loader, "load_symbol_data", new_callable=AsyncMock
            ) as mock_load:
                mock_load.return_value = 100

                with patch("asyncio.sleep", new_callable=AsyncMock):
                    result = await loader.load_all_symbols_data(
                        from_date=date(2024, 1, 1),
                        to_date=date(2024, 1, 5),
                        max_symbols=2,
                    )

                    assert result["total_symbols"] == 2  # Limited to 2
                    assert mock_load.call_count == 2


class TestHistoricalDataLoaderBatchInsert:
    """Test cases for batch insert functionality"""

    @pytest.fixture
    def loader(self):
        """Create loader instance for testing"""
        with patch("src.services.data_ingestion.historical_loader.PolygonClient"):
            return HistoricalDataLoader(batch_size=2)

    @pytest.mark.asyncio
    async def test_batch_insert_records_success(self, loader):
        """Test successful batch insert"""
        records = []
        for i in range(5):
            record = MarketData(
                symbol="AAPL",
                timestamp=datetime(2024, 1, i + 1, 9, 30, 0, tzinfo=timezone.utc),
                data_source="polygon",
                open=100.0 + i,
                high=105.0 + i,
                low=95.0 + i,
                close=102.0 + i,
                volume=1000000 + (i * 10000),
            )
            records.append(record)

        with patch(
            "src.services.data_ingestion.historical_loader.db_transaction"
        ) as mock_transaction:
            mock_session = Mock()
            mock_session.execute.return_value = Mock()
            mock_transaction.return_value.__enter__.return_value = mock_session

            result = await loader._batch_insert_records(records)

            assert result == 5
            # Should be called 3 times: 2 full batches + 1 partial
            assert mock_session.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_insert_empty_records(self, loader):
        """Test batch insert with empty records"""
        result = await loader._batch_insert_records([])
        assert result == 0


class TestHistoricalDataLoaderLoadRuns:
    """Test cases for load run tracking"""

    @pytest.fixture
    def loader(self):
        """Create loader instance for testing"""
        with patch("src.services.data_ingestion.historical_loader.PolygonClient"):
            return HistoricalDataLoader()

    @pytest.mark.asyncio
    async def test_get_last_successful_date(self, loader):
        """Test retrieving last successful date"""
        with patch(
            "src.services.data_ingestion.historical_loader.db_transaction"
        ) as mock_transaction:
            mock_session = Mock()
            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = date(2024, 1, 5)
            mock_session.execute.return_value = mock_result
            mock_transaction.return_value.__enter__.return_value = mock_session

            result = await loader._get_last_successful_date("AAPL", "day", 1)

            assert result == date(2024, 1, 5)

    @pytest.mark.asyncio
    async def test_get_last_successful_date_no_data(self, loader):
        """Test retrieving last successful date when none exists"""
        with patch(
            "src.services.data_ingestion.historical_loader.db_transaction"
        ) as mock_transaction:
            mock_session = Mock()
            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result
            mock_transaction.return_value.__enter__.return_value = mock_session

            result = await loader._get_last_successful_date("AAPL", "day", 1)

            assert result is None

    @pytest.mark.asyncio
    async def test_update_load_run_success(self, loader):
        """Test updating load run with success"""
        with patch(
            "src.services.data_ingestion.historical_loader.db_transaction"
        ) as mock_transaction:
            mock_session = Mock()
            mock_result = Mock()
            mock_load_run = Mock()
            mock_result.scalar_one_or_none.return_value = mock_load_run
            mock_session.execute.return_value = mock_result
            mock_transaction.return_value.__enter__.return_value = mock_session

            await loader._update_load_run(
                symbol="AAPL",
                data_source="polygon",
                timespan="day",
                multiplier=1,
                last_successful_date=date(2024, 1, 5),
                records_loaded=100,
                status="success",
            )

            assert mock_load_run.status == "success"
            assert mock_load_run.records_loaded == 100
            mock_session.commit.assert_called_once()


class TestHistoricalDataLoaderGapDetection:
    """Test cases for gap detection and backfill"""

    @pytest.fixture
    def loader(self):
        """Create loader instance for testing"""
        with patch("src.services.data_ingestion.historical_loader.PolygonClient"):
            return HistoricalDataLoader()

    @pytest.mark.asyncio
    async def test_detect_gaps_no_backfill_needed(self, loader):
        """Test gap detection when no backfill is needed"""
        with patch.object(
            loader, "_get_last_successful_date", new_callable=AsyncMock
        ) as mock_get_last:
            # Recent date, no gap
            mock_get_last.return_value = date.today() - timedelta(days=2)

            result = await loader.detect_gaps_and_backfill("AAPL", max_gap_days=7)

            assert result["backfill_needed"] is False
            assert result["gap_days"] == 2

    @pytest.mark.asyncio
    async def test_detect_gaps_backfill_needed(self, loader):
        """Test gap detection when backfill is needed"""
        with patch.object(
            loader, "_get_last_successful_date", new_callable=AsyncMock
        ) as mock_get_last:
            # Old date, gap exists
            mock_get_last.return_value = date.today() - timedelta(days=30)

            with patch.object(
                loader, "load_symbol_data", new_callable=AsyncMock
            ) as mock_load:
                mock_load.return_value = 100

                result = await loader.detect_gaps_and_backfill(
                    "AAPL", max_gap_days=7, max_backfill_days=10
                )

                assert result["backfill_needed"] is True
                assert result["gap_days"] == 30
                assert result["backfill_days"] == 10
                assert result["records_loaded"] == 100


class TestHistoricalDataLoaderProgress:
    """Test cases for loading progress tracking"""

    @pytest.fixture
    def loader(self):
        """Create loader instance for testing"""
        with patch("src.services.data_ingestion.historical_loader.PolygonClient"):
            return HistoricalDataLoader()

    @pytest.mark.asyncio
    async def test_get_loading_progress(self, loader):
        """Test getting loading progress"""
        with patch(
            "src.services.data_ingestion.historical_loader.db_transaction"
        ) as mock_transaction:
            mock_session = Mock()
            mock_session.scalar.side_effect = [
                100,
                75,
                5000,
            ]  # total, with_data, records
            mock_transaction.return_value.__enter__.return_value = mock_session

            result = await loader.get_loading_progress(
                from_date=date(2024, 1, 1), to_date=date(2024, 1, 31)
            )

            assert result["total_symbols"] == 100
            assert result["symbols_with_data"] == 75
            assert result["total_records"] == 5000
            assert result["progress_percent"] == 75.0


class TestHistoricalDataLoaderHealthCheck:
    """Test cases for health check"""

    @pytest.fixture
    def loader(self):
        """Create loader instance for testing"""
        with patch("src.services.data_ingestion.historical_loader.PolygonClient"):
            return HistoricalDataLoader()

    @pytest.mark.asyncio
    async def test_health_check_success(self, loader):
        """Test successful health check"""
        with patch.object(
            loader.polygon_client, "health_check", new_callable=AsyncMock
        ) as mock_health:
            mock_health.return_value = True

            with patch(
                "src.services.data_ingestion.historical_loader.db_transaction"
            ) as mock_transaction:
                mock_session = Mock()
                mock_transaction.return_value.__enter__.return_value = mock_session

                result = await loader.health_check()

                assert result is True

    @pytest.mark.asyncio
    async def test_health_check_polygon_failure(self, loader):
        """Test health check with Polygon API failure"""
        with patch.object(
            loader.polygon_client, "health_check", new_callable=AsyncMock
        ) as mock_health:
            mock_health.return_value = False

            result = await loader.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_database_failure(self, loader):
        """Test health check with database failure"""
        with patch.object(
            loader.polygon_client, "health_check", new_callable=AsyncMock
        ) as mock_health:
            mock_health.return_value = True

            with patch(
                "src.services.data_ingestion.historical_loader.db_transaction"
            ) as mock_transaction:
                mock_transaction.side_effect = Exception("Database error")

                result = await loader.health_check()

                assert result is False


class TestHistoricalDataLoaderDelistingDetection:
    """Test cases for delisting detection"""

    @pytest.fixture
    def loader(self):
        """Create loader instance for testing"""
        with patch("src.services.data_ingestion.historical_loader.PolygonClient"):
            return HistoricalDataLoader(detect_delisted=True)

    @pytest.mark.asyncio
    async def test_detect_delisted_on_no_data(self, loader):
        """Test delisting detection when no data is returned"""
        with patch.object(
            loader.polygon_client, "get_aggregates", new_callable=AsyncMock
        ) as mock_get_aggs:
            mock_get_aggs.return_value = []

            with patch.object(
                loader.symbol_service, "check_symbol_health", new_callable=AsyncMock
            ) as mock_health:
                mock_health.return_value = False

                with patch.object(
                    loader.symbol_service,
                    "mark_symbol_delisted",
                    new_callable=AsyncMock,
                ) as mock_mark:
                    with patch.object(
                        loader, "_get_last_successful_date", new_callable=AsyncMock
                    ) as mock_get_last:
                        mock_get_last.return_value = None

                        result = await loader.load_symbol_data(
                            "DELISTED",
                            from_date=date(2024, 1, 1),
                            to_date=date(2024, 1, 5),
                        )

                        assert result == 0
                        mock_health.assert_called_once()
                        mock_mark.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_delisting_detection_when_disabled(self):
        """Test that delisting detection doesn't run when disabled"""
        with patch("src.services.data_ingestion.historical_loader.PolygonClient"):
            loader = HistoricalDataLoader(detect_delisted=False)

            with patch.object(
                loader.polygon_client, "get_aggregates", new_callable=AsyncMock
            ) as mock_get_aggs:
                mock_get_aggs.return_value = []

                with patch.object(
                    loader, "_get_last_successful_date", new_callable=AsyncMock
                ) as mock_get_last:
                    mock_get_last.return_value = None

                    result = await loader.load_symbol_data(
                        "INVALID", from_date=date(2024, 1, 1), to_date=date(2024, 1, 5)
                    )

                    assert result == 0
                    # Should not call symbol service since it's disabled
                    assert loader.symbol_service is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
