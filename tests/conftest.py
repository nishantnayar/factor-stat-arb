"""
Pytest configuration and fixtures for database testing.

SAFETY: Fixtures that drop tables (e.g. setup_test_tables) will ONLY drop when:
  - Database name looks like a test DB (ends with _test), AND
  - data_ingestion.market_data has no more than MAX_MARKET_DATA_ROWS_BEFORE_REFUSE_DROP rows.
Never run pytest against your main/dev database without a separate test DB.
"""

import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from src.config.database import get_database_config  # noqa: E402

# --- Safety constants: prevent accidental drop of production/dev data ---
PRODUCTION_LIKE_DB_NAMES = ("trading_system",)  # Never drop tables in these
TEST_DB_NAME_SUFFIX = "_test"  # Only allow table drops when DB name ends with this
MAX_MARKET_DATA_ROWS_BEFORE_REFUSE_DROP = 1000  # Refuse to DROP if market_data has more rows


@pytest.fixture(scope="session")
def db_config():
    """Database configuration fixture"""
    return get_database_config()


def _is_safe_test_db(db_name: str) -> bool:
    """True only if database name indicates a dedicated test DB (not production/dev)."""
    if not db_name:
        return False
    d = db_name.lower()
    if d in (x.lower() for x in PRODUCTION_LIKE_DB_NAMES):
        return False
    return d.endswith(TEST_DB_NAME_SUFFIX)


def _warn_if_using_production_db():
    """Emit a critical warning at pytest load if TRADING_DB_NAME looks like production."""
    try:
        cfg = get_database_config()
        db_name = (cfg.trading_db_name or "").strip()
        if db_name.lower() in (x.lower() for x in PRODUCTION_LIKE_DB_NAMES):
            msg = (
                "\n"
                "*** CRITICAL: pytest is using the PRODUCTION/DEV database '%s'. ***\n"
                "    Table-dropping fixtures will NOT drop (to protect your data).\n"
                "    To run DB tests safely, use a separate test database, e.g.:\n"
                "    TRADING_DB_NAME=trading_system_test pytest tests/\n"
                "***\n"
            ) % db_name
            sys.stderr.write(msg)
    except Exception:
        pass


# Run once when conftest is loaded
_warn_if_using_production_db()


@pytest.fixture(scope="session")
def trading_engine(db_config):
    """Trading database engine fixture"""
    return db_config.get_engine("trading")


@pytest.fixture(scope="session")
def prefect_engine(db_config):
    """Prefect database engine fixture"""
    return db_config.get_engine("prefect")


