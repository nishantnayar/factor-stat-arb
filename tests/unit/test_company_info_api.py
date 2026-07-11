"""
Unit tests for Company Info API endpoints
"""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from src.web.main import app


class TestCompanyInfoAPI:
    """Test Company Info API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def mock_company_info(self):
        """Create mock company info"""
        company = Mock()
        company.symbol = "AAPL"
        company.name = "Apple Inc."
        company.sector = "Technology"
        company.industry = "Consumer Electronics"
        company.description = "Apple designs consumer electronics"
        company.website = "https://www.apple.com"
        company.phone = "408-996-1010"
        company.address = "One Apple Park Way"
        company.city = "Cupertino"
        company.state = "CA"
        company.zip = "95014"
        company.country = "United States"
        company.employees = 150000
        company.market_cap = 3000000000000
        company.market_cap_billions = 3000.0
        company.currency = "USD"
        company.exchange = "NASDAQ"
        company.quote_type = "EQUITY"
        company.data_source = "yahoo"
        return company

    @patch("src.web.api.company_info.db_transaction")
    def test_get_sectors(self, mock_db_transaction, client):
        """Test getting list of sectors"""
        mock_session = Mock()
        mock_result = Mock()
        mock_result.fetchall.return_value = [
            ("Technology",),
            ("Healthcare",),
            ("Finance",),
        ]
        mock_session.execute.return_value = mock_result
        mock_db_transaction.return_value.__enter__.return_value = mock_session

        response = client.get("/api/company-info/filters/sectors")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert "Technology" in data
        assert "Healthcare" in data
        assert "Finance" in data

    @patch("src.web.api.company_info.db_transaction")
    def test_get_sectors_empty(self, mock_db_transaction, client):
        """Test getting sectors when none exist"""
        mock_session = Mock()
        mock_result = Mock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result
        mock_db_transaction.return_value.__enter__.return_value = mock_session

        response = client.get("/api/company-info/filters/sectors")

        assert response.status_code == 200
        assert response.json() == []

    @patch("src.web.api.company_info.db_transaction")
    def test_get_industries(self, mock_db_transaction, client):
        """Test getting list of industries"""
        mock_session = Mock()
        mock_result = Mock()
        mock_result.fetchall.return_value = [
            ("Consumer Electronics",),
            ("Software",),
            ("Semiconductors",),
        ]
        mock_session.execute.return_value = mock_result
        mock_db_transaction.return_value.__enter__.return_value = mock_session

        response = client.get("/api/company-info/filters/industries")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert "Consumer Electronics" in data

    @patch("src.web.api.company_info.db_transaction")
    def test_get_industries_with_sector_filter(self, mock_db_transaction, client):
        """Test getting industries filtered by sector"""
        mock_session = Mock()
        mock_result = Mock()
        mock_result.fetchall.return_value = [("Consumer Electronics",), ("Software",)]
        mock_session.execute.return_value = mock_result
        mock_db_transaction.return_value.__enter__.return_value = mock_session

        response = client.get("/api/company-info/filters/industries?sector=Technology")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @patch("src.web.api.company_info.db_transaction")
    def test_get_symbols_by_filter(self, mock_db_transaction, client):
        """Test getting symbols with filters"""
        mock_session = Mock()
        mock_result = Mock()
        mock_result.fetchall.return_value = [
            ("AAPL", "Apple Inc."),
            ("MSFT", "Microsoft Corporation"),
        ]
        mock_session.execute.return_value = mock_result
        mock_db_transaction.return_value.__enter__.return_value = mock_session

        response = client.get("/api/company-info/filters/symbols?sector=Technology")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["symbol"] == "AAPL"
        assert data[0]["name"] == "Apple Inc."

    @patch("src.web.api.company_info.db_transaction")
    def test_get_symbols_by_multiple_filters(self, mock_db_transaction, client):
        """Test getting symbols with multiple filters"""
        mock_session = Mock()
        mock_result = Mock()
        mock_result.fetchall.return_value = [("AAPL", "Apple Inc.")]
        mock_session.execute.return_value = mock_result
        mock_db_transaction.return_value.__enter__.return_value = mock_session

        response = client.get(
            "/api/company-info/filters/symbols?sector=Technology&industry=Consumer Electronics"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    @patch("src.web.api.company_info.db_transaction")
    def test_get_company_info_success(
        self, mock_db_transaction, client, mock_company_info
    ):
        """Test getting company info for specific symbol"""
        mock_session = Mock()
        mock_session.scalar.return_value = mock_company_info
        mock_db_transaction.return_value.__enter__.return_value = mock_session

        response = client.get("/api/company-info/AAPL")

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "AAPL"
        assert data["name"] == "Apple Inc."
        assert data["sector"] == "Technology"
        assert data["industry"] == "Consumer Electronics"

    @patch("src.web.api.company_info.db_transaction")
    def test_get_company_info_not_found(self, mock_db_transaction, client):
        """Test getting company info for non-existent symbol"""
        mock_session = Mock()
        mock_session.scalar.return_value = None
        mock_db_transaction.return_value.__enter__.return_value = mock_session

        response = client.get("/api/company-info/INVALID")

        assert response.status_code == 404
        assert "company info" in response.json()["detail"].lower()

    @patch("src.web.api.company_info.db_transaction")
    def test_get_company_info_case_insensitive(
        self, mock_db_transaction, client, mock_company_info
    ):
        """Test that symbol lookup is case insensitive"""
        mock_session = Mock()
        mock_session.scalar.return_value = mock_company_info
        mock_db_transaction.return_value.__enter__.return_value = mock_session

        response = client.get("/api/company-info/aapl")

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "AAPL"

    @patch("src.web.api.company_info.db_transaction")
    def test_get_sectors_database_error(self, mock_db_transaction, client):
        """Test handling database errors in get_sectors"""
        mock_db_transaction.side_effect = Exception("Database error")

        response = client.get("/api/company-info/filters/sectors")

        assert response.status_code == 500
        assert "Failed to get sectors" in response.json()["detail"]

    @patch("src.web.api.company_info.db_transaction")
    def test_get_industries_database_error(self, mock_db_transaction, client):
        """Test handling database errors in get_industries"""
        mock_db_transaction.side_effect = Exception("Database error")

        response = client.get("/api/company-info/filters/industries")

        assert response.status_code == 500
        assert "Failed to get industries" in response.json()["detail"]

    @patch("src.web.api.company_info.db_transaction")
    def test_get_symbols_database_error(self, mock_db_transaction, client):
        """Test handling database errors in get_symbols"""
        mock_db_transaction.side_effect = Exception("Database error")

        response = client.get("/api/company-info/filters/symbols")

        assert response.status_code == 500
        assert "Failed to get symbols" in response.json()["detail"]

    @patch("src.web.api.company_info.db_transaction")
    def test_get_company_info_database_error(self, mock_db_transaction, client):
        """Test handling database errors in get_company_info"""
        mock_session = Mock()
        mock_session.scalar.side_effect = Exception("Database error")
        mock_db_transaction.return_value.__enter__.return_value = mock_session

        response = client.get("/api/company-info/AAPL")

        assert response.status_code == 500
        assert "Failed to get company info" in response.json()["detail"]
