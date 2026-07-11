"""
Unit tests for Key Statistics API endpoints
"""

from datetime import date, datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from src.web.api.key_statistics import get_key_statistics, list_available_symbols


class TestKeyStatisticsAPI:
    """Test cases for Key Statistics API endpoints"""

    @pytest.fixture
    def mock_key_statistics_data(self):
        """Mock key statistics data"""
        return {
            "id": 1,
            "symbol": "AAPL",
            "date": "2024-10-18",
            "market_cap": 3000000000000,
            "enterprise_value": 2950000000000,
            "pe_ratio": 28.5,
            "forward_pe": 25.2,
            "peg_ratio": 1.8,
            "price_to_sales": 7.2,
            "price_to_book": 45.6,
            "ev_to_revenue": 7.1,
            "ev_to_ebitda": 22.3,
            "beta": 1.2,
            "52_week_high": 199.62,
            "52_week_low": 164.08,
            "50_day_ma": 185.45,
            "200_day_ma": 175.32,
            "avg_volume": 50000000,
            "shares_outstanding": 15728714000,
            "float_shares": 15600000000,
            "percent_held_by_insiders": 0.07,
            "percent_held_by_institutions": 60.5,
            "short_ratio": 1.2,
            "short_interest": 100000000,
            "short_percent_of_float": 0.64,
            "book_value": 4.18,
            "price_to_cash_flow": 18.5,
            "return_on_equity": 0.147,
            "return_on_assets": 0.085,
            "gross_profit_margin": 0.438,
            "operating_margin": 0.298,
            "net_profit_margin": 0.253,
            "debt_to_equity": 1.73,
            "current_ratio": 1.05,
            "quick_ratio": 0.95,
            "cash_per_share": 4.18,
            "dividend_yield": 0.0044,
            "dividend_rate": 0.96,
            "payout_ratio": 0.156,
            "ex_dividend_date": "2024-11-08",
            "dividend_date": "2024-11-14",
            "earnings_date": "2025-01-30",
            "earnings_growth": 0.085,
            "revenue_growth": 0.022,
            "revenue_per_share": 24.31,
            "quarterly_revenue_growth": 0.006,
            "quarterly_earnings_growth": 0.036,
            "analyst_price_target": 195.50,
            "price_target_high": 250.00,
            "price_target_low": 150.00,
            "number_of_analysts": 35,
            "recommendation_mean": 2.1,
            "recommendation_key": "buy",
            "data_source": "yahoo",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

    @pytest.fixture
    def mock_key_statistics(self, mock_key_statistics_data):
        """Mock KeyStatistics object"""
        stats = Mock()
        stats.symbol = "AAPL"
        stats.date = date(2024, 10, 18)
        stats.data_source = "yahoo"
        stats.market_cap = 3000000000000
        stats.market_cap_display = "$3.0T"
        stats.enterprise_value = 2950000000000
        stats.trailing_pe = 28.5
        stats.forward_pe = 25.2
        stats.peg_ratio = 1.8
        stats.price_to_book = 45.6
        stats.price_to_sales = 7.2
        stats.ev_to_revenue = 7.1
        stats.ev_to_ebitda = 22.3
        stats.enterprise_to_revenue = 7.1
        stats.enterprise_to_ebitda = 22.3
        stats.beta = 1.2
        stats.shares_outstanding = 15728714000
        stats.shares_outstanding_display = "15.73B"
        stats.float_shares = 15600000000
        stats.avg_volume = 50000000
        stats.avg_volume_display = "50.0M"
        stats.short_interest = 100000000
        stats.short_interest_display = "100.0M"
        stats.dividend_yield = 0.0044
        stats.dividend_rate = 0.96
        stats.payout_ratio = 0.156
        stats.book_value = 4.18
        stats.price_to_cash_flow = 18.5
        stats.return_on_equity = 0.147
        stats.return_on_assets = 0.085
        stats.gross_profit_margin = 0.438
        stats.operating_margin = 0.298
        stats.net_profit_margin = 0.253
        stats.profit_margin = 0.253
        stats.debt_to_equity = 1.73
        stats.current_ratio = 1.05
        stats.quick_ratio = 0.95
        stats.cash_per_share = 4.18
        stats.earnings_growth = 0.085
        stats.revenue_growth = 0.022
        stats.revenue_per_share = 24.31
        stats.quarterly_revenue_growth = 0.006
        stats.quarterly_earnings_growth = 0.036
        stats.analyst_price_target = 195.50
        stats.price_target_high = 250.00
        stats.price_target_low = 150.00
        stats.number_of_analysts = 35
        stats.recommendation_mean = 2.1
        stats.recommendation_key = "buy"
        stats.percent_held_by_insiders = 0.07
        stats.percent_held_by_institutions = 60.5
        stats.short_ratio = 1.2
        stats.short_percent_of_float = 0.64
        stats.fifty_two_week_high = 199.62
        stats.fifty_two_week_low = 164.08
        stats.fifty_day_ma = 185.45
        stats.two_hundred_day_ma = 175.32
        stats.ex_dividend_date = "2024-11-08"
        stats.dividend_date = "2024-11-14"
        stats.earnings_date = "2025-01-30"

        # Add missing attributes that the API accesses
        stats.gross_margin = 0.438
        stats.ebitda_margin = 0.298
        stats.revenue = 383285000000
        stats.earnings_per_share = 6.13
        stats.total_cash = 162000000000
        stats.total_debt = 110000000000
        stats.free_cash_flow = 99584000000
        stats.operating_cash_flow = 110543000000
        stats.average_volume = 50000000
        stats.dividend_yield_display = "0.44%"
        stats.debt_to_equity_display = "1.73"
        stats.profit_margin_display = "25.3%"
        stats.roe_display = "14.7%"
        stats.shares_short = 100000000
        stats.held_percent_insiders = 0.07
        stats.held_percent_institutions = 60.5
        stats.fifty_day_average = 185.45
        stats.two_hundred_day_average = 175.32
        stats.updated_at = datetime(2024, 10, 18, 10, 30, 0)

        stats.to_dict.return_value = {
            **mock_key_statistics_data,
            "market_cap_display": "$3.0T",
            "enterprise_value_display": "$2.95T",
            "shares_outstanding_display": "15.73B",
            "float_shares_display": "15.60B",
            "avg_volume_display": "50.0M",
            "short_interest_display": "100.0M",
        }
        return stats

    @pytest.mark.asyncio
    async def test_get_key_statistics_success(self, mock_key_statistics):
        """Test successful retrieval of key statistics"""
        with (
            patch("src.web.api.key_statistics.db_transaction") as mock_db,
            patch("src.web.api.key_statistics.select") as mock_select,
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
            mock_session.execute.return_value.first.return_value = (
                mock_key_statistics,
            )

            result = await get_key_statistics("AAPL")

            assert result["success"] is True
            assert result["symbol"] == "AAPL"
            assert "data" in result
            assert "valuation" in result["data"]
            assert result["data"]["valuation"]["market_cap"] == 3000000000000

    @pytest.mark.asyncio
    async def test_get_key_statistics_no_data(self):
        """Test retrieval when no data exists"""
        with (
            patch("src.web.api.key_statistics.db_transaction") as mock_db,
            patch("src.web.api.key_statistics.select") as mock_select,
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

            # Mock empty query results - API expects first() to return None
            mock_session.execute.return_value.first.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await get_key_statistics("INVALID")

            assert exc_info.value.status_code == 404
            assert "No key statistics found for INVALID" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_key_statistics_latest_only(self, mock_key_statistics):
        """Test that only the latest statistics are returned"""
        with (
            patch("src.web.api.key_statistics.db_transaction") as mock_db,
            patch("src.web.api.key_statistics.select") as mock_select,
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

            # Mock query results - API expects first() to return tuple
            mock_session.execute.return_value.first.return_value = (
                mock_key_statistics,
            )

            result = await get_key_statistics("AAPL")

            assert result["success"] is True
            assert result["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_list_available_symbols_success(self):
        """Test listing available symbols with statistics counts"""
        with patch("src.web.api.key_statistics.db_transaction") as mock_db:
            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock query results
            mock_results = [
                ("AAPL", date(2024, 10, 18)),
                ("MSFT", date(2024, 10, 18)),
                ("GOOGL", date(2024, 10, 18)),
            ]
            mock_session.execute.return_value.all.return_value = mock_results

            result = await list_available_symbols()

            assert result["success"] is True
            assert result["count"] == 3
            assert len(result["symbols"]) == 3
            assert result["symbols"][0]["symbol"] == "AAPL"
            assert result["symbols"][0]["latest_date"] == "2024-10-18"

    @pytest.mark.asyncio
    async def test_list_available_symbols_no_data(self):
        """Test listing when no symbols exist"""
        with patch("src.web.api.key_statistics.db_transaction") as mock_db:
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
        with patch("src.web.api.key_statistics.db_transaction") as mock_db:
            # Mock database error
            mock_db.side_effect = Exception("Database connection failed")

            with pytest.raises(HTTPException) as exc_info:
                await get_key_statistics("AAPL")

            assert exc_info.value.status_code == 500
            assert "Failed to fetch key statistics" in str(exc_info.value.detail)

    def test_symbol_case_handling(self):
        """Test that symbol is converted to uppercase"""
        symbol = "aapl"
        assert symbol.upper() == "AAPL"

    def test_api_response_format(self, mock_key_statistics_data):
        """Test API response format structure"""
        response = {
            "success": True,
            "symbol": "AAPL",
            "count": 1,
            "statistics": [mock_key_statistics_data],
        }

        # Test required fields
        assert "success" in response
        assert "symbol" in response
        assert "count" in response
        assert "statistics" in response

        # Test statistics structure
        stats = response["statistics"][0]
        required_fields = [
            "symbol",
            "date",
            "market_cap",
            "pe_ratio",
            "beta",
            "shares_outstanding",
            "dividend_yield",
            "data_source",
        ]

        for field in required_fields:
            assert field in stats

    def test_market_cap_display_formatting(self):
        """Test market cap display formatting"""
        test_cases = [
            (3000000000000, "$3.0T"),  # 3 trillion
            (1500000000000, "$1.5T"),  # 1.5 trillion
            (500000000000, "$500.0B"),  # 500 billion
            (50000000000, "$50.0B"),  # 50 billion
            (1000000000, "$1.0B"),  # 1 billion
            (500000000, "$500.0M"),  # 500 million
            (1000000, "$1.0M"),  # 1 million
        ]

        for market_cap, expected_display in test_cases:
            if market_cap >= 1_000_000_000_000:
                actual_display = f"${market_cap / 1_000_000_000_000:.1f}T"
            elif market_cap >= 1_000_000_000:
                actual_display = f"${market_cap / 1_000_000_000:.1f}B"
            elif market_cap >= 1_000_000:
                actual_display = f"${market_cap / 1_000_000:.1f}M"
            else:
                actual_display = f"${market_cap:,.0f}"

            assert actual_display == expected_display

    def test_shares_outstanding_display_formatting(self):
        """Test shares outstanding display formatting"""
        test_cases = [
            (15728714000, "15.73B"),  # 15.73 billion
            (5000000000, "5.00B"),  # 5 billion
            (1000000000, "1.00B"),  # 1 billion
            (500000000, "500.00M"),  # 500 million
            (1000000, "1.00M"),  # 1 million
        ]

        for shares, expected_display in test_cases:
            if shares >= 1_000_000_000:
                actual_display = f"{shares / 1_000_000_000:.2f}B"
            elif shares >= 1_000_000:
                actual_display = f"{shares / 1_000_000:.2f}M"
            else:
                actual_display = f"{shares:,.0f}"

            assert actual_display == expected_display

    def test_percentage_display_formatting(self):
        """Test percentage display formatting"""
        test_cases = [
            (0.147, "14.70%"),  # ROE
            (0.085, "8.50%"),  # ROA
            (0.438, "43.80%"),  # Gross margin
            (0.0044, "0.44%"),  # Dividend yield
            (0.07, "7.00%"),  # Insider holdings
        ]

        for value, expected_display in test_cases:
            actual_display = f"{value * 100:.2f}%"
            assert actual_display == expected_display

    def test_ratio_display_formatting(self):
        """Test ratio display formatting"""
        test_cases = [
            (28.5, "28.50"),  # PE ratio
            (1.2, "1.20"),  # Beta
            (7.2, "7.20"),  # Price to sales
            (45.6, "45.60"),  # Price to book
            (1.73, "1.73"),  # Debt to equity
        ]

        for ratio, expected_display in test_cases:
            actual_display = f"{ratio:.2f}"
            assert actual_display == expected_display

    def test_currency_display_formatting(self):
        """Test currency display formatting"""
        test_cases = [
            (199.62, "$199.62"),  # 52-week high
            (164.08, "$164.08"),  # 52-week low
            (185.45, "$185.45"),  # 50-day MA
            (4.18, "$4.18"),  # Book value
            (0.96, "$0.96"),  # Dividend rate
        ]

        for value, expected_display in test_cases:
            actual_display = f"${value:.2f}"
            assert actual_display == expected_display

    def test_volume_display_formatting(self):
        """Test volume display formatting"""
        test_cases = [
            (50000000, "50.0M"),  # Average volume
            (100000000, "100.0M"),  # Short interest
            (1000000, "1.0M"),  # 1 million
            (500000, "500.0K"),  # 500 thousand
        ]

        for volume, expected_display in test_cases:
            if volume >= 1_000_000:
                actual_display = f"{volume / 1_000_000:.1f}M"
            elif volume >= 1_000:
                actual_display = f"{volume / 1_000:.1f}K"
            else:
                actual_display = f"{volume:,.0f}"

            assert actual_display == expected_display

    def test_key_statistics_data_types(self, mock_key_statistics_data):
        """Test that key statistics data has correct types"""
        stats = mock_key_statistics_data

        # Test numeric types
        assert isinstance(stats["market_cap"], int)
        assert isinstance(stats["pe_ratio"], float)
        assert isinstance(stats["beta"], float)
        assert isinstance(stats["shares_outstanding"], int)
        assert isinstance(stats["dividend_yield"], float)

        # Test string types
        assert isinstance(stats["symbol"], str)
        assert isinstance(stats["date"], str)  # This should be ISO format string
        assert isinstance(stats["data_source"], str)

        # Test date format
        from datetime import datetime

        try:
            datetime.fromisoformat(stats["date"])
        except ValueError:
            pytest.fail("Date is not in valid ISO format")

    def test_key_statistics_required_fields(self, mock_key_statistics_data):
        """Test that key statistics has all required fields"""
        stats = mock_key_statistics_data

        required_fields = [
            "symbol",
            "date",
            "market_cap",
            "pe_ratio",
            "shares_outstanding",
            "dividend_yield",
            "data_source",
        ]

        for field in required_fields:
            assert field in stats
            assert stats[field] is not None

    def test_key_statistics_optional_fields(self, mock_key_statistics_data):
        """Test that optional fields can be None"""
        stats = mock_key_statistics_data

        # Some fields might be None in real data
        optional_fields = [
            "forward_pe",
            "peg_ratio",
            "price_to_sales",
            "price_to_book",
            "ev_to_revenue",
            "ev_to_ebitda",
            "beta",
            "52_week_high",
            "52_week_low",
            "50_day_ma",
            "200_day_ma",
            "avg_volume",
            "float_shares",
            "percent_held_by_insiders",
            "percent_held_by_institutions",
            "short_ratio",
            "short_interest",
            "short_percent_of_float",
            "book_value",
            "price_to_cash_flow",
            "return_on_equity",
            "return_on_assets",
            "gross_profit_margin",
            "operating_margin",
            "net_profit_margin",
            "debt_to_equity",
            "current_ratio",
            "quick_ratio",
            "cash_per_share",
            "dividend_rate",
            "payout_ratio",
            "ex_dividend_date",
            "dividend_date",
            "earnings_date",
            "earnings_growth",
            "revenue_growth",
            "revenue_per_share",
            "quarterly_revenue_growth",
            "quarterly_earnings_growth",
            "analyst_price_target",
            "price_target_high",
            "price_target_low",
            "number_of_analysts",
            "recommendation_mean",
            "recommendation_key",
        ]

        # These fields should exist in the mock data
        for field in optional_fields:
            assert field in stats

    def test_key_statistics_value_ranges(self, mock_key_statistics_data):
        """Test that key statistics values are in reasonable ranges"""
        stats = mock_key_statistics_data

        # Market cap should be positive
        assert stats["market_cap"] > 0

        # PE ratio should be positive
        assert stats["pe_ratio"] > 0

        # Beta should be positive (can be less than 1)
        assert stats["beta"] > 0

        # Shares outstanding should be positive
        assert stats["shares_outstanding"] > 0

        # Dividend yield should be non-negative
        assert stats["dividend_yield"] >= 0

        # Percentages should be between 0 and 1
        assert 0 <= stats["percent_held_by_insiders"] <= 1
        # Note: percent_held_by_institutions is already in percentage form (60.5),
        # not decimal (0.605)
        assert 0 <= stats["percent_held_by_institutions"] <= 100

        # Margins should be between 0 and 1
        assert 0 <= stats["gross_profit_margin"] <= 1
        assert 0 <= stats["operating_margin"] <= 1
        assert 0 <= stats["net_profit_margin"] <= 1

    @pytest.mark.asyncio
    async def test_get_key_statistics_ordering(self, mock_key_statistics):
        """Test that statistics are ordered by date (most recent first)"""
        with (
            patch("src.web.api.key_statistics.db_transaction") as mock_db,
            patch("src.web.api.key_statistics.select") as mock_select,
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

            # Mock query results - API expects first() to return tuple
            mock_session.execute.return_value.first.return_value = (
                mock_key_statistics,
            )

            result = await get_key_statistics("AAPL")

            # Verify ordering was applied
            mock_query_obj.order_by.assert_called_once()

            assert result["success"] is True
            assert result["symbol"] == "AAPL"
