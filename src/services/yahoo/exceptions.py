"""
Yahoo Finance API Exceptions

Custom exception classes for Yahoo Finance data operations.
"""


class YahooAPIError(Exception):
    """Base exception for Yahoo Finance API errors"""

    pass


class YahooConnectionError(YahooAPIError):
    """Exception raised for connection errors to Yahoo Finance"""

    pass


class YahooAuthenticationError(YahooAPIError):
    """Exception raised for authentication errors (not typically used for Yahoo)"""

    pass


class YahooDataError(YahooAPIError):
    """Exception raised when data is missing or invalid"""

    pass


class YahooRateLimitError(YahooAPIError):
    """Exception raised when rate limits are exceeded"""

    pass


class YahooSymbolNotFoundError(YahooDataError):
    """Exception raised when a symbol is not found"""

    pass


class YahooDataQualityError(YahooDataError):
    """Exception raised when data quality issues are detected"""

    pass
