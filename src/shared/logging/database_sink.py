"""
Database sink for loguru that properly handles log records

This module implements a proper loguru sink that receives log records
and enqueues them for async database writing.
"""

import sys
from typing import Any, Callable
from uuid import uuid4

from .database_handler import LogQueueManager
from .formatters import format_for_database


class DatabaseSink:
    """
    Loguru sink class that writes logs to database via async queue
    
    Implements both write() and __call__() methods to work with
    different loguru configurations.
    """

    def __init__(self, queue_manager: LogQueueManager, fallback_to_file: bool = True):
        self.queue_manager = queue_manager
        self.fallback_to_file = fallback_to_file
        self._error_count = 0
        self._call_count = 0

    def write(self, message: Any) -> None:
        """Write method called by loguru"""
        self._process_message(message)

    def __call__(self, message: Any) -> None:
        """Callable interface for loguru"""
        self._process_message(message)

    def _process_message(self, message: Any) -> None:
        """Process log message and enqueue to database"""
        # Track calls for statistics (debug output removed for production)
        self._call_count += 1

        try:
            # Try to access record from message object
            # When enqueue=True, loguru passes a message object with .record
            record = None
            if hasattr(message, "record"):
                record = message.record
            elif isinstance(message, dict):
                # If message is already a dict, use it directly
                record = message
            else:
                # Unknown format - skip
                if self._error_count == 0:
                    print(
                        f"WARNING: Unknown message format: {type(message)}",
                        file=sys.stderr
                    )
                self._error_count += 1
                return

            # Build record dict for format_for_database
            # Loguru records support dict-like access
            record_dict = {
                "time": record["time"],
                "level": record["level"],
                "message": record["message"],
                "name": record["name"],
                "function": record["function"],
                "line": record["line"],
                "extra": record["extra"],
                "exception": record.get("exception"),
            }

            # Format record for database
            db_record = format_for_database(record_dict)
            
            # Enqueue for async processing
            if self.queue_manager:
                success = self.queue_manager.enqueue_log(db_record)

                # If queue is full, try to mark for file fallback
                if not success and self.fallback_to_file:
                    try:
                        record["extra"]["log_destination"] = "file_fallback"
                    except (KeyError, TypeError):
                        pass
            else:
                # Queue manager not available - this shouldn't happen
                if self._error_count == 0:
                    print(
                        "WARNING: Database sink queue manager not available",
                        file=sys.stderr
                    )
                self._error_count += 1

        except Exception as e:
            # Silently handle errors to avoid recursion
            # Only log first few errors for debugging
            self._error_count += 1
            if self._error_count <= 3:
                import traceback
                print(
                    f"Database sink error #{self._error_count}: {type(e).__name__}: {e}",
                    file=sys.stderr
                )
                if self._error_count == 1:
                    # Debug info for first error
                    try:
                        print(
                            f"  Message type: {type(message)}, "
                            f"Has record: {hasattr(message, 'record')}",
                            file=sys.stderr
                        )
                        if hasattr(message, "record"):
                            print(
                                f"  Record type: {type(message.record)}",
                                file=sys.stderr
                            )
                        print(
                            f"  Traceback: {traceback.format_exc()}",
                            file=sys.stderr
                        )
                    except Exception:
                        pass


def create_database_sink(
    queue_manager: LogQueueManager, fallback_to_file: bool = True
) -> DatabaseSink:
    """
    Create a database sink for loguru
    
    Returns a DatabaseSink instance that implements both write() and __call__()
    methods to work with different loguru configurations.

    Args:
        queue_manager: Queue manager for async log processing
        fallback_to_file: Whether to fallback to file if queue is full

    Returns:
        DatabaseSink instance that receives loguru message objects
    """
    return DatabaseSink(queue_manager, fallback_to_file)

