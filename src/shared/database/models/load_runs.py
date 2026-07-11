"""
Database model for tracking incremental data loading runs
"""

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class LoadRun(Base):
    """Tracks incremental data loading runs for different data sources and timespans"""

    __tablename__ = "load_runs"
    __table_args__ = {"schema": "data_ingestion"}

    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Symbol and data source identification
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    data_source: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'polygon', 'yahoo', etc.
    timespan: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # 'minute', 'hour', 'day', etc.
    multiplier: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # 1, 5, 15, 30, etc.

    # Loading progress tracking
    last_run_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_successful_date: Mapped[date] = mapped_column(Date, nullable=False)
    records_loaded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Status and error tracking
    status: Mapped[str] = mapped_column(
        String(20), default="success", nullable=False
    )  # 'success', 'failed', 'partial'
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<LoadRun(symbol='{self.symbol}', data_source='{self.data_source}', "
            f"timespan='{self.timespan}', multiplier={self.multiplier}, "
            f"last_successful_date='{self.last_successful_date}', status='{self.status}')>"
        )

    @property
    def is_success(self) -> bool:
        """Check if the last run was successful"""
        return self.status == "success"

    @property
    def is_failed(self) -> bool:
        """Check if the last run failed"""
        return self.status == "failed"

    @property
    def is_partial(self) -> bool:
        """Check if the last run was partially successful"""
        return self.status == "partial"

    @property
    def data_granularity(self) -> str:
        """Get human-readable data granularity"""
        if self.multiplier == 1:
            return self.timespan
        return f"{self.multiplier}-{self.timespan}"

    def days_since_last_success(self, reference_date: Optional[date] = None) -> int:
        """Calculate days since last successful data load"""
        if reference_date is None:
            reference_date = date.today()
        # Access the attribute directly to avoid SQLAlchemy issues
        last_date = getattr(self, "last_successful_date", None)
        if last_date is None:
            return 999  # Large number if no date
        return int((reference_date - last_date).days)

    def needs_backfill(self, max_gap_days: int = 7) -> bool:
        """Check if this symbol needs backfill due to large gap"""
        return self.days_since_last_success() > max_gap_days
