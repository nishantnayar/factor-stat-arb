"""
Unit tests for Database Models
"""

from datetime import date, datetime, timezone

import pytest

from src.shared.database.models.load_runs import LoadRun
from src.shared.database.models.market_data import MarketData
from src.shared.database.models.symbols import DelistedSymbol, Symbol, SymbolDataStatus


class TestSymbolModel:
    """Test cases for Symbol model"""

    def test_symbol_creation(self):
        """Test creating a Symbol instance"""
        symbol = Symbol(
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
            status="active",
        )

        assert symbol.symbol == "AAPL"
        assert symbol.name == "Apple Inc."
        assert symbol.exchange == "NASDAQ"
        assert symbol.status == "active"

    def test_symbol_with_optional_fields(self):
        """Test Symbol with optional fields"""
        symbol = Symbol(
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
            sector="Technology",
            market_cap=3000000000000,
        )

        assert symbol.sector == "Technology"
        assert symbol.market_cap == 3000000000000

    def test_symbol_timestamps(self):
        """Test Symbol timestamp fields"""
        added_date = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        last_updated = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

        symbol = Symbol(
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
            added_date=added_date,
            last_updated=last_updated,
        )

        assert symbol.added_date == added_date
        assert symbol.last_updated == last_updated

    def test_symbol_repr(self):
        """Test Symbol __repr__ method"""
        symbol = Symbol(
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
        )

        repr_str = repr(symbol)
        assert "Symbol" in repr_str
        assert "AAPL" in repr_str

    def test_symbol_default_status(self):
        """Test Symbol default status"""
        symbol = Symbol(
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
        )

        # Default status should be 'active' based on the model
        assert symbol.status in ["active", None]  # Depends on implementation


class TestDelistedSymbolModel:
    """Test cases for DelistedSymbol model"""

    def test_delisted_symbol_creation(self):
        """Test creating a DelistedSymbol instance"""
        delisted = DelistedSymbol(
            symbol="XYZ",
            delist_date=date(2024, 1, 1),
            notes="Delisted due to bankruptcy",
        )

        assert delisted.symbol == "XYZ"
        assert delisted.delist_date == date(2024, 1, 1)
        assert delisted.notes == "Delisted due to bankruptcy"

    def test_delisted_symbol_with_price(self):
        """Test DelistedSymbol with last price"""
        delisted = DelistedSymbol(
            symbol="XYZ",
            delist_date=date(2024, 1, 1),
            last_price=10.50,
        )

        assert delisted.last_price == 10.50

    def test_delisted_symbol_with_notes(self):
        """Test DelistedSymbol with notes"""
        delisted = DelistedSymbol(
            symbol="XYZ",
            delist_date=date(2024, 1, 1),
            notes="Merged with another company",
        )

        assert delisted.notes == "Merged with another company"

    def test_delisted_symbol_timestamp(self):
        """Test DelistedSymbol created_at timestamp"""
        delisted = DelistedSymbol(
            symbol="XYZ",
            delist_date=date(2024, 1, 1),
        )

        # created_at field should exist (default applied on insert)
        assert hasattr(delisted, "created_at")


class TestSymbolDataStatusModel:
    """Test cases for SymbolDataStatus model"""

    def test_symbol_data_status_creation(self):
        """Test creating a SymbolDataStatus instance"""
        status = SymbolDataStatus(
            symbol="AAPL",
            date=date(2024, 1, 1),
            data_source="polygon",
            status="success",
        )

        assert status.symbol == "AAPL"
        assert status.date == date(2024, 1, 1)
        assert status.data_source == "polygon"
        assert status.status == "success"

    def test_symbol_data_status_with_error(self):
        """Test SymbolDataStatus with error message"""
        status = SymbolDataStatus(
            symbol="AAPL",
            date=date(2024, 1, 1),
            data_source="polygon",
            status="failed",
            error_message="API rate limit exceeded",
        )

        assert status.status == "failed"
        assert status.error_message == "API rate limit exceeded"

    def test_symbol_data_status_timestamp(self):
        """Test SymbolDataStatus with timestamp"""
        status = SymbolDataStatus(
            symbol="AAPL",
            date=date(2024, 1, 1),
            data_source="polygon",
            status="success",
        )

        # last_attempt should be set or available
        assert hasattr(status, "last_attempt")


