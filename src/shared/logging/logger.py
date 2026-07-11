"""
Main logging setup and configuration

This module provides a clean, efficient logging system using:
- Loguru for logging framework
- Database-first approach with async batching
- File fallback for reliability
- Service-aware logging
"""

import atexit
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger as loguru_logger

from .config import (
    LoggingConfig,
    detect_service_from_module,
    get_service_config,
    load_logging_config,
)
from .correlation import get_correlation_id
from .database_handler import LogQueueManager, get_queue_manager, shutdown_queue_manager
from .database_sink import DatabaseSink, create_database_sink


class LoggingManager:
    """Manages logging configuration and setup"""

    def __init__(self, config: Optional[LoggingConfig] = None):
        self.config = config or load_logging_config()
        self._setup_complete = False
        self._service_loggers: Dict[str, Any] = {}
        self._queue_manager: Optional[LogQueueManager] = None
        self._database_sink: Optional[DatabaseSink] = None

    def setup_logging(self, service_name: Optional[str] = None) -> None:
        """
        Setup Loguru logging with database-first approach and file fallback

        Args:
            service_name: Optional service name for service-specific setup
        """
        if self._setup_complete:
            return

        # Remove default handler
        loguru_logger.remove()

        # Patch loguru to automatically inject correlation_id and service
        self._patch_loguru()

        # Setup console handler (always enabled for development)
        self._setup_console_handler()

        # Setup database handler first (primary logging method)
        if self.config.database.enabled:
            self._setup_database_handler()

        # Setup file handlers as fallback/backup (minimal, only for errors)
        if self.config.database.fallback_to_file:
            self._setup_file_handlers()

        # Setup service-specific handler if provided
        if service_name:
            self._setup_service_handler(service_name)

        # Register cleanup on exit
        atexit.register(self.shutdown)

        self._setup_complete = True

    def _patch_loguru(self) -> None:
        """
        Patch loguru to automatically inject correlation_id and service into log records
        """
        def patcher(record: Any) -> None:
            """
            Patcher function that modifies log records before they're processed
            Loguru passes a Record object, not a dict, but it supports dict-like access
            """
            try:
                # Ensure extra dict exists and is mutable
                if not hasattr(record, "extra"):
                    return
                
                # Get correlation_id from thread-local context if not already set
                if "correlation_id" not in record["extra"]:
                    correlation_id = get_correlation_id()
                    if correlation_id:
                        record["extra"]["correlation_id"] = correlation_id
                    # Debug: Uncomment to verify patcher is working
                    # else:
                    #     print(f"DEBUG: No correlation_id found for {record['name']}")
                
                # Detect and inject service if not already set
                if "service" not in record["extra"]:
                    service = detect_service_from_module(record["name"])
                    if service and service != "unknown":
                        record["extra"]["service"] = service
                    # Debug: Uncomment to verify patcher is working
                    # else:
                    #     print(f"DEBUG: Service detection failed for {record['name']}, got: {service}")
            except Exception:
                # Silently fail to avoid breaking logging
                pass

        # Patch modifies the logger in place - this applies to all loggers
        loguru_logger.patch(patcher)

    def _setup_console_handler(self) -> None:
        """Setup console logging handler"""
        loguru_logger.add(
            sys.stderr,
            level=self.config.root_level,
            format=self.config.format,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )

    def _setup_file_handlers(self) -> None:
        """
        Setup minimal file logging handlers as fallback
        
        Only logs errors to file when database is unavailable.
        This reduces file I/O overhead significantly.
        """
        # Ensure logs directory exists
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        # Only error log file for critical failures
        loguru_logger.add(
            self.config.files.errors,
            level="ERROR",
            format=self.config.format,
            rotation=self.config.rotation.size,
            retention=(
                self.config.retention.error_logs_retention
                if hasattr(self.config.retention, "error_logs_retention")
                else "90 days"
            ),
            compression="gz" if self.config.rotation.compression else None,
            enqueue=True,
            backtrace=True,
            diagnose=True,
            filter=lambda record: record["extra"].get("log_destination") == "file_fallback",
        )

    def _setup_service_handler(self, service_name: str) -> None:
        """Setup service-specific logging handler"""
        service_config = get_service_config(service_name, self.config)

        # Ensure logs directory exists
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        # Service-specific log file
        loguru_logger.add(
            service_config.file,
            level=service_config.level,
            format=self.config.format,
            rotation=self.config.rotation.size,
            retention=self.config.rotation.retention,
            compression="gz" if self.config.rotation.compression else None,
            enqueue=True,
            backtrace=True,
            diagnose=True,
            filter=lambda record: record["extra"].get("service") == service_name,
        )

    def _setup_database_handler(self) -> None:
        """
        Setup database logging handler with async queue-based batching
        
        This is the primary logging method - all logs go to database
        via an async queue for non-blocking writes.
        """
        try:
            # Initialize queue manager
            self._queue_manager = get_queue_manager(
                batch_size=self.config.database.batch_size,
                batch_timeout=self.config.database.batch_timeout,
                max_queue_size=10000,
            )

            # Create database sink function
            # This returns a callable that loguru will call with message objects
            self._database_sink = create_database_sink(
                queue_manager=self._queue_manager,
                fallback_to_file=self.config.database.fallback_to_file,
            )

            # Add database sink to loguru
            # When enqueue=True, loguru calls the sink function with message objects
            # The message object has a .record attribute with the log record
            # Type narrowing: _database_sink cannot be None after assignment above
            if self._database_sink is not None:
                loguru_logger.add(
                    self._database_sink,
                    level=self.config.level,
                    format=self.config.format,
                    enqueue=True,  # Loguru handles threading, passes message object to sink
                    backtrace=True,
                    diagnose=True,
                )

            loguru_logger.info("Database logging handler initialized")

        except Exception as e:
            loguru_logger.error(
                f"Failed to setup database logging handler: {e}. "
                "Falling back to file logging."
            )
            # If database setup fails, ensure file logging is enabled
            if not self.config.database.fallback_to_file:
                self._setup_file_handlers()

    def get_logger(self, module_name: str) -> Any:
        """
        Get logger for a specific module with automatic service detection

        Args:
            module_name: Full module name (e.g., '__main__' or
                'src.services.execution.order_manager')

        Returns:
            Logger: Configured logger instance
        """
        if not self._setup_complete:
            self.setup_logging()

        # Detect service from module name
        service_name = detect_service_from_module(module_name)

        # Create logger with service context
        logger = loguru_logger.bind(service=service_name)

        return logger

    def get_service_logger(self, service_name: str) -> Any:
        """
        Get logger for a specific service

        Args:
            service_name: Name of the service

        Returns:
            Logger: Configured logger instance
        """
        if not self._setup_complete:
            self.setup_logging(service_name)

        # Create logger with service context
        logger = loguru_logger.bind(service=service_name)

        return logger

    def shutdown(self) -> None:
        """Shutdown logging system and flush remaining logs"""
        if self._queue_manager:
            try:
                # Stop queue manager with shorter timeout for faster shutdown
                self._queue_manager.stop(timeout=5.0)
                loguru_logger.info("Logging system shutdown complete")
            except Exception as e:
                # Don't log errors during shutdown to avoid recursion
                print(f"Error during logging shutdown: {e}", file=sys.stderr)


