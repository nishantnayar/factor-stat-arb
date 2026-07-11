"""
Database Model Mixins
Reusable components for SQLAlchemy models
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.ext.declarative import declared_attr

from src.shared.utils.timezone import ensure_utc_timestamp

if TYPE_CHECKING:
    from sqlalchemy.sql.schema import Table


class TimestampMixin:
    """Adds timezone-aware created_at timestamp to models"""

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when record was created (UTC)",
    )

    def set_created_at(self, dt: Optional[datetime] = None) -> None:
        """Set created_at timestamp in UTC"""
        if dt is None:
            dt = datetime.now()
        # Use setattr to avoid mypy type checking issues with SQLAlchemy Column assignment
        setattr(self, "created_at", ensure_utc_timestamp(dt))


class UpdateTimestampMixin(TimestampMixin):
    """Adds timezone-aware created_at and updated_at timestamps to models"""

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Timestamp when record was last updated (UTC)",
    )

    def set_updated_at(self, dt: Optional[datetime] = None) -> None:
        """Set updated_at timestamp in UTC"""
        if dt is None:
            dt = datetime.now()
        # Use setattr to avoid mypy type checking issues with SQLAlchemy Column assignment
        setattr(self, "updated_at", ensure_utc_timestamp(dt))


class SerializerMixin:
    """Adds serialization methods to models"""

    if TYPE_CHECKING:
        __table__: "Table"

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert model instance to dictionary

        Returns:
            Dictionary representation of the model

        Example:
            market_data = MarketData(symbol='AAPL', price=150.0)
            data = market_data.to_dict()
            # {'symbol': 'AAPL', 'price': 150.0, ...}
        """
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SerializerMixin":
        """
        Create model instance from dictionary

        Args:
            data: Dictionary with model data

        Returns:
            Model instance

        Example:
            data = {'symbol': 'AAPL', 'price': 150.0}
            market_data = MarketData.from_dict(data)
        """
        return cls(**{key: value for key, value in data.items() if hasattr(cls, key)})


class ReprMixin:
    """Adds helpful __repr__ method to models"""

    if TYPE_CHECKING:
        __table__: "Table"

    def __repr__(self) -> str:
        """
        String representation of model instance

        Returns:
            String representation showing primary key values

        Example:
            Order(id=1, order_id='ORD123') -> "Order(id=1)"
        """
        class_name = self.__class__.__name__
        primary_keys = []

        for key in self.__table__.primary_key.columns:
            value = getattr(self, key.name)
            primary_keys.append(f"{key.name}={value}")

        return f"{class_name}({', '.join(primary_keys)})"


class SoftDeleteMixin:
    """Adds soft delete functionality to models"""

    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when record was soft deleted (NULL = active, UTC)",
    )

    def soft_delete(self) -> None:
        """Mark record as deleted without removing from database"""
        setattr(self, "deleted_at", ensure_utc_timestamp(datetime.now()))

    def restore(self) -> None:
        """Restore a soft-deleted record"""
        setattr(self, "deleted_at", None)

    @property
    def is_deleted(self) -> bool:
        """Check if record is soft deleted"""
        return self.deleted_at is not None


class VersionMixin:
    """Adds optimistic locking version field to models"""

    version: int = Column(  # type: ignore[assignment]
        "version",
        nullable=False,
        default=1,
        comment="Version number for optimistic locking",
    )

    def increment_version(self) -> None:
        """Increment version number"""
        self.version += 1


class AuditMixin:
    """Adds audit fields to models"""

    created_by: Optional[str] = Column(  # type: ignore[assignment]
        "created_by", String, nullable=True, comment="User who created the record"
    )

    updated_by: Optional[str] = Column(  # type: ignore[assignment]
        "updated_by", String, nullable=True, comment="User who last updated the record"
    )

    def set_audit_fields(self, user_id: str, is_update: bool = False) -> None:
        """
        Set audit fields

        Args:
            user_id: ID of the user performing the action
            is_update: Whether this is an update (True) or create (False)
        """
        if is_update:
            self.updated_by = user_id
        else:
            self.created_by = user_id
            self.updated_by = user_id


class UUIDMixin:
    """Adds UUID primary key to models"""

    @declared_attr
    def id(cls) -> "Column[uuid.UUID]":
        from sqlalchemy import Column
        from sqlalchemy.dialects.postgresql import UUID

        return Column(
            UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
            comment="Unique identifier",
        )


class NameMixin:
    """Adds name and description fields to models"""

    name: str = Column(  # type: ignore[assignment]
        "name", String, nullable=False, comment="Name of the record"
    )

    description: Optional[str] = Column(  # type: ignore[assignment]
        "description", String, nullable=True, comment="Description of the record"
    )


class StatusMixin:
    """Adds status field to models"""

    status: str = Column(  # type: ignore[assignment]
        "status",
        String,
        nullable=False,
        default="active",
        comment="Status of the record",
    )

    def activate(self) -> None:
        """Activate the record"""
        self.status = "active"

    def deactivate(self) -> None:
        """Deactivate the record"""
        self.status = "inactive"

    @property
    def is_active(self) -> bool:
        """Check if record is active"""
        return self.status == "active"
