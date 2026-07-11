"""
Prefect Configuration Module (Minimal)

Provides basic Prefect configuration access.
"""
from src.config.settings import Settings

settings = Settings()


class PrefectConfig:
    """Minimal Prefect configuration management"""
    
    @staticmethod
    def get_api_url() -> str:
        """Get Prefect API URL"""
        return settings.prefect_api_url
    
    @staticmethod
    def get_db_connection_url() -> str:
        """Get Prefect database connection URL"""
        return settings.prefect_db_connection_url
    
    @staticmethod
    def get_work_pool_name() -> str:
        """Get default work pool name for data ingestion"""
        return settings.prefect_work_pool_data_ingestion

