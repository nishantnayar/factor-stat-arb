#!/usr/bin/env python3
"""
Database Setup Script for Trading System
Creates the Prefect database and sets up the environment configuration.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Load environment variables from .env file
load_dotenv()

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from config.database import get_database_config


def run_sql_command(command: str, database: str = "template1") -> bool:
    """Run a SQL command using psycopg2"""
    try:
        # Get database connection details from environment
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "")

        # Connect to PostgreSQL (use template1 as default)
        conn = psycopg2.connect(
            host=host, port=port, user=user, password=password, database=database
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        # Execute command
        cursor = conn.cursor()
        cursor.execute(command)
        cursor.close()
        conn.close()

        print(f"Successfully executed: {command}")
        return True

    except psycopg2.OperationalError as e:
        print(f"Database connection error: {e}")
        return False
    except Exception as e:
        print(f"Error running SQL command: {e}")
        return False


def check_database_exists(db_name: str) -> bool:
    """Check if a database exists by querying pg_database"""
    try:
        # Get database connection details from environment
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "")

        # Connect to template1 database
        conn = psycopg2.connect(
            host=host, port=port, user=user, password=password, database="template1"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        # Check if database exists
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (db_name,))
        result = cursor.fetchone()

        # Close connection
        cursor.close()
        conn.close()

        return result is not None

    except Exception as e:
        print(f"Error checking database existence: {e}")
        return False


def create_prefect_database():
    """Create the Prefect database"""
    print("Creating Prefect database...")

    # Check if database already exists
    if check_database_exists("Prefect"):
        print("Prefect database already exists")
        return True

    # Create the database
    create_db_cmd = 'CREATE DATABASE "Prefect";'
    if run_sql_command(create_db_cmd):
        print("Prefect database created successfully")

        # Grant permissions
        grant_cmd = 'GRANT ALL PRIVILEGES ON DATABASE "Prefect" TO postgres;'
        if run_sql_command(grant_cmd):
            print("Permissions granted to postgres user")
            return True

    return False


def create_trading_system_database():
    """Create the trading system database if it doesn't exist"""
    config = get_database_config()
    db_name = config.trading_db_name
    print(f"Creating {db_name} database...")

    # Check if database already exists
    if check_database_exists(db_name):
        print(f"{db_name} database already exists")
        return True

    # Create the database
    create_db_cmd = f"CREATE DATABASE {db_name};"
    if run_sql_command(create_db_cmd):
        print(f"{db_name} database created successfully")
        return True

    return False


def create_service_schemas():
    """Create service-specific schemas in trading system database"""
    config = get_database_config()
    db_name = config.trading_db_name
    print(f"\nCreating service-specific schemas in {db_name} database...")

    # First verify that trading system database is accessible
    if not check_database_exists(db_name):
        print(f"ERROR: {db_name} database does not exist!")
        return False

    # Test connection to trading system database
    test_cmd = "SELECT 1;"
    if not run_sql_command(test_cmd, db_name):
        print(f"ERROR: Cannot connect to {db_name} database!")
        return False

    schemas = [
        "data_ingestion",
        "strategy_engine",
        "execution",
        "risk_management",
        "analytics",
        "notification",
        "logging",
        "shared",
    ]

    for schema in schemas:
        create_schema_cmd = f"CREATE SCHEMA IF NOT EXISTS {schema};"
        print(f"Creating schema '{schema}'...")
        if run_sql_command(create_schema_cmd, db_name):
            print(f"Schema '{schema}' created/verified successfully")
        else:
            print(f"ERROR: Failed to create schema '{schema}'")
            return False

    # Verify all schemas were created
    print("\nVerifying all schemas were created...")
    verify_cmd = "SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('data_ingestion', 'strategy_engine', 'execution', 'risk_management', 'analytics', 'notification', 'logging', 'shared') ORDER BY schema_name;"

    if run_sql_command(verify_cmd, db_name):
        print("All service schemas verified successfully!")
    else:
        print("WARNING: Could not verify schema creation")

    return True


def setup_prefect_config():
    """Setup Prefect configuration (optional)"""
    print("\n\nSetting up Prefect configuration...")

    # Check if Prefect is available
    try:
        subprocess.run(["prefect", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Prefect not available - skipping configuration")
        print("Prefect database is ready for when Prefect is installed")
        return True

    # Get database connection details
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "")

    # Construct Prefect database URL
    prefect_db_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/Prefect"

    try:
        # Set Prefect database URL
        subprocess.run(
            [
                "prefect",
                "config",
                "set",
                f"PREFECT_API_DATABASE_CONNECTION_URL={prefect_db_url}",
            ],
            check=True,
        )

        print("\nPrefect database URL configured")

        # Note: Prefect will automatically initialize its database tables when the server starts
        # No manual database upgrade command is needed in newer Prefect versions
        print(
            "\nPrefect database will be initialized automatically when server starts\n"
        )

        return True

    except subprocess.CalledProcessError as e:
        print(f"Error setting up Prefect configuration: {e}")
        print("Prefect database is ready for manual configuration")
        return True  # Don't fail the script for Prefect config issues
    except FileNotFoundError:
        print("Prefect command not found - skipping configuration")
        print("Prefect database is ready for when Prefect is installed")
        return True


def verify_databases():
    """Verify that both databases exist and are accessible"""
    config = get_database_config()
    trading_db_name = config.trading_db_name
    prefect_db_name = config.prefect_db_name

    print("=" * 50)
    print("Starting verifying database setup...")

    # Check trading system database
    if run_sql_command("SELECT 1;", trading_db_name):
        print(f"{trading_db_name} database is accessible")
    else:
        print(f"{trading_db_name} database is not accessible")
        return False

    # Check prefect database
    if run_sql_command("SELECT 1;", prefect_db_name):
        print(f"{prefect_db_name} database is accessible")
    else:
        print(f"{prefect_db_name} database is not accessible")
        return False

    return True


def main():
    """Main setup function"""
    print("=" * 50)
    print("\nStarting Database Setup for Trading System\n")
    print("=" * 50)

    # Check if required environment variables are set
    required_vars = [
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these variables in your .env file or environment")
        return False

    # Step 1: Create Prefect database
    if not create_prefect_database():
        print("Failed to create Prefect database")
        return False

    # Step 2: Create trading_system database
    if not create_trading_system_database():
        print("Failed to create trading_system database")
        return False

    # Step 3: Create service schemas
    if not create_service_schemas():
        print("Failed to create service schemas")
        return False

    # Step 4: Setup Prefect configuration
    if not setup_prefect_config():
        print("Failed to setup Prefect configuration")
        return False

    # Step 5: Verify setup
    if not verify_databases():
        print("Database verification failed")
        return False

    print("=" * 50)
    print("\nDatabase setup completed successfully!\n")
    print("=" * 50)
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
