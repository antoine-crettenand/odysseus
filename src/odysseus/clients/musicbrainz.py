"""
MusicBrainz Client Module
A client for searching the MusicBrainz database for music information.
"""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from rich.console import Console
from ..models.song import SongData
from ..models.search_results import MusicBrainzSong
from ..models.releases import Track, ReleaseInfo
from ..core.config import MUSICBRAINZ_CONFIG, ERROR_MESSAGES, DOWNLOADS_DIR
from ..utils.file_duration_reader import format_duration_ms
from ..utils.string_utils import normalize_string
from .base_api_client import BaseAPIClient
from .path_utils import PathUtils

console = Console()

# Constants
BASE_MAX_RETRIES = 3
RETRY_DELAY_BASE = 2
MAX_RETRIES_TRANSIENT_SSL = 5
PAGINATION_LIMIT = 100
COMPILATION_TYPES = {'Compilation'}


class MusicBrainzClient(BaseAPIClient):
    """MusicBrainz search client."""

    def __init__(self, cache_manager=None, http_client=None):
        """
        Initialize MusicBrainz client.

        Args:
            cache_manager: Optional CacheManager instance (will use global if not provided)
            http_client: Optional HttpClient instance (will use global if not provided)
        """
        super().__init__(MUSICBRAINZ_CONFIG, cache_manager, http_client)

        # Initialize path utils for checking existing releases
        self.path_utils = PathUtils()

        # Ensure MusicBrainz requests use the configured User-Agent (contact required)
        if hasattr(self.http_client, "session_manager"):
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            }
            session_manager = self.http_client.session_manager
            if hasattr(session_manager, "register_headers"):
                session_manager.register_headers("musicbrainz", headers)
            else:
                session_manager.get_session("musicbrainz").headers.update(headers)

    def _log(self, message: str, batch_progress: Optional[Tuple[int, int]] = None, dim: bool = False):
        """Log message with optional batch progress prefix and dimming."""
        prefix = f"[{batch_progress[0]}/{batch_progress[1]}] " if batch_progress else ""
        # Add newline at start to ensure message appears on new line (important when spinner is active)
        if dim:
            console.print(f"\n{prefix}[dim]{message}[/dim]")
        else:
            console.print(f"\n{prefix}{message}")

    def _check_release_folder_exists(self, song_data: SongData) -> bool:
        """
        Check if a release folder already exists for the given artist/album/year.

        Args:
            song_data: Song information with artist, album, and optional release_year

        Returns:
            True if folder exists and contains audio files, False otherwise
        """
        try:
            # Create metadata dict similar to what PathUtils.create_organized_path expects
            metadata = {
                'artist': song_data.artist or 'Unknown Artist',
                'album': song_data.album or 'Unknown Album',
                'year': song_data.release_year,
                'title': song_data.album or 'Unknown Album'
            }

            # Get the expected folder path
            expected_folder = self.path_utils.create_organized_path(DOWNLOADS_DIR, metadata)

            # Check if folder exists
            if not expected_folder.exists():
                return False

            # Check if folder contains audio files
            audio_extensions = ['.mp3', '.m4a', '.ogg', '.opus', '.flac', '.wav', '.aac', '.webm']
            system_files = {'.DS_Store', '.Thumbs.db', 'desktop.ini'}

            for ext in audio_extensions:
                audio_files = list(expected_folder.glob(f"*{ext}"))
                audio_files = [f for f in audio_files if f.is_file() and f.name not in system_files]
                if audio_files:
                    return True

            return False
        except Exception:
            # If any error occurs during checking, assume folder doesn't exist
            return False

    def _build_query(self, **kwargs) -> str:
        """Build MusicBrainz query string from keyword arguments."""
        query_parts = []
        if kwargs.get('title'):
            query_parts.append(f'title:"{kwargs["title"]}"')
        if kwargs.get('artist'):
            query_parts.append(f'artist:"{kwargs["artist"]}"')
        if kwargs.get('album'):
            query_parts.append(f'release:"{kwargs["album"]}"')
        if kwargs.get('release'):
            query_parts.append(f'title:"{kwargs["release"]}"')
        if kwargs.get('date'):
            query_parts.append(f'date:{kwargs["date"]}')
        if kwargs.get('release_type'):
            query_parts.append(f'type:"{kwargs["release_type"]}"')
        return ' AND '.join(query_parts)

    def _make_request(self, url: str, params: Dict[str, Any], batch_progress: Optional[Tuple[int, int]] = None, reduced_retries: bool = False) -> Optional[Dict[str, Any]]:
        """
        Make a request using HttpClient with SSL error handling and retries.

        Args:
            url: Request URL
            params: Request parameters
            batch_progress: Optional tuple (current, total) for batch operations (e.g., (1, 5))
            reduced_retries: If True, reduce retry attempts for faster failure (useful when release already exists)
        """
        # Create log callback wrapper for batch progress logging
        def log_callback(message: str, dim: bool = False):
            self._log(message, batch_progress, dim=dim)

        # Use HttpClient which handles retries, SSL errors, rate limiting, etc.
        return self.http_client.get_json(
            url,
            params=params,
            timeout=self.timeout,
            reduced_retries=reduced_retries,
            batch_progress=batch_progress,
            log_callback=log_callback,
            handle_rate_limit=True,
            rate_limit_codes=(429,),
            rate_limit_wait=60,  # MusicBrainz allows 1 request/second
            session_name="musicbrainz",
            request_delay=self.request_delay,
        )

    def search_recording(self, song_data: SongData, offset: int = 0, limit: Optional[int] = None) -> List[MusicBrainzSong]:
        """
        Search for recordings in MusicBrainz.

        Args:
            song_data: Song information to search for
            offset: Offset for pagination (default: 0)
            limit: Maximum number of results (default: uses self.max_results)

        Returns:
            List of MusicBrainz results
        """
        query = self._build_query(
            title=song_data.title,
            artist=song_data.artist,
            album=song_data.album,
            date=song_data.release_year
        )

        url = f"{self.base_url}/recording"
        params = {
            'query': query,
            'fmt': 'json',
            'limit': limit or self.max_results,
            'offset': offset,
            'inc': 'releases+release-groups'
        }

        try:
            print(f"Searching MusicBrainz recordings with query: {query}")
            data = self._make_request(url, params)
            return self._parse_recording_results(data) if data else []
        except Exception as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return []

    def search_release(self, song_data: SongData, offset: int = 0, limit: Optional[int] = None, release_type: Optional[str] = None) -> List[MusicBrainzSong]:
        """
        Search for releases (albums) in MusicBrainz with caching.

        Args:
            song_data: Song information to search for
            offset: Offset for pagination (default: 0)
            limit: Maximum number of results (default: uses self.max_results)
            release_type: Optional release type filter (e.g., "Album", "Single", "EP", "Compilation", "Live", etc.)

        Returns:
            List of MusicBrainz results
        """
        # Generate cache key from search parameters
        key = self._generate_search_cache_key(
            "search_release",
            song_data.album,
            song_data.artist,
            song_data.release_year,
            offset,
            limit or self.max_results,
            release_type
        )

        def fetch_func():
            query = self._build_query(
                release=song_data.album,
                artist=song_data.artist,
                date=song_data.release_year,
                release_type=release_type
            )

            url = f"{self.base_url}/release"
            params = {
                'query': query,
                'fmt': 'json',
                'limit': limit or self.max_results,
                'offset': offset,
                'inc': 'release-groups'
            }

            try:
                # Check if release folder already exists - if so, use reduced retries for faster failure
                release_exists = self._check_release_folder_exists(song_data)
                reduced_retries = release_exists

                if release_exists:
                    print(f"Release folder already exists for: {song_data.album} by {song_data.artist}. Using faster failure mode for connection errors.")

                print(f"Searching MusicBrainz releases with query: {query}")
                data = self._make_request(url, params, reduced_retries=reduced_retries)
                return self._parse_release_results(data) if data else []
            except Exception as e:
                print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
                return []

        cached_result = self._get_cached_or_fetch("search", key, fetch_func)
        if cached_result is not None and len(cached_result) > 0:
            print(f"Using cached result for: {song_data.album} by {song_data.artist}")
        return cached_result or []

    def get_release_info(self, release_mbid: str, batch_progress: Optional[Tuple[int, int]] = None) -> Optional[ReleaseInfo]:
        """
        Get detailed release information including track listing with caching.

        Args:
            release_mbid: MusicBrainz release ID
            batch_progress: Optional tuple (current, total) for batch operations (e.g., (1, 5))

        Returns:
            ReleaseInfo with tracks or None if failed
        """
        # Generate cache key
        key = self._generate_release_info_cache_key("get_release_info", release_mbid)

        def fetch_func():
            url = f"{self.base_url}/release/{release_mbid}"
            params = {
                'inc': 'recordings+artist-credits+media+release-groups',
                'fmt': 'json'
            }

            try:
                if not batch_progress:
                    print(f"Fetching release details for MBID: {release_mbid}")
                data = self._make_request(url, params, batch_progress=batch_progress)
                return self._parse_release_info(data) if data else None
            except Exception as e:
                print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
                return None

        # Skip cache check for batch operations to show progress
        skip_cache = batch_progress is not None
        result = self._get_cached_or_fetch("release_info", key, fetch_func, skip_cache=skip_cache)

        if result is not None and not skip_cache:
            print(f"Using cached release info for MBID: {release_mbid}")

        return result

    def search_artist_releases(self, artist: str, year: Optional[int] = None, max_results: Optional[int] = None, release_type: Optional[str] = None) -> List[MusicBrainzSong]:
        """
        Search for releases by a specific artist.
        Fetches all available releases using pagination.

        Args:
            artist: Artist name to search for
            year: Optional year filter
            max_results: Optional maximum number of results to fetch (None = fetch all)
            release_type: Optional release type filter (e.g., "Album", "Single", "EP", "Compilation", "Live", etc.)

        Returns:
            List of releases by the artist
        """
        query = self._build_query(artist=artist, date=year, release_type=release_type)
        url = f"{self.base_url}/release"
        all_results = []
        offset = 0

        try:
            while True:
                params = {
                    'query': query,
                    'fmt': 'json',
                    'limit': PAGINATION_LIMIT,
                    'offset': offset,
                    'inc': 'release-groups'
                }

                data = self._make_request(url, params)
                if not data:
                    break

                releases = data.get('releases', [])
                if not releases:
                    break

                all_results.extend(self._parse_release_results(data))

                count = data.get('count', 0)
                if offset + len(releases) >= count:
                    break

                if max_results and len(all_results) >= max_results:
                    all_results = all_results[:max_results]
                    break

                offset += PAGINATION_LIMIT
                time.sleep(self.request_delay)

            return all_results
        except Exception as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return all_results if all_results else []

    def search_artist_compilations(self, artist: str, year: Optional[int] = None, max_results: Optional[int] = None) -> List[MusicBrainzSong]:
        """
        Search for compilations where the artist appears as a track artist but not as the main release artist.
        This finds compilations, soundtracks, and other multi-artist releases where the artist contributed tracks.

        Args:
            artist: Artist name to search for
            year: Optional year filter
            max_results: Optional maximum number of results to fetch (None = fetch all)

        Returns:
            List of compilation releases where the artist appears
        """
        query = self._build_query(artist=artist, date=year)
        url = f"{self.base_url}/recording"
        all_results = []
        seen_release_mbids = set()
        offset = 0

        try:
            while True:
                params = {
                    'query': query,
                    'fmt': 'json',
                    'limit': PAGINATION_LIMIT,
                    'offset': offset,
                    'inc': 'releases+release-groups'
                }

                data = self._make_request(url, params)
                if not data:
                    break

                recordings = data.get('recordings', [])
                if not recordings:
                    break

                for recording in recordings:
                    artist_credits = recording.get('artist-credit', [])
                    recording_artist = artist_credits[0].get('name', '') if artist_credits else ''

                    for release in recording.get('releases', []):
                        release_mbid = release.get('id', '')
                        if not release_mbid or release_mbid in seen_release_mbids:
                            continue

                        release_artist_credits = release.get('artist-credit', [])
                        release_artist = release_artist_credits[0].get('name', '') if release_artist_credits else ''

                        release_group = release.get('release-group', {})
                        release_type = release_group.get('primary-type')
                        secondary_types = release_group.get('secondary-types', [])

                        is_compilation = (
                            release_type in COMPILATION_TYPES or
                            any(t in COMPILATION_TYPES for t in secondary_types)
                        )

                        normalized_recording = normalize_string(recording_artist)
                        normalized_release = normalize_string(release_artist)
                        normalized_search = normalize_string(artist)

                        if (is_compilation and
                            normalized_recording == normalized_search and
                            normalized_release != normalized_recording):

                            album = release.get('title', '')
                            release_date = release.get('date', '')
                            original_release_date = release_group.get('first-release-date')

                            if not release_date and original_release_date:
                                release_date = original_release_date

                            if year:
                                try:
                                    release_year = int(release_date[:4]) if release_date and len(release_date) >= 4 else None
                                    if release_year != year:
                                        continue
                                except ValueError:
                                    pass

                            result = MusicBrainzSong(
                                title='',
                                artist=release_artist,
                                album=album,
                                release_date=release_date,
                                original_release_date=original_release_date,
                                genre=None,
                                release_type='Compilation' if release_type == 'Compilation' or 'Compilation' in secondary_types else release_type,
                                mbid=release_mbid,
                                score=recording.get('score', 0),
                                url=f"https://musicbrainz.org/release/{release_mbid}"
                            )

                            all_results.append(result)
                            seen_release_mbids.add(release_mbid)

                            if max_results and len(all_results) >= max_results:
                                return all_results[:max_results]

                count = data.get('count', 0)
                if offset + len(recordings) >= count or (max_results and len(all_results) >= max_results):
                    break

                offset += PAGINATION_LIMIT
                time.sleep(self.request_delay)

            return all_results
        except Exception as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return all_results if all_results else []

    def _parse_recording_results(self, data: Dict[str, Any]) -> List[MusicBrainzSong]:
        """Parse recording search results."""
        results = []

        for recording in data.get('recordings', []):
            title = recording.get('title', '')
            mbid = recording.get('id', '')
            score = recording.get('score', 0)

            artist_credits = recording.get('artist-credit', [])
            artist = artist_credits[0].get('name', '') if artist_credits else ''

            album = None
            release_date = None
            original_release_date = None
            genre = None

            releases = recording.get('releases', [])
            if releases:
                release = releases[0]
                album = release.get('title', '')
                release_date = release.get('date', '')

                release_group = release.get('release-group')
                if release_group:
                    original_release_date = release_group.get('first-release-date')
                    if not release_date and original_release_date:
                        release_date = original_release_date

                genres = release.get('genres', [])
                genre = genres[0] if genres else None

            results.append(MusicBrainzSong(
                title=title,
                artist=artist,
                album=album,
                release_date=release_date,
                original_release_date=original_release_date,
                genre=genre,
                mbid=mbid,
                score=score,
                url=f"https://musicbrainz.org/recording/{mbid}"
            ))

        return results

    def _parse_release_results(self, data: Dict[str, Any]) -> List[MusicBrainzSong]:
        """Parse release search results."""
        results = []

        for release in data.get('releases', []):
            album = release.get('title', '')
            mbid = release.get('id', '')
            score = release.get('score', 0)
            release_date = release.get('date', '')

            artist = self._parse_artist_credit(release.get('artist-credit', []))

            release_type = None
            original_release_date = None
            release_group = release.get('release-group')
            if release_group:
                release_type = release_group.get('primary-type')
                secondary_types = release_group.get('secondary-types', [])
                if secondary_types:
                    release_type = secondary_types[0]
                original_release_date = release_group.get('first-release-date')
                if not release_date and original_release_date:
                    release_date = original_release_date

            results.append(MusicBrainzSong(
                title='',
                artist=artist,
                album=album,
                release_date=release_date,
                original_release_date=original_release_date,
                genre=None,
                release_type=release_type,
                mbid=mbid,
                score=score,
                url=f"https://musicbrainz.org/release/{mbid}"
            ))

        return results

    def _parse_artist_credit(self, artist_credits: List[Any]) -> str:
        """
        Parse MusicBrainz artist-credit array to build full artist name.

        Handles collaborative artists with join phrases (e.g., "Artist A & Artist B").
        """
        if not artist_credits:
            return ''

        artist_parts = []

        for index, credit in enumerate(artist_credits):
            if isinstance(credit, str):
                artist_parts.append(credit)
                continue
            if not isinstance(credit, dict):
                continue

            # MusicBrainz exposes the credited name separately from the
            # canonical artist name. Preserve what appeared on the release.
            name = credit.get('name')
            if not name:
                artist_obj = credit.get('artist')
                name = (
                    artist_obj.get('name')
                    if isinstance(artist_obj, dict)
                    else artist_obj
                )
            if name:
                artist_parts.append(str(name))

            if 'joinphrase' in credit:
                artist_parts.append(str(credit.get('joinphrase') or ''))
            elif index < len(artist_credits) - 1:
                # Retain compatibility with simplified fixtures or providers
                # that omit MusicBrainz's joinphrase field.
                artist_parts.append(' & ')

        return ''.join(artist_parts).strip()

    def _parse_release_info(self, data: Dict[str, Any]) -> Optional[ReleaseInfo]:
        """Parse detailed release information."""
        try:
            title = data.get('title', '')
            mbid = data.get('id', '')
            release_date = data.get('date', '')

            artist = self._parse_artist_credit(data.get('artist-credit', []))

            genres = data.get('genres', [])
            genre = genres[0].get('name', '') if genres else None

            release_type = None
            original_release_date = None
            release_group = data.get('release-group')
            if release_group:
                release_type = release_group.get('primary-type')
                secondary_types = release_group.get('secondary-types', [])
                if secondary_types:
                    release_type = secondary_types[0]
                original_release_date = release_group.get('first-release-date')
                if not release_date and original_release_date:
                    release_date = original_release_date

            # Parse tracks
            tracks = []
            current_position = 1

            for medium in data.get('media', []):
                for track_data in medium.get('tracks', []):
                    recording = track_data.get('recording', {})
                    track_title = recording.get('title', '')
                    track_mbid = recording.get('id', '')

                    track_artist_credits = recording.get('artist-credit', [])
                    track_artist = self._parse_artist_credit(track_artist_credits) or artist

                    duration = None
                    for source in [track_data, recording]:
                        if 'length' in source and source['length']:
                            duration = format_duration_ms(source['length'])
                            break

                    tracks.append(Track(
                        position=current_position,
                        title=track_title,
                        artist=track_artist,
                        duration=duration,
                        mbid=track_mbid
                    ))
                    current_position += 1

            return ReleaseInfo(
                title=title,
                artist=artist,
                release_date=release_date,
                original_release_date=original_release_date,
                genre=genre,
                release_type=release_type,
                mbid=mbid,
                url=f"https://musicbrainz.org/release/{mbid}",
                tracks=tracks
            )

        except Exception as e:
            print(f"Error parsing release info: {e}")
            return None
