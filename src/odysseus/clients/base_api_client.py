"""
Base API Client Module
Provides common functionality for API clients like MusicBrainz and Discogs.
"""

import threading
import weakref
from typing import Dict, List, Optional, Any, Callable, Tuple
from ..core.cache.cache_keys import generate_cache_key


class BaseAPIClient:
    """Base class for API clients (MusicBrainz, Discogs)."""

    def __init__(self, config: Dict[str, Any], cache_manager=None, http_client=None):
        """
        Initialize base API client.

        Args:
            config: Configuration dictionary with BASE_URL, USER_AGENT, REQUEST_DELAY, MAX_RESULTS, TIMEOUT
            cache_manager: Optional CacheManager instance (will use global if not provided)
            http_client: Optional HttpClient instance (will use global if not provided)
        """
        self.base_url = config["BASE_URL"]
        self.user_agent = config["USER_AGENT"]
        self.request_delay = config["REQUEST_DELAY"]
        self.max_results = config["MAX_RESULTS"]
        self.timeout = config["TIMEOUT"]

        # Initialize cache manager
        if cache_manager is None:
            from ..core.cache.cache_manager import get_global_cache_manager
            cache_manager = get_global_cache_manager()
        self.cache_manager = cache_manager

        # Initialize HTTP client
        if http_client is None:
            from ..core.http.http_client import HttpClient
            from ..core.http.session_manager import SessionManager
            from .network_agent import NetworkAgent
            self.network_agent = NetworkAgent(self.user_agent)
            http_client = HttpClient(
                session_manager=SessionManager(network_agent=self.network_agent),
                network_agent=self.network_agent,
                default_timeout=self.timeout,
                default_request_delay=self.request_delay
            )
        else:
            # Extract network_agent from http_client if available
            self.network_agent = getattr(http_client, 'network_agent', None)
            if self.network_agent is None:
                from .network_agent import NetworkAgent
                self.network_agent = NetworkAgent(self.user_agent)
        self.http_client = http_client
        self._cache_fetch_locks = weakref.WeakValueDictionary()
        self._cache_fetch_locks_guard = threading.Lock()

    def _get_cache_fetch_lock(self, cache_name: str, cache_key: str) -> threading.Lock:
        """Coalesce simultaneous identical cache misses into one upstream call."""
        lock_key = (cache_name, cache_key)
        with self._cache_fetch_locks_guard:
            lock = self._cache_fetch_locks.get(lock_key)
            if lock is None:
                lock = threading.Lock()
                self._cache_fetch_locks[lock_key] = lock
            return lock

    def _format_progress_message(self, message: str, batch_progress: Optional[Tuple[int, int]] = None) -> str:
        """Format message with optional batch progress prefix."""
        if batch_progress:
            return f"[{batch_progress[0]}/{batch_progress[1]}] {message}"
        return message

    def _make_request_json(self, url: str, params: Dict[str, Any], batch_progress: Optional[Tuple[int, int]] = None,
                          reduced_retries: bool = False, log_callback: Optional[Callable[[str, bool], None]] = None,
                          rate_limit_wait: int = 60, session_name: str = "default") -> Optional[Dict[str, Any]]:
        """
        Make a JSON request using HttpClient.

        Args:
            url: Request URL
            params: Request parameters
            batch_progress: Optional tuple (current, total) for batch operations
            reduced_retries: If True, reduce retry attempts for faster failure
            log_callback: Optional callback for logging
            rate_limit_wait: Seconds to wait when rate limited
            session_name: Session name identifier

        Returns:
            JSON response as dict, or None if failed
        """
        if log_callback is None:
            def log_callback(message: str, dim: bool = False):
                formatted = self._format_progress_message(message, batch_progress)
                if dim:
                    print(f"\033[2m{formatted}\033[0m")
                else:
                    print(formatted)

        return self.http_client.get_json(
            url,
            params=params,
            timeout=self.timeout,
            reduced_retries=reduced_retries,
            batch_progress=batch_progress,
            log_callback=log_callback,
            handle_rate_limit=True,
            rate_limit_codes=(429,),
            rate_limit_wait=rate_limit_wait,
            session_name=session_name,
            request_delay=self.request_delay,
        )

    def _make_request_response(self, url: str, params: Dict[str, Any], batch_progress: Optional[Tuple[int, int]] = None,
                               log_callback: Optional[Callable[[str, bool], None]] = None,
                               rate_limit_wait: int = 60, session_name: str = "default",
                               accepted_status_codes: Tuple[int, ...] = ()):
        """
        Make a request and return response object (for status code checking).

        Args:
            url: Request URL
            params: Request parameters
            batch_progress: Optional tuple (current, total) for batch operations
            log_callback: Optional callback for logging
            rate_limit_wait: Seconds to wait when rate limited
            session_name: Session name identifier
            accepted_status_codes: Error statuses the caller needs to inspect

        Returns:
            Response object, or None if failed
        """
        if log_callback is None:
            def log_callback(message: str, dim: bool = False):
                formatted = self._format_progress_message(message, batch_progress)
                if dim:
                    print(f"\033[2m{formatted}\033[0m")
                else:
                    print(formatted)

        return self.http_client.get(
            url,
            params=params,
            timeout=self.timeout,
            batch_progress=batch_progress,
            log_callback=log_callback,
            handle_rate_limit=True,
            rate_limit_codes=(429,),
            rate_limit_wait=rate_limit_wait,
            session_name=session_name,
            accepted_status_codes=accepted_status_codes,
            request_delay=self.request_delay,
        )

    def _get_cached_or_fetch(
        self,
        cache_name: str,
        cache_key: str,
        fetch_func: Callable,
        skip_cache: bool = False,
        stale_if_error_seconds: int = 86400,
    ) -> Any:
        """
        Get cached result or fetch using provided function.

        Args:
            cache_name: Name of cache backend (e.g., "search", "release_info")
            cache_key: Cache key string
            fetch_func: Function to call if cache miss
            skip_cache: If True, skip cache check (useful for batch operations)

        Returns:
            Cached or fetched result
        """
        cache = self.cache_manager.get_cache(cache_name)

        fetch_lock = self._get_cache_fetch_lock(cache_name, cache_key)
        with fetch_lock:
            stale_result = None
            if not skip_cache:
                # Recheck under the per-key lock: another caller may have filled
                # the cache while this caller was waiting.
                cached_result = cache.get(cache_key)
                if cached_result is not None:
                    return cached_result
                get_stale = getattr(type(cache), "get_stale", None)
                if get_stale is not None:
                    stale_result = cache.get_stale(
                        cache_key,
                        stale_if_error_seconds,
                    )

            try:
                result = fetch_func()
            except Exception:
                if stale_result is not None:
                    return stale_result
                raise

            is_empty = (
                result is None
                or (
                    isinstance(result, (list, dict, tuple, set))
                    and len(result) == 0
                )
            )
            if is_empty:
                return stale_result if stale_result is not None else result

            cache.set(cache_key, result)
            return result

    def _generate_search_cache_key(self, prefix: str, *args) -> str:
        """Generate cache key for search operations."""
        return generate_cache_key(prefix, *args)

    def _generate_release_info_cache_key(self, prefix: str, release_id: str) -> str:
        """Generate cache key for release info operations."""
        return generate_cache_key(prefix, release_id)
