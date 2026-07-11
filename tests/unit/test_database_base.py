"""
Unit tests for database base functionality
"""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy.exc import DataError, IntegrityError, OperationalError, ProgrammingError

from src.shared.database.base import db_readonly_session, db_transaction, get_session


class TestDatabaseBase:
    """Test database base functionality"""

    def test_db_transaction_success(self):
        """Test successful transaction"""
        with patch("src.shared.database.base.get_engine") as mock_get_engine:
            mock_engine = Mock()
            mock_get_engine.return_value = mock_engine

            with patch("src.shared.database.base.sessionmaker") as mock_sessionmaker:
                mock_session = Mock()
                mock_sessionmaker.return_value.return_value = mock_session

                with db_transaction() as session:
                    assert session == mock_session

                # Verify commit was called
                mock_session.commit.assert_called_once()
                mock_session.close.assert_called_once()

    def test_db_transaction_integrity_error(self):
        """Test transaction with integrity error"""
        with patch("src.shared.database.base.get_engine") as mock_get_engine:
            mock_engine = Mock()
            mock_get_engine.return_value = mock_engine

            with patch("src.shared.database.base.sessionmaker") as mock_sessionmaker:
                mock_session = Mock()
                mock_sessionmaker.return_value.return_value = mock_session
                mock_session.commit.side_effect = IntegrityError(
                    "Duplicate key", None, None
                )

                with pytest.raises(IntegrityError):
                    with db_transaction() as _:
                        pass

                # Verify rollback was called
                mock_session.rollback.assert_called_once()
                mock_session.close.assert_called_once()

    def test_db_transaction_operational_error(self):
        """Test transaction with operational error"""
        with patch("src.shared.database.base.get_engine") as mock_get_engine:
            mock_engine = Mock()
            mock_get_engine.return_value = mock_engine

            with patch("src.shared.database.base.sessionmaker") as mock_sessionmaker:
                mock_session = Mock()
                mock_sessionmaker.return_value.return_value = mock_session
                mock_session.commit.side_effect = OperationalError(
                    "Connection lost", None, None
                )

                with pytest.raises(OperationalError):
                    with db_transaction() as _:
                        pass

                # Verify rollback was called
                mock_session.rollback.assert_called_once()
                mock_session.close.assert_called_once()

    def test_db_transaction_data_error(self):
        """Test transaction with data error"""
        with patch("src.shared.database.base.get_engine") as mock_get_engine:
            mock_engine = Mock()
            mock_get_engine.return_value = mock_engine

            with patch("src.shared.database.base.sessionmaker") as mock_sessionmaker:
                mock_session = Mock()
                mock_sessionmaker.return_value.return_value = mock_session
                mock_session.commit.side_effect = DataError("Invalid data", None, None)

                with pytest.raises(DataError):
                    with db_transaction() as _:
                        pass

                # Verify rollback was called
                mock_session.rollback.assert_called_once()
                mock_session.close.assert_called_once()

    def test_db_transaction_programming_error(self):
        """Test transaction with programming error"""
        with patch("src.shared.database.base.get_engine") as mock_get_engine:
            mock_engine = Mock()
            mock_get_engine.return_value = mock_engine

            with patch("src.shared.database.base.sessionmaker") as mock_sessionmaker:
                mock_session = Mock()
                mock_sessionmaker.return_value.return_value = mock_session
                mock_session.commit.side_effect = ProgrammingError(
                    "SQL syntax error", None, None
                )

                with pytest.raises(ProgrammingError):
                    with db_transaction() as _:
                        pass

                # Verify rollback was called
                mock_session.rollback.assert_called_once()
                mock_session.close.assert_called_once()

    def test_db_transaction_general_exception(self):
        """Test transaction with general exception"""
        with patch("src.shared.database.base.get_engine") as mock_get_engine:
            mock_engine = Mock()
            mock_get_engine.return_value = mock_engine

            with patch("src.shared.database.base.sessionmaker") as mock_sessionmaker:
                mock_session = Mock()
                mock_sessionmaker.return_value.return_value = mock_session
                mock_session.commit.side_effect = Exception("Unexpected error")

                with pytest.raises(Exception):
                    with db_transaction() as _:
                        pass

                # Verify rollback was called
                mock_session.rollback.assert_called_once()
                mock_session.close.assert_called_once()

    def test_db_readonly_session_success(self):
        """Test successful read-only session"""
        with patch("src.shared.database.base.get_engine") as mock_get_engine:
            mock_engine = Mock()
            mock_get_engine.return_value = mock_engine

            with patch("src.shared.database.base.sessionmaker") as mock_sessionmaker:
                mock_session = Mock()
                mock_sessionmaker.return_value.return_value = mock_session

                with db_readonly_session() as session:
                    assert session == mock_session

                # Verify close was called (no commit for read-only)
                mock_session.close.assert_called_once()
                mock_session.commit.assert_not_called()

    def test_db_readonly_session_error(self):
        """Test read-only session with error"""
        with patch("src.shared.database.base.get_engine") as mock_get_engine:
            mock_engine = Mock()
            mock_get_engine.return_value = mock_engine

            with patch("src.shared.database.base.sessionmaker") as mock_sessionmaker:
                mock_session = Mock()
                mock_sessionmaker.return_value.return_value = mock_session

                with pytest.raises(Exception):
                    with db_readonly_session() as _:
                        raise Exception("Read error")

                # Verify close was called
                mock_session.close.assert_called_once()

    def test_get_session(self):
        """Test manual session creation"""
        with patch("src.shared.database.base.get_engine") as mock_get_engine:
            mock_engine = Mock()
            mock_get_engine.return_value = mock_engine

            with patch("src.shared.database.base.sessionmaker") as mock_sessionmaker:
                mock_session = Mock()
                mock_sessionmaker.return_value.return_value = mock_session

                session = get_session()
                assert session == mock_session
                mock_sessionmaker.assert_called_once_with(bind=mock_engine)
