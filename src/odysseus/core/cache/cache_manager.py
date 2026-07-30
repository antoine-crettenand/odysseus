"""
Central cache manager for Odysseus.
Manages multiple cache instances with different TTLs and backends.
"""

from typing import Dict, Optional
import threading
from .cache_backends import CacheBackend, TTLCache, MemoryCache
from ..config import CACHE_CONFIG


class CacheManager:
    """
    Central cache manager.

    Manages multiple named caches with different configurations.
    Provides a unified interface for caching across the application.
    """

    # Default TTL configurations (sourced from CACHE_CONFIG)
    DEFAULT_TTL_SEARCH = CACHE_CONFIG["SEARCH_TTL"]
    DEFAULT_TTL_RELEASE_INFO = CACHE_CONFIG["RELEASE_INFO_TTL"]
    DEFAULT_TTL_COVER_ART = CACHE_CONFIG["COVER_ART_TTL"]

    def __init__(self):
        """Initialize cache manager."""
        self._caches: Dict[str, CacheBackend] = {}
        self._lock = threading.RLock()
        self._default_ttls: Dict[str, int] = {
            "search": self.DEFAULT_TTL_SEARCH,
            "release_info": self.DEFAULT_TTL_RELEASE_INFO,
            "cover_art": self.DEFAULT_TTL_COVER_ART,
            "default": CACHE_CONFIG["DEFAULT_TTL"],
        }

    def get_cache(
        self,
        name: str,
        ttl_seconds: Optional[int] = None,
        backend: str = "ttl"
    ) -> CacheBackend:
        """
        Get or create a cache instance.

        Args:
            name: Cache name
            ttl_seconds: Optional TTL override (uses default if None)
            backend: Backend type ("ttl" or "memory")

        Returns:
            Cache backend instance
        """
        # Use default TTL if not specified
        with self._lock:
            if ttl_seconds is None:
                ttl_seconds = self._default_ttls.get(name, self.DEFAULT_TTL_SEARCH)
            if name not in self._caches:
                if backend == "memory":
                    self._caches[name] = MemoryCache()
                else:
                    self._caches[name] = TTLCache(ttl_seconds=ttl_seconds)
            return self._caches[name]

    def register_cache(self, name: str, cache: CacheBackend) -> None:
        """
        Register a custom cache instance.

        Args:
            name: Cache name
            cache: Cache backend instance
        """
        with self._lock:
            self._caches[name] = cache

    def clear_cache(self, name: str) -> None:
        """
        Clear a specific cache.

        Args:
            name: Cache name
        """
        with self._lock:
            cache = self._caches.get(name)
        if cache:
            cache.clear()

    def clear_all(self) -> None:
        """Clear all caches."""
        with self._lock:
            caches = list(self._caches.values())
        for cache in caches:
            cache.clear()

    def delete_cache(self, name: str) -> None:
        """
        Delete a cache instance.

        Args:
            name: Cache name
        """
        with self._lock:
            self._caches.pop(name, None)

    def get_cache_size(self, name: str) -> int:
        """
        Get size of a cache.

        Args:
            name: Cache name

        Returns:
            Number of items in cache
        """
        with self._lock:
            cache = self._caches.get(name)
        return cache.size() if cache else 0

    def cleanup_expired(self, name: Optional[str] = None) -> int:
        """
        Clean up expired entries.

        Args:
            name: Optional cache name (cleans all if None)

        Returns:
            Number of entries removed
        """
        total_removed = 0

        if name:
            with self._lock:
                cache = self._caches.get(name)
            if isinstance(cache, TTLCache):
                total_removed = cache.cleanup_expired()
        else:
            with self._lock:
                caches = list(self._caches.values())
            for cache in caches:
                if isinstance(cache, TTLCache):
                    total_removed += cache.cleanup_expired()

        return total_removed


# Global cache manager instance
_global_cache_manager: Optional[CacheManager] = None
_global_cache_manager_lock = threading.Lock()


def get_global_cache_manager() -> CacheManager:
    """Get global cache manager instance."""
    global _global_cache_manager
    if _global_cache_manager is None:
        with _global_cache_manager_lock:
            if _global_cache_manager is None:
                _global_cache_manager = CacheManager()
    return _global_cache_manager
