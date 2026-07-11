"""
Unit tests for Database Mixins
"""

from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

from src.shared.database.mixins import (
    AuditMixin,
    ReprMixin,
    SerializerMixin,
    SoftDeleteMixin,
    StatusMixin,
    TimestampMixin,
    UpdateTimestampMixin,
    VersionMixin,
)

# Create base with __allow_unmapped__ for testing with type annotations
Base: Any = declarative_base()
Base.__allow_unmapped__ = True


class TestTimestampMixin:
    """Test cases for TimestampMixin"""

    def test_timestamp_mixin_has_created_at(self):
        """Test that TimestampMixin adds created_at field"""

        class TestModel(TimestampMixin, Base):
            __tablename__ = "test_timestamp"
            id = Column(Integer, primary_key=True)

        assert hasattr(TestModel, "created_at")

    def test_set_created_at_with_datetime(self):
        """Test setting created_at with specific datetime"""

        class TestModel(TimestampMixin, Base):
            __tablename__ = "test_timestamp_set"
            id = Column(Integer, primary_key=True)

        model = TestModel()
        test_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        model.set_created_at(test_time)

        assert model.created_at == test_time

    def test_set_created_at_without_datetime(self):
        """Test setting created_at without specific datetime"""

        class TestModel(TimestampMixin, Base):
            __tablename__ = "test_timestamp_now"
            id = Column(Integer, primary_key=True)

        model = TestModel()
        model.set_created_at()

        assert model.created_at is not None
        assert model.created_at.tzinfo is not None


class TestUpdateTimestampMixin:
    """Test cases for UpdateTimestampMixin"""

    def test_update_timestamp_mixin_has_both_fields(self):
        """Test that UpdateTimestampMixin adds created_at and updated_at fields"""

        class TestModel(UpdateTimestampMixin, Base):
            __tablename__ = "test_update_timestamp"
            id = Column(Integer, primary_key=True)

        assert hasattr(TestModel, "created_at")
        assert hasattr(TestModel, "updated_at")

    def test_set_updated_at_with_datetime(self):
        """Test setting updated_at with specific datetime"""

        class TestModel(UpdateTimestampMixin, Base):
            __tablename__ = "test_update_set"
            id = Column(Integer, primary_key=True)

        model = TestModel()
        test_time = datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
        model.set_updated_at(test_time)

        assert model.updated_at == test_time

    def test_set_updated_at_without_datetime(self):
        """Test setting updated_at without specific datetime"""

        class TestModel(UpdateTimestampMixin, Base):
            __tablename__ = "test_update_now"
            id = Column(Integer, primary_key=True)

        model = TestModel()
        model.set_updated_at()

        assert model.updated_at is not None
        assert model.updated_at.tzinfo is not None


class TestSerializerMixin:
    """Test cases for SerializerMixin"""

    def test_to_dict(self):
        """Test converting model to dictionary"""

        class TestModel(SerializerMixin, Base):
            __tablename__ = "test_serializer"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))
            value = Column(Integer)

        model = TestModel()
        model.id = 1
        model.name = "Test"
        model.value = 100

        result = model.to_dict()

        assert result["id"] == 1
        assert result["name"] == "Test"
        assert result["value"] == 100

    def test_from_dict(self):
        """Test creating model from dictionary"""

        class TestModel(SerializerMixin, Base):
            __tablename__ = "test_from_dict"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))
            value = Column(Integer)

        data = {"id": 1, "name": "Test", "value": 100}
        model = TestModel.from_dict(data)

        assert model.id == 1
        assert model.name == "Test"
        assert model.value == 100

    def test_from_dict_ignores_unknown_fields(self):
        """Test that from_dict ignores unknown fields"""

        class TestModel(SerializerMixin, Base):
            __tablename__ = "test_from_dict_ignore"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))

        data = {"id": 1, "name": "Test", "unknown_field": "ignored"}
        model = TestModel.from_dict(data)

        assert model.id == 1
        assert model.name == "Test"
        assert not hasattr(model, "unknown_field")


class TestReprMixin:
    """Test cases for ReprMixin"""

    def test_repr_single_primary_key(self):
        """Test __repr__ with single primary key"""

        class TestModel(ReprMixin, Base):
            __tablename__ = "test_repr_single"
            id = Column(Integer, primary_key=True)

        model = TestModel()
        model.id = 123

        assert repr(model) == "TestModel(id=123)"

    def test_repr_composite_primary_key(self):
        """Test __repr__ with composite primary key"""

        class TestModel(ReprMixin, Base):
            __tablename__ = "test_repr_composite"
            id1 = Column(Integer, primary_key=True)
            id2 = Column(Integer, primary_key=True)

        model = TestModel()
        model.id1 = 1
        model.id2 = 2

        repr_str = repr(model)
        assert "TestModel(" in repr_str
        assert "id1=1" in repr_str
        assert "id2=2" in repr_str


