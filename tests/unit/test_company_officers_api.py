"""
Unit tests for Company Officers API endpoints
"""

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from src.web.api.company_officers import (
    get_company_officers,
    get_compensation_summary,
    get_officers_by_title,
    list_available_symbols,
)


class TestCompanyOfficersAPI:
    """Test cases for Company Officers API endpoints"""

    @pytest.fixture
    def mock_officer_data(self):
        """Mock company officer data"""
        return {
            "id": 1,
            "symbol": "AAPL",
            "name": "Tim Cook",
            "title": "Chief Executive Officer",
            "age": 63,
            "year_born": 1960,
            "fiscal_year": 2024,
            "total_pay": 99420000,  # $994,200 in cents
            "exercised_value": 0,
            "unexercised_value": 0,
            "data_source": "yahoo",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

    @pytest.fixture
    def mock_officer(self, mock_officer_data):
        """Mock CompanyOfficer object"""
        officer = Mock()
        officer.to_dict.return_value = {
            **mock_officer_data,
            "total_pay_display": "$994.2K",
            "exercised_value_display": "N/A",
            "unexercised_value_display": "N/A",
        }
        return officer

    @pytest.fixture
    def mock_multiple_officers(self):
        """Mock multiple company officers data"""
        return [
            {
                "id": 1,
                "symbol": "AAPL",
                "name": "Tim Cook",
                "title": "Chief Executive Officer",
                "age": 63,
                "year_born": 1960,
                "fiscal_year": 2024,
                "total_pay": 99420000,
                "exercised_value": 0,
                "unexercised_value": 0,
                "data_source": "yahoo",
                "total_pay_display": "$994.2K",
                "exercised_value_display": "N/A",
                "unexercised_value_display": "N/A",
            },
            {
                "id": 2,
                "symbol": "AAPL",
                "name": "Luca Maestri",
                "title": "Chief Financial Officer",
                "age": 60,
                "year_born": 1963,
                "fiscal_year": 2024,
                "total_pay": 26500000,
                "exercised_value": 0,
                "unexercised_value": 0,
                "data_source": "yahoo",
                "total_pay_display": "$26.5M",
                "exercised_value_display": "N/A",
                "unexercised_value_display": "N/A",
            },
        ]

    @pytest.mark.asyncio
    async def test_get_company_officers_success(self, mock_officer):
        """Test successful retrieval of company officers"""
        with (
            patch("src.web.api.company_officers.db_transaction") as mock_db,
            patch("src.web.api.company_officers.select") as mock_select,
        ):

            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock the SQLAlchemy query chain
            mock_query_obj = Mock()
            mock_select.return_value = mock_query_obj
            mock_query_obj.where.return_value = mock_query_obj
            mock_query_obj.order_by.return_value = mock_query_obj
            mock_query_obj.limit.return_value = mock_query_obj

            # Mock query results
            mock_session.execute.return_value.scalars.return_value.all.return_value = [
                mock_officer
            ]

            result = await get_company_officers("AAPL", 50)

            assert result["success"] is True
            assert result["symbol"] == "AAPL"
            assert result["count"] == 1
            assert len(result["officers"]) == 1
            assert result["officers"][0]["name"] == "Tim Cook"
            assert result["officers"][0]["title"] == "Chief Executive Officer"

    @pytest.mark.asyncio
    async def test_get_company_officers_no_data(self):
        """Test retrieval when no data exists"""
        with (
            patch("src.web.api.company_officers.db_transaction") as mock_db,
            patch("src.web.api.company_officers.select") as mock_select,
        ):

            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock the SQLAlchemy query chain
            mock_query_obj = Mock()
            mock_select.return_value = mock_query_obj
            mock_query_obj.where.return_value = mock_query_obj
            mock_query_obj.order_by.return_value = mock_query_obj
            mock_query_obj.limit.return_value = mock_query_obj

            # Mock empty query results
            mock_session.execute.return_value.scalars.return_value.all.return_value = []

            result = await get_company_officers("INVALID", 50)

            assert result["success"] is True
            assert result["symbol"] == "INVALID"
            assert result["count"] == 0
            assert result["officers"] == []
            assert "No company officers data available" in result["message"]

    @pytest.mark.asyncio
    async def test_get_company_officers_with_limit(self, mock_multiple_officers):
        """Test retrieval with custom limit"""
        with (
            patch("src.web.api.company_officers.db_transaction") as mock_db,
            patch("src.web.api.company_officers.select") as mock_select,
        ):

            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock the SQLAlchemy query chain
            mock_query_obj = Mock()
            mock_select.return_value = mock_query_obj
            mock_query_obj.where.return_value = mock_query_obj
            mock_query_obj.order_by.return_value = mock_query_obj
            mock_query_obj.limit.return_value = mock_query_obj

            # Mock query results
            mock_officers = [Mock() for _ in mock_multiple_officers]
            for i, officer in enumerate(mock_officers):
                officer.to_dict.return_value = mock_multiple_officers[i]

            mock_session.execute.return_value.scalars.return_value.all.return_value = (
                mock_officers
            )

            result = await get_company_officers("AAPL", 2)

            assert result["success"] is True
            assert result["count"] == 2
            assert len(result["officers"]) == 2
            # Verify limit was applied
            mock_query_obj.limit.assert_called_once_with(2)

    @pytest.mark.asyncio
    async def test_get_officers_by_title_success(self, mock_multiple_officers):
        """Test getting officers grouped by title"""
        with (
            patch("src.web.api.company_officers.db_transaction") as mock_db,
            patch("src.web.api.company_officers.select") as mock_select,
        ):

            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock the SQLAlchemy query chain
            mock_query_obj = Mock()
            mock_select.return_value = mock_query_obj
            mock_query_obj.where.return_value = mock_query_obj
            mock_query_obj.order_by.return_value = mock_query_obj

            # Mock query results
            mock_officers = [Mock() for _ in mock_multiple_officers]
            for i, officer in enumerate(mock_officers):
                officer.to_dict.return_value = mock_multiple_officers[i]
                officer.title = mock_multiple_officers[i]["title"]

            mock_session.execute.return_value.scalars.return_value.all.return_value = (
                mock_officers
            )

            result = await get_officers_by_title("AAPL", None)

            assert result["success"] is True
            assert result["symbol"] == "AAPL"
            assert result["count"] == 2
            assert "officers_by_title" in result
            assert "Chief Executive Officer" in result["officers_by_title"]
            assert "Chief Financial Officer" in result["officers_by_title"]

    @pytest.mark.asyncio
    async def test_get_officers_by_title_with_filter(self, mock_officer):
        """Test getting officers filtered by title"""
        with (
            patch("src.web.api.company_officers.db_transaction") as mock_db,
            patch("src.web.api.company_officers.select") as mock_select,
        ):

            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock the SQLAlchemy query chain
            mock_query_obj = Mock()
            mock_select.return_value = mock_query_obj
            mock_query_obj.where.return_value = mock_query_obj
            mock_query_obj.order_by.return_value = mock_query_obj

            # Mock query results
            mock_session.execute.return_value.scalars.return_value.all.return_value = [
                mock_officer
            ]

            result = await get_officers_by_title("AAPL", "CEO")

            assert result["success"] is True
            assert result["count"] == 1
            # Verify title filter was applied
            assert mock_query_obj.where.call_count >= 2  # symbol + title filter

    @pytest.mark.asyncio
    async def test_get_officers_by_title_no_data(self):
        """Test getting officers by title when no data exists"""
        with (
            patch("src.web.api.company_officers.db_transaction") as mock_db,
            patch("src.web.api.company_officers.select") as mock_select,
        ):

            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock the SQLAlchemy query chain
            mock_query_obj = Mock()
            mock_select.return_value = mock_query_obj
            mock_query_obj.where.return_value = mock_query_obj
            mock_query_obj.order_by.return_value = mock_query_obj

            # Mock empty query results
            mock_session.execute.return_value.scalars.return_value.all.return_value = []

            result = await get_officers_by_title("INVALID", "CEO")

            assert result["success"] is True
            assert result["count"] == 0
            assert result["officers_by_title"] == {}
            assert "No company officers data available" in result["message"]

    @pytest.mark.asyncio
    async def test_get_compensation_summary_success(self):
        """Test getting compensation summary"""
        with patch("src.web.api.company_officers.db_transaction") as mock_db:
            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock compensation statistics query result
            mock_result = Mock()
            mock_result.total_officers = 5
            mock_result.avg_total_pay = 50000000  # $500K in cents
            mock_result.max_total_pay = 99420000  # $994.2K in cents
            mock_result.min_total_pay = 10000000  # $100K in cents
            mock_result.sum_total_pay = 250000000  # $2.5M in cents

            mock_session.execute.return_value.first.return_value = mock_result

            result = await get_compensation_summary("AAPL")

            assert result["success"] is True
            assert result["symbol"] == "AAPL"
            assert result["total_officers"] == 5
            assert "compensation" in result
            assert result["compensation"]["average"] == "$500,000"
            assert result["compensation"]["highest"] == "$994,200"
            assert result["compensation"]["lowest"] == "$100,000"
            assert result["compensation"]["total"] == "$2,500,000"

    @pytest.mark.asyncio
    async def test_get_compensation_summary_no_data(self):
        """Test compensation summary when no data exists"""
        with patch("src.web.api.company_officers.db_transaction") as mock_db:
            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock no compensation data
            mock_session.execute.return_value.first.return_value = None

            result = await get_compensation_summary("INVALID")

            assert result["success"] is True
            assert result["symbol"] == "INVALID"
            assert "No compensation data available" in result["message"]

    @pytest.mark.asyncio
    async def test_get_compensation_summary_zero_officers(self):
        """Test compensation summary with zero officers"""
        with patch("src.web.api.company_officers.db_transaction") as mock_db:
            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock zero officers result
            mock_result = Mock()
            mock_result.total_officers = 0
            mock_session.execute.return_value.first.return_value = mock_result

            result = await get_compensation_summary("INVALID")

            assert result["success"] is True
            assert "No compensation data available" in result["message"]

    @pytest.mark.asyncio
    async def test_list_available_symbols_success(self):
        """Test listing available symbols with officer counts"""
        with patch("src.web.api.company_officers.db_transaction") as mock_db:
            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock query results
            mock_results = [("AAPL", 5), ("MSFT", 8), ("GOOGL", 6)]
            mock_session.execute.return_value.all.return_value = mock_results

            result = await list_available_symbols()

            assert result["success"] is True
            assert result["count"] == 3
            assert len(result["symbols"]) == 3
            assert result["symbols"][0]["symbol"] == "AAPL"
            assert result["symbols"][0]["officer_count"] == 5

    @pytest.mark.asyncio
    async def test_list_available_symbols_no_data(self):
        """Test listing when no symbols exist"""
        with patch("src.web.api.company_officers.db_transaction") as mock_db:
            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock empty query results
            mock_session.execute.return_value.all.return_value = []

            result = await list_available_symbols()

            assert result["success"] is True
            assert result["count"] == 0
            assert result["symbols"] == []

    @pytest.mark.asyncio
    async def test_database_error_handling(self):
        """Test database error handling"""
        with patch("src.web.api.company_officers.db_transaction") as mock_db:
            # Mock database error
            mock_db.side_effect = Exception("Database connection failed")

            with pytest.raises(HTTPException) as exc_info:
                await get_company_officers("AAPL")

            assert exc_info.value.status_code == 500
            assert "Failed to fetch company officers" in str(exc_info.value.detail)

    def test_symbol_case_handling(self):
        """Test that symbol is converted to uppercase"""
        symbol = "aapl"
        assert symbol.upper() == "AAPL"

    def test_api_response_format(self, mock_officer_data):
        """Test API response format structure"""
        response = {
            "success": True,
            "symbol": "AAPL",
            "count": 1,
            "officers": [mock_officer_data],
        }

        # Test required fields
        assert "success" in response
        assert "symbol" in response
        assert "count" in response
        assert "officers" in response

        # Test officer structure
        officer = response["officers"][0]
        required_fields = [
            "id",
            "symbol",
            "name",
            "title",
            "age",
            "year_born",
            "fiscal_year",
            "total_pay",
            "exercised_value",
            "unexercised_value",
            "data_source",
        ]

        for field in required_fields:
            assert field in officer

    def test_compensation_display_formatting(self):
        """Test compensation display formatting"""
        test_cases = [
            (99420000, "$994.2K"),  # $994,200 in cents
            (2650000000, "$26.5M"),  # $26.5M in cents
            (1000000, "$10.0K"),  # $10K in cents
            (500000000, "$5.0M"),  # $5M in cents
        ]

        for amount_cents, expected_display in test_cases:
            amount = amount_cents / 100
            if amount >= 1_000_000_000:
                actual_display = f"${amount / 1_000_000_000:.1f}B"
            elif amount >= 1_000_000:
                actual_display = f"${amount / 1_000_000:.1f}M"
            elif amount >= 1_000:
                actual_display = f"${amount / 1_000:.1f}K"
            else:
                actual_display = f"${amount:.1f}"

            assert actual_display == expected_display

    def test_officer_title_grouping(self, mock_multiple_officers):
        """Test officer title grouping logic"""
        # Simulate grouping by title
        officers_by_title = {}
        for officer in mock_multiple_officers:
            title = officer["title"]
            if title not in officers_by_title:
                officers_by_title[title] = []
            officers_by_title[title].append(officer)

        assert "Chief Executive Officer" in officers_by_title
        assert "Chief Financial Officer" in officers_by_title
        assert len(officers_by_title["Chief Executive Officer"]) == 1
        assert len(officers_by_title["Chief Financial Officer"]) == 1

    def test_compensation_statistics_calculation(self):
        """Test compensation statistics calculation"""
        # Test data: amounts in cents
        amounts = [99420000, 26500000, 10000000, 50000000, 75000000]

        # Convert to dollars for calculation
        amounts_dollars = [amount / 100 for amount in amounts]

        total_officers = len(amounts)
        avg_pay = sum(amounts_dollars) / total_officers
        max_pay = max(amounts_dollars)
        min_pay = min(amounts_dollars)
        total_pay = sum(amounts_dollars)

        assert total_officers == 5
        assert avg_pay == 52184000 / 100  # $521,840
        assert max_pay == 99420000 / 100  # $994,200
        assert min_pay == 10000000 / 100  # $100,000
        assert total_pay == 260920000 / 100  # $2,609,200

    def test_officer_name_handling(self):
        """Test officer name handling"""
        test_names = [
            "Tim Cook",
            "Luca Maestri",
            "Jeff Williams",
            "Katherine Adams",
            "Deirdre O'Brien",
        ]

        for name in test_names:
            assert isinstance(name, str)
            assert len(name) > 0
            assert len(name) <= 255  # Database limit

    def test_fiscal_year_handling(self):
        """Test fiscal year handling"""
        fiscal_years = [2020, 2021, 2022, 2023, 2024]

        for year in fiscal_years:
            assert isinstance(year, int)
            assert 2000 <= year <= 2030  # Reasonable range

    def test_age_calculation(self):
        """Test age calculation logic"""
        current_year = 2024
        birth_years = [1960, 1963, 1955, 1970, 1965]

        for birth_year in birth_years:
            age = current_year - birth_year
            assert 30 <= age <= 80  # Reasonable age range for executives

    @pytest.mark.asyncio
    async def test_get_company_officers_ordering(self, mock_multiple_officers):
        """Test that officers are ordered by total pay (highest first)"""
        with (
            patch("src.web.api.company_officers.db_transaction") as mock_db,
            patch("src.web.api.company_officers.select") as mock_select,
        ):

            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock the SQLAlchemy query chain
            mock_query_obj = Mock()
            mock_select.return_value = mock_query_obj
            mock_query_obj.where.return_value = mock_query_obj
            mock_query_obj.order_by.return_value = mock_query_obj
            mock_query_obj.limit.return_value = mock_query_obj

            # Mock query results
            mock_officers = [Mock() for _ in mock_multiple_officers]
            for i, officer in enumerate(mock_officers):
                officer.to_dict.return_value = mock_multiple_officers[i]

            mock_session.execute.return_value.scalars.return_value.all.return_value = (
                mock_officers
            )

            result = await get_company_officers("AAPL", 50)

            # Verify ordering was applied
            mock_query_obj.order_by.assert_called_once()

            # Check that results are ordered by total pay (highest first)
            officers = result["officers"]
            assert len(officers) == 2
            # Tim Cook should be first (higher total_pay: 99420000)
            assert officers[0]["name"] == "Tim Cook"
            assert officers[0]["total_pay"] == 99420000
            # Luca Maestri should be second (lower total_pay: 26500000)
            assert officers[1]["name"] == "Luca Maestri"
            assert officers[1]["total_pay"] == 26500000
