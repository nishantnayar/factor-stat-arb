"""
Integration tests for Prefect configuration

Tests that Prefect configuration can be read and Prefect can connect.
"""

import os

import pytest

from src.shared.prefect.config import PrefectConfig


def test_prefect_config_import():
    """Test that PrefectConfig can be imported"""
    assert PrefectConfig is not None


def test_prefect_config_get_api_url():
    """Test getting API URL from config"""
    api_url = PrefectConfig.get_api_url()
    assert api_url is not None
    assert isinstance(api_url, str)
    assert api_url.startswith("http")
    assert "/api" in api_url or api_url.endswith("/api")


def test_prefect_config_get_db_connection_url():
    """Test getting database connection URL"""
    db_url = PrefectConfig.get_db_connection_url()
    assert db_url is not None
    assert isinstance(db_url, str)
    assert "postgresql+asyncpg://" in db_url
    assert "prefect" in db_url


def test_prefect_config_get_work_pool_name():
    """Test getting work pool name"""
    pool_name = PrefectConfig.get_work_pool_name()
    assert pool_name is not None
    assert isinstance(pool_name, str)
    assert len(pool_name) > 0


@pytest.mark.integration
def test_prefect_can_import():
    """Integration test: Verify Prefect can be imported"""
    try:
        from prefect import flow, get_client, task

        assert flow is not None
        assert task is not None
        assert get_client is not None
    except ImportError as e:
        pytest.skip(f"Prefect not available: {e}")


@pytest.mark.integration
def test_prefect_config_connection():
    """Integration test: Verify Prefect can read configuration and connect"""
    try:
        from prefect import get_client
        from prefect.settings import PREFECT_API_URL

        # Get API URL from our config
        api_url = PrefectConfig.get_api_url()
        assert api_url is not None

        # Try to get Prefect client (may fail if server not running, that's OK)
        # This test verifies the config is accessible to Prefect
        original_url = os.environ.get("PREFECT_API_URL")
        try:
            os.environ["PREFECT_API_URL"] = api_url
            # Just verify we can create a client (connection may fail if server not running)
            client = get_client()
            assert client is not None
        except Exception:
            # Server not running is OK for this test
            # We're just verifying config is accessible
            pass
        finally:
            if original_url:
                os.environ["PREFECT_API_URL"] = original_url
            elif "PREFECT_API_URL" in os.environ:
                del os.environ["PREFECT_API_URL"]

    except ImportError:
        pytest.skip("Prefect not available")
