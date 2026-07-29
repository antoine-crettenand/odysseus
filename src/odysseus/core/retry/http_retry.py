"""
HTTP-specific retry strategy.
"""

import requests
from typing import Set, Optional
from .retry_strategy import RetryStrategy, RetryContext


class HttpRetryStrategy(RetryStrategy):
    """
    Retry strategy for HTTP requests.

    Handles:
    - Transient network errors (connection, timeout)
    - HTTP 5xx errors (server errors)
    - Rate limiting (429)
    - SSL errors (transient)
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 2.0,
        max_delay: float = 60.0,
        retryable_status_codes: Optional[Set[int]] = None,
        retry_on_ssl_error: bool = True
    ):
        """
        Initialize HTTP retry strategy.

        Args:
            max_retries: Maximum retry attempts
            base_delay: Base delay between retries
            max_delay: Maximum delay between retries
            retryable_status_codes: Set of HTTP status codes to retry on
            retry_on_ssl_error: Whether to retry on SSL errors
        """
        super().__init__(max_retries, base_delay, max_delay)
        self.retryable_status_codes = retryable_status_codes or {
            408,
            425,
            429,
            500,
            502,
            503,
            504,
        }
        self.retry_on_ssl_error = retry_on_ssl_error

    def should_retry(self, context: RetryContext, exception: Exception) -> bool:
        """
        Determine if HTTP request should be retried.

        Args:
            context: Retry context
            exception: The exception that occurred

        Returns:
            True if retry should be attempted
        """
        # HTTP errors
        if isinstance(exception, requests.exceptions.HTTPError):
            if hasattr(exception, 'response') and exception.response is not None:
                status_code = exception.response.status_code
                return status_code in self.retryable_status_codes

        # Connection errors - always retry
        if isinstance(exception, requests.exceptions.ConnectionError):
            return True

        # Timeout errors - always retry
        if isinstance(exception, requests.exceptions.Timeout):
            return True

        # SSL errors - retry if enabled and transient
        if isinstance(exception, requests.exceptions.SSLError):
            if not self.retry_on_ssl_error:
                return False
            # Check if transient SSL error
            error_str = str(exception).lower()
            is_transient = any(x in error_str for x in ['eof', 'unexpected_eof', 'connection'])
            return is_transient

        # Request exceptions - retry
        if isinstance(exception, requests.exceptions.RequestException):
            return True

        return False

    def calculate_delay(self, context: RetryContext) -> float:
        """
        Calculate delay with special handling for rate limiting.

        Args:
            context: Retry context

        Returns:
            Delay in seconds
        """
        # Check if last exception was rate limiting
        if context.last_exception:
            if isinstance(context.last_exception, requests.exceptions.HTTPError):
                if (
                    hasattr(context.last_exception, "response")
                    and context.last_exception.response is not None
                ):
                    if context.last_exception.response.status_code == 429:
                        # Use Retry-After header if available
                        retry_after = context.last_exception.response.headers.get('Retry-After')
                        if retry_after:
                            try:
                                return float(retry_after)
                            except ValueError:
                                pass
                        # Default to longer delay for rate limiting
                        return max(self.base_delay * 5, 60.0)

        return super().calculate_delay(context)
