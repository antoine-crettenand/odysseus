"""
Retry utilities with exponential backoff for API calls and network operations.
"""

import time
import random
from typing import Callable, TypeVar, Optional, List, Type
from functools import wraps
from ..core.exceptions import APIError
from ..core.config import API_LIMITS

T = TypeVar('T')


class RetryError(Exception):
    """Exception raised when all retry attempts are exhausted."""
    pass


def retry_with_backoff(
    max_retries: Optional[int] = None,
    backoff_factor: Optional[float] = None,
    exceptions: Optional[tuple] = None,
    jitter: bool = True
):
    """
    Decorator for retrying a function with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for exponential backoff
        exceptions: Tuple of exceptions to catch and retry
        jitter: Whether to add random jitter to backoff time
        
    Returns:
        Decorated function
    """
    max_retries = max_retries or API_LIMITS["MAX_RETRIES"]
    backoff_factor = backoff_factor or API_LIMITS["BACKOFF_FACTOR"]
    exceptions = exceptions or (APIError, ConnectionError, TimeoutError, OSError)
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        # Last attempt failed
                        raise RetryError(
                            f"Function {func.__name__} failed after {max_retries + 1} attempts"
                        ) from e
                    
                    # Calculate backoff time (exponential: base * 2^attempt)
                    wait_time = backoff_factor * (2 ** attempt)
                    
                    # Add jitter to prevent thundering herd
                    if jitter:
                        wait_time += random.uniform(0, wait_time * 0.1)
                    
                    time.sleep(wait_time)
                    
            # Should never reach here, but just in case
            raise RetryError(
                f"Function {func.__name__} failed after {max_retries + 1} attempts"
            ) from last_exception
        
        return wrapper
    return decorator


class NetworkError(ConnectionError):
    """Exception for network-related errors."""
    pass

