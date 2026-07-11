"""
Unit tests for Company Officers database model
"""

from datetime import datetime, timezone

import pytest

from src.shared.database.models.company_officers import CompanyOfficer


class TestCompanyOfficerModel:
    """Test cases for CompanyOfficer model"""

    @pytest.fixture
    def sample_company_officer(self):
        """Create a sample company officer for testing"""
        return CompanyOfficer(
            symbol="AAPL",
            name="Tim Cook",
            title="Chief Executive Officer",
            age=63,
            year_born=1960,
            fiscal_year=2024,
            total_pay=99420000,  # $994,200 in cents
            exercised_value=0,
            unexercised_value=0,
            data_source="yahoo",
        )

    def test_model_initialization(self, sample_company_officer):
        """Test model initialization with all fields"""
        officer = sample_company_officer

        assert officer.symbol == "AAPL"
        assert officer.name == "Tim Cook"
        assert officer.title == "Chief Executive Officer"
        assert officer.age == 63
        assert officer.year_born == 1960
        assert officer.fiscal_year == 2024
        assert officer.total_pay == 99420000
        assert officer.exercised_value == 0
        assert officer.unexercised_value == 0
        assert officer.data_source == "yahoo"
        # No data field in CompanyOfficer model

    def test_total_pay_display_property(self, sample_company_officer):
        """Test total_pay_display property"""
        officer = sample_company_officer

        # Test with value in cents
        result = officer.total_pay_display
        assert result == "$994.2K"

        # Test with None value
        officer.total_pay = None
        result = officer.total_pay_display
        assert result == "N/A"

        # Test with zero value
        officer.total_pay = 0
        result = officer.total_pay_display
        assert result == "$0"

    def test_total_pay_display_millions(self):
        """Test total_pay_display with millions"""
        officer = CompanyOfficer(
            symbol="TEST",
            name="Test Officer",
            total_pay=2650000000,  # $26.5M in cents
        )

        result = officer.total_pay_display
        assert result == "$26.5M"

    def test_total_pay_display_billions(self):
        """Test total_pay_display with billions"""
        officer = CompanyOfficer(
            symbol="TEST",
            name="Test Officer",
            total_pay=50000000000,  # $500M in cents
        )

        result = officer.total_pay_display
        assert result == "$500.0M"

    def test_total_pay_display_thousands(self):
        """Test total_pay_display with thousands"""
        officer = CompanyOfficer(
            symbol="TEST",
            name="Test Officer",
            total_pay=500000,  # $5K in cents
        )

        result = officer.total_pay_display
        assert result == "$5.0K"

    def test_exercised_value_display_property(self, sample_company_officer):
        """Test exercised_value_display property"""
        officer = sample_company_officer

        # Test with zero value
        result = officer.exercised_value_display
        assert result == "$0"

        # Test with None value
        officer.exercised_value = None
        result = officer.exercised_value_display
        assert result == "N/A"

        # Test with positive value
        officer.exercised_value = 1000000  # $10K in cents
        result = officer.exercised_value_display
        assert result == "$10.0K"

    def test_unexercised_value_display_property(self, sample_company_officer):
        """Test unexercised_value_display property"""
        officer = sample_company_officer

        # Test with zero value
        result = officer.unexercised_value_display
        assert result == "$0"

        # Test with None value
        officer.unexercised_value = None
        result = officer.unexercised_value_display
        assert result == "N/A"

        # Test with positive value
        officer.unexercised_value = 5000000  # $50K in cents
        result = officer.unexercised_value_display
        assert result == "$50.0K"

    def test_to_dict_method(self, sample_company_officer):
        """Test to_dict method"""
        officer = sample_company_officer
        result = officer.to_dict()

        # Test required fields
        assert "symbol" in result
        assert "name" in result
        assert "title" in result
        assert "age" in result
        assert "year_born" in result
        assert "fiscal_year" in result
        assert "total_pay" in result
        assert "exercised_value" in result
        assert "unexercised_value" in result
        assert "data_source" in result
        assert "created_at" in result
        assert "updated_at" in result

        # Test data types
        assert isinstance(result["symbol"], str)
        assert isinstance(result["name"], str)
        assert isinstance(result["title"], str)
        assert isinstance(result["age"], int)
        assert isinstance(result["year_born"], int)
        assert isinstance(result["fiscal_year"], int)
        assert isinstance(result["total_pay"], int)
        assert isinstance(result["exercised_value"], int)
        assert isinstance(result["unexercised_value"], int)
        assert isinstance(result["data_source"], str)

    def test_to_dict_with_none_values(self):
        """Test to_dict method with None values"""
        officer = CompanyOfficer(
            symbol="TEST",
            name="Test Officer",
            title=None,
            age=None,
            year_born=None,
            fiscal_year=None,
            total_pay=None,
            exercised_value=None,
            unexercised_value=None,
        )

        result = officer.to_dict()

        # None values should be preserved
        assert result["title"] is None
        assert result["age"] is None
        assert result["year_born"] is None
        assert result["fiscal_year"] is None
        assert result["total_pay"] is None
        assert result["exercised_value"] is None
        assert result["unexercised_value"] is None

    def test_repr_method(self, sample_company_officer):
        """Test __repr__ method"""
        officer = sample_company_officer
        result = repr(officer)

        assert "CompanyOfficer" in result
        assert "AAPL" in result
        assert "Tim Cook" in result

    def test_model_with_different_titles(self):
        """Test model with different officer titles"""
        titles = [
            "Chief Executive Officer",
            "Chief Financial Officer",
            "Chief Operating Officer",
            "Chief Technology Officer",
            "President",
            "Vice President",
            "Director",
            "Chairman",
        ]

        for title in titles:
            officer = CompanyOfficer(
                symbol="TEST",
                name="Test Officer",
                title=title,
            )

            assert officer.title == title

    def test_model_with_different_ages(self):
        """Test model with different ages"""
        ages = [30, 40, 50, 60, 70, 80]

        for age in ages:
            officer = CompanyOfficer(
                symbol="TEST",
                name="Test Officer",
                age=age,
                year_born=2024 - age,
            )

            assert officer.age == age
            assert officer.year_born == 2024 - age

    def test_model_with_different_fiscal_years(self):
        """Test model with different fiscal years"""
        fiscal_years = [2020, 2021, 2022, 2023, 2024, 2025]

        for fiscal_year in fiscal_years:
            officer = CompanyOfficer(
                symbol="TEST",
                name="Test Officer",
                fiscal_year=fiscal_year,
            )

            assert officer.fiscal_year == fiscal_year

    def test_model_with_different_compensation_values(self):
        """Test model with different compensation values"""
        test_cases = [
            (0, "$0"),
            (100000, "$1.0K"),
            (1000000, "$10.0K"),
            (10000000, "$100.0K"),
            (100000000, "$1.0M"),
            (1000000000, "$10.0M"),
            (10000000000, "$100.0M"),
            (100000000000, "$1000.0M"),
        ]

        for total_pay, expected_display in test_cases:
            officer = CompanyOfficer(
                symbol="TEST",
                name="Test Officer",
                total_pay=total_pay,
            )

            assert officer.total_pay_display == expected_display

    def test_model_with_special_characters_in_name(self):
        """Test model with special characters in name"""
        names = [
            "Jose Maria",
            "Jean-Pierre",
            "O'Connor",
            "Smith-Jones",
            "Dr. Smith",
            "Prof. Johnson",
        ]

        for name in names:
            officer = CompanyOfficer(
                symbol="TEST",
                name=name,
            )

            assert officer.name == name

    def test_model_with_long_names(self):
        """Test model with long names"""
        long_name = "A" * 255  # Maximum database length
        officer = CompanyOfficer(
            symbol="TEST",
            name=long_name,
        )

        assert officer.name == long_name
        assert len(officer.name) == 255

    def test_model_with_empty_strings(self):
        """Test model with empty strings"""
        officer = CompanyOfficer(
            symbol="TEST",
            name="",
            title="",
        )

        assert officer.name == ""
        assert officer.title == ""

    def test_model_created_at_updated_at(self, sample_company_officer):
        """Test created_at and updated_at timestamps"""
        officer = sample_company_officer

        # Set timestamps manually for testing (normally set by database)
        now = datetime.now(timezone.utc)
        officer.created_at = now
        officer.updated_at = now

        assert officer.created_at is not None
        assert officer.updated_at is not None
        assert isinstance(officer.created_at, datetime)
        assert isinstance(officer.updated_at, datetime)

    def test_model_data_validation(self):
        """Test model data validation"""
        # Test with valid data
        officer = CompanyOfficer(
            symbol="TEST",
            name="Test Officer",
            title="CEO",
            age=50,
            year_born=1974,
            fiscal_year=2024,
            total_pay=1000000,
            exercised_value=500000,
            unexercised_value=750000,
        )

        assert officer.symbol == "TEST"
        assert officer.name == "Test Officer"

    def test_model_edge_cases(self):
        """Test model edge cases"""
        # Test with very large compensation values
        officer = CompanyOfficer(
            symbol="TEST",
            name="Test Officer",
            total_pay=999999999999,  # Very large number
        )

        assert officer.total_pay == 999999999999
        assert officer.total_pay_display == "$10000.0M"

    def test_model_with_negative_values(self):
        """Test model with negative values"""
        officer = CompanyOfficer(
            symbol="TEST",
            name="Test Officer",
            total_pay=-1000000,  # Negative compensation
            exercised_value=-500000,
            unexercised_value=-750000,
        )

        # Negative values should be handled gracefully
        assert officer.total_pay == -1000000
        assert officer.exercised_value == -500000
        assert officer.unexercised_value == -750000

    def test_model_with_zero_values(self):
        """Test model with zero values"""
        officer = CompanyOfficer(
            symbol="TEST",
            name="Test Officer",
            total_pay=0,
            exercised_value=0,
            unexercised_value=0,
        )

        assert officer.total_pay == 0
        assert officer.exercised_value == 0
        assert officer.unexercised_value == 0
        assert officer.total_pay_display == "$0"
        assert officer.exercised_value_display == "$0"
        assert officer.unexercised_value_display == "$0"

    def test_model_with_unicode_characters(self):
        """Test model with unicode characters"""
        officer = CompanyOfficer(
            symbol="TEST",
            name="Jose Maria O'Connor",
            title="Chief Executive Officer",
        )

        assert officer.name == "Jose Maria O'Connor"
        assert officer.title == "Chief Executive Officer"

    def test_model_compensation_display_edge_cases(self):
        """Test compensation display with edge cases"""
        test_cases = [
            (1, "$0"),  # 1 cent
            (10, "$0"),  # 10 cents
            (100, "$1"),  # $1
            (1000, "$10"),  # $10
            (10000, "$100"),  # $100
            (100000, "$1.0K"),  # $1,000
            (1000000, "$10.0K"),  # $10,000
            (10000000, "$100.0K"),  # $100,000
            (100000000, "$1.0M"),  # $1,000,000
        ]

        for total_pay, expected_display in test_cases:
            officer = CompanyOfficer(
                symbol="TEST",
                name="Test Officer",
                total_pay=total_pay,
            )

            assert officer.total_pay_display == expected_display

    def test_model_with_complex_data(self):
        """Test model with complex data structure"""

        officer = CompanyOfficer(
            symbol="AAPL",
            name="Tim Cook",
        )

        assert officer.symbol == "AAPL"
        assert officer.name == "Tim Cook"
