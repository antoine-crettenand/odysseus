"""Cache of reusable release-search provider snapshots."""

from copy import deepcopy
import re
from typing import Any, Callable, Optional

from ....core.cache.cache_backends import TTLCache
from ....core.cache.cache_keys import generate_cache_key
from ....core.config import CACHE_CONFIG
from ....models.song import SongData
from .release_candidate_fetcher import ReleaseCandidateFetcher
from .release_snapshot import ReleaseSearchSnapshot


class ReleaseSearchCache:
    """Own the TTL cache and keying for release-search snapshots."""

    def __init__(
        self,
        cache=None,
        musicbrainz_client_getter: Optional[Callable[[], Any]] = None,
        discogs_client_getter: Optional[Callable[[], Any]] = None,
        spotify_client_getter: Optional[Callable[[], Any]] = None,
        apple_music_client_getter: Optional[Callable[[], Any]] = None,
    ):
        self._cache = cache
        self._musicbrainz_client_getter = musicbrainz_client_getter or (lambda: None)
        self._discogs_client_getter = discogs_client_getter or (lambda: None)
        self._spotify_client_getter = spotify_client_getter or (lambda: None)
        self._apple_music_client_getter = apple_music_client_getter or (lambda: None)

    @staticmethod
    def _normalize_release_search_term(value: Any) -> str:
        """Normalize user-entered terms so harmless casing changes share a cache."""
        return re.sub(r"\s+", " ", str(value or "").strip()).casefold()

    def _release_search_provider_signature(self) -> tuple:
        """Separate snapshots when optional providers or storefronts change."""
        spotify_client = self._spotify_client_getter()
        apple_music_client = self._apple_music_client_getter()
        return (
            id(self._musicbrainz_client_getter()),
            id(self._discogs_client_getter()),
            id(spotify_client)
            if ReleaseCandidateFetcher._client_is_authenticated(spotify_client)
            else None,
            (
                id(apple_music_client),
                getattr(apple_music_client, "storefront", None),
            )
            if ReleaseCandidateFetcher._client_is_authenticated(apple_music_client)
            else None,
        )

    def _release_search_cache_key(
        self,
        song_data: SongData,
        release_type: Optional[str],
    ) -> str:
        """Build a cache key for either an exact type or the all-types scope."""
        return generate_cache_key(
            "release_search_snapshot_v1",
            self._normalize_release_search_term(song_data.title),
            self._normalize_release_search_term(song_data.album),
            self._normalize_release_search_term(song_data.artist),
            song_data.release_year,
            self._normalize_release_search_term(release_type) or "*",
            self._release_search_provider_signature(),
        )

    def _get_release_search_cache(self):
        """Return the snapshot cache, creating a default TTL backend if needed."""
        cache = self._cache
        if cache is None:
            cache = TTLCache(ttl_seconds=CACHE_CONFIG["SEARCH_TTL"])
            self._cache = cache
        cleanup_expired = getattr(cache, "cleanup_expired", None)
        if callable(cleanup_expired):
            cleanup_expired()
        return cache

    def get_cached_release_snapshot(
        self,
        song_data: SongData,
        release_type: Optional[str],
        fetch_limit: int,
    ) -> Optional[ReleaseSearchSnapshot]:
        """Return a defensive copy when the snapshot covers the fetch window."""
        key = self._release_search_cache_key(song_data, release_type)
        snapshot = self._get_release_search_cache().get(key)
        if snapshot is None or snapshot.fetch_limit < fetch_limit:
            return None
        return deepcopy(snapshot)

    def cache_release_snapshot(
        self,
        song_data: SongData,
        release_type: Optional[str],
        snapshot: ReleaseSearchSnapshot,
    ) -> None:
        """Retain successful provider candidates without exposing mutable state."""
        if not snapshot.has_results():
            return
        key = self._release_search_cache_key(song_data, release_type)
        self._get_release_search_cache().set(key, deepcopy(snapshot))
