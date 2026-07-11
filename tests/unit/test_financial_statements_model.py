"""
Unit tests for Financial Statements database model
"""

from datetime import date, datetime
from decimal import Decimal

import pytest

from src.shared.database.models.financial_statements import FinancialStatement


class TestFinancialStatementModel:
    """Test cases for FinancialStatement model"""

    @pytest.fixture
    def sample_financial_statement(self):
        """Create a sample financial statement for testing"""
        return FinancialStatement(
            symbol="AAPL",
            period_end=date(2024, 9, 30),
            statement_type="income",
            period_type="quarterly",
            fiscal_year=2024,
            fiscal_quarter=4,
            data={
                "Total Revenue": 89498000000,
                "Net Income": 22956000000,
                "Gross Profit": 39180000000,
                "Operating Income": 26661000000,
                "EBITDA": 30000000000,
                "Total Assets": 352755000000,
                "Total Liabilities": 258549000000,
                "Total Equity": 94206000000,
                "Cash And Cash Equivalents": 29965000000,
                "Total Debt": 110000000000,
                "Operating Cash Flow": 28000000000,
                "Free Cash Flow": 25000000000,
                "Basic EPS": 1.46,
                "Diluted EPS": 1.45,
                "Book Value Per Share": 6.13,
            },
            data_source="yahoo",
        )

    def test_model_initialization(self, sample_financial_statement):
        """Test model initialization with all fields"""
        stmt = sample_financial_statement

        assert stmt.symbol == "AAPL"
        assert stmt.period_end == date(2024, 9, 30)
        assert stmt.statement_type == "income"
        assert stmt.period_type == "quarterly"
        assert stmt.fiscal_year == 2024
        assert stmt.fiscal_quarter == 4
        assert stmt.data_source == "yahoo"
        assert isinstance(stmt.data, dict)

    def test_populate_common_metrics(self, sample_financial_statement):
        """Test populate_common_metrics method"""
        stmt = sample_financial_statement
        stmt.populate_common_metrics()

        # Test income statement metrics
        assert stmt.total_revenue == 89498000000
        assert stmt.net_income == 22956000000
        assert stmt.gross_profit == 39180000000
        assert stmt.operating_income == 26661000000
        assert stmt.ebitda == 30000000000

        # Test balance sheet metrics
        assert stmt.total_assets == 352755000000
        assert stmt.total_liabilities == 258549000000
        assert stmt.total_equity == 94206000000
        assert stmt.cash_and_equivalents == 29965000000
        assert stmt.total_debt == 110000000000

        # Test cash flow metrics
        assert stmt.operating_cash_flow == 28000000000
        assert stmt.free_cash_flow == 25000000000

        # Test per-share metrics
        assert stmt.basic_eps == Decimal("1.46")
        assert stmt.diluted_eps == Decimal("1.45")
        assert stmt.book_value_per_share == Decimal("6.13")

    def test_populate_common_metrics_missing_data(self):
        """Test populate_common_metrics with missing data"""
        stmt = FinancialStatement(
            symbol="TEST",
            period_end=date(2024, 9, 30),
            statement_type="income",
            period_type="quarterly",
            data={},  # Empty data
        )

        stmt.populate_common_metrics()

        # All metrics should be None when data is missing
        assert stmt.total_revenue is None
        assert stmt.net_income is None
        assert stmt.gross_profit is None
        assert stmt.operating_income is None
        assert stmt.ebitda is None
        assert stmt.total_assets is None
        assert stmt.total_liabilities is None
        assert stmt.total_equity is None
        assert stmt.cash_and_equivalents is None
        assert stmt.total_debt is None
        assert stmt.operating_cash_flow is None
        assert stmt.free_cash_flow is None
        assert stmt.basic_eps is None
        assert stmt.diluted_eps is None
        assert stmt.book_value_per_share is None

    def test_safe_get_int_method(self, sample_financial_statement):
        """Test _safe_get_int helper method"""
        stmt = sample_financial_statement

        # Test with valid integer
        result = stmt._safe_get_int("Total Revenue")
        assert result == 89498000000

        # Test with missing key
        result = stmt._safe_get_int("Non Existent Key")
        assert result is None

        # Test with invalid value
        stmt.data["Invalid Value"] = "not a number"
        result = stmt._safe_get_int("Invalid Value")
        assert result is None

    def test_safe_get_decimal_method(self, sample_financial_statement):
        """Test _safe_get_decimal helper method"""
        stmt = sample_financial_statement

        # Test with valid decimal
        result = stmt._safe_get_decimal("Basic EPS")
        assert result == Decimal("1.46")

        # Test with missing key
        result = stmt._safe_get_decimal("Non Existent Key")
        assert result is None

        # Test with invalid value
        stmt.data["Invalid Value"] = "not a number"
        result = stmt._safe_get_decimal("Invalid Value")
        assert result is None

    def test_get_line_item_method(self, sample_financial_statement):
        """Test get_line_item method"""
        stmt = sample_financial_statement

        # Test with existing key
        result = stmt.get_line_item("Total Revenue")
        assert result == 89498000000

        # Test with missing key
        result = stmt.get_line_item("Non Existent Key")
        assert result is None

    def test_get_formatted_line_item_currency(self, sample_financial_statement):
        """Test get_formatted_line_item with currency format"""
        stmt = sample_financial_statement

        # Test positive value
        result = stmt.get_formatted_line_item("Total Revenue", "currency")
        assert result == "$89,498,000,000"

        # Test negative value
        stmt.data["Loss"] = -1000000
        result = stmt.get_formatted_line_item("Loss", "currency")
        assert result == "-$1,000,000"

        # Test zero value
        stmt.data["Zero"] = 0
        result = stmt.get_formatted_line_item("Zero", "currency")
        assert result == "$0"

    def test_get_formatted_line_item_percentage(self, sample_financial_statement):
        """Test get_formatted_line_item with percentage format"""
        stmt = sample_financial_statement

        # Test percentage value
        stmt.data["Margin"] = 0.25
        result = stmt.get_formatted_line_item("Margin", "percentage")
        assert result == "25.00%"

        # Test negative percentage
        stmt.data["Negative Margin"] = -0.05
        result = stmt.get_formatted_line_item("Negative Margin", "percentage")
        assert result == "-5.00%"

    def test_get_formatted_line_item_number(self, sample_financial_statement):
        """Test get_formatted_line_item with number format"""
        stmt = sample_financial_statement

        # Test number value
        result = stmt.get_formatted_line_item("Basic EPS", "number")
        assert result == "1.46"

        # Test large number
        result = stmt.get_formatted_line_item("Total Revenue", "number")
        assert result == "89,498,000,000"

    def test_get_formatted_line_item_none_value(self, sample_financial_statement):
        """Test get_formatted_line_item with None value"""
        stmt = sample_financial_statement

        # Test with missing key
        result = stmt.get_formatted_line_item("Non Existent Key", "currency")
        assert result == "N/A"

    def test_period_display_property(self, sample_financial_statement):
        """Test period_display property"""
        stmt = sample_financial_statement

        # Test quarterly display
        result = stmt.period_display
        assert "Q4 2024" in result

        # Test annual display
        stmt.period_type = "annual"
        stmt.fiscal_quarter = None
        result = stmt.period_display
        assert "2024" in result
        assert "Q" not in result

    def test_statement_display_property(self, sample_financial_statement):
        """Test statement_display property"""
        stmt = sample_financial_statement

        # Test income statement
        result = stmt.statement_display
        assert result == "Income Statement"

        # Test balance sheet
        stmt.statement_type = "balance_sheet"
        result = stmt.statement_display
        assert result == "Balance Sheet"

        # Test cash flow
        stmt.statement_type = "cash_flow"
        result = stmt.statement_display
        assert result == "Cash Flow Statement"

        # Test unknown type
        stmt.statement_type = "unknown"
        result = stmt.statement_display
        assert result == "Unknown"

    def test_to_dict_method(self, sample_financial_statement):
        """Test to_dict method"""
        stmt = sample_financial_statement
        stmt.populate_common_metrics()

        result = stmt.to_dict()

        # Test required fields
        assert "symbol" in result
        assert "period_end" in result
        assert "statement_type" in result
        assert "period_type" in result
        assert "fiscal_year" in result
        assert "fiscal_quarter" in result
        assert "data" in result
        assert "data_source" in result

        # Test common metrics fields
        assert "total_revenue" in result
        assert "net_income" in result
        assert "basic_eps" in result

        # Test data types
        assert isinstance(result["symbol"], str)
        assert isinstance(result["period_end"], str)  # ISO format
        assert isinstance(result["fiscal_year"], int)
        assert isinstance(result["fiscal_quarter"], int)
        assert isinstance(result["data"], dict)

    def test_repr_method(self, sample_financial_statement):
        """Test __repr__ method"""
        stmt = sample_financial_statement
        result = repr(stmt)

        assert "FinancialStatement" in result
        assert "AAPL" in result
        assert "income" in result
        assert "Q4" in result  # Check for period display instead of period_type

    def test_model_with_different_statement_types(self):
        """Test model with different statement types"""
        statement_types = ["income", "balance_sheet", "cash_flow"]

        for stmt_type in statement_types:
            stmt = FinancialStatement(
                symbol="TEST",
                period_end=date(2024, 9, 30),
                statement_type=stmt_type,
                period_type="quarterly",
                data={"Test Value": 1000000},
            )

            assert stmt.statement_type == stmt_type
            assert stmt.period_type == "quarterly"

    def test_model_with_different_period_types(self):
        """Test model with different period types"""
        period_types = ["annual", "quarterly", "ttm"]

        for period_type in period_types:
            stmt = FinancialStatement(
                symbol="TEST",
                period_end=date(2024, 9, 30),
                statement_type="income",
                period_type=period_type,
                data={"Test Value": 1000000},
            )

            assert stmt.period_type == period_type

    def test_model_with_none_values(self):
        """Test model with None values"""
        stmt = FinancialStatement(
            symbol="TEST",
            period_end=date(2024, 9, 30),
            statement_type="income",
            period_type="quarterly",
            fiscal_year=None,
            fiscal_quarter=None,
            data={},
        )

        assert stmt.fiscal_year is None
        assert stmt.fiscal_quarter is None
        assert stmt.data == {}

    def test_model_created_at_updated_at(self, sample_financial_statement):
        """Test created_at and updated_at timestamps"""
        stmt = sample_financial_statement

        # These should be set automatically by the database when saved
        # For unit tests, they might be None until saved to database
        # We'll test that they can be set manually
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        stmt.created_at = now
        stmt.updated_at = now

        assert stmt.created_at is not None
        assert stmt.updated_at is not None
        assert isinstance(stmt.created_at, datetime)
        assert isinstance(stmt.updated_at, datetime)

    def test_model_data_validation(self):
        """Test model data validation"""
        # Test with valid data
        stmt = FinancialStatement(
            symbol="TEST",
            period_end=date(2024, 9, 30),
            statement_type="income",
            period_type="quarterly",
            data={"Valid": 1000},
        )

        assert stmt.symbol == "TEST"
        assert stmt.data["Valid"] == 1000

    def test_model_edge_cases(self):
        """Test model edge cases"""
        # Test with very large numbers
        stmt = FinancialStatement(
            symbol="TEST",
            period_end=date(2024, 9, 30),
            statement_type="income",
            period_type="quarterly",
            data={"Large Number": 999999999999999},
        )

        stmt.populate_common_metrics()
        assert stmt._safe_get_int("Large Number") == 999999999999999

    def test_model_with_special_characters(self):
        """Test model with special characters in data"""
        stmt = FinancialStatement(
            symbol="TEST",
            period_end=date(2024, 9, 30),
            statement_type="income",
            period_type="quarterly",
            data={
                "Revenue (USD)": 1000000,
                "Cost of Goods Sold": 500000,
                "Net Income (After Tax)": 200000,
            },
        )

        stmt.populate_common_metrics()
        assert stmt._safe_get_int("Revenue (USD)") == 1000000
        assert stmt._safe_get_int("Cost of Goods Sold") == 500000
        assert stmt._safe_get_int("Net Income (After Tax)") == 200000
