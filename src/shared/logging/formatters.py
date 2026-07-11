"""
Log formatting utilities
"""

import json
from datetime import datetime
from typing import Any
from typing import Any as LogRecord
from typing import Dict, Optional

from src.shared.logging.config import detect_service_from_module
from src.shared.logging.correlation import get_correlation_id
from src.shared.utils.timezone import ensure_utc_timestamp, format_timestamp_for_logging


def format_log_record(record: LogRecord) -> Dict[str, Any]:
    """
    Format log record for structured logging

    Args:
        record: Loguru record object

    Returns:
        Dict: Formatted log record
    """
    # Ensure timestamp is timezone-aware and format for logging
    timestamp = ensure_utc_timestamp(record["time"])
    formatted_timestamp = format_timestamp_for_logging(timestamp)

    formatted_record = {
        "timestamp": timestamp.isoformat(),
        "timestamp_display": formatted_timestamp,
        "level": record["level"].name,
        "message": record["message"],
        "module": record["name"],
        "function": record["function"],
        "line": record["line"],
    }

    # Add service information if available
    if "service" in record["extra"]:
        formatted_record["service"] = record["extra"]["service"]

    # Add correlation ID if available
    if "correlation_id" in record["extra"]:
        formatted_record["correlation_id"] = record["extra"]["correlation_id"]

    # Add any additional extra fields
    for key, value in record["extra"].items():
        if key not in ["service", "correlation_id"]:
            formatted_record[key] = value

    # Add exception information if present
    if record["exception"]:
        formatted_record["exception"] = {
            "type": record["exception"].type.__name__,
            "value": str(record["exception"].value),
            "traceback": record["exception"].traceback,
        }

    return formatted_record


def extract_metadata(record: LogRecord) -> Dict[str, Any]:
    """
    Extract metadata from log record

    Args:
        record: Loguru record object

    Returns:
        Dict: Extracted metadata
    """
    metadata = {}

    # Extract service information
    if "service" in record["extra"]:
        metadata["service"] = record["extra"]["service"]

    # Extract correlation ID
    if "correlation_id" in record["extra"]:
        metadata["correlation_id"] = record["extra"]["correlation_id"]

    # Extract performance metrics
    if "execution_time_ms" in record["extra"]:
        metadata["execution_time_ms"] = record["extra"]["execution_time_ms"]

    if "memory_usage_mb" in record["extra"]:
        metadata["memory_usage_mb"] = record["extra"]["memory_usage_mb"]

    # Extract trading-specific metadata
    trading_fields = [
        "trade_id",
        "order_id",
        "symbol",
        "quantity",
        "price",
        "side",
        "strategy",
        "execution_time_ms",
        "status",
        "error_message",
    ]

    for field in trading_fields:
        if field in record["extra"]:
            metadata[field] = record["extra"][field]

    # Extract any other custom metadata
    for key, value in record["extra"].items():
        if key not in ["service", "correlation_id"] and key not in trading_fields:
            metadata[key] = value

    return metadata


def format_for_database(record: LogRecord) -> Dict[str, Any]:
    """
    Format log record for database storage

    Args:
        record: Loguru record object

    Returns:
        Dict: Database-formatted record
    """
    # Base record with timezone-aware timestamp
    timestamp = ensure_utc_timestamp(record["time"])

    # Check if this is a performance log
    log_type = record["extra"].get("log_type", "system")
    
    # Detect service from module name if not in extra context
    service = record["extra"].get("service")
    if not service:
        # Try to detect from module name (record["name"] contains the module path)
        service = detect_service_from_module(record["name"])
    
    # Get correlation_id from extra context or thread-local context
    correlation_id = record["extra"].get("correlation_id")
    if not correlation_id:
        # Try to get from thread-local correlation context
        correlation_id = get_correlation_id()
        # If still None, auto-generate one for this log entry
        # (This ensures every log has a correlation_id for tracking)
        if not correlation_id:
            from uuid import uuid4
            correlation_id = str(uuid4())
            # Store it in thread-local context so subsequent logs in same thread use same ID
            from src.shared.logging.correlation import set_correlation_id
            set_correlation_id(correlation_id)
    
    # Get event_type from extra context, or infer from log level
    event_type = record["extra"].get("event_type")
    if not event_type:
        # Auto-infer event_type from log level if not explicitly set
        level_name = record["level"].name
        event_type_map = {
            "DEBUG": "debug",
            "INFO": "info",
            "WARNING": "warning",
            "ERROR": "error",
            "CRITICAL": "critical",
        }
        event_type = event_type_map.get(level_name, "unknown")
    
    db_record = {
        "timestamp": timestamp,
        "level": record["level"].name,
        "message": record["message"],
        "service": service,
        "correlation_id": correlation_id,  # Can be None - always include
        "event_type": event_type,  # Can be None - always include
        "metadata": extract_metadata(record),
        "log_type": log_type,
    }

    # For performance logs, add performance-specific fields
    if log_type == "performance":
        metadata = extract_metadata(record)
        db_record["operation"] = record["extra"].get("operation") or metadata.get("operation", "unknown")
        db_record["execution_time_ms"] = record["extra"].get("execution_time_ms") or metadata.get("execution_time_ms", 0)
        db_record["memory_usage_mb"] = record["extra"].get("memory_usage_mb") or metadata.get("memory_usage_mb")
        db_record["cpu_usage_percent"] = record["extra"].get("cpu_usage_percent") or metadata.get("cpu_usage_percent")

    return db_record


def format_for_file(record: LogRecord) -> str:
    """
    Format log record for file output

    Args:
        record: Loguru record object

    Returns:
        str: Formatted log string
    """
    # Use the default Loguru format
    return str(record["message"])


def create_structured_message(message: str, **kwargs: Any) -> str:
    """
    Create structured log message with metadata

    Args:
        message: Base log message
        **kwargs: Additional metadata

    Returns:
        str: Structured message
    """
    if not kwargs:
        return message

    # Create structured message
    structured_data = {k: v for k, v in kwargs.items() if v is not None}

    if structured_data:
        return f"{message} | {json.dumps(structured_data, default=str)}"

    return message


def format_performance_log(
    operation: str,
    execution_time_ms: float,
    memory_usage_mb: Optional[float] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Format performance log entry

    Args:
        operation: Operation name
        execution_time_ms: Execution time in milliseconds
        memory_usage_mb: Memory usage in MB (optional)
        **kwargs: Additional metadata

    Returns:
        Dict: Formatted performance log
    """
    performance_log = {
        "log_type": "performance",
        "operation": operation,
        "execution_time_ms": execution_time_ms,
        "timestamp": ensure_utc_timestamp(datetime.now()).isoformat(),
    }

    if memory_usage_mb is not None:
        performance_log["memory_usage_mb"] = memory_usage_mb

    # Add any additional metadata
    performance_log.update(kwargs)

    return performance_log


def format_trading_log(
    trade_id: str, symbol: str, side: str, quantity: float, price: float, **kwargs: Any
) -> Dict[str, Any]:
    """
    Format trading log entry

    Args:
        trade_id: Trade identifier
        symbol: Trading symbol
        side: Buy or sell
        quantity: Trade quantity
        price: Trade price
        **kwargs: Additional metadata

    Returns:
        Dict: Formatted trading log
    """
    trading_log = {
        "log_type": "trading",
        "trade_id": trade_id,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "price": price,
        "timestamp": ensure_utc_timestamp(datetime.now()).isoformat(),
    }

    # Add any additional metadata
    trading_log.update(kwargs)

    return trading_log
