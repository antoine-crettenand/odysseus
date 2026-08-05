"""
Search service that coordinates searches across multiple sources.
"""

from typing import List, Optional, Dict, Any, Tuple

from ....models.song import SongData
from ....models.search_results import SearchResult, MusicBrainzSong, YouTubeVideo, DiscogsRelease
from .deduplicator import ResultDeduplicator
from .release_candidate_fetcher import ReleaseCandidateFetcher
from .release_ranker import ReleaseRanker
from .release_search_cache import ReleaseSearchCache
from .release_snapshot import ReleaseSearchSnapshot
from .youtube_catalog_search import YouTubeCatalogSearch
from ..validation.year_validator import YearValidator

# Back-compat alias for older imports/tests.
_ReleaseSearchSnapshot = ReleaseSearchSnapshot


class SearchService:
    """Service for searching music across multiple sources."""

    def __init__(
        self,
        musicbrainz_client=None,
        discogs_client=None,
        youtube_client=None,
        youtube_client_factory=None,
        spotify_client=None,
        apple_music_client=None,
        year_validator=None,
        deduplicator=None,
        release_search_cache=None,
    ):
        """
        Initialize search service with dependencies.

        Args:
            musicbrainz_client: MusicBrainz provider
            discogs_client: Discogs provider
            youtube_client: Optional YouTubeClient instance
            youtube_client_factory: Callable used to construct YouTube clients
            spotify_client: Optional authenticated Spotify client
            apple_music_client: Optional authenticated Apple Music catalog client
            year_validator: Optional YearValidator instance
            deduplicator: Optional ResultDeduplicator instance
            release_search_cache: Optional cache for reusable release snapshots
        """
        if musicbrainz_client is None or discogs_client is None:
            raise ValueError(
                "SearchService requires MusicBrainz and Discogs clients"
            )
        if youtube_client_factory is None:
            raise ValueError("SearchService requires a YouTube client factory")
        self.musicbrainz_client = musicbrainz_client
        self.discogs_client = discogs_client
        self.youtube_client = youtube_client
        self.youtube_client_factory = youtube_client_factory

        self._spotify_client = spotify_client
        self._apple_music_client = apple_music_client

        # Initialize helper services
        if year_validator is None:
            self.year_validator = YearValidator(
                spotify_client_getter=self._get_spotify_client,
                discogs_client=self.discogs_client
            )
        else:
            self.year_validator = year_validator

        self.deduplicator = deduplicator or ResultDeduplicator(year_validator=self.year_validator)

        self.release_candidate_fetcher = ReleaseCandidateFetcher(
            musicbrainz_client=self.musicbrainz_client,
            discogs_client=self.discogs_client,
            spotify_client_getter=self._get_spotify_client,
            apple_music_client_getter=self._get_apple_music_client,
            year_validator=self.year_validator,
        )
        self.release_ranker = ReleaseRanker(
            deduplicator=self.deduplicator,
            deduplicate_with_priority=lambda left, right: self._deduplicate_with_priority(
                left, right
            ),
        )
        self.release_search_cache = ReleaseSearchCache(
            cache=release_search_cache,
            musicbrainz_client_getter=lambda: self.musicbrainz_client,
            discogs_client_getter=lambda: self.discogs_client,
            spotify_client_getter=self._get_spotify_client,
            apple_music_client_getter=self._get_apple_music_client,
        )
        self.youtube_catalog_search = YouTubeCatalogSearch(
            youtube_client_factory=self.youtube_client_factory,
        )

    def _ensure_collaborators(self) -> None:
        """Build collaborators for legacy constructions that skip __init__."""
        musicbrainz_client = getattr(self, "musicbrainz_client", None)
        discogs_client = getattr(self, "discogs_client", None)

        if getattr(self, "release_candidate_fetcher", None) is None:
            self.release_candidate_fetcher = ReleaseCandidateFetcher(
                musicbrainz_client=musicbrainz_client,
                discogs_client=discogs_client,
                spotify_client_getter=self._get_spotify_client,
                apple_music_client_getter=self._get_apple_music_client,
                year_validator=getattr(self, "year_validator", None),
            )
        else:
            self.release_candidate_fetcher.musicbrainz_client = musicbrainz_client
            self.release_candidate_fetcher.discogs_client = discogs_client
            self.release_candidate_fetcher.year_validator = getattr(
                self, "year_validator", None
            )

        if getattr(self, "deduplicator", None) is None:
            self.deduplicator = ResultDeduplicator(
                year_validator=getattr(self, "year_validator", None)
            )

        if getattr(self, "release_ranker", None) is None:
            self.release_ranker = ReleaseRanker(
                deduplicator=self.deduplicator,
                deduplicate_with_priority=lambda left, right: self._deduplicate_with_priority(
                    left, right
                ),
            )
        else:
            self.release_ranker.deduplicator = self.deduplicator

        if getattr(self, "release_search_cache", None) is None:
            self.release_search_cache = ReleaseSearchCache(
                musicbrainz_client_getter=lambda: getattr(
                    self, "musicbrainz_client", None
                ),
                discogs_client_getter=lambda: getattr(
                    self, "discogs_client", None
                ),
                spotify_client_getter=self._get_spotify_client,
                apple_music_client_getter=self._get_apple_music_client,
            )

        factory = getattr(self, "youtube_client_factory", None)
        if getattr(self, "youtube_catalog_search", None) is None:
            if factory is not None:
                self.youtube_catalog_search = YouTubeCatalogSearch(
                    youtube_client_factory=factory,
                )
        elif factory is not None:
            self.youtube_catalog_search.youtube_client_factory = factory

    def _get_spotify_client(self):
        """Return the injected Spotify client when available."""
        return getattr(self, "_spotify_client", None)

    def _get_apple_music_client(self):
        """Return the injected Apple Music client when configured."""
        return getattr(self, "_apple_music_client", None)

    def _deduplicate_results(self, results: List[MusicBrainzSong], release_type: Optional[str] = None) -> List[MusicBrainzSong]:
        """Delegate to ResultDeduplicator."""
        return self.deduplicator.deduplicate_results(results, release_type)

    def _deduplicate_with_priority(self, mb_results: List[MusicBrainzSong], discogs_results: List[MusicBrainzSong]) -> List[MusicBrainzSong]:
        """Delegate to ResultDeduplicator."""
        return self.deduplicator.deduplicate_with_priority(mb_results, discogs_results)

    @staticmethod
    def _filter_release_type(
        results: List[MusicBrainzSong],
        release_type: Optional[str],
    ) -> List[MusicBrainzSong]:
        """Filter candidates before cross-provider deduplication."""
        return ReleaseRanker._filter_release_type(results, release_type)

    @staticmethod
    def _filter_release_years(
        results: List[MusicBrainzSong],
        year_from: Optional[int],
        year_to: Optional[int],
    ) -> List[MusicBrainzSong]:
        """Filter releases by inclusive year bounds before deduplication."""
        return ReleaseRanker._filter_release_years(results, year_from, year_to)

    @staticmethod
    def _safe_provider_search(provider: str, search_func, *args) -> list:
        """Keep one provider failure from discarding another provider's results."""
        return ReleaseCandidateFetcher._safe_provider_search(
            provider, search_func, *args
        )

    @staticmethod
    def _client_is_authenticated(client) -> bool:
        """Safely report whether an optional catalog client can be queried."""
        return ReleaseCandidateFetcher._client_is_authenticated(client)

    @staticmethod
    def _normalize_release_search_term(value: Any) -> str:
        """Normalize user-entered terms so harmless casing changes share a cache."""
        return ReleaseSearchCache._normalize_release_search_term(value)

    def _release_search_provider_signature(self) -> tuple:
        """Separate snapshots when optional providers or storefronts change."""
        self._ensure_collaborators()
        return self.release_search_cache._release_search_provider_signature()

    def _release_search_cache_key(
        self,
        song_data: SongData,
        release_type: Optional[str],
    ) -> str:
        """Build a cache key for either an exact type or the all-types scope."""
        self._ensure_collaborators()
        return self.release_search_cache._release_search_cache_key(
            song_data, release_type
        )

    def _get_release_search_cache(self):
        """Return the snapshot cache, including for legacy test constructions."""
        self._ensure_collaborators()
        return self.release_search_cache._get_release_search_cache()

    def _get_cached_release_snapshot(
        self,
        song_data: SongData,
        release_type: Optional[str],
        fetch_limit: int,
    ) -> Optional[ReleaseSearchSnapshot]:
        """Return a defensive copy when the snapshot covers the fetch window."""
        self._ensure_collaborators()
        return self.release_search_cache.get_cached_release_snapshot(
            song_data, release_type, fetch_limit
        )

    def _cache_release_snapshot(
        self,
        song_data: SongData,
        release_type: Optional[str],
        snapshot: ReleaseSearchSnapshot,
    ) -> None:
        """Retain successful provider candidates without exposing mutable state."""
        self._ensure_collaborators()
        self.release_search_cache.cache_release_snapshot(
            song_data, release_type, snapshot
        )

    def _fetch_release_candidates(
        self,
        song_data: SongData,
        fetch_limit: int,
        release_type: Optional[str],
    ) -> ReleaseSearchSnapshot:
        """Fetch and normalize unpaginated candidates from all active providers."""
        self._ensure_collaborators()
        return self.release_candidate_fetcher._fetch_release_candidates(
            song_data, fetch_limit, release_type
        )

    def _rank_release_candidates(
        self,
        snapshot: ReleaseSearchSnapshot,
        release_type: Optional[str],
        year_from: Optional[int],
        year_to: Optional[int],
    ) -> List[MusicBrainzSong]:
        """Apply local refinements, provider priority, deduplication, and sort."""
        self._ensure_collaborators()
        return self.release_ranker._rank_release_candidates(
            snapshot, release_type, year_from, year_to
        )

    def search_recordings(self, song_data: SongData, offset: int = 0, limit: Optional[int] = None) -> List[MusicBrainzSong]:
        """Search for recordings in MusicBrainz."""
        results = self.musicbrainz_client.search_recording(song_data, offset=offset, limit=limit)
        return self.deduplicator.deduplicate_results(
            results,
            release_type=None,
            recordings=True,
        )

    def search_releases(
        self,
        song_data: SongData,
        offset: int = 0,
        limit: Optional[int] = None,
        release_type: Optional[str] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
    ) -> List[MusicBrainzSong]:
        """Search releases with MusicBrainz-first metadata authority.

        Args:
            song_data: Song information to search for
            offset: Offset for pagination
            limit: Maximum number of results
            release_type: Optional release type filter (e.g., "Album", "Single", "EP", "Compilation", "Live", etc.)
            year_from: Optional inclusive lower release-year bound
            year_to: Optional inclusive upper release-year bound
        """
        self._ensure_collaborators()
        exact_year = song_data.release_year
        effective_year_from = exact_year if exact_year is not None else year_from
        effective_year_to = exact_year if exact_year is not None else year_to

        # Fetch a bounded candidate pool before deduplication and pagination.
        default_max = self.musicbrainz_client.max_results if hasattr(self.musicbrainz_client, 'max_results') else 3
        requested_limit = max(1, limit or default_max)
        # Start with enough candidates for deduplication without asking every
        # provider for 50 records when the UI normally displays only a few.
        page_end = max(0, offset) + requested_limit
        fetch_limit = min(max(page_end * 3, page_end), 50)
        if year_from is not None or year_to is not None:
            fetch_limit = 50

        # Prefer an exact cached scope. A broader all-types snapshot may also
        # serve a type refinement, but only when it contains the complete page
        # requested after local filtering and deduplication.
        all_results = None
        snapshot = self._get_cached_release_snapshot(
            song_data, release_type, fetch_limit
        )
        if snapshot is not None:
            all_results = self._rank_release_candidates(
                snapshot,
                release_type,
                effective_year_from,
                effective_year_to,
            )
        elif release_type:
            broad_snapshot = self._get_cached_release_snapshot(
                song_data, None, fetch_limit
            )
            if broad_snapshot is not None:
                broad_results = self._rank_release_candidates(
                    broad_snapshot,
                    release_type,
                    effective_year_from,
                    effective_year_to,
                )
                if len(broad_results) >= page_end:
                    snapshot = broad_snapshot
                    all_results = broad_results

        if all_results is None:
            snapshot = self._fetch_release_candidates(
                song_data, fetch_limit, release_type
            )
            self._cache_release_snapshot(song_data, release_type, snapshot)
            all_results = self._rank_release_candidates(
                snapshot,
                release_type,
                effective_year_from,
                effective_year_to,
            )

        # Apply pagination AFTER deduplication and sorting
        if offset > 0:
            all_results = all_results[offset:]

        return all_results[:requested_limit]

    def search_artist_releases(
        self,
        artist: str,
        year: Optional[int] = None,
        release_type: Optional[str] = None,
        include_compilations: bool = False,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
    ) -> List[MusicBrainzSong]:
        """Search for releases by a specific artist in MusicBrainz.
        Discogs is only consulted during deduplication for year validation when there's ambiguity.

        Args:
            artist: Artist name to search for
            year: Optional year filter
            release_type: Optional release type filter (e.g., "Album", "Single", "EP", "Compilation", "Live", etc.)
            include_compilations: If True, also search for compilations where the artist appears as a track artist
            year_from: Optional inclusive lower release-year bound
            year_to: Optional inclusive upper release-year bound
        """
        effective_year_from = year if year is not None else year_from
        effective_year_to = year if year is not None else year_to

        # Search MusicBrainz only - it usually has comprehensive coverage
        # Discogs is only used for year validation during deduplication when there's ambiguity
        mb_results = self.musicbrainz_client.search_artist_releases(artist, year, None, release_type)
        mb_results = self._filter_release_years(
            mb_results,
            effective_year_from,
            effective_year_to,
        )

        # Deduplicate MusicBrainz results only (no initial Discogs search)
        # Pass release_type so validation can filter Discogs searches
        all_results = self._deduplicate_results(mb_results, release_type=release_type)

        # If include_compilations is True, also search for compilations where artist appears on tracks
        if include_compilations:
            compilation_results = self.musicbrainz_client.search_artist_compilations(artist, year)
            compilation_results = self._filter_release_years(
                compilation_results,
                effective_year_from,
                effective_year_to,
            )
            # Deduplicate compilation results against existing results
            existing_keys = {self.deduplicator._create_deduplication_key(r) for r in all_results}
            for comp_result in compilation_results:
                comp_key = self.deduplicator._create_deduplication_key(comp_result)
                if comp_key[0] and comp_key not in existing_keys:
                    all_results.append(comp_result)
                    existing_keys.add(comp_key)

        if release_type:
            filtered_results = []
            for result in all_results:
                if result.release_type and result.release_type.lower() == release_type.lower():
                    filtered_results.append(result)
            all_results = filtered_results

        return all_results

    def get_release_info(self, release_mbid: str, batch_progress: Optional[Tuple[int, int]] = None, source: str = "musicbrainz") -> Optional[Any]:
        """Get detailed release information from a configured catalog provider.

        Args:
            release_mbid: Release ID (MBID for MusicBrainz, Discogs ID for Discogs, Spotify ID for Spotify)
            batch_progress: Optional tuple (current, total) for batch operations
            source: Source to query
        """
        # Handle Spotify source
        if source == "spotify":
            spotify_client = self._get_spotify_client()
            if spotify_client and spotify_client.is_authenticated():
                try:
                    return spotify_client.get_album_tracks(release_mbid)
                except Exception as e:
                    if batch_progress:
                        print(f"[{batch_progress[0]}/{batch_progress[1]}] Spotify release fetch failed: {e}")
                    else:
                        print(f"Spotify release fetch failed: {e}")
                    return None
            else:
                if batch_progress:
                    print(f"[{batch_progress[0]}/{batch_progress[1]}] Spotify API not authenticated")
                else:
                    print("Spotify API not authenticated")
                return None

        if source == "applemusic":
            apple_music_client = self._get_apple_music_client()
            if apple_music_client and apple_music_client.is_authenticated():
                try:
                    return apple_music_client.get_album_tracks(release_mbid)
                except Exception as e:
                    prefix = (
                        f"[{batch_progress[0]}/{batch_progress[1]}] "
                        if batch_progress else ""
                    )
                    print(f"{prefix}Apple Music release fetch failed: {e}")
            return None

        # Handle Discogs source
        if source == "discogs":
            return self.discogs_client.get_release_info(release_mbid, batch_progress=batch_progress)

        # Handle MusicBrainz source (default)
        return self.musicbrainz_client.get_release_info(release_mbid, batch_progress=batch_progress)

    def _convert_discogs_to_mb_format(self, discogs_results: List[DiscogsRelease]) -> List[MusicBrainzSong]:
        """Convert DiscogsRelease results to MusicBrainzSong format for consistency."""
        self._ensure_collaborators()
        return self.release_candidate_fetcher._convert_discogs_to_mb_format(
            discogs_results
        )

    def _convert_apple_music_to_mb_format(
        self, apple_music_data: List[Dict[str, Any]]
    ) -> List[MusicBrainzSong]:
        """Convert Apple Music catalog editions to the shared result model."""
        self._ensure_collaborators()
        return self.release_candidate_fetcher._convert_apple_music_to_mb_format(
            apple_music_data
        )

    def _convert_spotify_to_mb_format(self, spotify_data: List[Dict[str, Any]]) -> List[MusicBrainzSong]:
        """Convert Spotify search results to MusicBrainzSong format for consistency."""
        self._ensure_collaborators()
        return self.release_candidate_fetcher._convert_spotify_to_mb_format(
            spotify_data
        )

    def _ensure_youtube_catalog_search(self) -> YouTubeCatalogSearch:
        """Ensure the YouTube collaborator exists (including __new__ constructions)."""
        self._ensure_collaborators()
        if getattr(self, "youtube_catalog_search", None) is None:
            self.youtube_catalog_search = YouTubeCatalogSearch(
                youtube_client_factory=self.youtube_client_factory,
            )
        return self.youtube_catalog_search

    def search_youtube(self, query: str, max_results: int = 3, offset: int = 0) -> List[YouTubeVideo]:
        """Search YouTube for videos."""
        catalog = self._ensure_youtube_catalog_search()
        results = catalog.search_youtube(
            query, max_results=max_results, offset=offset
        )
        self.youtube_client = catalog.youtube_client
        return results

    def search_full_album(self, artist: str, album: str, max_results: int = 5, release_year: Optional[str] = None) -> List[YouTubeVideo]:
        """
        Search YouTube for full album videos (complete album in one video).

        Args:
            artist: Artist name
            album: Album title
            max_results: Maximum number of results to return
            release_year: Optional release year to improve search accuracy
        """
        return self._ensure_youtube_catalog_search().search_full_album(
            artist, album, max_results=max_results, release_year=release_year
        )

    def _build_full_album_queries(self, artist: str, album: str, release_year: Optional[str] = None) -> List[str]:
        """Build search queries for full album videos."""
        return self._ensure_youtube_catalog_search()._build_full_album_queries(
            artist, album, release_year
        )

    def search_playlist(self, artist: str, album: str, max_results: int = 5, track_titles: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Search YouTube for playlists matching the album.

        Args:
            artist: Artist name
            album: Album name
            max_results: Maximum number of playlists to return
            track_titles: Optional list of track titles from the album to search for playlists containing them
        """
        return self._ensure_youtube_catalog_search().search_playlist(
            artist, album, max_results=max_results, track_titles=track_titles
        )

    def search_all_sources(self, song_data: SongData) -> Dict[str, List[SearchResult]]:
        """Search all available sources for a song."""
        results = {}

        try:
            results['musicbrainz'] = self.search_recordings(song_data)
        except Exception as e:
            print(f"MusicBrainz search failed: {e}")
            results['musicbrainz'] = []

        try:
            discogs_results = self.discogs_client.search_release(song_data)
            results['discogs'] = discogs_results
        except Exception as e:
            print(f"Discogs search failed: {e}")
            results['discogs'] = []

        try:
            query = f"{song_data.artist} {song_data.title}"
            results['youtube'] = self.search_youtube(query)
        except Exception as e:
            print(f"YouTube search failed: {e}")
            results['youtube'] = []

        return results
