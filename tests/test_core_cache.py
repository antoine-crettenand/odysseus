"""Tests for cache backends."""

from unittest.mock import MagicMock

from odysseus.clients.base_api_client import BaseAPIClient
from odysseus.core.cache import MemoryCache, TTLCache


def test_memory_cache_update_does_not_evict_another_key():
    cache = MemoryCache(max_size=2)
    cache.set("first", 1)
    cache.set("second", 2)

    cache.set("second", 3)

    assert cache.get("first") == 1
    assert cache.get("second") == 3
    assert cache.size() == 2


def test_backend_can_distinguish_cached_none_from_missing_key():
    cache = TTLCache()

    cache.set("negative-result", None)

    assert cache.has("negative-result") is True
    assert cache.get("negative-result") is None
    assert cache.has("missing") is False


def test_recently_expired_value_is_returned_when_refresh_fails():
    cache = TTLCache(ttl_seconds=0)
    cache.set("release", ["cached"])
    cache_manager = type(
        "CacheManagerStub",
        (),
        {"get_cache": lambda self, name: cache},
    )()
    client = BaseAPIClient(
        {
            "BASE_URL": "https://example.test",
            "USER_AGENT": "test",
            "REQUEST_DELAY": 0,
            "MAX_RESULTS": 10,
            "TIMEOUT": 5,
        },
        cache_manager=cache_manager,
        http_client=object(),
    )

    result = client._get_cached_or_fetch(
        "search",
        "release",
        lambda: [],
        stale_if_error_seconds=60,
    )

    assert result == ["cached"]

def test_empty_search_results_are_not_cached():
    cache = MagicMock()
    cache.get.return_value = None
    cache_manager = MagicMock()
    cache_manager.get_cache.return_value = cache
    client = BaseAPIClient(
        {
            "BASE_URL": "https://example.test",
            "USER_AGENT": "test",
            "REQUEST_DELAY": 0,
            "MAX_RESULTS": 10,
            "TIMEOUT": 5,
        },
        cache_manager=cache_manager,
        http_client=MagicMock(),
    )

    result = client._get_cached_or_fetch("search", "key", lambda: [])

    assert result == []
    cache.set.assert_not_called()
