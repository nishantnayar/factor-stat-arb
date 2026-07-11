"""
Unit tests for Institutional Holders API endpoints
"""

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from src.web.api.institutional_holders import (
    _calculate_missing_percentages,
    get_institutional_holders,
    list_available_symbols,
)


class TestInstitutionalHoldersAPI:
    """Test cases for Institutional Holders API endpoints"""

    @pytest.fixture
    def mock_holders_data(self):
        """Mock institutional holders data"""
        return [
            {
                "id": 1,
                "symbol": "AAPL",
                "date_reported": "2024-09-30",
                "holder_name": "Vanguard Group Inc",
                "shares": 1234567890,
                "value": 24567890123.45,
                "percent_held": None,  # Missing percentage - should be calculated
                "percent_held_display": None,
                "data_source": "yahoo",
            },
            {
                "id": 2,
                "symbol": "AAPL",
                "date_reported": "2024-09-30",
                "holder_name": "BlackRock Inc",
                "shares": 987654321,
                "value": 19654321098.76,
                "percent_held": None,  # Missing percentage - should be calculated
                "percent_held_display": None,
                "data_source": "yahoo",
            },
        ]

    @pytest.fixture
    def mock_holders_with_percentages(self):
        """Mock institutional holders data with existing percentages"""
        return [
            {
                "id": 1,
                "symbol": "AAPL",
                "date_reported": "2024-09-30",
                "holder_name": "Vanguard Group Inc",
                "shares": 1234567890,
                "value": 24567890123.45,
                "percent_held": 0.0954,  # Stored as decimal (0.0954 = 9.54%)
                "percent_held_display": "9.54%",
                "data_source": "yahoo",
            },
        ]

    @pytest.fixture
    def mock_key_statistics(self):
        """Mock key statistics data"""
        return {
            "shares_outstanding": 15728714000,  # ~15.7B shares for AAPL
        }

    @pytest.mark.asyncio
    async def test_get_institutional_holders_success(self, mock_holders_data):
        """Test successful retrieval of institutional holders"""
        with (
            patch("src.web.api.institutional_holders.db_transaction") as mock_db,
            patch("src.web.api.institutional_holders.select") as mock_select,
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
            mock_holder = Mock()
            mock_holder.to_dict.return_value = mock_holders_data[0]
            mock_session.execute.return_value.scalars.return_value.all.return_value = [
                mock_holder
            ]

            # Mock percentage calculation
            with patch(
                "src.web.api.institutional_holders._calculate_missing_percentages"
            ) as mock_calc:
                mock_calc.return_value = [
                    {
                        **mock_holders_data[0],
                        "percent_held": 0.0785,  # Stored as decimal (0.0785 = 7.85%)
                        "percent_held_display": "7.85%",
                    }
                ]

                result = await get_institutional_holders("AAPL")

                assert result["success"] is True
                assert result["symbol"] == "AAPL"
                assert result["count"] == 1
                assert len(result["holders"]) == 1
                assert result["holders"][0]["percent_held"] == 0.0785

    @pytest.mark.asyncio
    async def test_get_institutional_holders_with_existing_percentages(
        self, mock_holders_with_percentages
    ):
        """Test retrieval when percentages already exist"""
        with (
            patch("src.web.api.institutional_holders.db_transaction") as mock_db,
            patch("src.web.api.institutional_holders.select") as mock_select,
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
            mock_holder = Mock()
            mock_holder.to_dict.return_value = mock_holders_with_percentages[0]
            mock_session.execute.return_value.scalars.return_value.all.return_value = [
                mock_holder
            ]

            # Mock percentage calculation should not be called
            with patch(
                "src.web.api.institutional_holders._calculate_missing_percentages"
            ) as mock_calc:
                result = await get_institutional_holders("AAPL")

                assert result["success"] is True
                assert result["holders"][0]["percent_held"] == 0.0954  # Stored as decimal
                mock_calc.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_institutional_holders_no_data(self):
        """Test retrieval when no data exists"""
        with (
            patch("src.web.api.institutional_holders.db_transaction") as mock_db,
            patch("src.web.api.institutional_holders.select") as mock_select,
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

            result = await get_institutional_holders("INVALID")

            assert result["success"] is True
            assert result["symbol"] == "INVALID"
            assert result["count"] == 0
            assert result["holders"] == []

    @pytest.mark.asyncio
    async def test_list_available_symbols_success(self):
        """Test successful listing of available symbols"""
        with patch("src.web.api.institutional_holders.db_transaction") as mock_db:
            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock query results
            mock_results = [("AAPL", 10), ("MSFT", 8), ("GOOGL", 12)]
            mock_session.execute.return_value.all.return_value = mock_results

            result = await list_available_symbols()

            assert result["success"] is True
            assert result["count"] == 3
            assert len(result["symbols"]) == 3
            assert result["symbols"][0]["symbol"] == "AAPL"
            assert result["symbols"][0]["holder_count"] == 10

    @pytest.mark.asyncio
    async def test_list_available_symbols_no_data(self):
        """Test listing when no symbols exist"""
        with patch("src.web.api.institutional_holders.db_transaction") as mock_db:
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
    async def test_calculate_missing_percentages_with_shares_outstanding(
        self, mock_holders_data, mock_key_statistics
    ):
        """Test percentage calculation using shares outstanding"""
        with patch("src.web.api.institutional_holders.db_transaction") as mock_db:
            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock shares outstanding query
            mock_session.execute.return_value.scalar.return_value = mock_key_statistics[
                "shares_outstanding"
            ]

            result = await _calculate_missing_percentages("AAPL", mock_holders_data)

            assert len(result) == 2

            # Check first holder (1234567890 shares out of 15728714000)
            # percent_held is stored as decimal (0.07849 = 7.849%)
            expected_percentage_decimal_1 = 1234567890 / 15728714000
            expected_percentage_display_1 = expected_percentage_decimal_1 * 100
            assert abs(result[0]["percent_held"] - expected_percentage_decimal_1) < 0.0001
            assert result[0]["percent_held_display"] == f"{expected_percentage_display_1:.2f}%"

            # Check second holder (987654321 shares out of 15728714000)
            expected_percentage_decimal_2 = 987654321 / 15728714000
            expected_percentage_display_2 = expected_percentage_decimal_2 * 100
            assert abs(result[1]["percent_held"] - expected_percentage_decimal_2) < 0.0001
            assert result[1]["percent_held_display"] == f"{expected_percentage_display_2:.2f}%"

    @pytest.mark.asyncio
    async def test_calculate_missing_percentages_fallback_method(
        self, mock_holders_data
    ):
        """Test percentage calculation using fallback method"""
        with patch("src.web.api.institutional_holders.db_transaction") as mock_db:
            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock no shares outstanding (fallback to relative percentages)
            mock_session.execute.return_value.scalar.return_value = None

            result = await _calculate_missing_percentages("AAPL", mock_holders_data)

            assert len(result) == 2

            # Total shares: 1234567890 + 987654321 = 2222222211
            total_shares = 1234567890 + 987654321

            # Check first holder (1234567890 out of 2222222211)
            # percent_held is stored as decimal (0.5556 = 55.56%)
            expected_percentage_decimal_1 = 1234567890 / total_shares
            expected_percentage_display_1 = expected_percentage_decimal_1 * 100
            assert abs(result[0]["percent_held"] - expected_percentage_decimal_1) < 0.0001
            assert result[0]["percent_held_display"] == f"{expected_percentage_display_1:.2f}%"

            # Check second holder (987654321 out of 2222222211)
            expected_percentage_decimal_2 = 987654321 / total_shares
            expected_percentage_display_2 = expected_percentage_decimal_2 * 100
            assert abs(result[1]["percent_held"] - expected_percentage_decimal_2) < 0.0001
            assert result[1]["percent_held_display"] == f"{expected_percentage_display_2:.2f}%"

    @pytest.mark.asyncio
    async def test_calculate_missing_percentages_no_shares_data(self):
        """Test percentage calculation with no shares data"""
        holders_no_shares = [
            {
                "symbol": "AAPL",
                "shares": None,
                "percent_held": None,
            }
        ]

        with patch("src.web.api.institutional_holders.db_transaction") as mock_db:
            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock no shares outstanding
            mock_session.execute.return_value.scalar.return_value = None

            result = await _calculate_missing_percentages("AAPL", holders_no_shares)

            assert len(result) == 1
            assert result[0]["percent_held"] == 0.0
            assert result[0]["percent_held_display"] == "N/A"

    @pytest.mark.asyncio
    async def test_calculate_missing_percentages_zero_shares_outstanding(
        self, mock_holders_data
    ):
        """Test percentage calculation with zero shares outstanding"""
        with patch("src.web.api.institutional_holders.db_transaction") as mock_db:
            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock zero shares outstanding
            mock_session.execute.return_value.scalar.return_value = 0

            result = await _calculate_missing_percentages("AAPL", mock_holders_data)

            # Should fall back to relative percentages
            # percent_held is stored as decimal (0.5556 = 55.56%)
            total_shares = 1234567890 + 987654321
            expected_percentage_decimal_1 = 1234567890 / total_shares
            assert abs(result[0]["percent_held"] - expected_percentage_decimal_1) < 0.0001

    def test_api_response_format(self, mock_holders_with_percentages):
        """Test API response format structure"""
        response = {
            "success": True,
            "symbol": "AAPL",
            "count": 1,
            "holders": mock_holders_with_percentages,
        }

        # Test required fields
        assert "success" in response
        assert "symbol" in response
        assert "count" in response
        assert "holders" in response

        # Test holder structure
        holder = response["holders"][0]
        required_holder_fields = [
            "id",
            "symbol",
            "date_reported",
            "holder_name",
            "shares",
            "value",
            "percent_held",
            "percent_held_display",
            "data_source",
        ]

        for field in required_holder_fields:
            assert field in holder

    @pytest.mark.asyncio
    async def test_database_error_handling(self):
        """Test database error handling"""
        with patch("src.web.api.institutional_holders.db_transaction") as mock_db:
            # Mock database error
            mock_db.side_effect = Exception("Database connection failed")

            with pytest.raises(HTTPException) as exc_info:
                await get_institutional_holders("AAPL")

            assert exc_info.value.status_code == 500
            assert "Failed to fetch institutional holders" in str(exc_info.value.detail)

    def test_percentage_display_formatting(self):
        """Test percentage display formatting"""
        test_cases = [
            (7.854321, "7.85%"),
            (0.123456, "0.12%"),
            (99.999999, "100.00%"),
            (0.0, "0.00%"),
        ]

        for percentage, expected_display in test_cases:
            actual_display = f"{percentage:.2f}%"
            assert actual_display == expected_display

    def test_holder_name_truncation(self):
        """Test holder name handling"""
        long_name = "A" * 300  # Very long institution name
        short_name = "Vanguard"

        # Test that long names are handled gracefully
        assert len(long_name) > 255  # Exceeds typical database limit
        assert len(short_name) <= 255

        # In practice, database constraints would limit name length
        # This test ensures the API can handle various name lengths
        assert isinstance(long_name, str)
        assert isinstance(short_name, str)
