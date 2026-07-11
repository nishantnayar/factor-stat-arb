"""
Database models for logging system

These models represent the logging tables in PostgreSQL:
- system_logs: General system logs
- performance_logs: Performance metrics
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ...utils.timezone import ensure_utc_timestamp
from ..base import Base


class SystemLog(Base):
    """
    System log entries for general application logging
    
    Stores structured log data with:
    - Service identification
    - Log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - Correlation IDs for request tracking
    - JSONB metadata for flexible data storage
    - Timezone-aware timestamps (UTC)
    """

    __tablename__ = "system_logs"
    __table_args__ = (
        Index("idx_system_logs_timestamp", "timestamp"),
        Index("idx_system_logs_service", "service"),
        Index("idx_system_logs_level", "level"),
        Index("idx_system_logs_correlation", "correlation_id"),
        Index("idx_system_logs_event_type", "event_type"),
        Index("idx_system_logs_service_timestamp", "service", "timestamp"),
        {"schema": "logging"},
    )

    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Service identification
    service: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Log level
    level: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # DEBUG, INFO, WARNING, ERROR, CRITICAL

    # Log message
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Structured data (JSONB for flexible schema)
    data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Correlation ID for request tracking
    correlation_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )

    # Event type classification
    event_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True
    )

    # Timestamp (UTC, timezone-aware)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: ensure_utc_timestamp(datetime.now(timezone.utc)),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<SystemLog(id={self.id}, service='{self.service}', "
            f"level='{self.level}', timestamp='{self.timestamp}')>"
        )


class PerformanceLog(Base):
    """
    Performance log entries for monitoring system performance
    
    Stores performance metrics with:
    - Service and operation identification
    - Execution time measurements
    - Resource usage (memory, CPU)
    - Timezone-aware timestamps (UTC)
    """

    __tablename__ = "performance_logs"
    __table_args__ = (
        Index("idx_performance_logs_timestamp", "timestamp"),
        Index("idx_performance_logs_service", "service"),
        Index("idx_performance_logs_operation", "operation"),
        Index("idx_performance_logs_service_timestamp", "service", "timestamp"),
        {"schema": "logging"},
    )

    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Service identification
    service: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Operation name
    operation: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Execution time in milliseconds
    execution_time_ms: Mapped[float] = mapped_column(
        Numeric(10, 3), nullable=False
    )

    # Memory usage in MB (optional)
    memory_usage_mb: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 3), nullable=True
    )

    # CPU usage percentage (optional)
    cpu_usage_percent: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 2), nullable=True
    )

    # Timestamp (UTC, timezone-aware)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: ensure_utc_timestamp(datetime.now(timezone.utc)),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<PerformanceLog(id={self.id}, service='{self.service}', "
            f"operation='{self.operation}', execution_time_ms={self.execution_time_ms})>"
        )

