"""
Alpaca API Exceptions
"""


class AlpacaAPIError(Exception):
    """Base exception for Alpaca API errors"""

    pass


class AlpacaConnectionError(AlpacaAPIError):
    """Exception raised when connection to Alpaca API fails"""

    pass


class AlpacaAuthenticationError(AlpacaAPIError):
    """Exception raised when authentication with Alpaca API fails"""

    pass


class AlpacaRateLimitError(AlpacaAPIError):
    """Exception raised when rate limit is exceeded"""

    pass