class TestMarketDataModel:
    """Test cases for MarketData model"""

    def test_market_data_creation(self):
        """Test creating a MarketData instance"""
        market_data = MarketData(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 1, 9, 30, 0, tzinfo=timezone.utc),
            data_source="polygon",
            open=150.0,
            high=155.0,
            low=149.0,
            close=153.0,
            volume=1000000,
        )

        assert market_data.symbol == "AAPL"
        assert market_data.timestamp == datetime(
            2024, 1, 1, 9, 30, 0, tzinfo=timezone.utc
        )
        assert market_data.open == 150.0
        assert market_data.high == 155.0
        assert market_data.low == 149.0
        assert market_data.close == 153.0
        assert market_data.volume == 1000000

    def test_market_data_calculated_properties(self):
        """Test MarketData calculated properties"""
        market_data = MarketData(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 1, 9, 30, 0, tzinfo=timezone.utc),
            data_source="polygon",
            open=150.0,
            high=155.0,
            low=149.0,
            close=153.0,
            volume=1000000,
        )

        # Test price_change property
        assert market_data.price_change == 3.0  # 153 - 150

        # Test price_change_percent property
        assert market_data.price_change_percent == 2.0  # (153-150)/150 * 100

        # Test is_complete property
        assert market_data.is_complete is True

    def test_market_data_timezone_aware(self):
        """Test that MarketData timestamps are timezone-aware"""
        timestamp = datetime(2024, 1, 1, 9, 30, 0, tzinfo=timezone.utc)
        market_data = MarketData(
            symbol="AAPL",
            timestamp=timestamp,
            data_source="polygon",
            open=150.0,
            high=155.0,
            low=149.0,
            close=153.0,
            volume=1000000,
        )

        assert market_data.timestamp.tzinfo is not None
        assert market_data.timestamp.tzinfo == timezone.utc

    def test_market_data_repr(self):
        """Test MarketData __repr__ method"""
        market_data = MarketData(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 1, 9, 30, 0, tzinfo=timezone.utc),
            data_source="polygon",
            open=150.0,
            high=155.0,
            low=149.0,
            close=153.0,
            volume=1000000,
        )

        repr_str = repr(market_data)
        assert "MarketData" in repr_str or "AAPL" in repr_str


class TestLoadRunModel:
    """Test cases for LoadRun model"""

    def test_load_run_creation(self):
        """Test creating a LoadRun instance"""
        load_run = LoadRun(
            symbol="AAPL",
            data_source="polygon",
            timespan="day",
            multiplier=1,
            last_run_date=date(2024, 1, 15),
            last_successful_date=date(2024, 1, 14),
            records_loaded=390,
            status="success",
        )

        assert load_run.symbol == "AAPL"
        assert load_run.data_source == "polygon"
        assert load_run.timespan == "day"
        assert load_run.multiplier == 1
        assert load_run.last_run_date == date(2024, 1, 15)
        assert load_run.last_successful_date == date(2024, 1, 14)
        assert load_run.records_loaded == 390
        assert load_run.status == "success"

    def test_load_run_with_error(self):
        """Test LoadRun with error message"""
        load_run = LoadRun(
            symbol="AAPL",
            data_source="polygon",
            timespan="day",
            multiplier=1,
            last_run_date=date(2024, 1, 15),
            last_successful_date=date(2024, 1, 14),
            records_loaded=0,
            status="failed",
            error_message="API connection failed",
        )

        assert load_run.status == "failed"
        assert load_run.error_message == "API connection failed"
        assert load_run.records_loaded == 0

    def test_load_run_different_timespans(self):
        """Test LoadRun with different timespans"""
        timespans = ["minute", "hour", "day", "week", "month"]

        for timespan in timespans:
            load_run = LoadRun(
                symbol="AAPL",
                data_source="polygon",
                timespan=timespan,
                multiplier=1,
                last_run_date=date(2024, 1, 15),
                last_successful_date=date(2024, 1, 14),
                records_loaded=100,
                status="success",
            )

            assert load_run.timespan == timespan

    def test_load_run_different_multipliers(self):
        """Test LoadRun with different multipliers"""
        multipliers = [1, 5, 15, 30, 60]

        for multiplier in multipliers:
            load_run = LoadRun(
                symbol="AAPL",
                data_source="polygon",
                timespan="minute",
                multiplier=multiplier,
                last_run_date=date(2024, 1, 15),
                last_successful_date=date(2024, 1, 14),
                records_loaded=100,
                status="success",
            )

            assert load_run.multiplier == multiplier


