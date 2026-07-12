"""
Application Settings Configuration
"""

import os
from typing import Any, Optional
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # Application Configuration
    app_name: str = Field(default="Trading System", alias="APP_NAME")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Database Configuration
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_user: str = Field(default="postgres", alias="POSTGRES_USER")
    postgres_password: str = Field(default="", alias="POSTGRES_PASSWORD")
    trading_db_name: str = Field(default="trading_system", alias="TRADING_DB_NAME")

    # Redis Configuration
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # Alpaca API Configuration
    alpaca_api_key: str = Field(default="", alias="ALPACA_API_KEY")
    alpaca_secret_key: str = Field(default="", alias="ALPACA_SECRET_KEY")
    alpaca_base_url: str = Field(
        default="https://paper-api.alpaca.markets", alias="ALPACA_BASE_URL"
    )
    alpaca_data_url: str = Field(
        default="https://data.alpaca.markets", alias="ALPACA_DATA_URL"
    )
    # Friendly label for the paper account (the Alpaca dashboard nickname is not
    # exposed by the Trading API, so set it here for display purposes only).
    alpaca_account_label: str = Field(default="", alias="ALPACA_ACCOUNT_LABEL")

    # Polygon.io API Configuration
    polygon_api_key: str = Field(default="", alias="POLYGON_API_KEY")
    polygon_base_url: str = Field(
        default="https://api.polygon.io", alias="POLYGON_BASE_URL"
    )
    polygon_data_delay_minutes: int = Field(
        default=15, alias="POLYGON_DATA_DELAY_MINUTES"
    )

    # Security Configuration
    secret_key: str = Field(default="", alias="SECRET_KEY")
    jwt_secret_key: str = Field(default="", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(
        default=30, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
    )

    # Trading Configuration
    paper_trading: bool = Field(default=True, alias="PAPER_TRADING")
    max_position_size: float = Field(default=0.15, alias="MAX_POSITION_SIZE")
    max_daily_loss: float = Field(default=0.05, alias="MAX_DAILY_LOSS")
    max_drawdown: float = Field(default=0.10, alias="MAX_DRAWDOWN")

    # Risk Management
    risk_enabled: bool = Field(default=True, alias="RISK_ENABLED")
    circuit_breaker_enabled: bool = Field(default=True, alias="CIRCUIT_BREAKER_ENABLED")
    max_orders_per_hour: int = Field(default=50, alias="MAX_ORDERS_PER_HOUR")
    max_orders_per_day: int = Field(default=200, alias="MAX_ORDERS_PER_DAY")

    # Logging Configuration
    log_file_path: str = Field(default="logs/trading.log", alias="LOG_FILE_PATH")
    log_retention_days: int = Field(default=30, alias="LOG_RETENTION_DAYS")
    log_rotation_size: str = Field(default="10MB", alias="LOG_ROTATION_SIZE")

    # Timezone Configuration
    default_timezone: str = Field(default="UTC", alias="DEFAULT_TIMEZONE")
    user_timezone: str = Field(default="America/Chicago", alias="USER_TIMEZONE")
    trading_timezone: str = Field(default="America/New_York", alias="TRADING_TIMEZONE")
    vendor_timezone: str = Field(default="UTC", alias="VENDOR_TIMEZONE")

    # Backtest Configuration
    backtest_slippage_bps: float = Field(default=5.0, alias="BACKTEST_SLIPPAGE_BPS")
    backtest_commission_per_trade: float = Field(
        default=0.0, alias="BACKTEST_COMMISSION_PER_TRADE"
    )

    # Email Configuration (Optional)
    smtp_host: Optional[str] = Field(default=None, alias="SMTP_HOST")
    smtp_port: Optional[int] = Field(default=None, alias="SMTP_PORT")
    smtp_username: Optional[str] = Field(default=None, alias="SMTP_USERNAME")
    smtp_password: Optional[str] = Field(default=None, alias="SMTP_PASSWORD")
    smtp_from_email: Optional[str] = Field(default=None, alias="SMTP_FROM_EMAIL")
    smtp_to_email: Optional[str] = Field(default=None, alias="SMTP_TO_EMAIL")

    # Harmonic Strategy Configuration
    harmonic_long_only: bool = Field(default=True, alias="HARMONIC_LONG_ONLY")

    # Ollama Agent Configuration
    ollama_base_url: str = Field(
        default="http://localhost:11434", alias="OLLAMA_BASE_URL"
    )
    ollama_model: str = Field(default="llama3.2:3b", alias="OLLAMA_MODEL")
    agent_enabled: bool = Field(default=True, alias="AGENT_ENABLED")
    agent_timeout_seconds: int = Field(default=30, alias="AGENT_TIMEOUT_SECONDS")

    # Prefect Configuration (Essential)
    prefect_api_url: str = Field(
        default="http://localhost:4200/api", alias="PREFECT_API_URL"
    )

    # Name of the (separate) Prefect metadata database for this repo.
    prefect_db_name: str = Field(
        default="factor_stat_arb_prefect", alias="PREFECT_DB_NAME"
    )
    # Optional explicit override. Normally left blank/placeholder - the connection
    # URL is derived from the postgres_* credentials so the password lives in ONE
    # place (POSTGRES_PASSWORD) instead of being duplicated here.
    prefect_db_url_override: str = Field(
        default="", alias="PREFECT_API_DATABASE_CONNECTION_URL"
    )

    prefect_work_pool_data_ingestion: str = Field(
        default="fsa-data-ingestion", alias="PREFECT_WORK_POOL_DATA_INGESTION"
    )

    @property
    def prefect_db_connection_url(self) -> str:
        """Async Postgres URL for Prefect's metadata DB.

        Uses PREFECT_API_DATABASE_CONNECTION_URL only if it's a real value (not a
        left-over placeholder); otherwise builds it from the postgres_* settings
        and prefect_db_name so the password is never duplicated.
        """
        override = self.prefect_db_url_override
        if (
            override
            and "your_password_here" not in override
            and ":password@" not in override
        ):
            return override
        pw = quote_plus(self.postgres_password)
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{pw}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.prefect_db_name}"
        )

    def __init__(self, **kwargs: Any) -> None:
        # Re-check DISABLE_ENV_FILE at instantiation time (not class-definition
        # time) so tests can toggle it via patch.dict after this module loads.
        if "_env_file" not in kwargs and os.getenv("DISABLE_ENV_FILE") == "true":
            kwargs["_env_file"] = None
        super().__init__(**kwargs)

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from environment


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