# Global logging manager instance
_logging_manager = LoggingManager()


def setup_logging(
    config_path: Optional[str] = None, service_name: Optional[str] = None
) -> None:
    """
    Setup Loguru logging with file and database handlers

    Args:
        config_path: Path to YAML configuration file
        service_name: Optional service name for service-specific setup
    """
    global _logging_manager

    if config_path:
        _logging_manager = LoggingManager(load_logging_config(config_path))

    _logging_manager.setup_logging(service_name)


def get_logger(module_name: str) -> Any:
    """
    Get logger for a specific module with automatic service detection

    Args:
        module_name: Full module name (e.g., '__main__' or 'src.services.execution.order_manager')

    Returns:
        Logger: Configured logger instance
    """
    return _logging_manager.get_logger(module_name)


def get_service_logger(service_name: str) -> Any:
    """
    Get logger for a specific service

    Args:
        service_name: Name of the service

    Returns:
        Logger: Configured logger instance
    """
    return _logging_manager.get_service_logger(service_name)


def get_config() -> LoggingConfig:
    """
    Get current logging configuration

    Returns:
        LoggingConfig: Current configuration
    """
    return _logging_manager.config


def shutdown_logging() -> None:
    """Shutdown the logging system"""
    if _logging_manager:
        _logging_manager.shutdown()
    shutdown_queue_manager()
