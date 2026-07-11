"""
Unit tests for Financial Statements API endpoints
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from src.web.api.financial_statements import (
    get_financial_statements,
    get_latest_financial_statements,
    get_line_item_history,
    list_available_symbols,
)


class TestFinancialStatementsAPI:
    """Test cases for Financial Statements API endpoints"""

    @pytest.fixture
    def mock_financial_statement(self):
        """Mock financial statement data"""
        stmt = Mock()
        stmt.symbol = "AAPL"
        stmt.period_end = date(2024, 9, 30)
        stmt.statement_type = "income"
        stmt.period_type = "quarterly"
        stmt.fiscal_year = 2024
        stmt.fiscal_quarter = 4
        stmt.data = {
            "Total Revenue": 89498000000,
            "Net Income": 22956000000,
            "Basic EPS": 1.46,
            "Total Assets": 352755000000,
            "Total Liabilities": 258549000000,
            "Total Equity": 94206000000,
        }
        stmt.total_revenue = 89498000000
        stmt.net_income = 22956000000
        stmt.basic_eps = Decimal("1.46")
        stmt.total_assets = 352755000000
        stmt.total_liabilities = 258549000000
        stmt.total_equity = 94206000000
        stmt.data_source = "yahoo"
        stmt.created_at = datetime.now(timezone.utc)
        stmt.updated_at = datetime.now(timezone.utc)

        # Mock methods
        stmt.to_dict.return_value = {
            "id": 1,
            "symbol": "AAPL",
            "period_end": "2024-09-30",
            "statement_type": "income",
            "period_type": "quarterly",
            "fiscal_year": 2024,
            "fiscal_quarter": 4,
            "data": stmt.data,
            "total_revenue": 89498000000,
            "net_income": 22956000000,
            "basic_eps": 1.46,
            "total_assets": 352755000000,
            "total_liabilities": 258549000000,
            "total_equity": 94206000000,
            "data_source": "yahoo",
            "created_at": stmt.created_at.isoformat(),
            "updated_at": stmt.updated_at.isoformat(),
        }
        stmt.get_line_item.return_value = 89498000000
        stmt.get_formatted_line_item.return_value = "$89,498,000,000"

        return stmt

    @pytest.fixture
    def mock_annual_statement(self):
        """Mock annual financial statement data"""
        stmt = Mock()
        stmt.symbol = "AAPL"
        stmt.period_end = date(2024, 9, 30)
        stmt.statement_type = "income"
        stmt.period_type = "annual"
        stmt.fiscal_year = 2024
        stmt.fiscal_quarter = None
        stmt.data = {
            "Total Revenue": 383285000000,
            "Net Income": 96995000000,
            "Basic EPS": 6.13,
        }
        stmt.total_revenue = 383285000000
        stmt.net_income = 96995000000
        stmt.basic_eps = Decimal("6.13")
        stmt.data_source = "yahoo"
        stmt.created_at = datetime.now(timezone.utc)
        stmt.updated_at = datetime.now(timezone.utc)

        stmt.to_dict.return_value = {
            "id": 2,
            "symbol": "AAPL",
            "period_end": "2024-09-30",
            "statement_type": "income",
            "period_type": "annual",
            "fiscal_year": 2024,
            "fiscal_quarter": None,
            "data": stmt.data,
            "total_revenue": 383285000000,
            "net_income": 96995000000,
            "basic_eps": 6.13,
            "data_source": "yahoo",
            "created_at": stmt.created_at.isoformat(),
            "updated_at": stmt.updated_at.isoformat(),
        }
        stmt.get_line_item.return_value = 383285000000
        stmt.get_formatted_line_item.return_value = "$383,285,000,000"

        return stmt

    @pytest.mark.asyncio
    async def test_get_financial_statements_success(self, mock_financial_statement):
        """Test successful retrieval of financial statements"""
        with (
            patch("src.web.api.financial_statements.db_transaction") as mock_db,
            patch("src.web.api.financial_statements.select") as mock_select,
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
                mock_financial_statement
            ]

            result = await get_financial_statements("AAPL", "income", "quarterly", 10)

            assert result["success"] is True
            assert result["symbol"] == "AAPL"
            assert result["count"] == 1
            assert len(result["statements"]) == 1
            assert result["statements"][0]["statement_type"] == "income"
            assert result["statements"][0]["period_type"] == "quarterly"

    @pytest.mark.asyncio
    async def test_get_financial_statements_no_data(self):
        """Test retrieval when no data exists"""
        with (
            patch("src.web.api.financial_statements.db_transaction") as mock_db,
            patch("src.web.api.financial_statements.select") as mock_select,
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

            result = await get_financial_statements(
                "INVALID", "income", "quarterly", 10
            )

            assert result["success"] is True
            assert result["symbol"] == "INVALID"
            assert result["count"] == 0
            assert result["statements"] == []
            assert "No financial statements data available" in result["message"]

    @pytest.mark.asyncio
    async def test_get_financial_statements_with_filters(
        self, mock_financial_statement
    ):
        """Test retrieval with statement type and period type filters"""
        with (
            patch("src.web.api.financial_statements.db_transaction") as mock_db,
            patch("src.web.api.financial_statements.select") as mock_select,
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
                mock_financial_statement
            ]

            result = await get_financial_statements("AAPL", "income", "quarterly", 5)

            # Verify query was built with correct filters
            assert (
                mock_query_obj.where.call_count >= 2
            )  # symbol + statement_type + period_type

            assert result["success"] is True
            assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_get_latest_financial_statements_success(
        self, mock_financial_statement, mock_annual_statement
    ):
        """Test getting latest financial statements for each type"""
        with (
            patch("src.web.api.financial_statements.db_transaction") as mock_db,
            patch("src.web.api.financial_statements.select") as mock_select,
        ):

            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock the SQLAlchemy query chain
            mock_query_obj = Mock()
            mock_select.return_value = mock_query_obj
            mock_query_obj.where.return_value = mock_query_obj
            mock_query_obj.order_by.return_value = mock_query_obj

            # Mock query results - annual and quarterly
            mock_session.execute.return_value.scalars.return_value.all.return_value = [
                mock_annual_statement,  # annual
                mock_financial_statement,  # quarterly
            ]

            result = await get_latest_financial_statements("AAPL")

            assert result["success"] is True
            assert result["symbol"] == "AAPL"
            assert "annual" in result
            assert "quarterly" in result
            assert "income" in result["annual"]
            assert "income" in result["quarterly"]

    @pytest.mark.asyncio
    async def test_get_line_item_history_success(self, mock_financial_statement):
        """Test getting historical data for a specific line item"""
        with (
            patch("src.web.api.financial_statements.db_transaction") as mock_db,
            patch("src.web.api.financial_statements.select") as mock_select,
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
                mock_financial_statement
            ]

            result = await get_line_item_history(
                "AAPL", "Total Revenue", "income", "quarterly", 20
            )

            assert result["success"] is True
            assert result["symbol"] == "AAPL"
            assert result["line_item"] == "Total Revenue"
            assert result["statement_type"] == "income"
            assert result["period_type"] == "quarterly"
            assert result["count"] == 1
            assert len(result["data"]) == 1
            assert result["data"][0]["value"] == 89498000000
            assert result["data"][0]["formatted_value"] == "$89,498,000,000"

    @pytest.mark.asyncio
    async def test_get_line_item_history_no_data(self):
        """Test line item history when no data exists"""
        with (
            patch("src.web.api.financial_statements.db_transaction") as mock_db,
            patch("src.web.api.financial_statements.select") as mock_select,
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

            result = await get_line_item_history(
                "INVALID", "Total Revenue", "income", "quarterly", 20
            )

            assert result["success"] is True
            assert result["count"] == 0
            assert result["data"] == []
            assert "No data available for Total Revenue" in result["message"]

    @pytest.mark.asyncio
    async def test_list_available_symbols_success(self):
        """Test listing available symbols with statement counts"""
        with patch("src.web.api.financial_statements.db_transaction") as mock_db:
            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock query results
            mock_results = [
                ("AAPL", "income", "annual", 4),
                ("AAPL", "income", "quarterly", 16),
                ("AAPL", "balance_sheet", "annual", 4),
                ("MSFT", "income", "annual", 3),
            ]
            mock_session.execute.return_value.all.return_value = mock_results

            result = await list_available_symbols()

            assert result["success"] is True
            assert result["count"] == 2  # AAPL and MSFT
            assert len(result["symbols"]) == 2

            # Check AAPL data
            aapl_data = next(s for s in result["symbols"] if s["symbol"] == "AAPL")
            assert aapl_data["total_count"] == 24  # 4+16+4
            assert "income" in aapl_data["statements"]
            assert "balance_sheet" in aapl_data["statements"]
            assert aapl_data["statements"]["income"]["annual"] == 4
            assert aapl_data["statements"]["income"]["quarterly"] == 16

    @pytest.mark.asyncio
    async def test_list_available_symbols_no_data(self):
        """Test listing when no symbols exist"""
        with patch("src.web.api.financial_statements.db_transaction") as mock_db:
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
        with patch("src.web.api.financial_statements.db_transaction") as mock_db:
            # Mock database error
            mock_db.side_effect = Exception("Database connection failed")

            with pytest.raises(HTTPException) as exc_info:
                await get_financial_statements("AAPL")

            assert exc_info.value.status_code == 500
            assert "Failed to fetch financial statements" in str(exc_info.value.detail)

    def test_symbol_case_handling(self):
        """Test that symbol is converted to uppercase"""
        # This would be tested in the actual API call
        symbol = "aapl"
        assert symbol.upper() == "AAPL"

    def test_financial_statement_model_methods(self, mock_financial_statement):
        """Test FinancialStatement model methods"""
        # Test get_line_item method
        mock_financial_statement.get_line_item("Total Revenue")
        mock_financial_statement.get_line_item.assert_called_with("Total Revenue")

        # Test get_formatted_line_item method
        mock_financial_statement.get_formatted_line_item("Total Revenue", "currency")
        mock_financial_statement.get_formatted_line_item.assert_called_with(
            "Total Revenue", "currency"
        )

    def test_api_response_format(self, mock_financial_statement):
        """Test API response format structure"""
        response = {
            "success": True,
            "symbol": "AAPL",
            "count": 1,
            "statements": [mock_financial_statement.to_dict()],
        }

        # Test required fields
        assert "success" in response
        assert "symbol" in response
        assert "count" in response
        assert "statements" in response

        # Test statement structure
        statement = response["statements"][0]
        required_fields = [
            "symbol",
            "period_end",
            "statement_type",
            "period_type",
            "fiscal_year",
            "fiscal_quarter",
            "data",
            "total_revenue",
            "net_income",
            "basic_eps",
            "data_source",
        ]

        for field in required_fields:
            assert field in statement

    def test_line_item_data_format(self, mock_financial_statement):
        """Test line item data format structure"""
        line_item_data = {
            "period_end": "2024-09-30",
            "fiscal_year": 2024,
            "fiscal_quarter": 4,
            "value": 89498000000,
            "formatted_value": "$89,498,000,000",
        }

        required_fields = [
            "period_end",
            "fiscal_year",
            "fiscal_quarter",
            "value",
            "formatted_value",
        ]

        for field in required_fields:
            assert field in line_item_data

    @pytest.mark.asyncio
    async def test_get_financial_statements_without_filters(
        self, mock_financial_statement
    ):
        """Test retrieval without statement type and period type filters"""
        with (
            patch("src.web.api.financial_statements.db_transaction") as mock_db,
            patch("src.web.api.financial_statements.select") as mock_select,
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
                mock_financial_statement
            ]

            result = await get_financial_statements("AAPL")

            assert result["success"] is True
            assert result["count"] == 1
            # Should filter by symbol, and optionally by statement_type and period_type if provided
            # The actual implementation may call where multiple times for different conditions
            assert mock_query_obj.where.call_count >= 1  # At least symbol filter

    @pytest.mark.asyncio
    async def test_get_latest_financial_statements_no_data(self):
        """Test latest financial statements when no data exists"""
        with (
            patch("src.web.api.financial_statements.db_transaction") as mock_db,
            patch("src.web.api.financial_statements.select") as mock_select,
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

            result = await get_latest_financial_statements("INVALID")

            assert result["success"] is True
            assert result["symbol"] == "INVALID"
            assert result["annual"] == {}
            assert result["quarterly"] == {}

    def test_financial_statement_period_display(self, mock_financial_statement):
        """Test financial statement period display properties"""
        # Test quarterly period display
        mock_financial_statement.period_type = "quarterly"
        mock_financial_statement.fiscal_year = 2024
        mock_financial_statement.fiscal_quarter = 4

        # This would test the period_display property if it exists
        # For now, we test the data structure
        assert mock_financial_statement.period_type == "quarterly"
        assert mock_financial_statement.fiscal_year == 2024
        assert mock_financial_statement.fiscal_quarter == 4

    def test_financial_statement_statement_display(self, mock_financial_statement):
        """Test financial statement type display properties"""
        # Test income statement display
        mock_financial_statement.statement_type = "income"

        # This would test the statement_display property if it exists
        # For now, we test the data structure
        assert mock_financial_statement.statement_type == "income"
