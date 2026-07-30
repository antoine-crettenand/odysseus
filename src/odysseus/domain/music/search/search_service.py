"""
Search service that coordinates searches across multiple sources.
"""

import concurrent.futures
import re
from typing import List, Optional, Dict, Any, Tuple
from ....models.song import SongData
from ....models.search_results import SearchResult, MusicBrainzSong, YouTubeVideo, DiscogsRelease
from ....utils.pattern_matcher import PatternMatcher
from .deduplicator import ResultDeduplicator
from ..validation.year_validator import YearValidator
from ..common.date_utils import extract_year, parse_release_date


class SearchService:
    """Service for searching music across multiple sources."""

    def __init__(
        self,
        musicbrainz_client=None,
        discogs_client=None,
        youtube_client=None,
        youtube_client_factory=None,
        spotify_client=None,
        year_validator=None,
        deduplicator=None
    ):
        """
        Initialize search service with dependencies.

        Args:
            musicbrainz_client: MusicBrainz provider
            discogs_client: Discogs provider
            youtube_client: Optional YouTubeClient instance
            youtube_client_factory: Callable used to construct YouTube clients
            spotify_client: Optional authenticated Spotify client
            year_validator: Optional YearValidator instance
            deduplicator: Optional ResultDeduplicator instance
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



    def _get_spotify_client(self):
        """Return the injected Spotify client when available."""
        return self._spotify_client

    def _deduplicate_results(self, results: List[MusicBrainzSong], release_type: Optional[str] = None) -> List[MusicBrainzSong]:
        """Delegate to ResultDeduplicator."""
        return self.deduplicator.deduplicate_results(results, release_type)

    def _deduplicate_with_priority(self, mb_results: List[MusicBrainzSong], discogs_results: List[MusicBrainzSong]) -> List[MusicBrainzSong]:
        """Delegate to ResultDeduplicator."""
        return self.deduplicator.deduplicate_with_priority(mb_results, discogs_results)

    @staticmethod
    def _safe_provider_search(provider: str, search_func, *args) -> list:
        """Keep one provider failure from discarding another provider's results."""
        try:
            return search_func(*args) or []
        except Exception as error:
            print(f"{provider} search failed: {error}")
            return []

    def search_recordings(self, song_data: SongData, offset: int = 0, limit: Optional[int] = None) -> List[MusicBrainzSong]:
        """Search for recordings in MusicBrainz."""
        results = self.musicbrainz_client.search_recording(song_data, offset=offset, limit=limit)
        return self.deduplicator.deduplicate_results(
            results,
            release_type=None,
            recordings=True,
        )

    def search_releases(self, song_data: SongData, offset: int = 0, limit: Optional[int] = None, release_type: Optional[str] = None) -> List[MusicBrainzSong]:
        """Search for releases, prioritizing Spotify if API key is available, then MusicBrainz and Discogs.

        Args:
            song_data: Song information to search for
            offset: Offset for pagination
            limit: Maximum number of results
            release_type: Optional release type filter (e.g., "Album", "Single", "EP", "Compilation", "Live", etc.)
        """
        # Fetch a bounded candidate pool before deduplication and pagination.
        default_max = self.musicbrainz_client.max_results if hasattr(self.musicbrainz_client, 'max_results') else 3
        requested_limit = max(1, limit or default_max)
        # Start with enough candidates for deduplication without asking every
        # provider for 50 records when the UI normally displays only a few.
        page_end = max(0, offset) + requested_limit
        fetch_limit = min(max(page_end * 3, page_end), 50)

        # Check if Spotify is available and search it first
        spotify_client = self._get_spotify_client()
        spotify_results = []

        if spotify_client and spotify_client.is_authenticated():
            try:
                print(f"Searching Spotify releases: {song_data.album} by {song_data.artist}")
                spotify_data = spotify_client.search_release(
                    album=song_data.album or "",
                    artist=song_data.artist or "",
                    release_year=song_data.release_year,
                    limit=fetch_limit
                )
                # Convert Spotify results to MusicBrainzSong format
                spotify_results = self._convert_spotify_to_mb_format(spotify_data)
            except Exception as e:
                # If Spotify search fails, continue with other sources
                print(f"Spotify search failed: {e}")

        # Search MusicBrainz and Discogs in parallel - always start from 0 to get all results for proper deduplication
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            mb_future = executor.submit(
                self._safe_provider_search,
                "MusicBrainz",
                self.musicbrainz_client.search_release,
                song_data,
                0,
                fetch_limit,
                None,
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

        # Convert Discogs to MusicBrainz format
        discogs_formatted = self._convert_discogs_to_mb_format(discogs_results)

        # Use priority-based deduplication: Spotify first (if available), then MusicBrainz, then Discogs
        # This deduplicates ALL results to find the best (earliest) release
        if spotify_results:
            # Spotify results first, then MusicBrainz, then Discogs
            all_results = self._deduplicate_with_priority(spotify_results, mb_results)
            all_results = self._deduplicate_with_priority(all_results, discogs_formatted)
        else:
            # No Spotify, use MusicBrainz and Discogs
            all_results = self._deduplicate_with_priority(mb_results, discogs_formatted)

        if release_type:
            filtered_results = []
            for result in all_results:
                if result.release_type and result.release_type.lower() == release_type.lower():
                    filtered_results.append(result)
            all_results = filtered_results

        # Sort results to prioritize original releases:
        # 1. By original release date (earliest first) - this is the most important factor
        # 2. True originals before re-releases (if same original date)
        # 3. Then by score (highest first)
        # This ensures original releases from the earliest year (1971) appear first
        def sort_key(r):
            # Use original_release_date for sorting (earliest first) - this is the key!
            # For re-releases, original_release_date should be the original year (e.g., 1971)
            # For true originals, original_release_date == release_date
            original_date_tuple = parse_release_date(r.original_release_date) or (9999, 12, 31)
            release_date_tuple = parse_release_date(r.release_date) or (9999, 12, 31)

            # Use the earlier of original_release_date or release_date for primary sorting
            # This ensures 1971 (original) sorts before 2021 (re-release)
            primary_date = original_date_tuple if original_date_tuple < release_date_tuple else release_date_tuple

            # Check if this is a true original (release_date matches original_release_date)
            is_true_original = (
                r.original_release_date and
                r.release_date and
                r.original_release_date == r.release_date
            )

            # Sort key: date (earliest first), then is_original (True=0, False=1), then score (highest first)
            # This ensures 1971 comes before 2021 regardless of whether they're true originals or re-releases
            return (
                primary_date,  # Primary sort: earliest original date first - 1971 before 2021
                0 if is_true_original else 1,  # Then true originals before re-releases
                -(r.score if r.score else 0)  # Then by score (highest first)
            )

        all_results.sort(key=sort_key)

        # Apply pagination AFTER deduplication and sorting
        if offset > 0:
            all_results = all_results[offset:]

        if limit and len(all_results) > limit:
            all_results = all_results[:limit]

        return all_results

    def search_artist_releases(self, artist: str, year: Optional[int] = None, release_type: Optional[str] = None, include_compilations: bool = False) -> List[MusicBrainzSong]:
        """Search for releases by a specific artist in MusicBrainz.
        Discogs is only consulted during deduplication for year validation when there's ambiguity.

        Args:
            artist: Artist name to search for
            year: Optional year filter
            release_type: Optional release type filter (e.g., "Album", "Single", "EP", "Compilation", "Live", etc.)
            include_compilations: If True, also search for compilations where the artist appears as a track artist
        """
        # Search MusicBrainz only - it usually has comprehensive coverage
        # Discogs is only used for year validation during deduplication when there's ambiguity
        mb_results = self.musicbrainz_client.search_artist_releases(artist, year, None, release_type)

        # Deduplicate MusicBrainz results only (no initial Discogs search)
        # Pass release_type so validation can filter Discogs searches
        all_results = self._deduplicate_results(mb_results, release_type=release_type)

        # If include_compilations is True, also search for compilations where artist appears on tracks
        if include_compilations:
            compilation_results = self.musicbrainz_client.search_artist_compilations(artist, year)
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
        """Get detailed release information from MusicBrainz, Discogs, or Spotify.

        Args:
            release_mbid: Release ID (MBID for MusicBrainz, Discogs ID for Discogs, Spotify ID for Spotify)
            batch_progress: Optional tuple (current, total) for batch operations
            source: Source to query ("musicbrainz", "discogs", or "spotify")
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

            mb_result = MusicBrainzSong(
                title=discogs_result.title or discogs_result.album or "",
                artist=discogs_result.artist,
                album=discogs_result.album,
                release_date=release_date,
                genre=discogs_result.genre,
                release_type=discogs_result.release_type,
                mbid=discogs_result.discogs_id,
                score=discogs_result.score,
                url=discogs_result.url,
                source="discogs"
            )
            mb_results.append(mb_result)
        return mb_results

    def _convert_spotify_to_mb_format(self, spotify_data: List[Dict[str, Any]]) -> List[MusicBrainzSong]:
        """Convert Spotify search results to MusicBrainzSong format for consistency."""
        mb_results = []
        for spotify_item in spotify_data:
            release_date = spotify_item.get("release_date")
            release_year = spotify_item.get("release_year")

            mb_result = MusicBrainzSong(
                title="",  # No title for releases
                artist=spotify_item.get("artist", ""),
                album=spotify_item.get("album", ""),
                release_date=release_date,
                original_release_date=release_date,  # Spotify doesn't distinguish original vs re-release
                genre=None,
                release_type="Album",  # Spotify search returns albums
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