@pytest.fixture(scope="function")
def trading_session(trading_engine):
    """Trading database session fixture"""
    Session = sessionmaker(bind=trading_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture(scope="function")
def prefect_session(prefect_engine):
    """Prefect database session fixture"""
    Session = sessionmaker(bind=prefect_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture(scope="function")
def clean_trading_db(trading_engine):
    """Clean trading database for each test"""
    # This fixture can be used to clean up test data
    yield
    # Add cleanup logic here if needed


@pytest.fixture(scope="function")
def clean_prefect_db(prefect_engine):
    """Clean prefect database for each test"""
    # This fixture can be used to clean up test data
    yield
    # Add cleanup logic here if needed


@pytest.fixture(scope="function")
def setup_test_tables(trading_engine):
    """Setup required database tables for tests"""
    from sqlalchemy import text

    # Create the data_ingestion schema if it doesn't exist
    with trading_engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS data_ingestion"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS shared"))
        conn.commit()

    # Create the load_runs table
    create_load_runs_table = """
    CREATE TABLE IF NOT EXISTS data_ingestion.load_runs (
        id BIGSERIAL PRIMARY KEY,
        symbol VARCHAR(20) NOT NULL,
        data_source VARCHAR(20) NOT NULL,
        timespan VARCHAR(10) NOT NULL,
        multiplier INTEGER NOT NULL,
        last_run_date DATE NOT NULL,
        last_successful_date DATE NOT NULL,
        records_loaded INTEGER DEFAULT 0,
        status VARCHAR(20) DEFAULT 'success',
        error_message TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

        CONSTRAINT unique_symbol_data_source_timespan UNIQUE (
            symbol, data_source, timespan, multiplier
        )
    );
    """

    # Create the market_data table
    create_market_data_table = """
    CREATE TABLE IF NOT EXISTS data_ingestion.market_data (
        id BIGSERIAL PRIMARY KEY,
        symbol VARCHAR(20) NOT NULL,
        timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
        data_source VARCHAR(20) NOT NULL DEFAULT 'yahoo',
        open DECIMAL(15,4),
        high DECIMAL(15,4),
        low DECIMAL(15,4),
        close DECIMAL(15,4),
        volume BIGINT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        
        -- Constraints
        CONSTRAINT unique_symbol_timestamp_data_source UNIQUE (symbol, timestamp, data_source),
        CONSTRAINT positive_prices CHECK (open > 0 AND high > 0 AND low > 0 AND close > 0),
        CONSTRAINT valid_ohlc CHECK (high >= GREATEST(open, close) AND low <= LEAST(open, close))
    );
    """

    # Create the symbols table
    create_symbols_table = """
    CREATE TABLE IF NOT EXISTS data_ingestion.symbols (
        symbol VARCHAR(20) PRIMARY KEY,
        name VARCHAR(255),
        exchange VARCHAR(50),
        sector VARCHAR(100),
        industry VARCHAR(100),
        market_cap BIGINT,
        status VARCHAR(20) DEFAULT 'active',
        added_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """

    # Create the analyst_recommendations table
    create_analyst_recommendations_table = """
    CREATE TABLE IF NOT EXISTS data_ingestion.analyst_recommendations (
        id SERIAL PRIMARY KEY,
        symbol VARCHAR(20) NOT NULL,
        date DATE NOT NULL,
        period VARCHAR(10) NOT NULL,
        strong_buy INTEGER DEFAULT 0,
        buy INTEGER DEFAULT 0,
        hold INTEGER DEFAULT 0,
        sell INTEGER DEFAULT 0,
        strong_sell INTEGER DEFAULT 0,
        total_analysts INTEGER GENERATED ALWAYS AS (strong_buy + buy + hold + sell + strong_sell) STORED,
        data_source VARCHAR(20) NOT NULL DEFAULT 'yahoo',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        
        CONSTRAINT fk_analyst_recommendations_symbol 
            FOREIGN KEY (symbol) REFERENCES data_ingestion.symbols(symbol) 
            ON DELETE CASCADE,
        
        CONSTRAINT uk_analyst_recommendations_unique 
            UNIQUE (symbol, date, period, data_source)
    );
    """

    with trading_engine.connect() as conn:
        conn.execute(text(create_load_runs_table))
        conn.execute(text(create_market_data_table))
        conn.execute(text(create_symbols_table))
        conn.execute(text(create_analyst_recommendations_table))
        conn.commit()

    yield

    # --- SAFETY: Only drop tables when DB is clearly a test DB and market_data is small ---
    db_name = (trading_engine.url.database or "").strip()

    if not _is_safe_test_db(db_name):
        import warnings
        warnings.warn(
            f"setup_test_tables: Skipping DROP of market_data etc. (db={db_name}). "
            f"Use a test database whose name ends with '{TEST_DB_NAME_SUFFIX}' (e.g. trading_system_test).",
            UserWarning,
            stacklevel=2,
        )
        return

    with trading_engine.connect() as conn:
        # Refuse to drop if market_data has many rows (catastrophic data loss guard)
        try:
            result = conn.execute(
                text("SELECT COUNT(*) FROM data_ingestion.market_data")
            )
            (row_count,) = result.fetchone()
            if row_count > MAX_MARKET_DATA_ROWS_BEFORE_REFUSE_DROP:
                raise RuntimeError(
                    f"REFUSING to DROP data_ingestion.market_data: table has {row_count} rows "
                    f"(max allowed for drop is {MAX_MARKET_DATA_ROWS_BEFORE_REFUSE_DROP}). "
                    "Use a dedicated test database with little or no production data."
                )
        except Exception as e:
            if "does not exist" in str(e).lower() or "relation" in str(e).lower():
                pass  # Table missing, safe to continue (drops are IF EXISTS)
            else:
                raise

        conn.execute(text("DROP TABLE IF EXISTS data_ingestion.load_runs CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS data_ingestion.market_data CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS data_ingestion.symbols CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS data_ingestion.analyst_recommendations CASCADE"))
        conn.commit()
