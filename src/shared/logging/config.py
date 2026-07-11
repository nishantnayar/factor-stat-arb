"""
Logging configuration management
"""

import os
from pathlib import Path
from typing import Dict, Optional

import yaml
from pydantic import BaseModel, Field


class LogRotationConfig(BaseModel):
    """Log rotation configuration"""

    size: str = "10 MB"
    time: str = "daily"
    retention: str = "30 days"
    compression: bool = True


class LogFilesConfig(BaseModel):
    """Log files configuration"""

    main: str = "logs/trading.log"
    errors: str = "logs/errors.log"
    system: str = "logs/system.log"
    trades: str = "logs/trades.log"
    performance: str = "logs/performance.log"


class DatabaseLoggingConfig(BaseModel):
    """Database logging configuration"""

    enabled: bool = True
    active_table: str = "system_logs"
    archive_table: str = "archived_system_logs"
    batch_size: int = 100  # Write when 100 logs are queued
    batch_timeout: int = 30  # Write every 30 seconds (or when batch is full)
    async_logging: bool = True
    fallback_to_file: bool = True


class RetentionConfig(BaseModel):
    """Log retention configuration"""

    active_days: int = 30
    archive_days: int = 90
    cleanup_schedule: str = "0 2 * * *"  # Daily at 2 AM


class ServiceLoggingConfig(BaseModel):
    """Service-specific logging configuration"""

    level: str = "INFO"
    file: str = "logs/{service}.log"


class PerformanceLoggingConfig(BaseModel):
    """Performance logging configuration"""

    enabled: bool = True
    log_execution_time: bool = True
    log_memory_usage: bool = True
    log_database_queries: bool = False


class LoggingConfig(BaseModel):
    """Main logging configuration"""

    # Log Levels
    level: str = "INFO"
    root_level: str = "INFO"

    # Log Rotation
    rotation: LogRotationConfig = Field(default_factory=LogRotationConfig)

    # Log Format
    format: str = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}"
    )

    # Log Files
    files: LogFilesConfig = Field(default_factory=LogFilesConfig)

    # Database Logging
    database: DatabaseLoggingConfig = Field(default_factory=DatabaseLoggingConfig)

    # Retention Settings
    retention: RetentionConfig = Field(default_factory=RetentionConfig)

    # Service-specific Logging
    services: Dict[str, ServiceLoggingConfig] = Field(default_factory=dict)

    # Structured Logging
    structured: bool = True
    json_format: bool = False

    # Performance Logging
    performance: PerformanceLoggingConfig = Field(
        default_factory=PerformanceLoggingConfig
    )


def load_logging_config(config_path: Optional[str] = None) -> LoggingConfig:
    """
    Load logging configuration from YAML file with environment variable overrides

    Args:
        config_path: Path to YAML configuration file

    Returns:
        LoggingConfig: Loaded configuration
    """
    if config_path is None:
        config_path = "config/logging.yaml"

    # Default configuration
    config_data = {
        "level": "INFO",
        "root_level": "INFO",
        "rotation": {
            "size": "10 MB",
            "time": "daily",
            "retention": "30 days",
            "compression": True,
        },
        "format": (
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
            "{name}:{function}:{line} | {message}"
        ),
        "files": {
            "main": "logs/trading.log",
            "errors": "logs/errors.log",
            "system": "logs/system.log",
            "trades": "logs/trades.log",
            "performance": "logs/performance.log",
        },
        "database": {
            "enabled": True,
            "active_table": "system_logs",
            "archive_table": "archived_system_logs",
            "batch_size": 100,  # Write when 100 logs are queued
            "batch_timeout": 30,  # Write every 30 seconds (or when batch is full)
            "async_logging": True,
            "fallback_to_file": True,
        },
        "retention": {
            "active_days": 30,
            "archive_days": 90,
            "cleanup_schedule": "0 2 * * *",
        },
        "services": {
            "data_ingestion": {"level": "INFO", "file": "logs/data_ingestion.log"},
            "strategy_engine": {"level": "DEBUG", "file": "logs/strategy_engine.log"},
            "execution": {"level": "INFO", "file": "logs/execution.log"},
            "risk_management": {"level": "WARNING", "file": "logs/risk_management.log"},
            "analytics": {"level": "INFO", "file": "logs/analytics.log"},
            "notification": {"level": "INFO", "file": "logs/notification.log"},
        },
        "structured": True,
        "json_format": False,
        "performance": {
            "enabled": True,
            "log_execution_time": True,
            "log_memory_usage": True,
            "log_database_queries": False,
        },
    }

    # Load from YAML file if it exists
    config_file = Path(config_path)
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f)
                if yaml_data and "logging" in yaml_data:
                    # Merge YAML data with defaults
                    config_data.update(yaml_data["logging"])
        except Exception as e:
            print(f"Warning: Could not load logging config from {config_path}: {e}")

    # Override with environment variables
    env_overrides = {
        "level": os.getenv("LOG_LEVEL"),
        "root_level": os.getenv("LOG_ROOT_LEVEL"),
        "structured": os.getenv("LOG_STRUCTURED"),
        "json_format": os.getenv("LOG_JSON_FORMAT"),
    }

    for key, value in env_overrides.items():
        if value is not None:
            if key in ["structured", "json_format"]:
                config_data[key] = value.lower() in ("true", "1", "yes", "on")
            else:
                config_data[key] = value

    # Convert services dict to ServiceLoggingConfig objects
    if "services" in config_data and isinstance(config_data["services"], dict):
        services_config = {}
        for service_name, service_config in config_data["services"].items():
            if isinstance(service_config, dict):
                services_config[service_name] = ServiceLoggingConfig(**service_config)
        config_data["services"] = services_config

    return LoggingConfig(**config_data)  # type: ignore


def get_service_config(
    service_name: str, config: LoggingConfig
) -> ServiceLoggingConfig:
    """
    Get service-specific logging configuration

    Args:
        service_name: Name of the service
        config: Main logging configuration

    Returns:
        ServiceLoggingConfig: Service-specific configuration
    """
    if service_name in config.services:
        return config.services[service_name]

    # Default service configuration
    return ServiceLoggingConfig(level=config.level, file=f"logs/{service_name}.log")


def detect_service_from_module(module_name: str) -> str:
    """
    Detect service name from module name

    Args:
        module_name: Full module name (e.g., 'src.services.execution.order_manager')

    Returns:
        str: Detected service name
    """
    # Extract service from module path
    parts = module_name.split(".")

    # Look for 'services' in the path
    if "services" in parts:
        services_index = parts.index("services")
        if services_index + 1 < len(parts):
            return parts[services_index + 1]

    # Look for 'src' in the path
    if "src" in parts:
        src_index = parts.index("src")
        if src_index + 1 < len(parts):
            return parts[src_index + 1]

    # Default to 'unknown' if no service detected
    return "unknown"
