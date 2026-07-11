"""
Unit tests for Logging Performance Tracking

Tests the performance tracking and monitoring functionality.
"""

import time

import pytest

from src.shared.logging.performance import (
    log_database_query,
    log_memory_usage,
    log_performance,
    track_execution_time,
)


class TestLogPerformanceDecorator:
    """Test log_performance decorator"""

    def test_log_performance_basic(self):
        """Test basic performance logging"""

        @log_performance(log_level="INFO")
        def test_function():
            time.sleep(0.05)
            return "result"

        result = test_function()

        assert result == "result"

    def test_log_performance_with_args(self):
        """Test performance logging with arguments"""

        @log_performance(track_args=True)
        def test_function(x, y):
            return x + y

        result = test_function(2, 3)

        assert result == 5

    def test_log_performance_with_memory(self):
        """Test performance logging with memory tracking"""

        @log_performance(track_memory=True)
        def test_function():
            # Create some data to use memory
            data = [0] * 10000
            return len(data)

        result = test_function()

        assert result == 10000

    def test_log_performance_with_exception(self):
        """Test performance logging with exception"""

        @log_performance()
        def test_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            test_function()

    def test_log_performance_different_log_levels(self):
        """Test performance logging with different log levels"""
        for level in ["DEBUG", "INFO", "WARNING"]:

            @log_performance(log_level=level)
            def test_function():
                return "result"

            result = test_function()
            assert result == "result"


class TestTrackExecutionTimeDecorator:
    """Test track_execution_time decorator"""

    def test_track_execution_time_basic(self):
        """Test basic execution time tracking"""

        @track_execution_time("test_operation")
        def test_function():
            time.sleep(0.05)
            return "result"

        result = test_function()

        assert result == "result"

    def test_track_execution_time_with_args(self):
        """Test execution time tracking with arguments"""

        @track_execution_time("calculation")
        def test_function(x, y):
            return x * y

        result = test_function(5, 10)

        assert result == 50

    def test_track_execution_time_with_exception(self):
        """Test execution time tracking with exception"""

        @track_execution_time("failing_operation")
        def test_function():
            raise RuntimeError("Test error")

        with pytest.raises(RuntimeError):
            test_function()

    def test_track_execution_time_different_log_levels(self):
        """Test execution time tracking with different log levels"""

        @track_execution_time("test_op", log_level="DEBUG")
        def debug_function():
            return "debug"

        @track_execution_time("test_op", log_level="WARNING")
        def warning_function():
            return "warning"

        assert debug_function() == "debug"
        assert warning_function() == "warning"


class TestLogMemoryUsageDecorator:
    """Test log_memory_usage decorator"""

    def test_log_memory_usage_basic(self):
        """Test basic memory usage logging"""

        @log_memory_usage("memory_test")
        def test_function():
            # Allocate some memory
            data = [0] * 100000
            return len(data)

        result = test_function()

        assert result == 100000

    def test_log_memory_usage_with_exception(self):
        """Test memory usage logging with exception"""

        @log_memory_usage("failing_memory_test")
        def test_function():
            raise MemoryError("Test error")

        with pytest.raises(MemoryError):
            test_function()


class TestLogDatabaseQueryDecorator:
    """Test log_database_query decorator"""

    def test_log_database_query_basic(self):
        """Test basic database query logging"""

        @log_database_query("select_users")
        def test_query():
            time.sleep(0.05)
            return ["user1", "user2"]

        result = test_query()

        assert len(result) == 2
        assert "user1" in result

    def test_log_database_query_with_exception(self):
        """Test database query logging with exception"""

        @log_database_query("failing_query")
        def test_query():
            raise Exception("Database error")

        with pytest.raises(Exception):
            test_query()

    def test_log_database_query_with_log_level(self):
        """Test database query logging with custom log level"""

        @log_database_query("select_trades", log_level="INFO")
        def test_query():
            return [{"trade_id": 1}, {"trade_id": 2}]

        result = test_query()

        assert len(result) == 2


class TestPerformanceIntegration:
    """Test performance decorators integration"""

    def test_multiple_decorators(self):
        """Test using multiple performance decorators"""

        @log_performance(track_memory=True)
        @track_execution_time("complex_operation")
        def complex_function(x):
            time.sleep(0.05)
            return x * 2

        result = complex_function(5)

        assert result == 10

    def test_decorator_preserves_function_metadata(self):
        """Test that decorators preserve function metadata"""

        @log_performance()
        def documented_function():
            """This is a documented function"""
            return "result"

        assert documented_function.__doc__ == "This is a documented function"
        assert documented_function.__name__ == "documented_function"

    def test_nested_performance_tracking(self):
        """Test nested performance tracking"""

        @log_performance()
        def outer_function():
            @log_performance()
            def inner_function():
                return "inner"

            return inner_function()

        result = outer_function()

        assert result == "inner"
