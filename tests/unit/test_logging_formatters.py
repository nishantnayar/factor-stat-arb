"""
Unit tests for Logging Formatters

Tests the custom logging formatters for structured logging.
"""

from datetime import datetime
from unittest.mock import Mock

import pytest

from src.shared.logging.formatters import (
    create_structured_message,
    extract_metadata,
    format_for_database,
    format_log_record,
    format_performance_log,
    format_trading_log,
)


class TestFormatLogRecord:
    """Test log record formatting"""

    @pytest.fixture
    def mock_record(self):
        """Create mock log record"""
        return {
            "time": datetime.now(),
            "level": Mock(name="INFO"),
            "message": "Test message",
            "name": "test_logger",
            "function": "test_function",
            "line": 42,
            "extra": {},
            "exception": None,
        }

    def test_format_log_record_basic(self, mock_record):
        """Test basic log record formatting"""
        result = format_log_record(mock_record)

        assert isinstance(result, dict)
        assert "timestamp" in result
        assert "level" in result
        assert "message" in result
        assert result["message"] == "Test message"

    def test_format_log_record_with_service(self, mock_record):
        """Test log record with service"""
        mock_record["extra"]["service"] = "trading"

        result = format_log_record(mock_record)

        assert result["service"] == "trading"

    def test_format_log_record_with_correlation_id(self, mock_record):
        """Test log record with correlation ID"""
        mock_record["extra"]["correlation_id"] = "test-123"

        result = format_log_record(mock_record)

        assert result["correlation_id"] == "test-123"

    def test_format_log_record_with_extra_fields(self, mock_record):
        """Test log record with extra fields"""
        mock_record["extra"]["custom_field"] = "custom_value"

        result = format_log_record(mock_record)

        assert result["custom_field"] == "custom_value"


class TestExtractMetadata:
    """Test metadata extraction"""

    def test_extract_metadata_basic(self):
        """Test basic metadata extraction"""
        record = {"extra": {"service": "trading", "correlation_id": "test-123"}}

        result = extract_metadata(record)

        assert result["service"] == "trading"
        assert result["correlation_id"] == "test-123"

    def test_extract_metadata_performance(self):
        """Test performance metadata extraction"""
        record = {"extra": {"execution_time_ms": 150.5, "memory_usage_mb": 25.3}}

        result = extract_metadata(record)

        assert result["execution_time_ms"] == 150.5
        assert result["memory_usage_mb"] == 25.3

    def test_extract_metadata_trading_fields(self):
        """Test trading fields extraction"""
        record = {
            "extra": {
                "trade_id": "TRADE123",
                "symbol": "AAPL",
                "quantity": 100,
                "price": 150.0,
            }
        }

        result = extract_metadata(record)

        assert result["trade_id"] == "TRADE123"
        assert result["symbol"] == "AAPL"

    def test_extract_metadata_empty(self):
        """Test empty metadata"""
        record = {"extra": {}}

        result = extract_metadata(record)

        assert isinstance(result, dict)


class TestFormatForDatabase:
    """Test database formatting"""

    @pytest.fixture
    def mock_record(self):
        """Create mock log record"""
        return {
            "time": datetime.now(),
            "level": Mock(name="INFO"),
            "message": "Test message",
            "extra": {"service": "trading"},
            "exception": None,
        }

    def test_format_for_database_basic(self, mock_record):
        """Test basic database formatting"""
        result = format_for_database(mock_record)

        assert isinstance(result, dict)
        assert "timestamp" in result
        assert "level" in result
        assert "message" in result
        assert "service" in result

    def test_format_for_database_with_event_type(self, mock_record):
        """Test database formatting with event type"""
        mock_record["extra"]["event_type"] = "trade_execution"

        result = format_for_database(mock_record)

        assert result["event_type"] == "trade_execution"


class TestCreateStructuredMessage:
    """Test structured message creation"""

    def test_create_structured_message_basic(self):
        """Test basic structured message"""
        result = create_structured_message("Test message")

        assert result == "Test message"

    def test_create_structured_message_with_metadata(self):
        """Test structured message with metadata"""
        result = create_structured_message(
            "Trade executed", symbol="AAPL", quantity=100, price=150.0
        )

        assert "Test executed" in result or "Trade executed" in result
        assert isinstance(result, str)

    def test_create_structured_message_with_none_values(self):
        """Test structured message with None values"""
        result = create_structured_message("Test message", field1="value1", field2=None)

        assert isinstance(result, str)


class TestFormatPerformanceLog:
    """Test performance log formatting"""

    def test_format_performance_log_basic(self):
        """Test basic performance log"""
        result = format_performance_log("database_query", 150.5)

        assert result["log_type"] == "performance"
        assert result["operation"] == "database_query"
        assert result["execution_time_ms"] == 150.5
        assert "timestamp" in result

    def test_format_performance_log_with_memory(self):
        """Test performance log with memory"""
        result = format_performance_log("data_processing", 500.0, memory_usage_mb=128.5)

        assert result["execution_time_ms"] == 500.0
        assert result["memory_usage_mb"] == 128.5

    def test_format_performance_log_with_metadata(self):
        """Test performance log with extra metadata"""
        result = format_performance_log(
            "api_call", 200.0, endpoint="/api/trades", status_code=200
        )

        assert result["endpoint"] == "/api/trades"
        assert result["status_code"] == 200


class TestFormatTradingLog:
    """Test trading log formatting"""

    def test_format_trading_log_basic(self):
        """Test basic trading log"""
        result = format_trading_log("TRADE123", "AAPL", "buy", 100, 150.0)

        assert result["log_type"] == "trading"
        assert result["trade_id"] == "TRADE123"
        assert result["symbol"] == "AAPL"
        assert result["side"] == "buy"
        assert result["quantity"] == 100
        assert result["price"] == 150.0
        assert "timestamp" in result

    def test_format_trading_log_with_metadata(self):
        """Test trading log with extra metadata"""
        result = format_trading_log(
            "TRADE456",
            "MSFT",
            "sell",
            50,
            350.0,
            strategy="momentum",
            order_id="ORDER789",
        )

        assert result["strategy"] == "momentum"
        assert result["order_id"] == "ORDER789"
