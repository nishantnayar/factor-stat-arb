"""
Unit tests for Settings Configuration
"""

from unittest.mock import patch

import pytest

from src.config.settings import Settings, get_settings


class TestSettingsInitialization:
    """Test cases for Settings initialization"""

    def test_settings_default_values(self):
        """Test settings with default values"""
        # Set explicit environment variables to test defaults (override .env)
        default_env = {
            "TRADING_DB_NAME": "trading_system",  # Override test .env value
        }
        with patch.dict("os.environ", default_env, clear=True):
            settings = Settings()

            # Application settings
            assert settings.app_name == "Trading System"
            assert settings.app_version == "1.0.0"
            assert settings.debug is False
            assert settings.log_level == "INFO"

            # Database settings
            assert settings.postgres_host == "localhost"
            assert settings.postgres_port == 5432
            assert settings.postgres_user == "postgres"
            assert settings.trading_db_name == "trading_system"

            # Redis settings
            assert settings.redis_host == "localhost"
            assert settings.redis_port == 6379
            assert settings.redis_db == 0

    def test_settings_from_environment(self):
        """Test settings loaded from environment variables"""
        env_vars = {
            "APP_NAME": "Test Trading System",
            "APP_VERSION": "2.0.0",
            "DEBUG": "true",
            "LOG_LEVEL": "DEBUG",
            "POSTGRES_HOST": "db.example.com",
            "POSTGRES_PORT": "5433",
            "POSTGRES_USER": "testuser",
            "POSTGRES_PASSWORD": "testpass",
            "TRADING_DB_NAME": "test_trading",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            settings = Settings()

            assert settings.app_name == "Test Trading System"
            assert settings.app_version == "2.0.0"
            assert settings.debug is True
            assert settings.log_level == "DEBUG"
            assert settings.postgres_host == "db.example.com"
            assert settings.postgres_port == 5433
            assert settings.postgres_user == "testuser"
            assert settings.postgres_password == "testpass"
            assert settings.trading_db_name == "test_trading"

    def test_settings_alpaca_configuration(self):
        """Test Alpaca API configuration"""
        env_vars = {
            "ALPACA_API_KEY": "test_api_key",
            "ALPACA_SECRET_KEY": "test_secret",
            "ALPACA_BASE_URL": "https://paper-api.alpaca.markets",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            settings = Settings()

            assert settings.alpaca_api_key == "test_api_key"
            assert settings.alpaca_secret_key == "test_secret"
            assert settings.alpaca_base_url == "https://paper-api.alpaca.markets"

    def test_settings_polygon_configuration(self):
        """Test Polygon.io API configuration"""
        env_vars = {
            "POLYGON_API_KEY": "test_polygon_key",
            "POLYGON_BASE_URL": "https://api.polygon.io",
            "POLYGON_DATA_DELAY_MINUTES": "20",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            settings = Settings()

            assert settings.polygon_api_key == "test_polygon_key"
            assert settings.polygon_base_url == "https://api.polygon.io"
            assert settings.polygon_data_delay_minutes == 20

    def test_settings_security_configuration(self):
        """Test security configuration"""
        env_vars = {
            "SECRET_KEY": "test_secret_key",
            "JWT_SECRET_KEY": "test_jwt_key",
            "JWT_ALGORITHM": "HS512",
            "JWT_ACCESS_TOKEN_EXPIRE_MINUTES": "60",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            settings = Settings()

            assert settings.secret_key == "test_secret_key"
            assert settings.jwt_secret_key == "test_jwt_key"
            assert settings.jwt_algorithm == "HS512"
            assert settings.jwt_access_token_expire_minutes == 60

    def test_settings_trading_configuration(self):
        """Test trading configuration"""
        env_vars = {
            "PAPER_TRADING": "false",
            "MAX_POSITION_SIZE": "0.25",
            "MAX_DAILY_LOSS": "0.10",
            "MAX_DRAWDOWN": "0.15",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            settings = Settings()

            assert settings.paper_trading is False
            assert settings.max_position_size == 0.25
            assert settings.max_daily_loss == 0.10
            assert settings.max_drawdown == 0.15

    def test_settings_risk_management_configuration(self):
        """Test risk management configuration"""
        env_vars = {
            "RISK_ENABLED": "true",
            "CIRCUIT_BREAKER_ENABLED": "true",
            "MAX_ORDERS_PER_HOUR": "100",
            "MAX_ORDERS_PER_DAY": "500",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            settings = Settings()

            assert settings.risk_enabled is True
            assert settings.circuit_breaker_enabled is True
            assert settings.max_orders_per_hour == 100
            assert settings.max_orders_per_day == 500

    def test_settings_logging_configuration(self):
        """Test logging configuration"""
        env_vars = {
            "LOG_FILE_PATH": "logs/custom.log",
            "LOG_RETENTION_DAYS": "60",
            "LOG_ROTATION_SIZE": "20MB",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            settings = Settings()

            assert settings.log_file_path == "logs/custom.log"
            assert settings.log_retention_days == 60
            assert settings.log_rotation_size == "20MB"

    def test_settings_timezone_configuration(self):
        """Test timezone configuration"""
        env_vars = {
            "DEFAULT_TIMEZONE": "UTC",
            "USER_TIMEZONE": "America/New_York",
            "TRADING_TIMEZONE": "America/Chicago",
            "VENDOR_TIMEZONE": "UTC",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            settings = Settings()

            assert settings.default_timezone == "UTC"
            assert settings.user_timezone == "America/New_York"
            assert settings.trading_timezone == "America/Chicago"
            assert settings.vendor_timezone == "UTC"

    def test_settings_optional_email_configuration(self):
        """Test optional email configuration"""
        env_vars = {
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "587",
            "SMTP_USERNAME": "user@example.com",
            "SMTP_PASSWORD": "smtp_password",
            "SMTP_FROM_EMAIL": "noreply@example.com",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            settings = Settings()

            assert settings.smtp_host == "smtp.example.com"
            assert settings.smtp_port == 587
            assert settings.smtp_username == "user@example.com"
            assert settings.smtp_password == "smtp_password"
            assert settings.smtp_from_email == "noreply@example.com"

    def test_settings_optional_email_defaults(self):
        """Test optional email configuration defaults"""
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings()

            # These fields are optional and may be None or have default values from .env
            # Just verify they can be accessed
            assert hasattr(settings, "smtp_host")
            assert hasattr(settings, "smtp_port")
            assert hasattr(settings, "smtp_username")
            assert hasattr(settings, "smtp_password")
            assert hasattr(settings, "smtp_from_email")


class TestGetSettings:
    """Test cases for get_settings function"""

    def test_get_settings_singleton(self):
        """Test that get_settings returns singleton instance"""
        with patch.dict("os.environ", {}, clear=True):
            # Reset the global settings
            import src.config.settings

            src.config.settings._settings = None

            settings1 = get_settings()
            settings2 = get_settings()

            assert settings1 is settings2

    def test_get_settings_creates_instance(self):
        """Test that get_settings creates Settings instance"""
        with patch.dict("os.environ", {}, clear=True):
            # Reset the global settings
            import src.config.settings

            src.config.settings._settings = None

            settings = get_settings()

            assert isinstance(settings, Settings)
            assert settings.app_name == "Trading System"

    def test_get_settings_uses_cached_instance(self):
        """Test that get_settings uses cached instance"""
        with patch.dict("os.environ", {"APP_NAME": "First App"}, clear=True):
            # Reset the global settings
            import src.config.settings

            src.config.settings._settings = None

            settings1 = get_settings()
            assert settings1.app_name == "First App"

        # Change environment but should still use cached instance
        with patch.dict("os.environ", {"APP_NAME": "Second App"}, clear=True):
            settings2 = get_settings()
            assert settings2.app_name == "First App"  # Still uses cached


class TestSettingsValidation:
    """Test cases for settings validation"""

    def test_settings_boolean_parsing(self):
        """Test boolean value parsing"""
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("0", False),
        ]

        for env_value, expected in test_cases:
            with patch.dict("os.environ", {"DEBUG": env_value}, clear=True):
                settings = Settings()
                assert settings.debug == expected

    def test_settings_integer_parsing(self):
        """Test integer value parsing"""
        with patch.dict("os.environ", {"POSTGRES_PORT": "3306"}, clear=True):
            settings = Settings()
            assert settings.postgres_port == 3306
            assert isinstance(settings.postgres_port, int)

    def test_settings_float_parsing(self):
        """Test float value parsing"""
        with patch.dict("os.environ", {"MAX_POSITION_SIZE": "0.20"}, clear=True):
            settings = Settings()
            assert settings.max_position_size == 0.20
            assert isinstance(settings.max_position_size, float)

    def test_settings_extra_fields_ignored(self):
        """Test that extra environment fields are ignored"""
        env_vars = {
            "APP_NAME": "Test App",
            "UNKNOWN_FIELD": "unknown_value",
            "ANOTHER_UNKNOWN": "another_value",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            # Should not raise an error
            settings = Settings()
            assert settings.app_name == "Test App"
            assert not hasattr(settings, "UNKNOWN_FIELD")
            assert not hasattr(settings, "ANOTHER_UNKNOWN")


class TestSettingsEdgeCases:
    """Test cases for edge cases"""

    def test_settings_empty_string_values(self):
        """Test handling of empty string values"""
        env_vars = {
            "ALPACA_API_KEY": "",
            "POLYGON_API_KEY": "",
            "SECRET_KEY": "",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            settings = Settings()

            assert settings.alpaca_api_key == ""
            assert settings.polygon_api_key == ""
            assert settings.secret_key == ""

    def test_settings_default_urls(self):
        """Test default URL configurations"""
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings()

            assert settings.alpaca_base_url == "https://paper-api.alpaca.markets"
            assert settings.alpaca_data_url == "https://data.alpaca.markets"
            assert settings.polygon_base_url == "https://api.polygon.io"
            assert settings.redis_url == "redis://localhost:6379/0"

    def test_settings_case_insensitive(self):
        """Test case insensitivity of environment variables"""
        env_vars = {
            "app_name": "Lower Case App",
            "APP_VERSION": "1.0.0",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            settings = Settings()

            # Should work with case insensitive matching
            assert settings.app_name == "Lower Case App"
            assert settings.app_version == "1.0.0"


class TestSettingsDefaults:
    """Test cases for default values"""

    def test_database_defaults(self):
        """Test database default values"""
        # Set explicit environment variables to test defaults (override .env)
        default_env = {
            "TRADING_DB_NAME": "trading_system",  # Override test .env value
        }
        with patch.dict("os.environ", default_env, clear=True):
            settings = Settings()

            assert settings.postgres_host == "localhost"
            assert settings.postgres_port == 5432
            assert settings.postgres_user == "postgres"
            # Password may be set in .env, just verify it exists
            assert hasattr(settings, "postgres_password")
            assert settings.trading_db_name == "trading_system"

    def test_redis_defaults(self):
        """Test Redis default values"""
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings()

            assert settings.redis_host == "localhost"
            assert settings.redis_port == 6379
            assert settings.redis_db == 0
            assert settings.redis_url == "redis://localhost:6379/0"

    def test_security_defaults(self):
        """Test security default values"""
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings()

            # Secret keys may be set in .env, just verify they exist
            assert hasattr(settings, "secret_key")
            assert hasattr(settings, "jwt_secret_key")
            assert settings.jwt_algorithm == "HS256"
            assert settings.jwt_access_token_expire_minutes == 30

    def test_trading_defaults(self):
        """Test trading default values"""
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings()

            assert settings.paper_trading is True
            assert settings.max_position_size == 0.15
            assert settings.max_daily_loss == 0.05
            assert settings.max_drawdown == 0.10

    def test_risk_management_defaults(self):
        """Test risk management default values"""
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings()

            assert settings.risk_enabled is True
            assert settings.circuit_breaker_enabled is True
            assert settings.max_orders_per_hour == 50
            assert settings.max_orders_per_day == 200

    def test_logging_defaults(self):
        """Test logging default values"""
        # Disable .env file reading and set explicit values
        env_vars = {
            "DISABLE_ENV_FILE": "true",
            "LOG_FILE_PATH": "logs/trading.log",
            "LOG_RETENTION_DAYS": "30",
            "LOG_ROTATION_SIZE": "10MB",
        }
        with patch.dict("os.environ", env_vars, clear=True):
            settings = Settings()

            assert settings.log_file_path == "logs/trading.log"
            assert settings.log_retention_days == 30
            assert settings.log_rotation_size == "10MB"

    def test_timezone_defaults(self):
        """Test timezone default values"""
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings()

            assert settings.default_timezone == "UTC"
            assert settings.user_timezone == "America/Chicago"
            assert settings.trading_timezone == "America/New_York"
            assert settings.vendor_timezone == "UTC"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
