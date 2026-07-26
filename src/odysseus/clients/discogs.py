"""
Discogs Client Module
A client for searching the Discogs database for music information.
"""

import time
from typing import Any, Dict, List, Optional, Tuple
from ..models.song import SongData
from ..models.search_results import DiscogsRelease
from ..models.releases import Track, ReleaseInfo
from ..core.config import DISCOGS_CONFIG, ERROR_MESSAGES
from .base_api_client import BaseAPIClient


class DiscogsClient(BaseAPIClient):
    """Discogs search client."""

    def __init__(self, cache_manager=None, http_client=None):
        """
        Initialize Discogs client.

        Args:
            cache_manager: Optional CacheManager instance (will use global if not provided)
            http_client: Optional HttpClient instance (will use global if not provided)
        """
        super().__init__(DISCOGS_CONFIG, cache_manager, http_client)

        self.user_token = DISCOGS_CONFIG.get("USER_TOKEN")  # Optional, for higher rate limits

        # Setup Discogs-specific session headers
        # Access the session manager from http_client to set up Discogs-specific headers
        if hasattr(self.http_client, 'session_manager'):
            session = self.http_client.session_manager.get_session("discogs")
            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'application/json'
            }
            # Add user token if available (for higher rate limits)
            if self.user_token:
                headers['Authorization'] = f'Discogs token={self.user_token}'
            session.headers.update(headers)

    def _make_request(self, url: str, params: Dict[str, Any], batch_progress: Optional[Tuple[int, int]] = None) -> Optional[Dict[str, Any]]:
        """
        Make a request using HttpClient with retries and Discogs-specific error handling.

        Args:
            url: Request URL
            params: Request parameters
            batch_progress: Optional tuple (current, total) for batch operations (e.g., (1, 5))
        """
        def log_callback(message: str, dim: bool = False):
            formatted = self._format_progress_message(message, batch_progress)
            if dim:
                print(f"\033[2m{formatted}\033[0m")
            else:
                print(formatted)

        # Use HttpClient.get() to get response object so we can check status code
        response = self._make_request_response(
            url, params, batch_progress, log_callback, rate_limit_wait=60, session_name="discogs"
        )

        if response is None:
            return None

        # Check for 403 Forbidden (often User-Agent or authentication issue)
        if response.status_code == 403:
            print(self._format_progress_message("403 Forbidden: Discogs API blocked the request", batch_progress))
            print(self._format_progress_message("This usually means:", batch_progress))
            print(self._format_progress_message("  1. User-Agent format issue (Discogs requires contact info)", batch_progress))
            print(self._format_progress_message("  2. Rate limit exceeded (60 req/min without token, 300 with token)", batch_progress))
            print(self._format_progress_message("  3. Missing or invalid authentication token", batch_progress))
            print(self._format_progress_message("Note: Discogs search may be unavailable. MusicBrainz results will still work.", batch_progress))
            return None

        # Parse JSON response
        if response.status_code == 200:
            try:
                return response.json()
            except ValueError:
                return None

        return None

    def search_release(self, song_data: SongData, offset: int = 0, limit: Optional[int] = None, release_type: Optional[str] = None) -> List[DiscogsRelease]:
        """
        Search for releases in Discogs with caching.

        Args:
            song_data: Song information to search for
            offset: Offset for pagination (default: 0)
            limit: Maximum number of results (default: uses self.max_results)
            release_type: Optional release type filter (e.g., "album", "single", "ep", etc.)

        Returns:
            List of Discogs results
        """
        # Generate cache key from search parameters
        key = self._generate_search_cache_key(
            "discogs_search_release",
            song_data.title,
            song_data.album,
            song_data.artist,
            song_data.release_year,
            offset,
            limit or self.max_results,
            release_type
        )

        def fetch_func():
            # Build query string
            query_parts = []
            if song_data.title:
                query_parts.append(song_data.title)
            if song_data.artist:
                query_parts.append(song_data.artist)
            if song_data.album:
                query_parts.append(song_data.album)
            query = ' '.join(query_parts)

            # Make request
            url = f"{self.base_url}/database/search"
            params = {
                'q': query,
                'type': 'release',
                'per_page': limit or self.max_results,
                'page': (offset // (limit or self.max_results)) + 1 if offset > 0 else 1
            }

            # Add release type filter if specified
            if release_type:
                params['format'] = release_type.lower()

            try:
                # Dimmed text for technical/log message - Discogs is used for deduplication
                import sys
                if sys.stdout.isatty():
                    print(f"\033[2;36mℹ\033[0m \033[2mSearching Discogs (for deduplication): {query}\033[0m", flush=True)
                else:
                    print(f"Searching Discogs releases with query: {query}")
                data = self._make_request(url, params)
                return self._parse_release_results(data) if data else []
            except Exception as e:
                print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
                return []

        cached_result = self._get_cached_or_fetch("search", key, fetch_func)
        if cached_result is not None and len(cached_result) > 0:
            print(f"Using cached Discogs result for: {song_data.album} by {song_data.artist}")
        return cached_result or []

    def _search_artist_id(self, artist: str) -> Optional[int]:
        """
        Search for an artist by name and return their Discogs ID.

        Args:
            artist: Artist name to search for

        Returns:
            Artist ID if found, None otherwise
        """
        url = f"{self.base_url}/database/search"
        params = {
            'q': artist,
            'type': 'artist',
            'per_page': 5  # Only need the first result
        }

        data = self._make_request(url, params)
        if not data:
            return None

        results = data.get('results', [])
        if results:
            # Return the first (most relevant) artist ID
            return results[0].get('id')

        return None

    def search_artist_releases(self, artist: str, year: Optional[int] = None, max_results: Optional[int] = None, release_type: Optional[str] = None) -> List[DiscogsRelease]:
        """
        Search for releases by a specific artist using the faster artist releases endpoint.
        First finds the artist ID, then fetches their releases directly.

        Args:
            artist: Artist name to search for
            year: Optional year filter (applied client-side after fetching)
            max_results: Optional maximum number of results to fetch (None = use default limit of 500)
            release_type: Optional release type filter (e.g., "album", "single", "ep", etc.) - applied client-side

        Returns:
            List of releases by the artist
        """
        # Set a reasonable default limit if none specified
        if max_results is None:
            max_results = 500

        # Step 1: Find the artist ID (much faster than searching releases)
        print(f"Searching for artist: {artist}")
        artist_id = self._search_artist_id(artist)

        if not artist_id:
            print(f"Artist '{artist}' not found on Discogs")
            return []

        # Step 2: Use the direct artist releases endpoint (much faster!)
        url = f"{self.base_url}/artists/{artist_id}/releases"
        all_results = []
        page = 1
        per_page = 100  # Discogs allows up to 100 results per page for this endpoint
        max_pages = min(50, (max_results // per_page) + 1)

        try:
            while page <= max_pages:
                params = {
                    'per_page': per_page,
                    'page': page,
                    'sort': 'year',  # Sort by year for better organization
                    'sort_order': 'desc'  # Most recent first
                }

                data = self._make_request(url, params)

                if not data:
                    break

                releases = data.get('releases', [])
                if not releases:
                    break

                # Parse releases from the artist releases endpoint (different format than search)
                for release_data in releases:
                    # The artist releases endpoint returns a different structure
                    release_info = release_data.get('basic_information', release_data)

                    title = release_info.get('title', '')
                    release_id = str(release_info.get('id', ''))
                    year_val = release_info.get('year', 0)

                    # Extract artist and album from title (format: "Artist - Album" or just "Album")
                    artist_name = artist  # We already know the artist
                    album = title
                    if ' - ' in title:
                        parts = title.split(' - ', 1)
                        album = parts[1].strip()

                    # Get additional metadata
                    genres = release_info.get('genres', [])
                    genre = genres[0] if genres else None

                    styles = release_info.get('styles', [])
                    style = styles[0] if styles else None

                    labels = release_info.get('labels', [])
                    label = labels[0].get('name') if labels else None

                    country = release_info.get('country', '')

                    formats = release_info.get('formats', [])
                    format_type = None
                    if formats:
                        format_type = formats[0].get('name', '')

                    # Prefer full-size image over thumbnail
                    # Discogs provides: 'thumb' (low quality), 'cover_image' (full size)
                    cover_art_url = release_info.get('cover_image', '') or release_info.get('thumb', '')
                    cover_art_url = cover_art_url if cover_art_url else None

                    url_str = release_info.get('resource_url', '') or f"https://www.discogs.com/release/{release_id}"

                    # Apply year filter if specified
                    if year and year_val != year:
                        continue

                    # Apply release type filter if specified
                    if release_type and format_type:
                        if release_type.lower() not in format_type.lower():
                            continue

                    result = DiscogsRelease(
                        title=album,
                        artist=artist_name,
                        album=album,
                        year=year_val if year_val > 0 else None,
                        genre=genre,
                        style=style,
                        label=label,
                        country=country,
                        format=format_type,
                        cover_art_url=cover_art_url,
                        discogs_id=release_id,
                        url=url_str,
                        score=0
                    )
                    all_results.append(result)

                    # Check if we've reached max_results limit
                    if len(all_results) >= max_results:
                        break

                if len(all_results) >= max_results:
                    all_results = all_results[:max_results]
                    break

                # Check if we've fetched all results
                pagination = data.get('pagination', {})
                total_pages = pagination.get('pages', 0)
                current_page_num = pagination.get('page', page)

                # Safety check: if pagination says we're on the last page, stop
                if total_pages > 0 and current_page_num >= total_pages:
                    break

                # If we got fewer results than per_page, we're likely on the last page
                if len(releases) < per_page:
                    break

                page += 1

                # Rate limiting between requests
                time.sleep(self.request_delay)

            if page > max_pages:
                print(f"Reached maximum page limit ({max_pages}). Stopping pagination.")

            return all_results

        except Exception as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return all_results if all_results else []

    def get_release_info(self, release_id: str, batch_progress: Optional[Tuple[int, int]] = None) -> Optional[ReleaseInfo]:
        """
        Get detailed release information including track listing with caching.

        Args:
            release_id: Discogs release ID
            batch_progress: Optional tuple (current, total) for batch operations (e.g., (1, 5))

        Returns:
            ReleaseInfo with tracks or None if failed
        """
        # Generate cache key
        key = self._generate_release_info_cache_key("discogs_get_release_info", release_id)

        def fetch_func():
            url = f"{self.base_url}/releases/{release_id}"
            try:
                if not batch_progress:
                    print(f"Fetching release details for Discogs ID: {release_id}")
                data = self._make_request(url, {}, batch_progress=batch_progress)
                if data:
                    return self._parse_release_info(data)
                else:
                    print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: Failed to get data from Discogs")
                    return None
            except Exception as e:
                print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
                return None

        # Skip cache check for batch operations to show progress
        skip_cache = batch_progress is not None
        result = self._get_cached_or_fetch("release_info", key, fetch_func, skip_cache=skip_cache)

        if result is not None and not skip_cache:
            print(f"Using cached Discogs release info for ID: {release_id}")

        return result

    def _parse_release_results(self, data: Dict[str, Any]) -> List[DiscogsRelease]:
        """Parse release search results."""
        results = []

        releases = data.get('results', [])
        for release in releases:
            title = release.get('title', '')
            release_id = str(release.get('id', ''))
            year = release.get('year')

            # Extract artist and album from title (format: "Artist - Album" or "Artist - Title")
            artist = ''
            album = ''
            if ' - ' in title:
                parts = title.split(' - ', 1)
                artist = parts[0].strip()
                album = parts[1].strip()
            else:
                album = title

            # Get additional metadata
            genre = None
            style = None
            label = None
            country = None
            format_type = None
            cover_art_url = None

            genres = release.get('genre', [])
            if genres:
                genre = genres[0]

            styles = release.get('style', [])
            if styles:
                style = styles[0]

            labels = release.get('label', [])
            if labels:
                label = labels[0]

            country = release.get('country', '')

            formats = release.get('format', [])
            if formats:
                format_type = formats[0]

            # Prefer full-size image over thumbnail
            # Discogs search results may have 'cover_image' (full size) or 'thumb' (thumbnail)
            cover_art_url = release.get('cover_image', '') or release.get('thumb', '')
            cover_art_url = cover_art_url if cover_art_url else None

            url = release.get('uri', '') or f"https://www.discogs.com/release/{release_id}"

            result = DiscogsRelease(
                title=album,  # Use album as title for consistency
                artist=artist,
                album=album,
                year=year,
                genre=genre,
                style=style,
                label=label,
                country=country,
                format=format_type,
                cover_art_url=cover_art_url,
                discogs_id=release_id,
                url=url,
                score=0  # Discogs doesn't provide scores in search results
            )
            results.append(result)

        return results

    def _parse_release_info(self, data: Dict[str, Any]) -> Optional[ReleaseInfo]:
        """Parse detailed release information."""
        try:
            # Basic release info
            title = data.get('title', '')
            release_id = str(data.get('id', ''))
            year = data.get('year')
            release_date = str(year) if year else None

            # Extract artist and album from title (format: "Artist - Album")
            artist = ''
            album = title
            if ' - ' in title:
                parts = title.split(' - ', 1)
                artist = parts[0].strip()
                album = parts[1].strip()

            # Get genre information
            genres = data.get('genres', [])
            genre = None
            if genres:
                genre = genres[0]

            # Get release type from format
            release_type = None
            formats = data.get('formats', [])
            if formats:
                format_info = formats[0]
                release_type = format_info.get('name', '').title()  # e.g., "Album", "Single", "EP"

            url = data.get('uri', '') or f"https://www.discogs.com/release/{release_id}"

            # Get cover art URL - prefer full-size images
            cover_art_url = None
            images = data.get('images', [])
            if images:
                # Use the primary image or first image
                # Prefer 'uri' (full-size) over 'uri150' (150px thumbnail)
                for img in images:
                    if img.get('type') == 'primary' or img.get('type') == 'secondary':
                        # Prefer full-size uri, fall back to uri150, then resource_url
                        cover_art_url = img.get('uri') or img.get('uri150') or img.get('resource_url')
                        break
                # If no primary/secondary, use first image
                if not cover_art_url and images:
                    # Prefer full-size uri, fall back to uri150, then resource_url
                    cover_art_url = images[0].get('uri') or images[0].get('uri150') or images[0].get('resource_url')

            # Parse tracks
            tracks = []
            tracklist = data.get('tracklist', [])

            # Use sequential positions (1, 2, 3, ..., N) instead of parsing Discogs positions
            # Discogs positions are per-side for vinyl (A1, A2, B1, B2, etc.) which causes duplicates
            # Sequential positions work better for downloads and track selection
            for idx, track_data in enumerate(tracklist, start=1):
                track_title = track_data.get('title', '')
                duration = track_data.get('duration', '')

                # Get track artist (usually same as release artist, but can be different)
                track_artist = artist
                if 'artists' in track_data and track_data['artists']:
                    track_artist = track_data['artists'][0].get('name', artist)

                # Use sequential position (idx) instead of parsing Discogs position field
                # This ensures positions are 1, 2, 3, ..., N across all sides/discs
                # Discogs positions like "A1", "A2", "B1", "B2" would become 1, 2, 1, 2 (duplicates)
                position = idx

                track = Track(
                    position=position,
                    title=track_title,
                    artist=track_artist,
                    duration=duration if duration else None
                )
                tracks.append(track)

            return ReleaseInfo(
                title=album,
                artist=artist,
                release_date=release_date,
                genre=genre,
                release_type=release_type,
                mbid=release_id,  # Use Discogs ID in mbid field for consistency
                url=url,
                cover_art_url=cover_art_url,
                tracks=tracks
            )

        except Exception as e:
            print(f"Error parsing release info: {e}")
            return None
