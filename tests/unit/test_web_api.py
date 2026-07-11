"""
Unit tests for Web API endpoints
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.web.api.timezone_helpers import (
    format_api_timestamp,
    get_current_time_info,
    get_market_status_info,
)
from src.web.main import app


class TestWebAPI:
    """Test cases for Web API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200

    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()

    def test_dashboard_endpoint(self, client):
        """Test dashboard endpoint"""
        response = client.get("/dashboard")
        assert response.status_code == 200

    def test_trading_endpoint(self, client):
        """Test trading endpoint"""
        response = client.get("/trading")
        assert response.status_code == 200

    def test_analytics_endpoint(self, client):
        """Test analytics endpoint"""
        response = client.get("/analysis")
        assert response.status_code == 200

    def test_strategies_endpoint(self, client):
        """Test strategies endpoint"""
        response = client.get("/strategies")
        assert response.status_code == 200

    def test_profile_endpoint(self, client):
        """Test profile endpoint"""
        response = client.get("/profile")
        assert response.status_code == 200


class TestTimezoneHelpers:
    """Test cases for timezone helper functions"""

    def test_get_current_time_info(self):
        """Test get current time info function"""
        result = get_current_time_info()

        assert "utc" in result
        assert "central" in result
        assert "eastern" in result
        assert "market_status" in result

    def test_format_api_timestamp(self):
        """Test API timestamp formatting"""
        test_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        result = format_api_timestamp(test_time)

        assert isinstance(result, str)
        assert "2024-01-01" in result

    def test_get_market_status_info(self):
        """Test market status info function"""
        result = get_market_status_info()

        assert isinstance(result, dict)
        assert "is_market_hours" in result
        assert "current_time_eastern" in result
        assert "next_market_open" in result
        assert "last_market_close" in result

    def test_get_market_status_info_returns_required_fields(self):
        """Test get market status info returns all required fields"""
        result = get_market_status_info()

        assert isinstance(result, dict)
        assert "is_market_hours" in result
        assert "is_weekend" in result
        assert "next_market_open" in result
        assert "last_market_close" in result
        assert "current_time_eastern" in result

    def test_timezone_conversion_aware_datetime(self):
        """Test timezone conversion with aware datetime"""
        aware_dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = format_api_timestamp(aware_dt)
        assert isinstance(result, str)
        assert "2024" in result

    def test_timezone_display_formatting(self):
        """Test timezone display formatting"""
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        result = format_api_timestamp(dt)

        assert isinstance(result, str)
        # Central time would be 6 hours behind UTC in winter
        assert "2024-01-01" in result

    def test_market_status_integration(self):
        """Test market status integration"""
        info = get_current_time_info()

        assert "market_status" in info
        assert isinstance(info["market_status"], dict)
        assert "is_market_hours" in info["market_status"]


class TestWebAPIErrorHandling:
    """Test error handling in Web API"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_404_endpoint(self, client):
        """Test 404 for non-existent endpoint"""
        response = client.get("/nonexistent")
        assert response.status_code == 404

    def test_method_not_allowed(self, client):
        """Test method not allowed"""
        response = client.put("/health")  # PUT not allowed on health endpoint
        assert response.status_code == 405

    def test_nonexistent_api_route(self, client):
        """Test accessing nonexistent API route"""
        response = client.get("/api/nonexistent")

        assert response.status_code == 404
