"""
Correlation ID management for tracking related operations
"""

import threading
import uuid
from contextlib import contextmanager
from typing import Any, Callable, Generator, Optional, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

# Thread-local storage for correlation IDs
_correlation_context = threading.local()


def generate_correlation_id() -> str:
    """
    Generate a new correlation ID

    Returns:
        str: New correlation ID
    """
    return str(uuid.uuid4())


def get_correlation_id() -> Optional[str]:
    """
    Get current correlation ID from thread-local storage

    Returns:
        Optional[str]: Current correlation ID or None
    """
    result = getattr(_correlation_context, "correlation_id", None)
    return str(result) if result is not None else None


def set_correlation_id(correlation_id: str) -> None:
    """
    Set correlation ID in thread-local storage

    Args:
        correlation_id: Correlation ID to set
    """
    _correlation_context.correlation_id = correlation_id


def clear_correlation_id() -> None:
    """
    Clear correlation ID from thread-local storage
    """
    if hasattr(_correlation_context, "correlation_id"):
        delattr(_correlation_context, "correlation_id")


@contextmanager
def correlation_context(
    correlation_id: Optional[str] = None,
) -> Generator[str, None, None]:
    """
    Context manager for correlation ID tracking

    Args:
        correlation_id: Optional correlation ID (generates new one if not provided)

    Yields:
        str: The correlation ID being used
    """
    # Generate new correlation ID if not provided
    if correlation_id is None:
        correlation_id = generate_correlation_id()

    # Store previous correlation ID
    previous_correlation_id = get_correlation_id()

    try:
        # Set new correlation ID
        set_correlation_id(correlation_id)
        yield correlation_id
    finally:
        # Restore previous correlation ID
        if previous_correlation_id is not None:
            set_correlation_id(previous_correlation_id)
        else:
            clear_correlation_id()


def with_correlation_id(correlation_id: str) -> Callable[[F], F]:
    """
    Decorator to add correlation ID to function calls

    Args:
        correlation_id: Correlation ID to use

    Returns:
        Decorator function
    """

    def decorator(func: F) -> F:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with correlation_context(correlation_id):
                return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def get_correlation_context() -> dict:
    """
    Get current correlation context

    Returns:
        dict: Current correlation context
    """
    correlation_id = get_correlation_id()
    if correlation_id:
        return {"correlation_id": correlation_id}
    return {}


def format_correlation_message(message: str) -> str:
    """
    Format message with correlation ID

    Args:
        message: Base message

    Returns:
        str: Message with correlation ID
    """
    correlation_id = get_correlation_id()
    if correlation_id:
        return f"[{correlation_id}] {message}"
    return message
