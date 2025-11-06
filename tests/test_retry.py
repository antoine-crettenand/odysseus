"""
Tests for retry utilities.
"""

import pytest
import time
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from odysseus.utils.retry import retry_with_backoff, RetryError
from odysseus.core.exceptions import APIError


def test_retry_success():
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


def test_retry_with_failure_then_success():
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


def test_retry_exhausted():
    """Test that retry raises error after all attempts exhausted."""
    call_count = 0
    
    @retry_with_backoff(max_retries=2, backoff_factor=0.1)
    def always_failing_function():
        nonlocal call_count
        call_count += 1
        raise APIError("Always fails")
    
    with pytest.raises(RetryError):
        always_failing_function()
    
    assert call_count == 3  # Initial + 2 retries

