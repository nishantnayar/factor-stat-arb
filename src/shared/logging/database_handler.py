"""
Database logging handler with async queue-based batching

This module provides efficient database logging by:
- Using a queue-based system for non-blocking writes
- Batching log entries for efficient database inserts
- Automatic fallback to file logging if database fails
- Thread-safe operations
"""

import queue
import sys
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from loguru import logger as loguru_logger
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.config.database import get_engine, get_service_engine
from src.shared.database.base import db_transaction
from src.shared.database.models.logging_models import PerformanceLog, SystemLog
from src.shared.logging.formatters import format_for_database
from src.shared.utils.timezone import ensure_utc_timestamp


class LogQueueManager:
    """
    Manages async queue-based logging with batch writes
    
    Features:
    - Non-blocking log writes via queue
    - Automatic batching for efficient database inserts
    - Thread-safe operations
    - Graceful shutdown
    """

    def __init__(
        self,
        batch_size: int = 100,
        batch_timeout: float = 10.0,
        max_queue_size: int = 10000,
    ):
        """
        Initialize the log queue manager

        Args:
            batch_size: Number of logs to batch before writing
            batch_timeout: Maximum seconds to wait before flushing batch
            max_queue_size: Maximum queue size before blocking
        """
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.max_queue_size = max_queue_size

        # Queue for log entries
        self.log_queue: queue.Queue = queue.Queue(maxsize=max_queue_size)

        # Batch buffer
        self.batch_buffer: List[Dict[str, Any]] = []
        self.batch_lock = threading.Lock()
        self.last_flush_time = time.time()

        # Worker thread
        self.worker_thread: Optional[threading.Thread] = None
        self.running = False
        self.shutdown_event = threading.Event()

        # Statistics
        self.stats = {
            "logs_queued": 0,
            "logs_written": 0,
            "batches_written": 0,
            "errors": 0,
        }

    def start(self) -> None:
        """Start the background worker thread"""
        if self.running:
            return

        self.running = True
        self.shutdown_event.clear()
        self.worker_thread = threading.Thread(
            target=self._worker_loop, daemon=True, name="LogQueueWorker"
        )
        self.worker_thread.start()
        loguru_logger.info("Log queue manager started")

    def stop(self, timeout: float = 5.0) -> None:
        """
        Stop the worker thread and flush remaining logs

        Args:
            timeout: Maximum seconds to wait for shutdown
        """
        if not self.running:
            return

        # Use print to avoid logging during shutdown (which could cause recursion)
        print("Stopping log queue manager...", file=sys.stderr)
        self.running = False
        self.shutdown_event.set()

        # Wait for worker thread to finish processing
        if self.worker_thread and self.worker_thread.is_alive():
            # Give worker thread time to process remaining items
            self.worker_thread.join(timeout=timeout)
            
            if self.worker_thread.is_alive():
                print(
                    f"WARNING: Log queue worker thread did not stop within {timeout}s timeout",
                    file=sys.stderr
                )
                # Force flush any remaining items
                self._flush_batch()
        
        # Flush any remaining items in queue (safety net)
        remaining = []
        try:
            while not self.log_queue.empty():
                try:
                    remaining.append(self.log_queue.get_nowait())
                except queue.Empty:
                    break
        except Exception as e:
            print(f"Error getting remaining logs from queue: {e}", file=sys.stderr)
        
        if remaining:
            print(f"Flushing {len(remaining)} remaining logs from queue", file=sys.stderr)
            try:
                self._write_batch_to_database(remaining)
                self.stats["logs_written"] += len(remaining)
                self.stats["batches_written"] += 1
            except Exception as e:
                print(f"Error flushing remaining logs: {e}", file=sys.stderr)

        # Final flush of batch buffer
        self._flush_batch()

        print(
            f"Log queue manager stopped. Stats: {self.stats}",
            file=sys.stderr
        )

    def enqueue_log(self, log_record: Dict[str, Any]) -> bool:
        """
        Enqueue a log record for async processing

        Args:
            log_record: Formatted log record dictionary

        Returns:
            True if successfully queued, False otherwise
        """
        try:
            self.log_queue.put_nowait(log_record)
            self.stats["logs_queued"] += 1
            # Debug: log first few entries to verify they're being queued
            if self.stats["logs_queued"] <= 3:
                loguru_logger.debug(
                    f"Enqueued log #{self.stats['logs_queued']}: {log_record.get('message', 'N/A')[:50]}"
                )
            return True
        except queue.Full:
            # Queue is full, log to stderr as fallback
            loguru_logger.error(
                f"Log queue is full! Dropping log: {log_record.get('message', 'N/A')}"
            )
            self.stats["errors"] += 1
            return False

    def _worker_loop(self) -> None:
        """Main worker loop that processes log queue"""
        while self.running or not self.log_queue.empty():
            try:
                # Try to get a log entry with timeout
                try:
                    # Use shorter timeout when shutting down
                    timeout = 0.1 if not self.running else 1.0
                    log_record = self.log_queue.get(timeout=timeout)
                except queue.Empty:
                    # Check if we should flush batch due to timeout
                    if self._should_flush_batch():
                        self._flush_batch()
                    # If shutting down and queue is empty, check batch buffer and exit
                    if not self.running:
                        self._flush_batch()
                        # Check if batch buffer is empty (need lock)
                        with self.batch_lock:
                            batch_empty = len(self.batch_buffer) == 0
                        if self.log_queue.empty() and batch_empty:
                            break
                    continue

                # Add to batch buffer
                batch_full = False
                with self.batch_lock:
                    self.batch_buffer.append(log_record)
                    batch_full = len(self.batch_buffer) >= self.batch_size
                
                # Flush outside lock if batch is full
                if batch_full:
                    self._flush_batch()

            except Exception as e:
                # Use print to avoid recursion during shutdown
                if self.running:
                    try:
                        loguru_logger.error(f"Error in log queue worker: {e}")
                    except Exception:
                        print(f"Error in log queue worker: {e}", file=sys.stderr)
                self.stats["errors"] += 1
                # Don't sleep if shutting down
                if self.running:
                    time.sleep(0.1)

        # Final flush on shutdown
        self._flush_batch()

    def _should_flush_batch(self) -> bool:
        """Check if batch should be flushed due to timeout"""
        if not self.batch_buffer:
            return False

        elapsed = time.time() - self.last_flush_time
        return elapsed >= self.batch_timeout

    def _flush_batch(self) -> None:
        """Flush current batch to database"""
        with self.batch_lock:
            if not self.batch_buffer:
                return

            batch = self.batch_buffer.copy()
            self.batch_buffer.clear()
            self.last_flush_time = time.time()

        if not batch:
            return

        try:
            self._write_batch_to_database(batch)
            self.stats["logs_written"] += len(batch)
            self.stats["batches_written"] += 1
        except Exception as e:
            loguru_logger.error(f"Error writing log batch to database: {e}")
            self.stats["errors"] += 1
            # Fallback: write to file if database fails
            self._fallback_to_file(batch)

    def _write_batch_to_database(self, batch: List[Dict[str, Any]]) -> None:
        """
        Write batch of logs to database using bulk insert

        Args:
            batch: List of log record dictionaries
        """
        try:
            # Use logging schema engine for proper schema access
            engine = get_service_engine("logging")
            from sqlalchemy.orm import sessionmaker
            SessionLocal = sessionmaker(bind=engine)
            session = SessionLocal()

            try:
                system_logs = []
                performance_logs = []

                for record in batch:
                    log_type = record.get("log_type", "system")

                    if log_type == "performance":
                        perf_log = self._create_performance_log(record)
                        if perf_log:
                            performance_logs.append(perf_log)
                    else:
                        sys_log = self._create_system_log(record)
                        if sys_log:
                            system_logs.append(sys_log)

                # Add system logs to session (using add_all for better JSONB handling)
                if system_logs:
                    session.add_all(system_logs)
                    session.flush()
                    loguru_logger.debug(f"Flushed {len(system_logs)} system logs to session")

                # Add performance logs to session
                if performance_logs:
                    session.add_all(performance_logs)
                    session.flush()
                    loguru_logger.debug(f"Flushed {len(performance_logs)} performance logs to session")

                # Commit the transaction
                session.commit()
                total_written = len(system_logs) + len(performance_logs)
                if total_written > 0:
                    loguru_logger.info(
                        f"Successfully wrote {len(system_logs)} system logs and "
                        f"{len(performance_logs)} performance logs to database"
                    )

            except Exception as e:
                session.rollback()
                loguru_logger.error(f"Error in database transaction, rolling back: {e}", exc_info=True)
                raise
            finally:
                session.close()

        except SQLAlchemyError as e:
            loguru_logger.error(f"Database error writing logs: {e}", exc_info=True)
            raise
        except Exception as e:
            loguru_logger.error(f"Unexpected error writing logs: {e}", exc_info=True)
            raise

    def _create_system_log(self, record: Dict[str, Any]) -> Optional[SystemLog]:
        """Create SystemLog model from record"""
        try:
            timestamp = record.get("timestamp")
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            elif timestamp is None:
                timestamp = ensure_utc_timestamp(datetime.now())
            elif isinstance(timestamp, datetime):
                timestamp = ensure_utc_timestamp(timestamp)
            else:
                timestamp = ensure_utc_timestamp(datetime.now())

            # Get metadata/data - format_for_database returns "metadata" key
            data = record.get("metadata", {})
            if not isinstance(data, dict):
                data = {}
            
            # data is now guaranteed to be a dict (not None) after the check above

            # Get values from formatted record (format_for_database already handles fallbacks)
            service = record.get("service", "unknown")
            correlation_id = record.get("correlation_id")  # Can be None
            event_type = record.get("event_type")  # Can be None
            
            return SystemLog(
                service=service,
                level=record.get("level", "INFO"),
                message=record.get("message", ""),
                data=data,
                correlation_id=correlation_id,  # None is allowed (nullable field)
                event_type=event_type,  # None is allowed (nullable field)
                timestamp=timestamp,
            )
        except Exception as e:
            loguru_logger.error(f"Error creating system log: {e}")
            return None

    def _create_performance_log(
        self, record: Dict[str, Any]
    ) -> Optional[PerformanceLog]:
        """Create PerformanceLog model from record"""
        try:
            timestamp = record.get("timestamp")
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            elif timestamp is None:
                timestamp = ensure_utc_timestamp(datetime.now())
            elif isinstance(timestamp, datetime):
                timestamp = ensure_utc_timestamp(timestamp)
            else:
                timestamp = ensure_utc_timestamp(datetime.now())

            # For performance logs, metadata might contain the performance metrics
            metadata = record.get("metadata", {})
            if isinstance(metadata, dict):
                operation = record.get("operation") or metadata.get("operation", "unknown")
                execution_time_ms = record.get("execution_time_ms") or metadata.get("execution_time_ms", 0)
                memory_usage_mb = record.get("memory_usage_mb") or metadata.get("memory_usage_mb")
                cpu_usage_percent = record.get("cpu_usage_percent") or metadata.get("cpu_usage_percent")
            else:
                operation = record.get("operation", "unknown")
                execution_time_ms = record.get("execution_time_ms", 0)
                memory_usage_mb = record.get("memory_usage_mb")
                cpu_usage_percent = record.get("cpu_usage_percent")

            return PerformanceLog(
                service=record.get("service", "unknown"),
                operation=operation,
                execution_time_ms=float(execution_time_ms),
                memory_usage_mb=float(memory_usage_mb) if memory_usage_mb is not None else None,
                cpu_usage_percent=float(cpu_usage_percent) if cpu_usage_percent is not None else None,
                timestamp=timestamp,
            )
        except Exception as e:
            loguru_logger.error(f"Error creating performance log: {e}")
            return None

    def _fallback_to_file(self, batch: List[Dict[str, Any]]) -> None:
        """
        Fallback to file logging if database fails

        Args:
            batch: List of log records to write to file
        """
        for record in batch:
            try:
                level = record.get("level", "INFO").lower()
                message = record.get("message", "")
                service = record.get("service", "unknown")

                log_message = f"[{service}] {message}"

                if level == "error":
                    loguru_logger.error(log_message)
                elif level == "warning":
                    loguru_logger.warning(log_message)
                elif level == "debug":
                    loguru_logger.debug(log_message)
                else:
                    loguru_logger.info(log_message)
            except Exception as e:
                loguru_logger.error(f"Error in fallback file logging: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics"""
        return self.stats.copy()


# Global queue manager instance
_queue_manager: Optional[LogQueueManager] = None
_queue_manager_lock = threading.Lock()


def get_queue_manager(
    batch_size: int = 100,
    batch_timeout: float = 10.0,
    max_queue_size: int = 10000,
) -> LogQueueManager:
    """
    Get or create the global log queue manager

    Args:
        batch_size: Number of logs to batch before writing
        batch_timeout: Maximum seconds to wait before flushing batch
        max_queue_size: Maximum queue size before blocking

    Returns:
        LogQueueManager instance
    """
    global _queue_manager

    with _queue_manager_lock:
        if _queue_manager is None:
            _queue_manager = LogQueueManager(
                batch_size=batch_size,
                batch_timeout=batch_timeout,
                max_queue_size=max_queue_size,
            )
            _queue_manager.start()

        return _queue_manager


def shutdown_queue_manager() -> None:
    """Shutdown the global queue manager"""
    global _queue_manager

    with _queue_manager_lock:
        if _queue_manager is not None:
            _queue_manager.stop()
            _queue_manager = None

