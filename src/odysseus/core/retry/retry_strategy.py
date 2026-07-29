"""
Base retry strategy interface.
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, Any
from dataclasses import dataclass
from enum import Enum


class RetryResult(Enum):
    """Result of a retry attempt."""
    SUCCESS = "success"
    RETRY = "retry"
    FAIL = "fail"


@dataclass
class RetryContext:
    """Context for retry operations."""
    attempt: int = 0
    max_attempts: int = 3
    last_exception: Optional[Exception] = None
    delay: float = 0.0


T = TypeVar('T')


class RetryStrategy(ABC, Generic[T]):
    """
    Base class for retry strategies.

    Subclasses should implement should_retry() and calculate_delay() methods.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 2.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: bool = True
    ):
        """
        Initialize retry strategy.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
            backoff_factor: Multiplier for exponential backoff
            jitter: Whether to add random jitter to delays
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter

    @abstractmethod
    def should_retry(self, context: RetryContext, exception: Exception) -> bool:
        """
        Determine if a retry should be attempted.

        Args:
            context: Retry context
            exception: The exception that occurred

        Returns:
            True if retry should be attempted, False otherwise
        """
        pass

    def calculate_delay(self, context: RetryContext) -> float:
        """
        Calculate delay before next retry attempt.

        Args:
            context: Retry context

        Returns:
            Delay in seconds
        """
        # Exponential backoff
        delay = min(
            self.base_delay * (self.backoff_factor ** context.attempt),
            self.max_delay
        )

        # Add jitter if enabled
        if self.jitter:
            import random
            jitter_amount = delay * 0.1  # 10% jitter
            delay += random.uniform(0, jitter_amount)

        return delay

    def execute(
        self,
        func: callable,
        *args,
        **kwargs
    ) -> T:
        """
        Execute a function with retry logic.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If all retries fail
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                context = RetryContext(
                    attempt=attempt,
                    max_attempts=self.max_retries,
                    last_exception=e
                )

                if attempt == self.max_retries or not self.should_retry(context, e):
                    raise

                delay = self.calculate_delay(context)
                context.delay = delay

                import time
                time.sleep(delay)

        # Should never reach here, but just in case
        if last_exception:
            raise last_exception
        raise Exception("Retry failed without exception")
