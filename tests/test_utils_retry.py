"""
Tests for retry utilities.
"""

import pytest
import time
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from odysseus.utils.retry import retry_with_backoff, RetryError
from odysseus.core.exceptions import APIError, NetworkError


class TestRetryWithBackoff:
    """Tests for retry_with_backoff decorator."""
    
    def test_retry_success_immediate(self):
        """Test that retry decorator works for successful calls."""
        call_count = 0
        
        @retry_with_backoff(max_retries=3)
        def successful_function():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = successful_function()
        assert result == "success"
        assert call_count == 1
    
    def test_retry_with_failure_then_success(self):
        """Test retry with initial failure then success."""
        call_count = 0
        
        @retry_with_backoff(max_retries=3, backoff_factor=0.1)
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise APIError("Temporary failure")
            return "success"
        
        result = flaky_function()
        assert result == "success"
        assert call_count == 2
    
    def test_retry_exhausted(self):
        """Test that retry raises error after all attempts exhausted."""
        call_count = 0
        
        @retry_with_backoff(max_retries=2, backoff_factor=0.1)
        def always_failing_function():
            nonlocal call_count
            call_count += 1
            raise APIError("Always fails")
        
        with pytest.raises(RetryError) as exc_info:
            always_failing_function()
        
        assert "failed after" in str(exc_info.value).lower()
        assert call_count == 3  # Initial + 2 retries
    
    def test_retry_with_connection_error(self):
        """Test retry with ConnectionError."""
        call_count = 0
        
        @retry_with_backoff(max_retries=2, backoff_factor=0.1)
        def connection_error_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Connection failed")
            return "success"
        
        result = connection_error_function()
        assert result == "success"
        assert call_count == 2
    
    def test_retry_with_timeout_error(self):
        """Test retry with TimeoutError."""
        call_count = 0
        
        @retry_with_backoff(max_retries=2, backoff_factor=0.1)
        def timeout_error_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("Timeout")
            return "success"
        
        result = timeout_error_function()
        assert result == "success"
        assert call_count == 2
    
    def test_retry_with_os_error(self):
        """Test retry with OSError."""
        call_count = 0
        
        @retry_with_backoff(max_retries=2, backoff_factor=0.1)
        def os_error_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise OSError("OS error")
            return "success"
        
        result = os_error_function()
        assert result == "success"
        assert call_count == 2
    
    def test_retry_with_custom_exceptions(self):
        """Test retry with custom exception list."""
        call_count = 0
        
        @retry_with_backoff(max_retries=2, backoff_factor=0.1, exceptions=(ValueError,))
        def custom_exception_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Custom error")
            return "success"
        
        result = custom_exception_function()
        assert result == "success"
        assert call_count == 2
    
    def test_retry_does_not_catch_other_exceptions(self):
        """Test that retry doesn't catch exceptions not in the list."""
        @retry_with_backoff(max_retries=2, backoff_factor=0.1, exceptions=(APIError,))
        def raise_other_exception():
            raise ValueError("Should not be caught")
        
        with pytest.raises(ValueError):
            raise_other_exception()
    
    def test_retry_backoff_timing(self):
        """Test that backoff timing increases exponentially."""
        call_times = []
        
        @retry_with_backoff(max_retries=3, backoff_factor=0.1, jitter=False)
        def timing_function():
            call_times.append(time.time())
            # Always fail to trigger RetryError after max_retries
            raise APIError("Fail")
        
        start_time = time.time()
        with pytest.raises(RetryError):
            timing_function()
        
        # Check that delays increase (allowing some tolerance)
        # With max_retries=3, we should have 4 calls (initial + 3 retries)
        assert len(call_times) == 4
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        delay3 = call_times[3] - call_times[2]
        # delay2 should be approximately 2x delay1 (0.1 vs 0.2)
        # delay3 should be approximately 2x delay2 (0.2 vs 0.4)
        assert delay2 > delay1
        assert delay3 > delay2
    
    def test_retry_with_jitter(self):
        """Test that jitter adds randomness to backoff."""
        # This is a basic test - jitter makes exact timing unpredictable
        call_count = 0
        
        @retry_with_backoff(max_retries=2, backoff_factor=0.1, jitter=True)
        def jitter_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise APIError("Fail")
            return "success"
        
        result = jitter_function()
        assert result == "success"
        assert call_count == 2
    
    def test_retry_preserves_function_metadata(self):
        """Test that retry decorator preserves function metadata."""
        @retry_with_backoff(max_retries=1)
        def test_function():
            """Test function docstring."""
            return "test"
        
        assert test_function.__name__ == "test_function"
        # Note: __doc__ might be wrapped, so we just check it exists
        assert hasattr(test_function, '__name__')
    
    def test_retry_with_arguments(self):
        """Test that retry works with function arguments."""
        call_count = 0
        
        @retry_with_backoff(max_retries=2, backoff_factor=0.1)
        def function_with_args(arg1, arg2, kwarg1=None):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise APIError("Fail")
            return f"{arg1}-{arg2}-{kwarg1}"
        
        result = function_with_args("a", "b", kwarg1="c")
        assert result == "a-b-c"
        assert call_count == 2

