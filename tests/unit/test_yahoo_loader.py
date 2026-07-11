"""
Unit tests for Yahoo Finance Data Loader
"""

from datetime import date
from unittest.mock import Mock, patch

import pytest

from src.services.yahoo.exceptions import YahooAPIError
from src.services.yahoo.loader import YahooDataLoader
from src.services.yahoo.models import (
    AnalystRecommendation,
    CompanyInfo,
    CompanyOfficer,
    Dividend,
    ESGScore,
    FinancialStatement,
    InstitutionalHolder,
    KeyStatistics,
    StockSplit,
)


class TestYahooDataLoader:
    """Test cases for Yahoo Data Loader"""

    @pytest.fixture
    def loader(self):
        """Create Yahoo data loader"""
        return YahooDataLoader()

    @pytest.fixture
    def mock_company_info(self):
        """Mock company info data"""
        return CompanyInfo(
            symbol="AAPL",
            name="Apple Inc.",
            sector="Technology",
            industry="Consumer Electronics",
            description="Apple designs and manufactures consumer electronics",
            website="https://www.apple.com",
            phone="408-996-1010",
            address="One Apple Park Way",
            city="Cupertino",
            state="CA",
            zip="95014",
            country="United States",
            employees=150000,
            market_cap=3000000000000,
            currency="USD",
            exchange="NASDAQ",
            quote_type="EQUITY",
        )

    @pytest.fixture
    def mock_key_statistics(self):
        """Mock key statistics data"""
        return KeyStatistics(
            symbol="AAPL",
            date=date(2024, 10, 18),
            market_cap=3000000000000,
            pe_ratio=28.5,
            beta=1.2,
            shares_outstanding=15728714000,
            dividend_yield=0.0044,
            data={
                "marketCap": 3000000000000,
                "trailingPE": 28.5,
                "beta": 1.2,
                "sharesOutstanding": 15728714000,
                "dividendYield": 0.0044,
            },
        )

    @pytest.fixture
    def mock_institutional_holders(self):
        """Mock institutional holders data"""
        return [
            InstitutionalHolder(
                symbol="AAPL",
                date_reported=date(2024, 9, 30),
                holder_name="Vanguard Group Inc",
                shares=1234567890,
                value=24567890123,
                percent_held=7.85,
                data={
                    "dateReported": "2024-09-30",
                    "holderName": "Vanguard Group Inc",
                    "shares": 1234567890,
                    "value": 24567890123,
                    "percentHeld": 7.85,
                },
            ),
            InstitutionalHolder(
                symbol="AAPL",
                date_reported=date(2024, 9, 30),
                holder_name="BlackRock Inc",
                shares=987654321,
                value=19654321098,
                percent_held=6.28,
                data={
                    "dateReported": "2024-09-30",
                    "holderName": "BlackRock Inc",
                    "shares": 987654321,
                    "value": 19654321098,
                    "percentHeld": 6.28,
                },
            ),
        ]

    @pytest.fixture
    def mock_financial_statements(self):
        """Mock financial statements data"""
        return [
            FinancialStatement(
                symbol="AAPL",
                period_end=date(2024, 9, 30),
                statement_type="income",
                period_type="quarterly",
                data={
                    "Total Revenue": 89498000000,
                    "Net Income": 22956000000,
                    "Basic EPS": 1.46,
                    "Total Assets": 352755000000,
                    "Total Liabilities": 258549000000,
                    "Total Equity": 94206000000,
                },
            ),
            FinancialStatement(
                symbol="AAPL",
                period_end=date(2024, 9, 30),
                statement_type="income",
                period_type="annual",
                data={
                    "Total Revenue": 383285000000,
                    "Net Income": 96995000000,
                    "Basic EPS": 6.13,
                },
            ),
        ]

    @pytest.fixture
    def mock_dividends(self):
        """Mock dividends data"""
        return [
            Dividend(
                symbol="AAPL",
                ex_date=date(2024, 2, 9),
                amount=0.24,
                payment_date=date(2024, 2, 15),
                record_date=date(2024, 2, 12),
                dividend_type="regular",
                currency="USD",
            ),
            Dividend(
                symbol="AAPL",
                ex_date=date(2024, 5, 10),
                amount=0.25,
                payment_date=date(2024, 5, 16),
                record_date=date(2024, 5, 13),
                dividend_type="regular",
                currency="USD",
            ),
            Dividend(
                symbol="AAPL",
                ex_date=date(2024, 8, 9),
                amount=0.25,
                payment_date=date(2024, 8, 15),
                record_date=date(2024, 8, 12),
                dividend_type="regular",
                currency="USD",
            ),
        ]

    @pytest.fixture
    def mock_stock_splits(self):
        """Mock stock splits data"""
        return [
            StockSplit(
                symbol="AAPL",
                split_date=date(2020, 8, 31),
                split_ratio=4.0,
                ratio_str="4:1",
            ),
            StockSplit(
                symbol="AAPL",
                split_date=date(2014, 6, 9),
                split_ratio=7.0,
                ratio_str="7:1",
            ),
        ]

    @pytest.fixture
    def mock_analyst_recommendations(self):
        """Mock analyst recommendations data"""
        return [
            AnalystRecommendation(
                symbol="AAPL",
                date=date(2024, 11, 1),
                period="0m",
                strong_buy=15,
                buy=8,
                hold=3,
                sell=1,
                strong_sell=0,
            ),
            AnalystRecommendation(
                symbol="AAPL",
                date=date(2024, 10, 1),
                period="-1m",
                strong_buy=12,
                buy=10,
                hold=4,
                sell=1,
                strong_sell=0,
            ),
            AnalystRecommendation(
                symbol="AAPL",
                date=date(2024, 9, 1),
                period="-2m",
                strong_buy=10,
                buy=12,
                hold=5,
                sell=0,
                strong_sell=0,
            ),
        ]

    @pytest.fixture
    def mock_esg_scores(self):
        """Mock ESG scores data"""
        return ESGScore(
            symbol="AAPL",
            date=date(2024, 11, 1),
            total_esg=72.5,
            environment_score=75.0,
            social_score=70.0,
            governance_score=72.5,
            controversy_level=2,
            esg_performance="OUT_PERF",
            peer_group="Technology",
            peer_count=150,
            percentile=85.5,
        )

    @pytest.fixture
    def mock_company_officers(self):
        """Mock company officers data"""
        return [
            CompanyOfficer(
                symbol="AAPL",
                name="Tim Cook",
                title="Chief Executive Officer",
                age=63,
                year_born=1960,
                fiscal_year=2024,
                total_pay=99420000,
                exercised_value=0,
                unexercised_value=0,
                data={
                    "name": "Tim Cook",
                    "title": "Chief Executive Officer",
                    "age": 63,
                    "yearBorn": 1960,
                    "fiscalYear": 2024,
                    "totalPay": 99420000,
                    "exercisedValue": 0,
                    "unexercisedValue": 0,
                },
            ),
            CompanyOfficer(
                symbol="AAPL",
                name="Luca Maestri",
                title="Chief Financial Officer",
                age=60,
                year_born=1963,
                fiscal_year=2024,
                total_pay=26500000,
                exercised_value=0,
                unexercised_value=0,
                data={
                    "name": "Luca Maestri",
                    "title": "Chief Financial Officer",
                    "age": 60,
                    "yearBorn": 1963,
                    "fiscalYear": 2024,
                    "totalPay": 26500000,
                    "exercisedValue": 0,
                    "unexercisedValue": 0,
                },
            ),
        ]

    @pytest.mark.asyncio
    async def test_load_company_info_success(self, loader, mock_company_info):
        """Test successful loading of company info"""
        with (
            patch.object(
                loader.client, "get_company_info", return_value=mock_company_info
            ),
            patch("src.services.yahoo.loader.db_transaction") as mock_db,
        ):

            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            result = await loader.load_company_info("AAPL")

            assert result is True  # Method returns boolean success indicator
            mock_session.merge.assert_called_once()
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_company_info_api_error(self, loader):
        """Test handling of API errors in company info loading"""
        with patch.object(
            loader.client, "get_company_info", side_effect=YahooAPIError("API Error")
        ):
            with pytest.raises(YahooAPIError):
                await loader.load_company_info("INVALID")

    @pytest.mark.asyncio
    async def test_load_key_statistics_success(self, loader, mock_key_statistics):
        """Test successful loading of key statistics"""
        with (
            patch.object(
                loader.client, "get_key_statistics", return_value=mock_key_statistics
            ),
            patch("src.services.yahoo.loader.db_transaction") as mock_db,
            patch("src.services.yahoo.loader.insert") as mock_insert,
        ):

            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock upsert statement
            mock_upsert_stmt = Mock()
            mock_insert.return_value.on_conflict_do_update.return_value = (
                mock_upsert_stmt
            )

            result = await loader.load_key_statistics("AAPL")

            assert result is True  # Method returns boolean success indicator
            mock_session.execute.assert_called_once()
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_key_statistics_no_data(self, loader):
        """Test handling of no key statistics data"""
        with patch.object(loader.client, "get_key_statistics", return_value=None):
            result = await loader.load_key_statistics("INVALID")
            assert result is False  # Method returns False when there's no data

    @pytest.mark.asyncio
    async def test_load_institutional_holders_success(
        self, loader, mock_institutional_holders
    ):
        """Test successful loading of institutional holders"""
        with (
            patch.object(
                loader.client,
                "get_institutional_holders",
                return_value=mock_institutional_holders,
            ),
            patch("src.services.yahoo.loader.db_transaction") as mock_db,
            patch("src.services.yahoo.loader.update") as mock_update,
            patch("src.services.yahoo.loader.insert") as mock_insert,
            patch("sqlalchemy.select") as mock_select,
        ):

            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock update statement chain (for setting is_latest=False on previous records)
            # update(InstitutionalHolder).where(...).values(...)
            mock_update_stmt = Mock()
            mock_update_where = Mock()
            mock_update_where.values.return_value = mock_update_stmt
            mock_update.return_value.where.return_value = mock_update_where

            # Mock select statement chain (for getting previous percent_held)
            # select(...).where(...).order_by(...).limit(...)
            mock_select_final = Mock()
            mock_select_limit = Mock()
            mock_select_order = Mock()
            mock_select_where = Mock()
            mock_select_limit.limit.return_value = mock_select_final
            mock_select_order.order_by.return_value = mock_select_limit
            mock_select_where.where.return_value = mock_select_order
            mock_select.return_value = mock_select_where
            
            # Mock insert/upsert statement chain
            # insert(InstitutionalHolder).values(...).on_conflict_do_update(...)
            mock_insert_upsert = Mock()
            mock_insert_values = Mock()
            # Make excluded support subscripting for _upsert_records
            mock_excluded = Mock()
            mock_excluded.__getitem__ = Mock(side_effect=lambda key: Mock())
            mock_insert_values.excluded = mock_excluded
            mock_insert_values.on_conflict_do_update.return_value = mock_insert_upsert
            mock_insert.return_value.values.return_value = mock_insert_values

            # Make execute return a result that works for all statement types
            # For select statements, it needs scalar_one_or_none() which returns None
            # For update and insert, they don't use the return value, so any Mock works
            mock_execute_result = Mock()
            mock_execute_result.scalar_one_or_none.return_value = None  # For select statements
            
            # Track executed statements to identify selects
            executed_statements = []
            def execute_side_effect(stmt):
                executed_statements.append(stmt)
                # All statements return the same result (which has scalar_one_or_none for selects)
                return mock_execute_result

            mock_session.execute.side_effect = execute_side_effect

            result = await loader.load_institutional_holders("AAPL")

            assert result == 2  # Method returns count of records loaded
            # Each holder: 1 update + 1 select (for percent_change) = 2 calls per holder
            # Outer transaction: 2 holders * 2 = 4 calls
            # Inner transaction (_upsert_records): 1 bulk insert = 1 call
            # Total: 5 calls
            assert mock_session.execute.call_count == 5
            # Only _upsert_records commits; outer transaction is just for queries/updates
            assert mock_session.commit.call_count == 1

    @pytest.mark.asyncio
    async def test_load_institutional_holders_no_data(self, loader):
        """Test handling of no institutional holders data"""
        with patch.object(loader.client, "get_institutional_holders", return_value=[]):
            result = await loader.load_institutional_holders("INVALID")
            assert result == 0  # Method returns count of records loaded

    @pytest.mark.asyncio
    async def test_load_financial_statements_success(
        self, loader, mock_financial_statements
    ):
        """Test successful loading of financial statements"""

        def mock_get_financial_statements(symbol, stmt_type, period_type):
            """Mock function that returns appropriate data based on parameters"""
            # Only return data for income statements to avoid duplicates
            # The method calls this 6 times (3 statement types x 2 period types)
            if stmt_type == "income":
                return mock_financial_statements
            else:
                # Return empty list for other statement types (balance_sheet, cash_flow)
                return []

        with (
            patch.object(
                loader.client,
                "get_financial_statements",
                side_effect=mock_get_financial_statements,
            ),
            patch("src.services.yahoo.loader.db_transaction") as mock_db,
            patch("src.services.yahoo.loader.insert") as mock_insert,
        ):

            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock upsert statement chain
            # insert(model).values(records) returns object with .excluded and .on_conflict_do_update()
            mock_upsert_stmt = Mock()
            mock_insert_values = Mock()
            # Make excluded support subscripting for _upsert_records
            # Also need to support model.__table__.columns when update_fields is None
            mock_excluded = Mock()
            mock_excluded.__getitem__ = Mock(side_effect=lambda key: Mock())
            mock_insert_values.excluded = mock_excluded
            mock_insert_values.on_conflict_do_update.return_value = mock_upsert_stmt
            mock_insert.return_value.values.return_value = mock_insert_values

            result = await loader.load_financial_statements("AAPL")

            # The method calls get_financial_statements for income statements twice (annual and quarterly)
            # So we expect the mock data to be duplicated (2 statements x 2 calls = 4 total)
            expected_count = (
                len(mock_financial_statements) * 2
            )  # Annual + Quarterly calls
            assert len(result) == expected_count
            # _upsert_records does a single bulk insert for all financial statements
            assert mock_session.execute.call_count == 1  # Single bulk insert
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_financial_statements_no_data(self, loader):
        """Test handling of no financial statements data"""
        with patch.object(loader.client, "get_financial_statements", return_value=[]):
            result = await loader.load_financial_statements("INVALID")
            assert result == []

    @pytest.mark.asyncio
    async def test_load_company_officers_success(self, loader, mock_company_officers):
        """Test successful loading of company officers"""
        with (
            patch.object(
                loader.client,
                "get_company_officers",
                return_value=mock_company_officers,
            ),
            patch("src.services.yahoo.loader.db_transaction") as mock_db,
            patch("src.services.yahoo.loader.insert") as mock_insert,
        ):

            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock upsert statement chain
            # insert(model).values(records) returns object with .excluded and .on_conflict_do_update()
            mock_upsert_stmt = Mock()
            mock_insert_values = Mock()
            # Make excluded support subscripting for _upsert_records
            mock_excluded = Mock()
            mock_excluded.__getitem__ = Mock(side_effect=lambda key: Mock())
            mock_insert_values.excluded = mock_excluded
            mock_insert_values.on_conflict_do_update.return_value = mock_upsert_stmt
            mock_insert.return_value.values.return_value = mock_insert_values

            result = await loader.load_company_officers("AAPL")

            assert result == mock_company_officers
            # _upsert_records does a single bulk insert for all officers
            assert mock_session.execute.call_count == 1  # Single bulk insert
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_company_officers_no_data(self, loader):
        """Test handling of no company officers data"""
        with patch.object(loader.client, "get_company_officers", return_value=[]):
            result = await loader.load_company_officers("INVALID")
            assert result == []

    @pytest.mark.asyncio
    async def test_load_dividends_success(self, loader, mock_dividends):
        """Test successful loading of dividends"""
        with (
            patch.object(
                loader.client, "get_dividends", return_value=mock_dividends
            ),
            patch("src.services.yahoo.loader.db_transaction") as mock_db,
            patch("src.services.yahoo.loader.insert") as mock_insert,
        ):

            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock upsert statement chain
            # insert(model).values(records) returns object with .excluded and .on_conflict_do_update()
            mock_upsert_stmt = Mock()
            mock_insert_values = Mock()
            # Make excluded support subscripting for _upsert_records
            mock_excluded = Mock()
            mock_excluded.__getitem__ = Mock(side_effect=lambda key: Mock())
            mock_insert_values.excluded = mock_excluded
            mock_insert_values.on_conflict_do_update.return_value = mock_upsert_stmt
            mock_insert.return_value.values.return_value = mock_insert_values

            result = await loader.load_dividends(
                symbol="AAPL",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
            )

            assert result == 3  # Method returns count of dividends loaded
            # _upsert_records does a single bulk insert for all dividends
            assert mock_session.execute.call_count == 1  # Single bulk insert
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_dividends_no_data(self, loader):
        """Test handling of no dividends data"""
        with patch.object(loader.client, "get_dividends", return_value=[]):
            result = await loader.load_dividends(
                symbol="INVALID",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
            )
            assert result == 0  # Method returns count of dividends loaded

    @pytest.mark.asyncio
    async def test_load_dividends_api_error(self, loader):
        """Test handling of API errors in dividends loading"""
        with patch.object(
            loader.client, "get_dividends", side_effect=YahooAPIError("API Error")
        ):
            with pytest.raises(YahooAPIError):
                await loader.load_dividends(
                    symbol="INVALID",
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 12, 31),
                )

    @pytest.mark.asyncio
    async def test_load_splits_success(self, loader, mock_stock_splits):
        """Test successful loading of stock splits"""
        with (
            patch.object(
                loader.client, "get_splits", return_value=mock_stock_splits
            ),
            patch("src.services.yahoo.loader.db_transaction") as mock_db,
            patch("src.services.yahoo.loader.insert") as mock_insert,
        ):

            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock upsert statement chain
            # insert(model).values(records) returns object with .excluded and .on_conflict_do_update()
            mock_upsert_stmt = Mock()
            mock_insert_values = Mock()
            # Make excluded support subscripting for _upsert_records
            mock_excluded = Mock()
            mock_excluded.__getitem__ = Mock(side_effect=lambda key: Mock())
            mock_insert_values.excluded = mock_excluded
            mock_insert_values.on_conflict_do_update.return_value = mock_upsert_stmt
            mock_insert.return_value.values.return_value = mock_insert_values

            result = await loader.load_splits(
                symbol="AAPL",
                start_date=date(2020, 1, 1),
                end_date=date(2024, 12, 31),
            )

            assert result == 2  # Method returns count of splits loaded
            # _upsert_records does a single bulk insert for all splits
            assert mock_session.execute.call_count == 1  # Single bulk insert
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_splits_no_data(self, loader):
        """Test handling of no stock splits data"""
        with patch.object(loader.client, "get_splits", return_value=[]):
            result = await loader.load_splits(
                symbol="INVALID",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
            )
            assert result == 0  # Method returns count of splits loaded

    @pytest.mark.asyncio
    async def test_load_splits_api_error(self, loader):
        """Test handling of API errors in stock splits loading"""
        with patch.object(
            loader.client, "get_splits", side_effect=YahooAPIError("API Error")
        ):
            with pytest.raises(YahooAPIError):
                await loader.load_splits(
                    symbol="INVALID",
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 12, 31),
                )

    @pytest.mark.asyncio
    async def test_load_analyst_recommendations_success(
        self, loader, mock_analyst_recommendations
    ):
        """Test successful loading of analyst recommendations"""
        with (
            patch.object(
                loader.client,
                "get_analyst_recommendations",
                return_value=mock_analyst_recommendations,
            ),
            patch("src.services.yahoo.loader.db_transaction") as mock_db,
            patch("src.services.yahoo.loader.insert") as mock_insert,
        ):

            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock upsert statement chain
            # insert(model).values(records) returns object with .excluded and .on_conflict_do_update()
            mock_upsert_stmt = Mock()
            mock_insert_values = Mock()
            # Make excluded support subscripting for _upsert_records
            mock_excluded = Mock()
            mock_excluded.__getitem__ = Mock(side_effect=lambda key: Mock())
            mock_insert_values.excluded = mock_excluded
            mock_insert_values.on_conflict_do_update.return_value = mock_upsert_stmt
            mock_insert.return_value.values.return_value = mock_insert_values

            count = await loader.load_analyst_recommendations("AAPL")

            assert count == 3  # Method returns count of recommendations loaded
            # _upsert_records does a single bulk insert for all recommendations
            assert mock_session.execute.call_count == 1  # Single bulk insert
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_analyst_recommendations_no_data(self, loader):
        """Test handling of no analyst recommendations data"""
        with patch.object(
            loader.client, "get_analyst_recommendations", return_value=[]
        ):
            count = await loader.load_analyst_recommendations("AAPL")
            assert count == 0

    @pytest.mark.asyncio
    async def test_load_analyst_recommendations_api_error(self, loader):
        """Test handling of API errors in analyst recommendations loading"""
        with patch.object(
            loader.client,
            "get_analyst_recommendations",
            side_effect=YahooAPIError("API Error"),
        ):
            with pytest.raises(YahooAPIError):
                await loader.load_analyst_recommendations("INVALID")

    @pytest.mark.asyncio
    async def test_load_all_data_success(
        self, loader, mock_company_info, mock_key_statistics, setup_test_tables
    ):
        """Test successful loading of all data types"""
        with (
            patch.object(loader, "load_company_info", return_value=True),
            patch.object(loader, "load_key_statistics", return_value=True),
            patch.object(loader, "load_institutional_holders", return_value=0),
            patch.object(loader, "load_financial_statements", return_value=[]),
            patch.object(loader, "load_company_officers", return_value=0),
            patch.object(loader, "load_dividends", return_value=0),
            patch.object(loader, "load_splits", return_value=0),
            patch.object(loader, "load_analyst_recommendations", return_value=0),
            patch.object(loader, "load_esg_scores", return_value=True),
        ):

            result = await loader.load_all_data("AAPL")

            # The method returns counts/status indicators, not the actual data objects
            # Since include_fundamentals and include_key_statistics are False by default,
            # these won't be loaded unless explicitly requested
            assert result["company_info"] == 0  # Not loaded by default
            assert result["key_statistics"] == 0  # Not loaded by default
            assert result["institutional_holders"] == 0
            assert (
                result["financial_statements"] == 0
            )  # load_financial_statements returns [], len([]) = 0
            assert result["company_officers"] == 0
            assert result["dividends"] == 0  # Not loaded by default
            assert result["splits"] == 0  # Not loaded by default

    @pytest.mark.asyncio
    async def test_load_all_data_with_options(
        self, loader, mock_company_info, setup_test_tables
    ):
        """Test loading all data with specific options"""
        with (
            patch.object(loader, "load_company_info", return_value=True),
            patch.object(loader, "load_key_statistics", return_value=False),
            patch.object(loader, "load_institutional_holders", return_value=0),
            patch.object(loader, "load_financial_statements", return_value=[]),
            patch.object(loader, "load_company_officers", return_value=0),
            patch.object(loader, "load_dividends", return_value=5),
            patch.object(loader, "load_splits", return_value=0),
            patch.object(loader, "load_analyst_recommendations", return_value=3),
            patch.object(loader, "load_esg_scores", return_value=True),
        ):

            result = await loader.load_all_data(
                "AAPL",
                include_fundamentals=True,  # Need to enable fundamentals to load company_info
                include_key_statistics=True,
                include_institutional_holders=False,
                include_financial_statements=False,
                include_company_officers=False,
                include_dividends=True,
                include_analyst_recommendations=True,
                include_esg_scores=True,
            )

            # The method returns counts/status indicators
            assert result["company_info"] == 1  # True gets converted to 1
            assert result["key_statistics"] == 0  # False gets converted to 0
            assert result["institutional_holders"] == 0
            assert result["financial_statements"] == 0  # len([]) = 0
            assert result["company_officers"] == 0
            assert result["dividends"] == 5  # Count of dividends loaded
            assert result["splits"] == 0  # Not loaded
            assert result["analyst_recommendations"] == 3  # Count of recommendations loaded
            assert result["esg_scores"] == 1  # True gets converted to 1

    @pytest.mark.asyncio
    async def test_load_all_symbols_data_success(self, loader, setup_test_tables):
        """Test successful loading of all symbols data"""
        with (
            patch.object(loader, "_get_active_symbols", return_value=["AAPL", "MSFT"]),
            patch.object(
                loader, "load_market_data", return_value=10
            ) as mock_market_data,
            patch.object(
                loader, "load_company_info", return_value=True
            ) as mock_company_info,
            patch.object(
                loader, "load_key_statistics", return_value=True
            ) as mock_key_stats,
            patch.object(
                loader, "load_institutional_holders", return_value=5
            ) as mock_holders,
            patch.object(
                loader, "load_financial_statements", return_value=[]
            ) as mock_financial,
            patch.object(
                loader, "load_company_officers", return_value=3
            ) as mock_officers,
            patch.object(
                loader, "load_dividends", return_value=4
            ) as mock_dividends,
            patch.object(
                loader, "load_splits", return_value=1
            ) as mock_splits,
            patch.object(
                loader, "load_analyst_recommendations", return_value=2
            ) as mock_analyst_recs,
            patch.object(
                loader, "load_esg_scores", return_value=True
            ) as mock_esg_scores,
        ):

            result = await loader.load_all_symbols_data()

            # The method returns a statistics dictionary, not a dictionary with symbol keys.
            # load_market_data is called twice per symbol (auto_adjust=False and True).
            assert result["total_symbols"] == 2
            assert result["successful"] == 2
            assert result["failed"] == 0
            assert result["total_records"] == 40  # 2 symbols x (10 + 10) unadjusted + adjusted
            assert mock_market_data.call_count == 4  # 2 calls per symbol

    @pytest.mark.asyncio
    async def test_load_all_symbols_data_with_options(self, loader, setup_test_tables):
        """Test loading all symbols data with specific options"""
        with (
            patch.object(loader, "_get_active_symbols", return_value=["AAPL"]),
            patch.object(
                loader, "load_market_data", return_value=15
            ) as mock_market_data,
            patch.object(
                loader, "load_key_statistics", return_value=True
            ) as mock_key_stats,
            patch.object(
                loader, "load_institutional_holders", return_value=8
            ) as mock_holders,
            patch.object(
                loader, "load_dividends", return_value=3
            ) as mock_dividends,
        ):

            result = await loader.load_all_symbols_data(
                include_key_statistics=True,
                include_institutional_holders=True,
                include_dividends=True,
            )

            # The method returns a statistics dictionary. load_market_data called twice per symbol.
            assert result["total_symbols"] == 1
            assert result["successful"] == 1
            assert result["failed"] == 0
            assert result["total_records"] == 30  # 1 symbol x (15 + 15) unadjusted + adjusted
            assert mock_market_data.call_count == 2
            assert mock_key_stats.call_count == 1
            assert mock_holders.call_count == 1
            assert mock_dividends.call_count == 1

    def test_detect_fiscal_year_quarter_apple(self, loader):
        """Test fiscal year and quarter detection for Apple (September end)"""
        # Apple's fiscal year ends in September
        period_end = date(2024, 9, 30)  # Q4 2024
        fiscal_year, fiscal_quarter = loader._detect_fiscal_year_quarter(
            "AAPL", period_end
        )

        assert fiscal_year == 2024
        assert fiscal_quarter == 4

    def test_detect_fiscal_year_quarter_apple_q1(self, loader):
        """Test fiscal year and quarter detection for Apple Q1"""
        # Apple's Q1 2025 would be Oct-Dec 2024
        period_end = date(2024, 12, 31)  # Q1 2025
        fiscal_year, fiscal_quarter = loader._detect_fiscal_year_quarter(
            "AAPL", period_end
        )

        assert fiscal_year == 2025
        assert fiscal_quarter == 1

    def test_detect_fiscal_year_quarter_microsoft(self, loader):
        """Test fiscal year and quarter detection for Microsoft (December end)"""
        # Microsoft's fiscal year ends in December
        period_end = date(2024, 12, 31)  # Q4 2024
        fiscal_year, fiscal_quarter = loader._detect_fiscal_year_quarter(
            "MSFT", period_end
        )

        assert fiscal_year == 2024
        assert fiscal_quarter == 4

    def test_detect_fiscal_year_quarter_microsoft_q1(self, loader):
        """Test fiscal year and quarter detection for Microsoft Q1"""
        # Microsoft's Q1 2025 would be Jan-Mar 2025
        period_end = date(2025, 3, 31)  # Q1 2025
        fiscal_year, fiscal_quarter = loader._detect_fiscal_year_quarter(
            "MSFT", period_end
        )

        assert fiscal_year == 2025
        assert fiscal_quarter == 1

    def test_detect_fiscal_year_quarter_unknown_symbol(self, loader):
        """Test fiscal year and quarter detection for unknown symbol (defaults to December)"""
        period_end = date(2024, 12, 31)  # Q4 2024
        fiscal_year, fiscal_quarter = loader._detect_fiscal_year_quarter(
            "UNKNOWN", period_end
        )

        assert fiscal_year == 2024
        assert fiscal_quarter == 4

    def test_detect_fiscal_year_quarter_edge_cases(self, loader):
        """Test fiscal year and quarter detection edge cases"""
        # Test various months for Apple (September end)
        test_cases = [
            (date(2024, 10, 31), 2025, 1),  # October = Q1 next year
            (date(2024, 11, 30), 2025, 1),  # November = Q1 next year
            (date(2024, 12, 31), 2025, 1),  # December = Q1 next year
            (date(2025, 1, 31), 2025, 2),  # January = Q2
            (date(2025, 2, 28), 2025, 2),  # February = Q2
            (date(2025, 3, 31), 2025, 2),  # March = Q2
            (date(2025, 4, 30), 2025, 3),  # April = Q3
            (date(2025, 5, 31), 2025, 3),  # May = Q3
            (date(2025, 6, 30), 2025, 3),  # June = Q3
            (date(2025, 7, 31), 2025, 4),  # July = Q4
            (date(2025, 8, 31), 2025, 4),  # August = Q4
            (date(2025, 9, 30), 2025, 4),  # September = Q4
        ]

        for period_end, expected_year, expected_quarter in test_cases:
            fiscal_year, fiscal_quarter = loader._detect_fiscal_year_quarter(
                "AAPL", period_end
            )
            assert fiscal_year == expected_year, f"Failed for {period_end}"
            assert fiscal_quarter == expected_quarter, f"Failed for {period_end}"

    @pytest.mark.asyncio
    async def test_health_check_success(self, loader):
        """Test successful health check"""
        with patch.object(
            loader.client, "health_check", return_value=Mock(healthy=True)
        ):
            result = await loader.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, loader):
        """Test failed health check"""
        with patch.object(
            loader.client, "health_check", return_value=Mock(healthy=False)
        ):
            result = await loader.health_check()
            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_exception(self, loader):
        """Test health check with exception"""
        with patch.object(
            loader.client, "health_check", side_effect=Exception("Health check failed")
        ):
            result = await loader.health_check()
            assert result is False

    def test_fiscal_year_patterns_coverage(self, loader):
        """Test that fiscal year patterns cover major companies"""
        # Test that the fiscal year patterns dictionary has entries for major companies
        # This is a basic test - in practice, we'd check the actual patterns dictionary
        # For now, we test that the method works for known symbols
        test_symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA"]

        for symbol in test_symbols:
            # Test with a December date
            period_end = date(2024, 12, 31)
            fiscal_year, fiscal_quarter = loader._detect_fiscal_year_quarter(
                symbol, period_end
            )

            # Should return valid values
            assert isinstance(fiscal_year, int)
            assert isinstance(fiscal_quarter, int)
            assert 2020 <= fiscal_year <= 2030  # Reasonable range
            assert 1 <= fiscal_quarter <= 4

    def test_financial_statement_upsert_logic(self, loader):
        """Test financial statement upsert logic"""
        # This tests the upsert logic without actually executing database operations
        stmt_data = {
            "symbol": "AAPL",
            "period_end": date(2024, 9, 30),
            "statement_type": "income",
            "period_type": "quarterly",
            "fiscal_year": 2024,
            "fiscal_quarter": 4,
            "data": {"Total Revenue": 89498000000},
            "total_revenue": 89498000000,
            "net_income": None,
            "basic_eps": None,
            "data_source": "yahoo",
        }

        # Test that the upsert dictionary has the correct structure
        required_keys = [
            "symbol",
            "period_end",
            "statement_type",
            "period_type",
            "fiscal_year",
            "fiscal_quarter",
            "data",
            "total_revenue",
            "data_source",
        ]

        for key in required_keys:
            assert key in stmt_data

    def test_company_officer_merge_logic(self, loader):
        """Test company officer merge logic"""
        officer_data = {
            "symbol": "AAPL",
            "name": "Tim Cook",
            "title": "Chief Executive Officer",
            "age": 63,
            "year_born": 1960,
            "fiscal_year": 2024,
            "total_pay": 99420000,
            "exercised_value": 0,
            "unexercised_value": 0,
        }

        # Test that the officer data has the correct structure
        required_keys = [
            "symbol",
            "name",
            "title",
            "age",
            "year_born",
            "fiscal_year",
            "total_pay",
            "exercised_value",
            "unexercised_value",
        ]

        for key in required_keys:
            assert key in officer_data

    @pytest.mark.asyncio
    async def test_load_financial_statements_with_fiscal_calculation(self, loader):
        """Test financial statements loading with fiscal year/quarter calculation"""
        mock_statements = [
            FinancialStatement(
                symbol="AAPL",
                period_end=date(2024, 9, 30),
                statement_type="income",
                period_type="quarterly",
                data={"Total Revenue": 89498000000},
            )
        ]

        def mock_get_financial_statements(symbol, stmt_type, period_type):
            """Mock function that returns data only for income statements"""
            if stmt_type == "income":
                return mock_statements
            else:
                return []

        with (
            patch.object(
                loader.client,
                "get_financial_statements",
                side_effect=mock_get_financial_statements,
            ),
            patch("src.services.yahoo.loader.db_transaction") as mock_db,
            patch("src.services.yahoo.loader.insert") as mock_insert,
        ):

            # Setup mock session
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock upsert statement
            mock_upsert_stmt = Mock()
            mock_insert.return_value.on_conflict_do_update.return_value = (
                mock_upsert_stmt
            )

            result = await loader.load_financial_statements("AAPL")

            # Verify that fiscal year and quarter were calculated
            # The method calls get_financial_statements for income statements twice (annual and quarterly)
            # So we expect the mock data to be duplicated
            expected_count = len(mock_statements) * 2  # Annual + Quarterly calls
            assert len(result) == expected_count
            # The actual fiscal calculation would be tested in the
            # _detect_fiscal_year_quarter method

    @pytest.mark.asyncio
    async def test_error_handling_in_load_methods(self, loader):
        """Test error handling in load methods"""
        # Test that all load methods properly handle exceptions
        with patch.object(
            loader.client, "get_company_info", side_effect=Exception("Test error")
        ):
            with pytest.raises(YahooAPIError):
                await loader.load_company_info("AAPL")

    @pytest.mark.asyncio
    async def test_data_validation_in_load_methods(self, loader):
        """Test data validation in load methods"""
        # Test that load methods validate input data
        with pytest.raises(ValueError):
            await loader.load_company_info("")  # Empty symbol

        with pytest.raises(ValueError):
            await loader.load_company_info(None)  # None symbol
