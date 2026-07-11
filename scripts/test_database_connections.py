#!/usr/bin/env python3
"""
Test Database Connections

This script tests connectivity to both the trading system database and Prefect database.
"""

import asyncio
import os
import sys
from datetime import datetime

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)

from loguru import logger
from sqlalchemy import text

from src.config.database import get_database_config
from src.shared.logging import setup_logging


def test_trading_database_connection():
    """Test connection to trading system database"""
    config = get_database_config()

    try:
        engine = config.get_engine("trading")
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT 1 as test, current_database() as db_name")
            )
            row = result.fetchone()
            logger.info("Trading database connection successful [OK]")
            logger.info(f"  Database: {row.db_name}")
            return True
    except Exception as e:
        logger.error(f"Trading database connection failed [FAIL]: {e}")
        return False


def test_prefect_database_connection():
    """Test connection to Prefect database"""
    config = get_database_config()

    try:
        engine = config.get_engine("prefect")
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT 1 as test, current_database() as db_name")
            )
            row = result.fetchone()
            logger.info("Prefect database connection successful [OK]")
            logger.info(f"  Database: {row.db_name}")
            return True
    except Exception as e:
        logger.error(f"Prefect database connection failed [FAIL]: {e}")
        return False


def test_schema_access():
    """Test access to service-specific schemas"""
    config = get_database_config()

    schemas_to_test = [
        "data_ingestion",
        "strategy_engine",
        "execution",
        "risk_management",
        "analytics",
        "notification",
        "logging",
        "shared",
    ]

    logger.info("Testing schema access...")
    all_schemas_accessible = True

    for schema_name in schemas_to_test:
        try:
            engine = config.get_service_engine(schema_name)
            with engine.connect() as conn:
                result = conn.execute(text("SELECT current_schema() as schema_name"))
                row = result.fetchone()
                logger.info(f"Schema '{schema_name}' accessible [OK]: {row.schema_name}")
        except Exception as e:
            logger.error(f"Schema '{schema_name}' not accessible [FAIL]: {e}")
            all_schemas_accessible = False

    return all_schemas_accessible


def test_shared_engine():
    """Test shared engine functionality"""
    config = get_database_config()

    try:
        engine = config.get_shared_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT current_schema() as schema_name"))
            row = result.fetchone()
            logger.info(f"Shared engine accessible [OK]: {row.schema_name}")
            return True
    except Exception as e:
        logger.error(f"Shared engine not accessible [FAIL]: {e}")
        return False


def main():
    """Main function to run all database connection tests"""
    setup_logging()

    logger.info("=" * 60)
    logger.info("Database Connection Tests")
    logger.info("=" * 60)

    # Test results
    results = {
        "trading_db": False,
        "prefect_db": False,
        "schemas": False,
        "shared_engine": False,
    }

    # Test trading database
    logger.info("\n1. Testing Trading Database Connection...")
    results["trading_db"] = test_trading_database_connection()

    # Test Prefect database
    logger.info("\n2. Testing Prefect Database Connection...")
    results["prefect_db"] = test_prefect_database_connection()

    # Test schema access
    logger.info("\n3. Testing Schema Access...")
    results["schemas"] = test_schema_access()

    # Test shared engine
    logger.info("\n4. Testing Shared Engine...")
    results["shared_engine"] = test_shared_engine()

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Results Summary")
    logger.info("=" * 60)

    all_passed = True
    for test_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        logger.info(f"{test_name.replace('_', ' ').title()}: {status}")
        if not passed:
            all_passed = False

    logger.info("=" * 60)
    if all_passed:
        logger.info("All database connection tests PASSED [OK]")
        return 0
    else:
        logger.error("Some database connection tests FAILED [FAIL]")
        return 1


if __name__ == "__main__":
    exit(main())
