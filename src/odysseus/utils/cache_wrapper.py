"""
Cache wrapper utility for unified cache access.
Handles both cache manager backends and local dict caches.
"""

from typing import Dict, Optional, Any, Union, Callable
from ..core.cache.cache_backends import CacheBackend


class CacheWrapper:
    """
    Generic cache wrapper that handles both cache manager backends and local dict caches.
    Provides a unified interface for cache operations.
    """

    def __init__(
        self,
        cache_backend: Optional[CacheBackend] = None,
        local_cache: Optional[Dict] = None,
        key_converter: Optional[Callable[[Any], str]] = None
    ):
        """
        Initialize cache wrapper.

        Args:
            cache_backend: Optional cache backend from cache manager
            local_cache: Optional local dict cache (fallback)
            key_converter: Optional function to convert keys (e.g., tuple to string)
        """
        self.cache_backend = cache_backend
        self.local_cache = local_cache if local_cache is not None else {}
        self.use_cache_manager = cache_backend is not None
        self.key_converter = key_converter

    def _normalize_key(self, key: Any) -> Union[str, Any]:
        """Normalize key for cache backend (convert if needed)."""
        if self.key_converter:
            return self.key_converter(key)
        return key

    def get(self, key: Any) -> Optional[Any]:
        """Get value from cache."""
        if self.use_cache_manager:
            normalized_key = self._normalize_key(key)
            return self.cache_backend.get(normalized_key)
        return self.local_cache.get(key)

    def set(self, key: Any, value: Optional[Any]) -> None:
        """Set value in cache."""
        if self.use_cache_manager:
            normalized_key = self._normalize_key(key)
            self.cache_backend.set(normalized_key, value)
        else:
            self.local_cache[key] = value

    def has(self, key: Any) -> bool:
        """Check if key exists in cache."""
        if self.use_cache_manager:
            normalized_key = self._normalize_key(key)
            return self.cache_backend.has(normalized_key)
        return key in self.local_cache

    def delete(self, key: Any) -> None:
        """Delete value from cache."""
        if self.use_cache_manager:
            normalized_key = self._normalize_key(key)
            if hasattr(self.cache_backend, 'delete'):
                self.cache_backend.delete(normalized_key)
        elif key in self.local_cache:
            del self.local_cache[key]
