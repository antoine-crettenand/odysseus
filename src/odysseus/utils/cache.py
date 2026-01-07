"""
Caching utilities for API responses.
"""
from functools import lru_cache
from typing import Dict, Any, Optional, TypeVar
from datetime import datetime, timedelta
import hashlib
import json

T = TypeVar('T')


class TTLCache:
    """Time-to-live cache for API responses."""
    
    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize TTL cache.
        
        Args:
            ttl_seconds: Time-to-live in seconds (default: 1 hour)
        """
        self._cache: Dict[str, tuple[Any, datetime]] = {}
        self.ttl = timedelta(seconds=ttl_seconds)
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get cached value if not expired.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if expired/not found
        """
        if key not in self._cache:
            return None
        
        value, timestamp = self._cache[key]
        if datetime.now() - timestamp > self.ttl:
            del self._cache[key]
            return None
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """
        Cache a value.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        self._cache[key] = (value, datetime.now())
    
    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()
    
    def size(self) -> int:
        """Get number of cached items."""
        return len(self._cache)


def cache_key(*args, **kwargs) -> str:
    """
    Generate cache key from arguments.
    
    Args:
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        SHA256 hash of serialized arguments
    """
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.sha256(key_data.encode()).hexdigest()


# Global cache instances
_search_cache = TTLCache(ttl_seconds=3600)  # 1 hour TTL for searches
_release_info_cache = TTLCache(ttl_seconds=7200)  # 2 hour TTL for release info


def get_search_cache() -> TTLCache:
    """Get the global search cache instance."""
    return _search_cache


def get_release_info_cache() -> TTLCache:
    """Get the global release info cache instance."""
    return _release_info_cache


def clear_all_caches() -> None:
    """Clear all global caches."""
    _search_cache.clear()
    _release_info_cache.clear()

