#!/usr/bin/env python3
"""
MusicBrainz Client Module
A client for searching the MusicBrainz database for music information.
"""

import requests
import json
import time
import ssl
import urllib3
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from config import MUSICBRAINZ_CONFIG, ERROR_MESSAGES, SUCCESS_MESSAGES, DEFAULTS

# Disable SSL warnings for problematic connections
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@dataclass
class SongData:
    """Song data structure."""
    title: str
    artist: str
    album: Optional[str] = None
    release_year: Optional[int] = None


@dataclass
class MusicBrainzSong:
    """MusicBrainz search result."""
    title: str
    artist: str
    album: Optional[str]
    release_date: Optional[str]
    genre: Optional[str]
    score: int
    mbid: str
    url: str


@dataclass
class Track:
    """Track information from a release."""
    position: int
    title: str
    artist: str
    duration: Optional[str] = None
    mbid: Optional[str] = None


@dataclass
class ReleaseInfo:
    """Detailed release information with tracks."""
    title: str
    artist: str
    release_date: Optional[str]
    genre: Optional[str]
    mbid: str
    url: str
    tracks: List[Track]


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
        
        # Configure SSL settings to handle connection issues
        self._configure_ssl()
        
        # Track if we should try HTTP fallback
        self.use_http_fallback = False
    
    def _configure_ssl(self):
        """Configure SSL settings to handle connection issues."""
        try:
            # Create a custom SSL context with more permissive settings
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # Configure the session to use the custom SSL context
            adapter = requests.adapters.HTTPAdapter()
            self.session.mount('https://', adapter)
            
            # Set verify=False for problematic SSL connections
            self.session.verify = False
            
        except Exception as e:
            print(f"Warning: Could not configure SSL settings: {e}")
    
    def _make_request(self, url: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make a request with SSL error handling and retries."""
        max_retries = 3
        retry_delay = 2
        
        # Try HTTPS first
        for attempt in range(max_retries):
            try:
                print(f"Making request to MusicBrainz (attempt {attempt + 1}/{max_retries})")
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                
                # Rate limiting
                time.sleep(self.request_delay)
                
                return response.json()
                
            except requests.exceptions.SSLError as e:
                print(f"SSL Error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    print("All SSL retry attempts failed, trying HTTP fallback...")
                    return self._try_http_fallback(url, params)
                    
            except requests.exceptions.ConnectionError as e:
                print(f"Connection Error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    print("All connection retry attempts failed, trying HTTP fallback...")
                    return self._try_http_fallback(url, params)
                    
            except requests.exceptions.RequestException as e:
                print(f"Request Error: {e}")
                return None
                
        return None
    
    def _try_http_fallback(self, url: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Try HTTP fallback if HTTPS fails."""
        if self.use_http_fallback:
            return None  # Already tried HTTP
            
        try:
            # Convert HTTPS URL to HTTP
            http_url = url.replace('https://', 'http://')
            print(f"Trying HTTP fallback: {http_url}")
            
            response = self.session.get(http_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            # Rate limiting
            time.sleep(self.request_delay)
            
            self.use_http_fallback = True
            return response.json()
            
        except Exception as e:
            print(f"HTTP fallback also failed: {e}")
            return None
    
    def search_recording(self, song_data: SongData) -> List[MusicBrainzSong]:
        """
        Search for recordings in MusicBrainz.
        
        Args:
            song_data: Song information to search for
            
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
            'limit': self.max_results
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
    
    def search_release(self, song_data: SongData) -> List[MusicBrainzSong]:
        """
        Search for releases (albums) in MusicBrainz.
        
        Args:
            song_data: Song information to search for
            
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
        
        query = ' AND '.join(query_parts)
        
        url = f"{self.base_url}/release"
        params = {
            'query': query,
            'fmt': 'json',
            'limit': self.max_results
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
    
    def get_release_info(self, release_mbid: str) -> Optional[ReleaseInfo]:
        """
        Get detailed release information including track listing.
        
        Args:
            release_mbid: MusicBrainz release ID
            
        Returns:
            ReleaseInfo with tracks or None if failed
        """
        url = f"{self.base_url}/release/{release_mbid}"
        params = {
            'inc': 'recordings+artist-credits',
            'fmt': 'json'
        }
        
        try:
            print(f"Fetching release details for MBID: {release_mbid}")
            data = self._make_request(url, params)
            
            if data:
                return self._parse_release_info(data)
            else:
                print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: Failed to get data from MusicBrainz")
                return None
            
        except Exception as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return None
    
    def _parse_release_info(self, data: Dict[str, Any]) -> Optional[ReleaseInfo]:
        """Parse detailed release information."""
        try:
            # Basic release info
            title = data.get('title', '')
            mbid = data.get('id', '')
            release_date = data.get('date', '')
            
            # Get artist information
            artist_credits = data.get('artist-credit', [])
            artist = ''
            if artist_credits:
                artist = artist_credits[0].get('name', '')
            
            # Get genre information
            genres = data.get('genres', [])
            genre = None
            if genres:
                genre = genres[0].get('name', '')
            
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
                    
                    # Get track artist (usually same as release artist)
                    track_artist_credits = recording.get('artist-credit', [])
                    track_artist = artist  # Default to release artist
                    if track_artist_credits:
                        track_artist = track_artist_credits[0].get('name', artist)
                    
                    # Get duration
                    duration = None
                    if 'length' in recording and recording['length']:
                        duration_ms = recording['length']
                        duration = self._format_duration(duration_ms)
                    
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
                mbid=mbid,
                url=url,
                tracks=tracks
            )
            
        except Exception as e:
            print(f"Error parsing release info: {e}")
            return None
    
    def _format_duration(self, duration_ms: int) -> str:
        """Format duration from milliseconds to MM:SS format."""
        if not duration_ms:
            return None
        
        seconds = duration_ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        
        return f"{minutes:02d}:{seconds:02d}"
    
    def search_artist_releases(self, artist: str, year: Optional[int] = None) -> List[MusicBrainzSong]:
        """
        Search for releases by a specific artist.
        
        Args:
            artist: Artist name to search for
            year: Optional year filter
            
        Returns:
            List of releases by the artist
        """
        query_parts = [f'artist:"{artist}"']
        
        if year:
            query_parts.append(f'date:{year}')
        
        query = ' AND '.join(query_parts)
        
        url = f"{self.base_url}/release"
        params = {
            'query': query,
            'fmt': 'json',
            'limit': 20  # More results for discography
        }
        
        try:
            print(f"Searching releases by artist: {artist}")
            if year:
                print(f"Filtering by year: {year}")
            data = self._make_request(url, params)
            
            if data:
                return self._parse_release_results(data)
            else:
                print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: Failed to get data from MusicBrainz")
                return []
            
        except Exception as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return []
    
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
            genre = None
            
            if releases:
                release = releases[0]  # Take first release
                album = release.get('title', '')
                release_date = release.get('date', '')
                genre = release.get('genres', [])
                if genre:
                    genre = genre[0]
            url = f"https://musicbrainz.org/recording/{mbid}"
            
            result = MusicBrainzSong(
                title=title,
                artist=artist,
                album=album,
                release_date=release_date,
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
            
            # Get artist information
            artist_credits = release.get('artist-credit', [])
            artist = ''
            if artist_credits:
                artist = artist_credits[0].get('name', '')
            
            url = f"https://musicbrainz.org/release/{mbid}"
            
            result = MusicBrainzSong(
                title='',  # Releases don't have individual track titles
                artist=artist,
                album=album,
                release_date=release_date,
                genre=None,  # Releases don't have genre in basic search
                mbid=mbid,
                score=score,
                url=url
            )
            results.append(result)
        
        return results
    
    def search(self, song_data: SongData) -> List[MusicBrainzSong]:
        """
        Smart search that chooses the appropriate search type based on input data.
        - If title is provided: search for recordings only
        - If only album (LP) is known: search for releases only
        
        Args:
            song_data: Song information to search for
            
        Returns:
            List of MusicBrainz results
        """
        results = []
        
        # If title is provided, search for recordings
        if song_data.title:
            print(f"Title provided ({song_data.title}) - searching for recordings")
            results = self.search_recording(song_data)
        
        # If only album is known (no title), search for releases
        elif song_data.album and not song_data.title:
            print(f"Only album provided ({song_data.album}) - searching for releases")
            results = self.search_release(song_data)
        
        # If both title and album are provided, prioritize recordings
        elif song_data.title and song_data.album:
            print(f"Both title ({song_data.title}) and album ({song_data.album}) provided - searching for recordings")
            results = self.search_recording(song_data)
        
        else:
            print("Insufficient data for search. Please provide at least a title or album.")
        
        return results


def print_results(results: List[MusicBrainzSong], search_type: str):
    """Print search results in a formatted way."""
    if not results:
        print(f"No {search_type} results found.")
        return
    
    print(f"\n=== {search_type.upper()} RESULTS ===")
    print("-" * 60)
    
    for i, result in enumerate(results, 1):
        print(f"{i}. {result.title or result.album}")
        print(f"   Artist: {result.artist}")
        if result.album and search_type == "recording":
            print(f"   Album: {result.album}")
        if result.release_date:
            print(f"   Release Date: {result.release_date}")
        print(f"   Score: {result.score}")
        print(f"   URL: {result.url}")
        print()