class TestSoftDeleteMixin:
    """Test cases for SoftDeleteMixin"""

    def test_soft_delete_mixin_has_deleted_at(self):
        """Test that SoftDeleteMixin adds deleted_at field"""

        class TestModel(SoftDeleteMixin, Base):
            __tablename__ = "test_soft_delete"
            id = Column(Integer, primary_key=True)

        assert hasattr(TestModel, "deleted_at")

    def test_soft_delete(self):
        """Test soft delete functionality"""

        class TestModel(SoftDeleteMixin, Base):
            __tablename__ = "test_soft_delete_func"
            id = Column(Integer, primary_key=True)

        model = TestModel()
        assert model.deleted_at is None
        assert not model.is_deleted

        model.soft_delete()

        assert model.deleted_at is not None
        assert model.deleted_at.tzinfo is not None
        assert model.is_deleted

    def test_restore(self):
        """Test restore functionality"""

        class TestModel(SoftDeleteMixin, Base):
            __tablename__ = "test_restore"
            id = Column(Integer, primary_key=True)

        model = TestModel()
        model.soft_delete()
        assert model.is_deleted

        model.restore()
        assert model.deleted_at is None
        assert not model.is_deleted

    def test_is_deleted_property(self):
        """Test is_deleted property"""

        class TestModel(SoftDeleteMixin, Base):
            __tablename__ = "test_is_deleted"
            id = Column(Integer, primary_key=True)

        model = TestModel()
        assert not model.is_deleted

        model.deleted_at = datetime.now(timezone.utc)
        assert model.is_deleted


class TestMixinFunctionality:
    """Test cases for mixin functionality (non-type-annotated mixins)"""

    def test_version_mixin_increment(self):
        """Test VersionMixin increment_version method"""
        # Test the method directly without creating a test model
        mixin = VersionMixin()
        mixin.version = 1

        mixin.increment_version()
        assert mixin.version == 2

        mixin.increment_version()
        assert mixin.version == 3

    def test_audit_mixin_set_fields(self):
        """Test AuditMixin set_audit_fields method"""
        # Test the method directly
        mixin = AuditMixin()

        mixin.set_audit_fields("user123", is_update=False)
        assert mixin.created_by == "user123"
        assert mixin.updated_by == "user123"

        mixin.set_audit_fields("user456", is_update=True)
        assert mixin.created_by == "user123"  # Should not change
        assert mixin.updated_by == "user456"  # Should update

    def test_status_mixin_methods(self):
        """Test StatusMixin activate/deactivate methods"""
        # Test the methods directly
        mixin = StatusMixin()
        mixin.status = "inactive"

        mixin.activate()
        assert mixin.status == "active"
        assert mixin.is_active

        mixin.deactivate()
        assert mixin.status == "inactive"
        assert not mixin.is_active


class TestMixinCombinations:
    """Test cases for combining multiple mixins"""

    def test_combined_mixins(self):
        """Test combining multiple mixins (without type annotations)"""

        class TestModel(
            UpdateTimestampMixin,
            SoftDeleteMixin,
            Base,
        ):
            __tablename__ = "test_combined"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))

        model = TestModel()
        model.id = 1
        model.name = "Test"

        # Test mixin functionality
        assert hasattr(model, "created_at")
        assert hasattr(model, "updated_at")
        assert hasattr(model, "deleted_at")

    def test_serializer_with_timestamps(self):
        """Test SerializerMixin with TimestampMixin"""

        class TestModel(UpdateTimestampMixin, SerializerMixin, Base):
            __tablename__ = "test_serializer_timestamp"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))

        model = TestModel()
        model.id = 1
        model.name = "Test"
        model.set_created_at(datetime(2024, 1, 1, tzinfo=timezone.utc))
        model.set_updated_at(datetime(2024, 1, 2, tzinfo=timezone.utc))

        result = model.to_dict()

        assert result["id"] == 1
        assert result["name"] == "Test"
        assert "created_at" in result
        assert "updated_at" in result

    def test_repr_with_multiple_mixins(self):
        """Test ReprMixin with other mixins"""

        class TestModel(ReprMixin, SoftDeleteMixin, Base):
            __tablename__ = "test_repr_multiple"
            id = Column(Integer, primary_key=True)

        model = TestModel()
        model.id = 123

        repr_str = repr(model)
        assert "TestModel(id=123)" == repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
