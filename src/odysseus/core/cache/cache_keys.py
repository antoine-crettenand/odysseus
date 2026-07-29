"""
Cache key generation utilities.
"""

import hashlib
import json
from typing import Any


def generate_cache_key(*args, **kwargs) -> str:
    """
    Generate cache key from arguments.

    Creates a SHA256 hash of serialized arguments for consistent key generation.

    Args:
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        SHA256 hash string

    Example:
        >>> key = generate_cache_key("search", artist="Beatles", album="Abbey Road")
        >>> key
        'a1b2c3d4e5f6...'
    """
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.sha256(key_data.encode()).hexdigest()


def generate_simple_key(*parts: str) -> str:
    """
    Generate a simple cache key from string parts.

    Args:
        *parts: String parts to combine

    Returns:
        Combined key string

    Example:
        >>> key = generate_simple_key("cover_art", "mbid", "12345")
        >>> key
        'cover_art:mbid:12345'
    """
    return ":".join(str(part) for part in parts)
