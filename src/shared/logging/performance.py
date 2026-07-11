"""
Performance tracking decorators and utilities
"""

import functools
import time
from typing import Any, Callable, TypeVar

import psutil
from loguru import logger

from .correlation import get_correlation_context

F = TypeVar("F", bound=Callable[..., Any])


def log_performance(
    track_memory: bool = False, track_args: bool = False, log_level: str = "INFO"
) -> Callable[[F], F]:
    """
    Decorator to log function execution time and optionally memory usage

    Args:
        track_memory: Whether to track memory usage
        track_args: Whether to log function arguments (be careful with sensitive data)
        log_level: Log level for performance logs

    Returns:
        Decorator function
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get function metadata
            func_name = f"{func.__module__}.{func.__name__}"
            start_time = time.time()

            # Track memory usage if requested
            memory_before = None
            if track_memory:
                process = psutil.Process()
                memory_before = process.memory_info().rss / 1024 / 1024  # MB

            # Get correlation context
            correlation_context = get_correlation_context()

            # Prepare log data
            log_data = {
                "log_type": "performance",
                "operation": func_name,
                **correlation_context,
            }

            # Add arguments if requested
            if track_args:
                log_data["args"] = str(args) if args else None
                log_data["kwargs"] = str(kwargs) if kwargs else None

            try:
                # Execute function
                result = func(*args, **kwargs)

                # Calculate execution time
                execution_time_ms = (time.time() - start_time) * 1000

                # Calculate memory usage if requested
                memory_after = None
                memory_usage_mb = None
                if track_memory:
                    memory_after = process.memory_info().rss / 1024 / 1024  # MB
                    memory_usage_mb = (
                        memory_after - memory_before if memory_before else None
                    )

                # Log performance metrics
                performance_data = {
                    "execution_time_ms": round(execution_time_ms, 2),
                    **log_data,
                }

                if memory_usage_mb is not None:
                    performance_data["memory_usage_mb"] = round(memory_usage_mb, 2)

                # Log based on level
                if log_level.upper() == "DEBUG":
                    logger.debug(f"Performance: {func_name}", **performance_data)
                elif log_level.upper() == "INFO":
                    logger.info(f"Performance: {func_name}", **performance_data)
                elif log_level.upper() == "WARNING":
                    logger.warning(f"Performance: {func_name}", **performance_data)
                else:
                    logger.info(f"Performance: {func_name}", **performance_data)

                return result

            except Exception as e:
                # Calculate execution time even for failed functions
                execution_time_ms = (time.time() - start_time) * 1000

                # Log performance with error
                error_data = {
                    "execution_time_ms": round(execution_time_ms, 2),
                    "error": str(e),
                    "error_type": type(e).__name__,
                    **log_data,
                }

                logger.error(f"Performance (ERROR): {func_name}", **error_data)
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


def track_execution_time(operation_name: str, log_level: str = "INFO") -> Callable:
    """
    Decorator to track execution time for a specific operation

    Args:
        operation_name: Name of the operation
        log_level: Log level for performance logs

    Returns:
        Decorator function
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                execution_time_ms = (time.time() - start_time) * 1000

                # Log execution time
                log_data = {
                    "log_type": "performance",
                    "operation": operation_name,
                    "execution_time_ms": round(execution_time_ms, 2),
                    **get_correlation_context(),
                }

                if log_level.upper() == "DEBUG":
                    logger.debug(f"Execution time: {operation_name}", **log_data)
                elif log_level.upper() == "INFO":
                    logger.info(f"Execution time: {operation_name}", **log_data)
                elif log_level.upper() == "WARNING":
                    logger.warning(f"Execution time: {operation_name}", **log_data)
                else:
                    logger.info(f"Execution time: {operation_name}", **log_data)

                return result

            except Exception as e:
                execution_time_ms = (time.time() - start_time) * 1000

                error_data = {
                    "log_type": "performance",
                    "operation": operation_name,
                    "execution_time_ms": round(execution_time_ms, 2),
                    "error": str(e),
                    "error_type": type(e).__name__,
                    **get_correlation_context(),
                }

                logger.error(f"Execution time (ERROR): {operation_name}", **error_data)
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


def log_memory_usage(operation_name: str) -> Callable:
    """
    Decorator to log memory usage for a specific operation

    Args:
        operation_name: Name of the operation

    Returns:
        Decorator function
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            process = psutil.Process()
            memory_before = process.memory_info().rss / 1024 / 1024  # MB

            try:
                result = func(*args, **kwargs)
                memory_after = process.memory_info().rss / 1024 / 1024  # MB
                memory_usage_mb = memory_after - memory_before

                # Log memory usage
                log_data = {
                    "log_type": "performance",
                    "operation": operation_name,
                    "memory_usage_mb": round(memory_usage_mb, 2),
                    "memory_before_mb": round(memory_before, 2),
                    "memory_after_mb": round(memory_after, 2),
                    **get_correlation_context(),
                }

                logger.info(f"Memory usage: {operation_name}", **log_data)
                return result

            except Exception as e:
                memory_after = process.memory_info().rss / 1024 / 1024  # MB
                memory_usage_mb = memory_after - memory_before

                error_data = {
                    "log_type": "performance",
                    "operation": operation_name,
                    "memory_usage_mb": round(memory_usage_mb, 2),
                    "memory_before_mb": round(memory_before, 2),
                    "memory_after_mb": round(memory_after, 2),
                    "error": str(e),
                    "error_type": type(e).__name__,
                    **get_correlation_context(),
                }

                logger.error(f"Memory usage (ERROR): {operation_name}", **error_data)
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


def log_database_query(query_name: str, log_level: str = "DEBUG") -> Callable:
    """
    Decorator to log database query execution

    Args:
        query_name: Name of the query
        log_level: Log level for query logs

    Returns:
        Decorator function
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                execution_time_ms = (time.time() - start_time) * 1000

                # Log query execution
                log_data = {
                    "log_type": "database",
                    "operation": query_name,
                    "execution_time_ms": round(execution_time_ms, 2),
                    **get_correlation_context(),
                }

                if log_level.upper() == "DEBUG":
                    logger.debug(f"Database query: {query_name}", **log_data)
                elif log_level.upper() == "INFO":
                    logger.info(f"Database query: {query_name}", **log_data)
                else:
                    logger.debug(f"Database query: {query_name}", **log_data)

                return result

            except Exception as e:
                execution_time_ms = (time.time() - start_time) * 1000

                error_data = {
                    "log_type": "database",
                    "operation": query_name,
                    "execution_time_ms": round(execution_time_ms, 2),
                    "error": str(e),
                    "error_type": type(e).__name__,
                    **get_correlation_context(),
                }

                logger.error(f"Database query (ERROR): {query_name}", **error_data)
                raise

        return wrapper  # type: ignore[return-value]

    return decorator