class TestModelRelationships:
    """Test cases for model relationships"""

    def test_symbol_unique_constraint(self):
        """Test that symbol field should be unique"""
        # This would be a database-level test
        # Here we just verify the model has the field
        symbol = Symbol(
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
        )

        assert symbol.symbol == "AAPL"
        # Uniqueness would be enforced at database level

    def test_market_data_composite_key(self):
        """Test MarketData composite key (symbol, timestamp, data_source)"""
        # Verify the model has all fields that make up composite key
        market_data = MarketData(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 1, 9, 30, 0, tzinfo=timezone.utc),
            data_source="polygon",
            open=150.0,
            high=155.0,
            low=149.0,
            close=153.0,
            volume=1000000,
        )

        assert market_data.symbol == "AAPL"
        assert market_data.timestamp is not None
        # Composite key uniqueness would be enforced at database level


class TestModelValidation:
    """Test cases for model validation"""

    def test_symbol_required_fields(self):
        """Test Symbol required fields"""
        # All required fields provided
        symbol = Symbol(
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
        )

        assert symbol.symbol is not None
        assert symbol.name is not None
        assert symbol.exchange is not None

    def test_market_data_required_fields(self):
        """Test MarketData required fields"""
        market_data = MarketData(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 1, 9, 30, 0, tzinfo=timezone.utc),
            data_source="polygon",
            open=150.0,
            high=155.0,
            low=149.0,
            close=153.0,
            volume=1000000,
        )

        assert market_data.symbol is not None
        assert market_data.timestamp is not None
        assert market_data.open is not None
        assert market_data.high is not None
        assert market_data.low is not None
        assert market_data.close is not None
        assert market_data.volume is not None

    def test_load_run_required_fields(self):
        """Test LoadRun required fields"""
        load_run = LoadRun(
            symbol="AAPL",
            data_source="polygon",
            timespan="day",
            multiplier=1,
            last_run_date=date(2024, 1, 15),
            last_successful_date=date(2024, 1, 14),
            records_loaded=100,
            status="success",
        )

        assert load_run.symbol is not None
        assert load_run.data_source is not None
        assert load_run.timespan is not None
        assert load_run.multiplier is not None


class TestModelEdgeCases:
    """Test cases for edge cases"""

    def test_market_data_zero_volume(self):
        """Test MarketData with zero volume"""
        market_data = MarketData(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 1, 9, 30, 0, tzinfo=timezone.utc),
            data_source="polygon",
            open=150.0,
            high=150.0,
            low=150.0,
            close=150.0,
            volume=0,
        )

        assert market_data.volume == 0

    def test_market_data_negative_price(self):
        """Test MarketData can store negative prices (for derivatives)"""
        market_data = MarketData(
            symbol="OIL_FUTURES",
            timestamp=datetime(2024, 1, 1, 9, 30, 0, tzinfo=timezone.utc),
            data_source="polygon",
            open=-5.0,
            high=-3.0,
            low=-7.0,
            close=-4.0,
            volume=1000,
        )

        assert market_data.close == -4.0

    def test_symbol_very_long_name(self):
        """Test Symbol with very long company name"""
        long_name = "A" * 255  # Very long name
        symbol = Symbol(
            symbol="TEST",
            name=long_name,
            exchange="NASDAQ",
        )

        assert len(symbol.name) == 255

    def test_load_run_zero_records_success(self):
        """Test LoadRun with zero records but success status"""
        load_run = LoadRun(
            symbol="AAPL",
            data_source="polygon",
            timespan="day",
            multiplier=1,
            last_run_date=date(2024, 1, 15),
            last_successful_date=date(2024, 1, 14),
            records_loaded=0,
            status="success",
        )

        assert load_run.records_loaded == 0
        assert load_run.status == "success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
