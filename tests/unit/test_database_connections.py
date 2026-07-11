"""
Unit tests for database connections and configuration
"""

import pytest
from sqlalchemy import text

from src.config.database import get_engine


@pytest.mark.unit
@pytest.mark.database
class TestDatabaseConnections:
    """Test database connection functionality"""

    def test_trading_database_connection(self, trading_engine):
        """Test connection to trading_system database"""
        with trading_engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            assert row[0] == 1

    def test_prefect_database_connection(self, prefect_engine):
        """Test connection to Prefect database"""
        with prefect_engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            assert row[0] == 1

    def test_database_config_creation(self, db_config):
        """Test database configuration creation"""
        assert db_config.postgres_host == "localhost"
        assert db_config.postgres_port == 5432
        # Check that trading_db_name is set (could be default or from env)
        assert db_config.trading_db_name in ["trading_system", "trading_system_test"]
        assert db_config.prefect_db_name == "Prefect"

    def test_trading_db_url_generation(self, db_config):
        """Test trading database URL generation"""
        url = db_config.trading_db_url
        assert "postgresql://" in url
        assert db_config.trading_db_name in url
        assert "localhost" in url

    def test_prefect_db_url_generation(self, db_config):
        """Test Prefect database URL generation"""
        url = db_config.prefect_db_url
        assert "postgresql://" in url
        assert "Prefect" in url
        assert "localhost" in url

    def test_get_engine_function(self, db_config):
        """Test get_engine convenience function"""
        trading_engine = get_engine("trading")
        prefect_engine = get_engine("prefect")

        # Test trading engine
        with trading_engine.connect() as conn:
            result = conn.execute(text("SELECT current_database()"))
            db_name = result.fetchone()[0]
            assert db_config.trading_db_name in db_name

        # Test prefect engine
        with prefect_engine.connect() as conn:
            result = conn.execute(text("SELECT current_database()"))
            db_name = result.fetchone()[0]
            assert "Prefect" in db_name


@pytest.mark.unit
@pytest.mark.database
class TestServiceSchemas:
    """Test service-specific schema access"""

    def test_data_ingestion_schema(self, db_config):
        """Test data_ingestion schema access"""
        engine = db_config.get_service_engine("data_ingestion")
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name = 'data_ingestion'"
                )
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "data_ingestion"

    def test_strategy_engine_schema(self, db_config):
        """Test strategy_engine schema access"""
        engine = db_config.get_service_engine("strategy_engine")
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name = 'strategy_engine'"
                )
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "strategy_engine"

    def test_execution_schema(self, db_config):
        """Test execution schema access"""
        engine = db_config.get_service_engine("execution")
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name = 'execution'"
                )
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "execution"

    def test_risk_management_schema(self, db_config):
        """Test risk_management schema access"""
        engine = db_config.get_service_engine("risk_management")
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name = 'risk_management'"
                )
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "risk_management"

    def test_analytics_schema(self, db_config):
        """Test analytics schema access"""
        engine = db_config.get_service_engine("analytics")
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name = 'analytics'"
                )
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "analytics"

    def test_notification_schema(self, db_config):
        """Test notification schema access"""
        engine = db_config.get_service_engine("notification")
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name = 'notification'"
                )
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "notification"

    def test_logging_schema(self, db_config):
        """Test logging schema access"""
        engine = db_config.get_service_engine("logging")
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name = 'logging'"
                )
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "logging"

    def test_shared_schema(self, db_config):
        """Test shared schema access"""
        engine = db_config.get_service_engine("shared")
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name = 'shared'"
                )
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "shared"


@pytest.mark.unit
@pytest.mark.database
class TestConnectionPools:
    """Test connection pool configuration"""

    def test_trading_connection_pool(self, trading_engine):
        """Test trading database connection pool"""
        pool = trading_engine.pool
        assert pool.size() == 10  # Default pool size
        assert pool.checkedout() == 0  # No connections checked out initially

    def test_prefect_connection_pool(self, prefect_engine):
        """Test Prefect database connection pool"""
        pool = prefect_engine.pool
        assert pool.size() == 10  # Default pool size
        assert pool.checkedout() == 0  # No connections checked out initially

    def test_connection_pool_reuse(self, trading_engine):
        """Test connection pool reuse"""
        pool = trading_engine.pool
        initial_size = pool.size()

        # Use multiple connections
        with trading_engine.connect() as conn1:
            with trading_engine.connect() as conn2:
                # Pool should still be the same size
                assert pool.size() == initial_size

                # Both connections should work
                result1 = conn1.execute(text("SELECT 1"))
                result2 = conn2.execute(text("SELECT 1"))
                assert result1.fetchone()[0] == 1
                assert result2.fetchone()[0] == 1
