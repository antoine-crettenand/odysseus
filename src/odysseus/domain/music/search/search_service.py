"""
Search service that coordinates searches across multiple sources.
"""

import concurrent.futures
from copy import deepcopy
from dataclasses import dataclass
import re
from typing import List, Optional, Dict, Any, Tuple
from ....core.cache.cache_backends import TTLCache
from ....core.cache.cache_keys import generate_cache_key
from ....core.config import CACHE_CONFIG
from ....models.song import SongData
from ....models.search_results import SearchResult, MusicBrainzSong, YouTubeVideo, DiscogsRelease
from ....utils.pattern_matcher import PatternMatcher
from .deduplicator import ResultDeduplicator
from ..validation.year_validator import YearValidator
from ..common.date_utils import (
    extract_year,
    parse_release_date,
    release_year_in_range,
)


@dataclass
class _ReleaseSearchSnapshot:
    """Unpaginated provider candidates retained for local refinements."""

    fetch_limit: int
    musicbrainz: List[MusicBrainzSong]
    discogs: List[MusicBrainzSong]
    spotify: List[MusicBrainzSong]
    apple_music: List[MusicBrainzSong]

    def has_results(self) -> bool:
        """Return whether at least one provider supplied a candidate."""
        return any(
            (self.musicbrainz, self.discogs, self.spotify, self.apple_music)
        )


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

        # Initialize helper services
        if year_validator is None:
            self.year_validator = YearValidator(
                spotify_client_getter=self._get_spotify_client,
                discogs_client=self.discogs_client
            )
        else:
            self.year_validator = year_validator

        self.deduplicator = deduplicator or ResultDeduplicator(year_validator=self.year_validator)

        self._spotify_client = spotify_client
        self._apple_music_client = apple_music_client
        self._release_search_cache = release_search_cache or TTLCache(
            ttl_seconds=CACHE_CONFIG["SEARCH_TTL"]
        )



    def _get_spotify_client(self):
        """Return the injected Spotify client when available."""
        return self._spotify_client

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
        if not release_type:
            return results
        expected = release_type.casefold()
        return [
            result
            for result in results
            if result.release_type
            and result.release_type.casefold() == expected
        ]

    @staticmethod
    def _filter_release_years(
        results: List[MusicBrainzSong],
        year_from: Optional[int],
        year_to: Optional[int],
    ) -> List[MusicBrainzSong]:
        """Filter releases by inclusive year bounds before deduplication."""
        return [
            result
            for result in results
            if release_year_in_range(result, year_from, year_to)
        ]

    @staticmethod
    def _safe_provider_search(provider: str, search_func, *args) -> list:
        """Keep one provider failure from discarding another provider's results."""
        try:
            return search_func(*args) or []
        except Exception as error:
            print(f"{provider} search failed: {error}")
            return []

    @staticmethod
    def _normalize_release_search_term(value: Any) -> str:
        """Normalize user-entered terms so harmless casing changes share a cache."""
        return re.sub(r"\s+", " ", str(value or "").strip()).casefold()

    @staticmethod
    def _client_is_authenticated(client) -> bool:
        """Safely report whether an optional catalog client can be queried."""
        if client is None:
            return False
        try:
            return bool(client.is_authenticated())
        except Exception:
            return False

    def _release_search_provider_signature(self) -> tuple:
        """Separate snapshots when optional providers or storefronts change."""
        spotify_client = self._get_spotify_client()
        apple_music_client = self._get_apple_music_client()
        return (
            id(self.musicbrainz_client),
            id(self.discogs_client),
            id(spotify_client)
            if self._client_is_authenticated(spotify_client)
            else None,
            (
                id(apple_music_client),
                getattr(apple_music_client, "storefront", None),
            )
            if self._client_is_authenticated(apple_music_client)
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
        """Return the snapshot cache, including for legacy test constructions."""
        cache = getattr(self, "_release_search_cache", None)
        if cache is None:
            cache = TTLCache(ttl_seconds=CACHE_CONFIG["SEARCH_TTL"])
            self._release_search_cache = cache
        cleanup_expired = getattr(cache, "cleanup_expired", None)
        if callable(cleanup_expired):
            cleanup_expired()
        return cache

    def _get_cached_release_snapshot(
        self,
        song_data: SongData,
        release_type: Optional[str],
        fetch_limit: int,
    ) -> Optional[_ReleaseSearchSnapshot]:
        """Return a defensive copy when the snapshot covers the fetch window."""
        key = self._release_search_cache_key(song_data, release_type)
        snapshot = self._get_release_search_cache().get(key)
        if snapshot is None or snapshot.fetch_limit < fetch_limit:
            return None
        return deepcopy(snapshot)

    def _cache_release_snapshot(
        self,
        song_data: SongData,
        release_type: Optional[str],
        snapshot: _ReleaseSearchSnapshot,
    ) -> None:
        """Retain successful provider candidates without exposing mutable state."""
        if not snapshot.has_results():
            return
        key = self._release_search_cache_key(song_data, release_type)
        self._get_release_search_cache().set(key, deepcopy(snapshot))

    def _fetch_release_candidates(
        self,
        song_data: SongData,
        fetch_limit: int,
        release_type: Optional[str],
    ) -> _ReleaseSearchSnapshot:
        """Fetch and normalize unpaginated candidates from all active providers."""
        spotify_results = []
        apple_music_results = []

        spotify_client = self._get_spotify_client()
        if self._client_is_authenticated(spotify_client):
            try:
                print(
                    f"Searching Spotify releases: {song_data.album} "
                    f"by {song_data.artist}"
                )
                spotify_data = spotify_client.search_release(
                    album=song_data.album or "",
                    artist=song_data.artist or "",
                    release_year=song_data.release_year,
                    limit=fetch_limit,
                )
                spotify_results = self._convert_spotify_to_mb_format(
                    spotify_data
                )
            except Exception as error:
                print(f"Spotify search failed: {error}")

        apple_music_client = self._get_apple_music_client()
        if self._client_is_authenticated(apple_music_client):
            try:
                print(
                    f"Searching Apple Music releases: "
                    f"{song_data.album} by {song_data.artist}"
                )
                apple_music_data = apple_music_client.search_release(
                    album=song_data.album or "",
                    artist=song_data.artist or "",
                    release_year=song_data.release_year,
                    limit=fetch_limit,
                )
                apple_music_results = self._convert_apple_music_to_mb_format(
                    apple_music_data
                )
            except Exception as error:
                print(f"Apple Music search failed: {error}")

        # Always start from zero so pagination happens after cross-source
        # deduplication. MusicBrainz and Discogs can run concurrently.
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            mb_future = executor.submit(
                self._safe_provider_search,
                "MusicBrainz",
                self.musicbrainz_client.search_release,
                song_data,
                0,
                fetch_limit,
                release_type,
            )
            discogs_future = executor.submit(
                self._safe_provider_search,
                "Discogs",
                self.discogs_client.search_release,
                song_data,
                0,
                fetch_limit,
                release_type,
            )

            mb_results = mb_future.result()
            discogs_results = discogs_future.result()

        # Resolve Discogs master years once, before storing a reusable snapshot.
        resolve_discogs_year = getattr(
            getattr(self, "year_validator", None),
            "resolve_discogs_year",
            None,
        )
        if (
            callable(resolve_discogs_year)
            and discogs_results
            and song_data.album
            and song_data.artist
        ):
            resolve_discogs_year(
                song_data.artist, song_data.album, discogs_results
            )

        return _ReleaseSearchSnapshot(
            fetch_limit=fetch_limit,
            musicbrainz=mb_results,
            discogs=self._convert_discogs_to_mb_format(discogs_results),
            spotify=spotify_results,
            apple_music=apple_music_results,
        )

    def _rank_release_candidates(
        self,
        snapshot: _ReleaseSearchSnapshot,
        release_type: Optional[str],
        year_from: Optional[int],
        year_to: Optional[int],
    ) -> List[MusicBrainzSong]:
        """Apply local refinements, provider priority, deduplication, and sort."""
        spotify_results = self._filter_release_type(
            snapshot.spotify, release_type
        )
        apple_music_results = self._filter_release_type(
            snapshot.apple_music, release_type
        )
        mb_results = self._filter_release_type(
            snapshot.musicbrainz, release_type
        )
        discogs_results = self._filter_release_type(
            snapshot.discogs, release_type
        )

        spotify_results = self._filter_release_years(
            spotify_results, year_from, year_to
        )
        apple_music_results = self._filter_release_years(
            apple_music_results, year_from, year_to
        )
        mb_results = self._filter_release_years(
            mb_results, year_from, year_to
        )
        discogs_results = self._filter_release_years(
            discogs_results, year_from, year_to
        )

        # MusicBrainz is the metadata authority, followed by Discogs, Apple
        # Music, and Spotify for editions absent from the preceding catalogs.
        all_results = self._deduplicate_with_priority(
            mb_results, discogs_results
        )
        all_results = self._deduplicate_with_priority(
            all_results, apple_music_results
        )
        all_results = self._deduplicate_with_priority(
            all_results, spotify_results
        )

        def sort_key(result):
            original_date = parse_release_date(
                result.original_release_date
            ) or (9999, 12, 31)
            edition_date = parse_release_date(
                result.release_date
            ) or (9999, 12, 31)
            primary_date = min(original_date, edition_date)
            is_true_original = bool(
                result.original_release_date
                and result.release_date
                and result.original_release_date == result.release_date
            )
            return (
                primary_date,
                0 if is_true_original else 1,
                -(result.score or 0),
            )

        all_results.sort(key=sort_key)
        return all_results

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
        mb_results = []
        for discogs_result in discogs_results:
            release_date = str(discogs_result.year) if discogs_result.year else None
            original_release_date = (
                str(discogs_result.master_year)
                if discogs_result.master_year
                else None
            )

            mb_result = MusicBrainzSong(
                title=discogs_result.title or discogs_result.album or "",
                artist=discogs_result.artist,
                album=discogs_result.album,
                release_date=release_date,
                original_release_date=original_release_date,
                genre=discogs_result.genre,
                cover_art_url=discogs_result.cover_art_url,
                release_type=discogs_result.release_type,
                release_status="Official",
                country=discogs_result.country,
                label=discogs_result.label,
                media_format=discogs_result.format,
                mbid=discogs_result.discogs_id,
                score=discogs_result.score,
                url=discogs_result.url,
                source="discogs"
            )
            mb_results.append(mb_result)
        return mb_results

    def _convert_apple_music_to_mb_format(
        self, apple_music_data: List[Dict[str, Any]]
    ) -> List[MusicBrainzSong]:
        """Convert Apple Music catalog editions to the shared result model."""
        return [
            MusicBrainzSong(
                title="",
                artist=item.get("artist", ""),
                album=item.get("album", ""),
                release_date=item.get("release_date"),
                original_release_date=None,
                genre=item.get("genre"),
                cover_art_url=item.get("cover_art_url"),
                release_type=item.get("release_type") or "Album",
                release_status="Official",
                label=item.get("label"),
                barcode=item.get("barcode"),
                media_format="Digital Media",
                track_count=item.get("track_count"),
                mbid=item.get("id", ""),
                score=0,
                url=item.get("url", ""),
                source="applemusic",
            )
            for item in apple_music_data
        ]

    def _convert_spotify_to_mb_format(self, spotify_data: List[Dict[str, Any]]) -> List[MusicBrainzSong]:
        """Convert Spotify search results to MusicBrainzSong format for consistency."""
        mb_results = []
        for spotify_item in spotify_data:
            release_date = spotify_item.get("release_date")

            mb_result = MusicBrainzSong(
                title="",  # No title for releases
                artist=spotify_item.get("artist", ""),
                album=spotify_item.get("album", ""),
                release_date=release_date,
                # Spotify exposes the selected digital edition date, not a
                # trustworthy original release-group date.
                original_release_date=None,
                genre=None,
                cover_art_url=spotify_item.get("cover_art_url"),
                release_type=spotify_item.get("release_type") or "Album",
                mbid=spotify_item.get("spotify_id", ""),
                score=spotify_item.get("popularity", 0),  # Use popularity as score
                url=spotify_item.get("url", ""),
                source="spotify"
            )
            mb_results.append(mb_result)
        return mb_results

    def search_youtube(self, query: str, max_results: int = 3, offset: int = 0) -> List[YouTubeVideo]:
        """Search YouTube for videos."""
        offset = max(0, offset)
        fetch_limit = max_results + offset
        self.youtube_client = self.youtube_client_factory(query, fetch_limit)
        return self.youtube_client.videos[offset:offset + max_results]

    def search_full_album(self, artist: str, album: str, max_results: int = 5, release_year: Optional[str] = None) -> List[YouTubeVideo]:
        """
        Search YouTube for full album videos (complete album in one video).

        Args:
            artist: Artist name
            album: Album title
            max_results: Maximum number of results to return
            release_year: Optional release year to improve search accuracy
        """
        queries = self._build_full_album_queries(artist, album, release_year)
        all_results = []
        seen_ids = set()

        for query in queries:
            client = self.youtube_client_factory(query, max_results)
            for video in client.videos:
                if video.video_id and video.video_id not in seen_ids:
                    if not PatternMatcher.has_full_album_keyword(video.title):
                        continue

                    if PatternMatcher.is_live_or_non_album_video(video.title):
                        continue

                    all_results.append(video)
                    seen_ids.add(video.video_id)
                    if len(all_results) >= max_results:
                        return all_results[:max_results]

        return all_results[:max_results]

    def _build_full_album_queries(self, artist: str, album: str, release_year: Optional[str] = None) -> List[str]:
        """
        Build search queries for full album videos.

        Args:
            artist: Artist name
            album: Album title
            release_year: Optional release year

        Returns:
            List of search query strings
        """
        if release_year:
            return [
                f'"{artist}" "{album}" {release_year} full album',
                f"{artist} {album} {release_year} full album",
                f"{artist} {album} full album {release_year}",
                f"{artist} {album} full album",
                f"{artist} {album} complete album",
            ]
        else:
            return [
                f'"{artist}" "{album}" full album',  # Use quotes for exact phrase matching
                f"{artist} {album} full album",
                f"{artist} {album} complete album",
                f"{artist} {album} album full",
                f"{artist} {album} full",
            ]


    def search_playlist(self, artist: str, album: str, max_results: int = 5, track_titles: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Search YouTube for playlists matching the album.

        Args:
            artist: Artist name
            album: Album name
            max_results: Maximum number of playlists to return
            track_titles: Optional list of track titles from the album to search for playlists containing them
        """
        # Include queries for vinyl "Side 1" and "Side 2" playlists
        queries = [
            f"{artist} {album} playlist",
            f"{artist} {album} album playlist",
            f"{artist} {album} side 1",
            f"{artist} {album} side 2",
            f"{artist} {album} vinyl side 1",
            f"{artist} {album} vinyl side 2",
            f"{artist} {album} side a",
            f"{artist} {album} side b",
            f"{artist} {album}",  # More general search
            f"{album} playlist",  # Search without artist (in case of compilation albums)
        ]

        # Also search for playlists using individual track titles (helps find playlists that contain the tracks)
        if track_titles:
            # Use first few track titles to find playlists that might contain album tracks
            for track_title in track_titles[:3]:  # Limit to first 3 tracks to avoid too many queries
                queries.append(f"{artist} {track_title} playlist")
                queries.append(f"{track_title} playlist")

        all_results = []
        seen_ids = set()
        # Separate lists for regular playlists and side playlists (prioritize side playlists)
        side_playlists = []
        regular_playlists = []

        # Increase results per query to be more thorough
        results_per_query = max(max_results * 3, 15)

        for query in queries:
            try:
                client = self.youtube_client_factory(query, results_per_query)
                for video in client.videos:
                    if video.url_suffix and 'list=' in video.url_suffix:
                        match = re.search(r'list=([^&]+)', video.url_suffix)
                        if match:
                            playlist_id = match.group(1)

                            # Skip Radio playlists (RD prefix) - these are auto-generated and often inaccessible
                            if playlist_id.startswith('RD'):
                                continue

                            if playlist_id not in seen_ids:
                                playlist_info = {
                                    'playlist_id': playlist_id,
                                    'title': video.title,
                                    'url': f"https://www.youtube.com/playlist?list={playlist_id}",
                                    'video': video
                                }

                                # Check if this is a "Side 1" or "Side 2" playlist
                                title_lower = video.title.lower()
                                is_side_playlist = any(
                                    keyword in title_lower
                                    for keyword in ['side 1', 'side 2', 'side a', 'side b', 'side one', 'side two']
                                )

                                if is_side_playlist:
                                    side_playlists.append(playlist_info)
                                else:
                                    regular_playlists.append(playlist_info)

                                seen_ids.add(playlist_id)

                                # If we have enough results, combine and return
                                if len(side_playlists) + len(regular_playlists) >= max_results * 2:
                                    # Prioritize side playlists, then regular playlists
                                    all_results = side_playlists + regular_playlists
                                    return all_results[:max_results]
            except Exception:
                # Continue with next query if one fails
                continue

        # Combine results with side playlists first
        all_results = side_playlists + regular_playlists
        return all_results[:max_results]

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
