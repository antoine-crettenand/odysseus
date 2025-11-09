"""
MusicBrainz Client Module
A client for searching the MusicBrainz database for music information.
"""

import requests
import json
import time
from typing import Dict, List, Optional, Any
from ..models.song import SongData
from ..models.search_results import MusicBrainzSong
from ..models.releases import Track, ReleaseInfo
from ..core.config import MUSICBRAINZ_CONFIG, ERROR_MESSAGES
from ..utils.string_utils import normalize_string

# Note: SSL verification is enabled by default for security
# If you encounter SSL issues, check your system's certificate store


class MusicBrainzClient:
    """MusicBrainz search client."""
    
    def __init__(self):
        self.base_url = MUSICBRAINZ_CONFIG["BASE_URL"]
        self.user_agent = MUSICBRAINZ_CONFIG["USER_AGENT"]
        self.request_delay = MUSICBRAINZ_CONFIG["REQUEST_DELAY"]
        self.max_results = MUSICBRAINZ_CONFIG["MAX_RESULTS"]
        self.timeout = MUSICBRAINZ_CONFIG["TIMEOUT"]
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'application/json'
        })
        
        # SSL verification is enabled by default for security
        # MusicBrainz uses valid SSL certificates, so verification should work
        self.session.verify = True
        
        # Track if we should try HTTP fallback (only as last resort)
        self.use_http_fallback = False
    
    def _make_request(self, url: str, params: Dict[str, Any], batch_progress: Optional[tuple[int, int]] = None) -> Optional[Dict[str, Any]]:
        """
        Make a request with SSL error handling and retries.
        
        Args:
            url: Request URL
            params: Request parameters
            batch_progress: Optional tuple (current, total) for batch operations (e.g., (1, 5))
        """
        base_max_retries = 3
        retry_delay = 2
        # Track if we've seen transient SSL errors (will use more retries)
        seen_transient_ssl_error = False
        max_retries = base_max_retries
        
        # Build progress prefix if batch progress is provided
        progress_prefix = ""
        if batch_progress:
            current, total = batch_progress
            progress_prefix = f"[{current}/{total}] "
        
        # Calculate page number from offset and limit if available
        page_info = ""
        if 'offset' in params and 'limit' in params:
            offset = params.get('offset', 0)
            limit = params.get('limit', 100)
            if limit > 0:
                page = (offset // limit) + 1
                page_info = f" (page {page})"
        
        # Try HTTPS first
        attempt = 0
        while attempt < max_retries:
            try:
                if batch_progress:
                    print(f"{progress_prefix}Making request to MusicBrainz{page_info} (attempt {attempt + 1}/{max_retries})")
                else:
                    print(f"Making request to MusicBrainz{page_info} (attempt {attempt + 1}/{max_retries})")
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                
                # Rate limiting
                time.sleep(self.request_delay)
                
                return response.json()
                
            except requests.exceptions.SSLError as e:
                # Check if this is a transient SSL error (SSLEOFError) vs certificate error
                error_str = str(e).lower()
                is_transient = 'eof' in error_str or 'unexpected_eof' in error_str or 'connection' in error_str
                
                # For transient errors, allow more retries (increase max_retries for future attempts)
                if is_transient and not seen_transient_ssl_error:
                    seen_transient_ssl_error = True
                    max_retries = 5  # Increase retries for transient SSL errors
                    # Continue the loop with the new max_retries
                
                if batch_progress:
                    if is_transient:
                        print(f"{progress_prefix}SSL Connection Error (attempt {attempt + 1}/{max_retries}): {e}")
                        print(f"{progress_prefix}This appears to be a transient network issue. Retrying...")
                    else:
                        print(f"{progress_prefix}SSL Error (attempt {attempt + 1}/{max_retries}): {e}")
                        print(f"{progress_prefix}Note: SSL verification is required for security. Please check your system's certificate store.")
                else:
                    if is_transient:
                        print(f"SSL Connection Error (attempt {attempt + 1}/{max_retries}): {e}")
                        print("This appears to be a transient network issue. Retrying...")
                    else:
                        print(f"SSL Error (attempt {attempt + 1}/{max_retries}): {e}")
                        print("Note: SSL verification is required for security. Please check your system's certificate store.")
                
                if attempt < max_retries - 1:
                    # For transient errors, use longer delays (network issues need more time)
                    # For certificate errors, use shorter delays (won't help but faster failure)
                    delay = retry_delay * 2 if is_transient else retry_delay
                    if batch_progress:
                        print(f"{progress_prefix}Retrying in {delay} seconds...")
                    else:
                        print(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                    retry_delay *= 2  # Exponential backoff
                    attempt += 1
                    continue  # Continue to next iteration
                else:
                    # SSL errors should not fall back to HTTP for security reasons
                    if batch_progress:
                        if is_transient:
                            print(f"{progress_prefix}SSL connection failed after {max_retries} attempts. This may be a network issue.")
                        else:
                            print(f"{progress_prefix}SSL verification failed. Please check your system's SSL certificates.")
                    else:
                        if is_transient:
                            print(f"SSL connection failed after {max_retries} attempts. This may be a network issue.")
                        else:
                            print("SSL verification failed. Please check your system's SSL certificates.")
                    return None
                    
            except requests.exceptions.ConnectionError as e:
                if batch_progress:
                    print(f"{progress_prefix}Connection Error (attempt {attempt + 1}): {e}")
                else:
                    print(f"Connection Error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    if batch_progress:
                        print(f"{progress_prefix}Retrying in {retry_delay} seconds...")
                    else:
                        print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    attempt += 1
                    continue  # Continue to next iteration
                else:
                    if batch_progress:
                        print(f"{progress_prefix}All connection retry attempts failed, trying HTTP fallback...")
                    else:
                        print("All connection retry attempts failed, trying HTTP fallback...")
                    return self._try_http_fallback(url, params, batch_progress)
                    
            except requests.exceptions.RequestException as e:
                if batch_progress:
                    print(f"{progress_prefix}Request Error: {e}")
                else:
                    print(f"Request Error: {e}")
                return None
                
        return None
    
    def _try_http_fallback(self, url: str, params: Dict[str, Any], batch_progress: Optional[tuple[int, int]] = None) -> Optional[Dict[str, Any]]:
        """
        Try HTTP fallback if HTTPS fails (only for connection errors, not SSL errors).
        
        WARNING: HTTP is insecure and should only be used as a last resort.
        This method is kept for backward compatibility but should rarely be needed.
        """
        if self.use_http_fallback:
            return None  # Already tried HTTP
            
        # Build progress prefix if batch progress is provided
        progress_prefix = ""
        if batch_progress:
            current, total = batch_progress
            progress_prefix = f"[{current}/{total}] "
            
        try:
            # Convert HTTPS URL to HTTP
            http_url = url.replace('https://', 'http://')
            if batch_progress:
                print(f"{progress_prefix}Warning: Trying insecure HTTP fallback: {http_url}")
                print(f"{progress_prefix}Note: HTTP is not secure. This should only be used if HTTPS is unavailable.")
            else:
                print(f"Warning: Trying insecure HTTP fallback: {http_url}")
                print("Note: HTTP is not secure. This should only be used if HTTPS is unavailable.")
            
            response = self.session.get(http_url, params=params, timeout=self.timeout, verify=False)
            response.raise_for_status()
            
            # Rate limiting
            time.sleep(self.request_delay)
            
            self.use_http_fallback = True
            return response.json()
            
        except Exception as e:
            if batch_progress:
                print(f"{progress_prefix}HTTP fallback also failed: {e}")
            else:
                print(f"HTTP fallback also failed: {e}")
            return None
    
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
        # Build query string
        query_parts = []
        
        if song_data.title:
            query_parts.append(f'title:"{song_data.title}"')
        
        if song_data.artist:
            query_parts.append(f'artist:"{song_data.artist}"')
        
        if song_data.album:
            query_parts.append(f'release:"{song_data.album}"')
        
        if song_data.release_year:
            query_parts.append(f'date:{song_data.release_year}')
        
        query = ' AND '.join(query_parts)
        
        # Make request
        url = f"{self.base_url}/recording"
        params = {
            'query': query,
            'fmt': 'json',
            'limit': limit or self.max_results,
            'offset': offset,
            'inc': 'releases+release-groups'  # Include release and release-group info for better date enrichment
        }
        
        try:
            print(f"Searching MusicBrainz recordings with query: {query}")
            data = self._make_request(url, params)
            
            if data:
                return self._parse_recording_results(data)
            else:
                print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: Failed to get data from MusicBrainz")
                return []
            
        except Exception as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return []
    
    def search_release(self, song_data: SongData, offset: int = 0, limit: Optional[int] = None, release_type: Optional[str] = None) -> List[MusicBrainzSong]:
        """
        Search for releases (albums) in MusicBrainz.
        
        Args:
            song_data: Song information to search for
            offset: Offset for pagination (default: 0)
            limit: Maximum number of results (default: uses self.max_results)
            release_type: Optional release type filter (e.g., "Album", "Single", "EP", "Compilation", "Live", etc.)
            
        Returns:
            List of MusicBrainz results
        """
        query_parts = []
        
        if song_data.album:
            query_parts.append(f'title:"{song_data.album}"')
        
        if song_data.artist:
            query_parts.append(f'artist:"{song_data.artist}"')
        
        if song_data.release_year:
            query_parts.append(f'date:{song_data.release_year}')
        
        # Add release type filter if specified
        if release_type:
            query_parts.append(f'type:"{release_type}"')
        
        query = ' AND '.join(query_parts)
        
        url = f"{self.base_url}/release"
        params = {
            'query': query,
            'fmt': 'json',
            'limit': limit or self.max_results,
            'offset': offset,
            'inc': 'release-groups'  # Include release-group info to get release type
        }
        
        try:
            print(f"Searching MusicBrainz releases with query: {query}")
            data = self._make_request(url, params)
            
            if data:
                return self._parse_release_results(data)
            else:
                print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: Failed to get data from MusicBrainz")
                return []
            
        except Exception as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return []
    
    def get_release_info(self, release_mbid: str, batch_progress: Optional[tuple[int, int]] = None) -> Optional[ReleaseInfo]:
        """
        Get detailed release information including track listing.
        
        Args:
            release_mbid: MusicBrainz release ID
            batch_progress: Optional tuple (current, total) for batch operations (e.g., (1, 5))
            
        Returns:
            ReleaseInfo with tracks or None if failed
        """
        url = f"{self.base_url}/release/{release_mbid}"
        params = {
            'inc': 'recordings+artist-credits+media+release-groups',
            'fmt': 'json'
        }
        
        try:
            if not batch_progress:
                print(f"Fetching release details for MBID: {release_mbid}")
            data = self._make_request(url, params, batch_progress=batch_progress)
            
            if data:
                return self._parse_release_info(data)
            else:
                print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: Failed to get data from MusicBrainz")
                return None
            
        except Exception as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return None
    
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
        query_parts = [f'artist:"{artist}"']
        
        if year:
            query_parts.append(f'date:{year}')
        
        # Add release type filter if specified
        if release_type:
            query_parts.append(f'type:"{release_type}"')
        
        query = ' AND '.join(query_parts)
        
        url = f"{self.base_url}/release"
        all_results = []
        offset = 0
        limit = 100  # MusicBrainz allows up to 100 results per request
        
        try:
            # Don't print here - let the UI handle it with loading spinner
            # print(f"Searching releases by artist: {artist}")
            # if year:
            #     print(f"Filtering by year: {year}")
            
            while True:
                params = {
                    'query': query,
                    'fmt': 'json',
                    'limit': limit,
                    'offset': offset,
                    'inc': 'release-groups'  # Include release-group info to get release type
                }
                
                data = self._make_request(url, params)
                
                if not data:
                    break
                
                releases = data.get('releases', [])
                if not releases:
                    break
                
                parsed_results = self._parse_release_results(data)
                all_results.extend(parsed_results)
                
                # Check if we've fetched all results
                count = data.get('count', 0)
                if offset + len(releases) >= count:
                    break
                
                # Check if we've reached max_results limit
                if max_results and len(all_results) >= max_results:
                    all_results = all_results[:max_results]
                    break
                
                offset += limit
                
                # Rate limiting between requests
                time.sleep(self.request_delay)
            
            # Don't print here - let the UI handle it
            # if all_results:
            #     print(f"Found {len(all_results)} release{'s' if len(all_results) != 1 else ''}")
            # else:
            #     print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: Failed to get data from MusicBrainz")
            
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
        # Search for recordings by the artist
        query_parts = [f'artist:"{artist}"']
        
        if year:
            query_parts.append(f'date:{year}')
        
        query = ' AND '.join(query_parts)
        
        url = f"{self.base_url}/recording"
        all_results = []
        seen_release_mbids = set()
        offset = 0
        limit = 100  # MusicBrainz allows up to 100 results per request
        
        try:
            while True:
                params = {
                    'query': query,
                    'fmt': 'json',
                    'limit': limit,
                    'offset': offset,
                    'inc': 'releases+release-groups'  # Include releases to get compilation info
                }
                
                data = self._make_request(url, params)
                
                if not data:
                    break
                
                recordings = data.get('recordings', [])
                if not recordings:
                    break
                
                # Process each recording to find compilations
                for recording in recordings:
                    # Get the recording artist
                    artist_credits = recording.get('artist-credit', [])
                    recording_artist = ''
                    if artist_credits:
                        recording_artist = artist_credits[0].get('name', '')
                    
                    # Get releases this recording appears on
                    releases = recording.get('releases', [])
                    for release in releases:
                        release_mbid = release.get('id', '')
                        if not release_mbid or release_mbid in seen_release_mbids:
                            continue
                        
                        # Get release artist
                        release_artist_credits = release.get('artist-credit', [])
                        release_artist = ''
                        if release_artist_credits:
                            release_artist = release_artist_credits[0].get('name', '')
                        
                        # Get release type from release-group
                        release_group = release.get('release-group', {})
                        release_type = release_group.get('primary-type')
                        secondary_types = release_group.get('secondary-types', [])
                        
                        # Check if this is a compilation or has compilation as secondary type
                        is_compilation = (
                            release_type == 'Compilation' or 
                            'Compilation' in secondary_types or
                            # Also include soundtracks and other multi-artist releases
                            release_type == 'Soundtrack' or
                            'Soundtrack' in secondary_types
                        )
                        
                        # Only include if:
                        # 1. It's a compilation/soundtrack type
                        # 2. The release artist is different from the recording artist (or normalized differently)
                        # 3. The recording artist matches our search artist (normalized)
                        normalized_recording_artist = normalize_string(recording_artist)
                        normalized_release_artist = normalize_string(release_artist)
                        normalized_search_artist = normalize_string(artist)
                        
                        if (is_compilation and 
                            normalized_recording_artist == normalized_search_artist and
                            normalized_release_artist != normalized_recording_artist):
                            
                            # Create a MusicBrainzSong result for this compilation
                            album = release.get('title', '')
                            release_date = release.get('date', '')
                            
                            # Get original release date from release-group
                            original_release_date = None
                            if release_group:
                                original_release_date = release_group.get('first-release-date')
                                # If release date is missing, use original release date as fallback
                                if not release_date and original_release_date:
                                    release_date = original_release_date
                            
                            # Apply year filter if specified
                            if year:
                                release_year = None
                                if release_date and len(release_date) >= 4:
                                    try:
                                        release_year = int(release_date[:4])
                                    except ValueError:
                                        pass
                                if release_year != year:
                                    continue
                            
                            # Use release artist as the main artist (since it's a compilation)
                            # but we know our artist appears on it
                            result = MusicBrainzSong(
                                title='',  # Releases don't have individual track titles
                                artist=release_artist,  # Compilation artist
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
                            
                            # Check if we've reached max_results limit
                            if max_results and len(all_results) >= max_results:
                                return all_results[:max_results]
                
                # Check if we've fetched all results
                count = data.get('count', 0)
                if offset + len(recordings) >= count:
                    break
                
                # If we've reached max_results, stop
                if max_results and len(all_results) >= max_results:
                    break
                
                offset += limit
                
                # Rate limiting between requests
                time.sleep(self.request_delay)
            
            return all_results
            
        except Exception as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return all_results if all_results else []
    
    def _parse_recording_results(self, data: Dict[str, Any]) -> List[MusicBrainzSong]:
        """Parse recording search results."""
        results = []
        
        recordings = data.get('recordings', [])
        for recording in recordings:
            title = recording.get('title', '')
            mbid = recording.get('id', '')
            score = recording.get('score', 0)
            
            # Get artist information
            artist_credits = recording.get('artist-credit', [])
            artist = ''
            if artist_credits:
                artist = artist_credits[0].get('name', '')
            
            # Get release information
            releases = recording.get('releases', [])
            album = None
            release_date = None
            original_release_date = None
            genre = None
            
            if releases:
                release = releases[0]  # Take first release
                album = release.get('title', '')
                release_date = release.get('date', '')
                
                # Get original release date from release-group
                release_group = release.get('release-group')
                if release_group:
                    original_release_date = release_group.get('first-release-date')
                    # If release date is missing, use original release date as fallback
                    if not release_date and original_release_date:
                        release_date = original_release_date
                
                genre = release.get('genres', [])
                if genre:
                    genre = genre[0]
            url = f"https://musicbrainz.org/recording/{mbid}"
            
            result = MusicBrainzSong(
                title=title,
                artist=artist,
                album=album,
                release_date=release_date,
                original_release_date=original_release_date,
                genre=genre,
                mbid=mbid,
                score=score,
                url=url
            )
            results.append(result)
        
        return results
    
    def _parse_release_results(self, data: Dict[str, Any]) -> List[MusicBrainzSong]:
        """Parse release search results."""
        results = []
        
        releases = data.get('releases', [])
        for release in releases:
            album = release.get('title', '')
            mbid = release.get('id', '')
            score = release.get('score', 0)
            release_date = release.get('date', '')
            
            # Get artist information (properly handle collaborative artists)
            artist_credits = release.get('artist-credit', [])
            artist = self._parse_artist_credit(artist_credits)
            
            # Get release type from release-group
            release_type = None
            original_release_date = None
            release_group = release.get('release-group')
            if release_group:
                release_type = release_group.get('primary-type')
                # Also check for secondary types (e.g., "Live" can be a secondary type)
                secondary_types = release_group.get('secondary-types', [])
                if secondary_types:
                    # If there are secondary types, prefer them (e.g., "Live" over "Album")
                    release_type = secondary_types[0] if secondary_types else release_type
                
                # Always capture the original release date from release-group (first-release-date)
                # This helps identify original releases vs re-releases
                original_release_date = release_group.get('first-release-date')
                
                # If release date is missing, use original release date as fallback
                if not release_date and original_release_date:
                    release_date = original_release_date
            
            url = f"https://musicbrainz.org/release/{mbid}"
            
            result = MusicBrainzSong(
                title='',  # Releases don't have individual track titles
                artist=artist,
                album=album,
                release_date=release_date,
                original_release_date=original_release_date,
                genre=None,  # Releases don't have genre in basic search
                release_type=release_type,
                mbid=mbid,
                score=score,
                url=url
            )
            results.append(result)
        
        return results
    
    def _parse_artist_credit(self, artist_credits: List[Dict[str, Any]]) -> str:
        """
        Parse MusicBrainz artist-credit array to build full artist name.
        
        Handles collaborative artists with join phrases (e.g., "Artist A & Artist B").
        Format: [
            {"artist": {"name": "Artist A"}},
            {"name": " & "},  // join phrase
            {"artist": {"name": "Artist B"}}
        ]
        Or simplified: [{"name": "Artist A"}, {"name": " & "}, {"name": "Artist B"}]
        """
        if not artist_credits:
            return ''
        
        artist_names = []
        join_phrases = []
        artist_parts = []
        
        for i, credit in enumerate(artist_credits):
            # If it has an "artist" key, it's an artist entry
            if 'artist' in credit:
                artist_obj = credit['artist']
                if isinstance(artist_obj, dict) and 'name' in artist_obj:
                    artist_name = artist_obj['name']
                    artist_names.append(artist_name)
                    artist_parts.append(artist_name)
                elif isinstance(artist_obj, str):
                    artist_names.append(artist_obj)
                    artist_parts.append(artist_obj)
            # If it only has a "name" key, it could be either:
            # 1. A join phrase (like " & " or " and ")
            # 2. A simplified artist name (legacy format)
            elif 'name' in credit:
                name = credit['name']
                # Check if this looks like a join phrase (contains &, and, or is mostly spaces/punctuation)
                name_stripped = name.strip()
                is_join_phrase = (
                    not name_stripped or  # Empty or just whitespace
                    name_stripped in ['&', 'and', 'And', 'AND'] or
                    '&' in name_stripped or
                    (len(name_stripped) <= 5 and not any(c.isalnum() for c in name_stripped))  # Just punctuation/spaces
                )
                
                if is_join_phrase:
                    # Normalize join phrase to " & " if it's just "&" or similar
                    if name_stripped in ['&', 'and', 'And', 'AND']:
                        join_phrases.append(' & ')
                        artist_parts.append(' & ')
                    else:
                        join_phrases.append(name)
                        artist_parts.append(name)
                else:
                    # This is an artist name (legacy format)
                    artist_names.append(name)
                    artist_parts.append(name)
        
        # If we have multiple artists but no join phrases, add " & " between them
        if len(artist_names) > 1 and not join_phrases:
            # Rebuild with " & " separators
            return ' & '.join(artist_names)
        
        return ''.join(artist_parts) if artist_parts else ''
    
    def _parse_release_info(self, data: Dict[str, Any]) -> Optional[ReleaseInfo]:
        """Parse detailed release information."""
        try:
            # Basic release info
            title = data.get('title', '')
            mbid = data.get('id', '')
            release_date = data.get('date', '')
            
            # Get artist information (properly handle collaborative artists)
            artist_credits = data.get('artist-credit', [])
            artist = self._parse_artist_credit(artist_credits)
            
            # Get genre information
            genres = data.get('genres', [])
            genre = None
            if genres:
                genre = genres[0].get('name', '')
            
            # Get release type from release-group
            release_type = None
            release_group = data.get('release-group')
            if release_group:
                release_type = release_group.get('primary-type')
                # Also check for secondary types (e.g., "Live" can be a secondary type)
                secondary_types = release_group.get('secondary-types', [])
                if secondary_types:
                    # If there are secondary types, prefer them (e.g., "Live" over "Album")
                    release_type = secondary_types[0] if secondary_types else release_type
                
                # If release date is missing, try to get it from release-group's first-release-date
                if not release_date and release_group.get('first-release-date'):
                    release_date = release_group.get('first-release-date')
            
            url = f"https://musicbrainz.org/release/{mbid}"
            
            # Parse tracks
            tracks = []
            media = data.get('media', [])
            if media:
                # Get tracks from the first medium (disc)
                medium = media[0]
                track_list = medium.get('tracks', [])
                
                for track_data in track_list:
                    position = track_data.get('position', 0)
                    recording = track_data.get('recording', {})
                    track_title = recording.get('title', '')
                    track_mbid = recording.get('id', '')
                    
                    # Get track artist (properly handle collaborative artists)
                    track_artist_credits = recording.get('artist-credit', [])
                    track_artist = artist  # Default to release artist
                    if track_artist_credits:
                        track_artist = self._parse_artist_credit(track_artist_credits) or artist
                    
                    # Get duration - check track-level length first, then recording-level
                    duration = None
                    # Track-level length (if available) - this is the actual length on this release
                    # Note: MusicBrainz 'length' field in track/recording objects is in milliseconds
                    if 'length' in track_data and track_data['length']:
                        duration_value = track_data['length']
                        duration = self._format_duration(duration_value)
                    # Fall back to recording-level length if track-level not available
                    elif 'length' in recording and recording['length']:
                        duration_value = recording['length']
                        duration = self._format_duration(duration_value)
                    
                    track = Track(
                        position=position,
                        title=track_title,
                        artist=track_artist,
                        duration=duration,
                        mbid=track_mbid
                    )
                    tracks.append(track)
            
            return ReleaseInfo(
                title=title,
                artist=artist,
                release_date=release_date,
                genre=genre,
                release_type=release_type,
                mbid=mbid,
                url=url,
                tracks=tracks
            )
            
        except Exception as e:
            print(f"Error parsing release info: {e}")
            return None
    
    def _format_duration(self, duration_value: int) -> str:
        """
        Format duration to MM:SS format.
        MusicBrainz API 'length' field is in milliseconds.
        """
        if not duration_value:
            return None
        
        # MusicBrainz 'length' field is in milliseconds
        # Convert to seconds (round to nearest second for display)
        seconds = round(duration_value / 1000)
        minutes = seconds // 60
        seconds = seconds % 60
        
        return f"{minutes:02d}:{seconds:02d}"
