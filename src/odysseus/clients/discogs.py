"""
Discogs Client Module
A client for searching the Discogs database for music information.
"""

import requests
import time
from typing import Dict, List, Optional, Any
from ..models.song import SongData
from ..models.search_results import DiscogsRelease
from ..models.releases import Track, ReleaseInfo
from ..core.config import DISCOGS_CONFIG, ERROR_MESSAGES


class DiscogsClient:
    """Discogs search client."""
    
    def __init__(self):
        self.base_url = DISCOGS_CONFIG["BASE_URL"]
        self.user_agent = DISCOGS_CONFIG["USER_AGENT"]
        self.user_token = DISCOGS_CONFIG.get("USER_TOKEN")  # Optional, for higher rate limits
        self.request_delay = DISCOGS_CONFIG["REQUEST_DELAY"]
        self.max_results = DISCOGS_CONFIG["MAX_RESULTS"]
        self.timeout = DISCOGS_CONFIG["TIMEOUT"]
        
        self.session = requests.Session()
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'application/json'
        }
        # Add user token if available (for higher rate limits)
        if self.user_token:
            headers['Authorization'] = f'Discogs token={self.user_token}'
        
        self.session.headers.update(headers)
    
    def _make_request(self, url: str, params: Dict[str, Any], batch_progress: Optional[tuple[int, int]] = None) -> Optional[Dict[str, Any]]:
        """
        Make a request with retries.
        
        Args:
            url: Request URL
            params: Request parameters
            batch_progress: Optional tuple (current, total) for batch operations (e.g., (1, 5))
        """
        max_retries = 3
        retry_delay = 2
        
        # Build progress prefix if batch progress is provided
        progress_prefix = ""
        if batch_progress:
            current, total = batch_progress
            progress_prefix = f"[{current}/{total}] "
        
        for attempt in range(max_retries):
            try:
                # Only print on retries or if batch progress is provided
                if attempt > 0 or batch_progress:
                    if batch_progress:
                        print(f"{progress_prefix}Making request to Discogs (attempt {attempt + 1}/{max_retries})")
                    else:
                        print(f"Making request to Discogs (attempt {attempt + 1}/{max_retries})")
                
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                
                # Rate limiting (Discogs allows 60 requests per minute without token, 300 with token)
                time.sleep(self.request_delay)
                
                return response.json()
                
            except requests.exceptions.HTTPError as e:
                # Check for rate limiting (429)
                if hasattr(e, 'response') and e.response is not None and e.response.status_code == 429:
                    if batch_progress:
                        print(f"{progress_prefix}Rate limit exceeded. Waiting 60 seconds...")
                    else:
                        print("Rate limit exceeded. Waiting 60 seconds...")
                    time.sleep(60)
                    # Don't count rate limit as a failed attempt, but limit retries
                    if attempt < max_retries - 1:
                        continue
                    else:
                        print(f"{progress_prefix}Max retries reached after rate limit. Aborting.")
                        return None
                elif batch_progress:
                    print(f"{progress_prefix}HTTP Error (attempt {attempt + 1}): {e}")
                else:
                    print(f"HTTP Error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    return None
                    
            except requests.exceptions.RequestException as e:
                if batch_progress:
                    print(f"{progress_prefix}Request Error: {e}")
                else:
                    print(f"Request Error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    return None
                
        return None
    
    def search_release(self, song_data: SongData, offset: int = 0, limit: Optional[int] = None, release_type: Optional[str] = None) -> List[DiscogsRelease]:
        """
        Search for releases in Discogs.
        
        Args:
            song_data: Song information to search for
            offset: Offset for pagination (default: 0)
            limit: Maximum number of results (default: uses self.max_results)
            release_type: Optional release type filter (e.g., "album", "single", "ep", etc.)
            
        Returns:
            List of Discogs results
        """
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
            print(f"Searching Discogs releases with query: {query}")
            data = self._make_request(url, params)
            
            if data:
                return self._parse_release_results(data)
            else:
                print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: Failed to get data from Discogs")
                return []
            
        except Exception as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return []
    
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
                    
                    thumb = release_info.get('thumb', '')
                    cover_art_url = thumb if thumb else None
                    
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
    
    def get_release_info(self, release_id: str, batch_progress: Optional[tuple[int, int]] = None) -> Optional[ReleaseInfo]:
        """
        Get detailed release information including track listing.
        
        Args:
            release_id: Discogs release ID
            batch_progress: Optional tuple (current, total) for batch operations (e.g., (1, 5))
            
        Returns:
            ReleaseInfo with tracks or None if failed
        """
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
            
            thumb = release.get('thumb', '')
            if thumb:
                cover_art_url = thumb
            
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
            
            # Get cover art URL
            cover_art_url = None
            images = data.get('images', [])
            if images:
                # Use the primary image or first image
                for img in images:
                    if img.get('type') == 'primary' or img.get('type') == 'secondary':
                        cover_art_url = img.get('uri') or img.get('uri150') or img.get('resource_url')
                        break
                # If no primary/secondary, use first image
                if not cover_art_url and images:
                    cover_art_url = images[0].get('uri') or images[0].get('uri150') or images[0].get('resource_url')
            
            # Parse tracks
            tracks = []
            tracklist = data.get('tracklist', [])
            
            for idx, track_data in enumerate(tracklist, start=1):
                track_title = track_data.get('title', '')
                duration = track_data.get('duration', '')
                
                # Get track artist (usually same as release artist, but can be different)
                track_artist = artist
                if 'artists' in track_data and track_data['artists']:
                    track_artist = track_data['artists'][0].get('name', artist)
                
                # Position might be a string like "A1" or a number
                position = track_data.get('position', str(idx))
                # Try to extract numeric position if it's a string like "A1"
                try:
                    if isinstance(position, str) and position:
                        # Extract number from position string (e.g., "A1" -> 1)
                        numeric_pos = ''.join(filter(str.isdigit, position))
                        if numeric_pos:
                            position = int(numeric_pos)
                        else:
                            position = idx
                    elif not isinstance(position, int):
                        position = idx
                except (ValueError, TypeError):
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

