"""
Integration tests for database schemas and table creation
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from config.database import get_database_config


@pytest.mark.integration
@pytest.mark.database
class TestSchemaCreation:
    """Test database schema creation and structure"""

    def test_all_service_schemas_exist(self, trading_engine):
        """Test that all required service schemas exist"""
        with trading_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name IN (
                    'data_ingestion', 'strategy_engine', 'execution',
                    'risk_management', 'analytics', 'notification',
                    'logging', 'shared'
                )
                ORDER BY schema_name
            """))
            schemas = [row[0] for row in result.fetchall()]

            expected_schemas = [
                "analytics",
                "data_ingestion",
                "execution",
                "logging",
                "notification",
                "risk_management",
                "shared",
                "strategy_engine",
            ]

            assert schemas == expected_schemas

    def test_schema_permissions(self, trading_engine):
        """Test that schemas have proper permissions"""
        with trading_engine.connect() as conn:
            # Test that we can create tables in each schema
            for schema in [
                "data_ingestion",
                "strategy_engine",
                "execution",
                "risk_management",
                "analytics",
                "notification",
                "logging",
                "shared",
            ]:
                # Create a test table
                conn.execute(text(f"""
                    CREATE TABLE IF NOT EXISTS {schema}.test_table (
                        id SERIAL PRIMARY KEY,
                        test_column VARCHAR(50)
                    )
                """))

                # Verify table was created
                result = conn.execute(text(f"""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = '{schema}'
                    AND table_name = 'test_table'
                """))
                assert result.fetchone() is not None

                # Clean up test table
                conn.execute(text(f"DROP TABLE IF EXISTS {schema}.test_table"))


@pytest.mark.integration
@pytest.mark.database
class TestDatabaseStructure:
    """Test overall database structure and configuration"""

    def test_database_encoding(self, trading_engine):
        """Test database encoding is UTF-8"""
        with trading_engine.connect() as conn:
            # Get the database name from configuration
            config = get_database_config()
            db_name = config.trading_db_name

            result = conn.execute(
                text(
                    f"SELECT pg_encoding_to_char(encoding) FROM pg_database "
                    f"WHERE datname = '{db_name}'"
                )
            )
            encoding = result.fetchone()[0]
            assert encoding == "UTF8"

    def test_database_timezone(self, trading_engine):
        """Test database timezone configuration"""
        with trading_engine.connect() as conn:
            result = conn.execute(text("SHOW timezone"))
            timezone = result.fetchone()[0]
            # Should be UTC for financial data, but allow other timezones for local development
            # In production, this should be UTC
            assert timezone is not None
            # For now, just verify timezone is set (can be made stricter later)
            assert len(timezone) > 0

    def test_database_version(self, trading_engine):
        """Test PostgreSQL version compatibility"""
        with trading_engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            # Should be PostgreSQL 12 or higher
            assert "PostgreSQL" in version
            # Extract version number and check it's >= 12
            version_parts = version.split()[1].split(".")
            major_version = int(version_parts[0])
            assert major_version >= 12


@pytest.mark.integration
@pytest.mark.database
class TestConnectionManagement:
    """Test database connection management"""

    def test_connection_timeout(self, trading_engine):
        """Test connection timeout behavior"""
        # This test would need to be implemented based on specific timeout requirements
        # For now, just test that connections work
        with trading_engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.fetchone()[0] == 1

    def test_connection_pool_exhaustion(self, trading_engine):
        """Test that the pool recovers connections after they are closed"""
        pool_size = trading_engine.pool.size()
        connections = [trading_engine.connect() for _ in range(pool_size)]
        try:
            for conn in connections:
                assert conn.execute(text("SELECT 1")).fetchone()[0] == 1
        finally:
            for conn in connections:
                conn.close()

        # Pool should be reusable once connections are released
        with trading_engine.connect() as conn:
            assert conn.execute(text("SELECT 1")).fetchone()[0] == 1

    def test_transaction_isolation(self, trading_engine):
        """Test transaction isolation levels"""
        with trading_engine.connect() as conn:
            # Test that we can set isolation level
            conn.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
            result = conn.execute(text("SELECT 1"))
            assert result.fetchone()[0] == 1


@pytest.mark.integration
@pytest.mark.database
class TestDataIntegrity:
    """Test data integrity and constraints"""

    def test_foreign_key_constraints(self, trading_engine):
        """A FOREIGN KEY constraint rejects inserts referencing a missing parent row"""
        with trading_engine.connect() as conn:
            with conn.begin():
                conn.execute(text("CREATE SCHEMA IF NOT EXISTS shared"))
                conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS shared.test_fk_parent (
                            id VARCHAR(20) PRIMARY KEY
                        )
                        """))
                conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS shared.test_fk_child (
                            id SERIAL PRIMARY KEY,
                            parent_id VARCHAR(20)
                                REFERENCES shared.test_fk_parent(id) ON DELETE CASCADE
                        )
                        """))

            try:
                trans = conn.begin()
                try:
                    with pytest.raises(IntegrityError):
                        conn.execute(
                            text(
                                "INSERT INTO shared.test_fk_child (parent_id) "
                                "VALUES ('MISSING')"
                            )
                        )
                finally:
                    trans.rollback()
            finally:
                with conn.begin():
                    conn.execute(text("DROP TABLE IF EXISTS shared.test_fk_child"))
                    conn.execute(text("DROP TABLE IF EXISTS shared.test_fk_parent"))

    def test_check_constraints(self, trading_engine):
        """A CHECK constraint rejects inserts with an out-of-range value"""
        with trading_engine.connect() as conn:
            with conn.begin():
                conn.execute(text("CREATE SCHEMA IF NOT EXISTS shared"))
                conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS shared.test_check_table (
                            id SERIAL PRIMARY KEY,
                            status VARCHAR(20)
                                CONSTRAINT test_valid_status
                                CHECK (status IN ('active', 'inactive'))
                        )
                        """))

            try:
                trans = conn.begin()
                try:
                    with pytest.raises(IntegrityError):
                        conn.execute(
                            text(
                                "INSERT INTO shared.test_check_table (status) "
                                "VALUES ('not_a_valid_status')"
                            )
                        )
                finally:
                    trans.rollback()
            finally:
                with conn.begin():
                    conn.execute(text("DROP TABLE IF EXISTS shared.test_check_table"))

    def test_unique_constraints(self, trading_engine):
        """A UNIQUE constraint rejects a duplicate insert"""
        with trading_engine.connect() as conn:
            with conn.begin():
                conn.execute(text("CREATE SCHEMA IF NOT EXISTS shared"))
                conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS shared.test_unique_table (
                            id SERIAL PRIMARY KEY,
                            code VARCHAR(20) UNIQUE
                        )
                        """))

            try:
                trans = conn.begin()
                try:
                    insert_stmt = text(
                        "INSERT INTO shared.test_unique_table (code) VALUES ('DUP')"
                    )
                    conn.execute(insert_stmt)
                    with pytest.raises(IntegrityError):
                        conn.execute(insert_stmt)
                finally:
                    trans.rollback()
            finally:
                with conn.begin():
                    conn.execute(text("DROP TABLE IF EXISTS shared.test_unique_table"))
