"""
Cache backend implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple
from datetime import datetime, timedelta
import threading


class CacheBackend(ABC):
    """Base class for cache backends."""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get cached value."""
        pass

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Set cached value."""
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete cached value."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all cached values."""
        pass

    @abstractmethod
    def size(self) -> int:
        """Get number of cached items."""
        pass

    def has(self, key: str) -> bool:
        """Return whether a non-expired key exists."""
        return self.get(key) is not None

    def get_stale(self, key: str, max_stale_seconds: int) -> Optional[Any]:
        """Return a recently expired value when supported by the backend."""
        return None


class TTLCache(CacheBackend):
    """
    Time-to-live cache backend.

    Stores values with expiration timestamps.
    Retains expired entries for bounded stale-if-error recovery.
    """

    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize TTL cache.

        Args:
            ttl_seconds: Time-to-live in seconds (default: 1 hour)
        """
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        self.ttl = timedelta(seconds=ttl_seconds)
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """
        Get cached value if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if expired/not found
        """
        with self._lock:
            if key not in self._cache:
                return None
            value, timestamp = self._cache[key]
            if datetime.now() - timestamp > self.ttl:
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        """
        Cache a value.

        Args:
            key: Cache key
            value: Value to cache
        """
        with self._lock:
            self._cache[key] = (value, datetime.now())

    def has(self, key: str) -> bool:
        """Return whether a key exists and has not expired."""
        with self._lock:
            if key not in self._cache:
                return False
            _, timestamp = self._cache[key]
            return datetime.now() - timestamp <= self.ttl

    def get_stale(self, key: str, max_stale_seconds: int) -> Optional[Any]:
        """Return an expired entry while it remains inside the stale window."""
        with self._lock:
            if key not in self._cache:
                return None
            value, timestamp = self._cache[key]
            age = datetime.now() - timestamp
            if age <= self.ttl:
                return value
            if age <= self.ttl + timedelta(seconds=max(0, max_stale_seconds)):
                return value
            return None

    def delete(self, key: str) -> None:
        """
        Delete cached value.

        Args:
            key: Cache key
        """
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cached values."""
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """Get number of cached items."""
        with self._lock:
            return len(self._cache)

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.

        Returns:
            Number of entries removed
        """
        with self._lock:
            now = datetime.now()
            expired_keys = [
                key for key, (_, timestamp) in self._cache.items()
                if now - timestamp > self.ttl
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)


class MemoryCache(CacheBackend):
    """
    Simple in-memory cache without TTL.

    Stores values indefinitely until explicitly deleted or cleared.
    """

    def __init__(self, max_size: Optional[int] = None):
        """
        Initialize memory cache.

        Args:
            max_size: Maximum number of items (None for unlimited)
        """
        self._cache: Dict[str, Any] = {}
        self.max_size = max_size
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """
        Get cached value.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        with self._lock:
            return self._cache.get(key)

    def set(self, key: str, value: Any) -> None:
        """
        Cache a value.

        Args:
            key: Cache key
            value: Value to cache
        """
        # Evict oldest if at max size
        with self._lock:
            if (
                self.max_size
                and key not in self._cache
                and len(self._cache) >= self.max_size
            ):
                first_key = next(iter(self._cache))
                del self._cache[first_key]
            self._cache[key] = value

    def has(self, key: str) -> bool:
        """Return whether a key exists, including keys cached with ``None``."""
        with self._lock:
            return key in self._cache

    def delete(self, key: str) -> None:
        """
        Delete cached value.

        Args:
            key: Cache key
        """
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cached values."""
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """Get number of cached items."""
        with self._lock:
            return len(self._cache)
