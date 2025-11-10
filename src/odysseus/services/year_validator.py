"""
Year validator module for validating and retrieving release years from external sources.
"""

from typing import List, Optional, Dict, Tuple
from ..utils.string_utils import normalize_string


class YearValidator:
    """Handles year validation using external sources like Spotify and Discogs."""
    
    def __init__(self, spotify_client_getter=None, discogs_client=None):
        """
        Initialize year validator.
        
        Args:
            spotify_client_getter: Optional callable that returns SpotifyClient instance
            discogs_client: Optional DiscogsClient instance
        """
        self._spotify_client_getter = spotify_client_getter
        self.discogs_client = discogs_client
        self._year_validation_cache: Dict[Tuple[str, str, str], Optional[int]] = {}
    
    def _get_spotify_client(self):
        """Get Spotify client using the getter."""
        if self._spotify_client_getter:
            return self._spotify_client_getter()
        return None
    
    def _get_release_year_from_spotify(self, artist: str, album: str) -> Optional[int]:
        """
        Search Spotify for release year validation.
        
        Args:
            artist: Artist name
            album: Album name
            
        Returns:
            Release year if found, None otherwise
        """
        cache_key = (normalize_string(artist), normalize_string(album), 'spotify')
        if cache_key in self._year_validation_cache:
            return self._year_validation_cache[cache_key]
        
        spotify_client = self._get_spotify_client()
        if not spotify_client or not hasattr(spotify_client, 'access_token') or not spotify_client.access_token:
            self._year_validation_cache[cache_key] = None
            return None
        
        try:
            import requests
            query = f"album:{album} artist:{artist}"
            search_url = f"{spotify_client.base_url}/search"
            headers = spotify_client._get_headers()
            params = {
                'q': query,
                'type': 'album',
                'limit': 5
            }
            
            response = requests.get(search_url, headers=headers, params=params, timeout=10)
            if response.status_code != 200:
                self._year_validation_cache[cache_key] = None
                return None
            
            data = response.json()
            albums = data.get('albums', {}).get('items', [])
            
            if not albums:
                self._year_validation_cache[cache_key] = None
                return None
            
            # Find the best matching album (exact match preferred)
            for album_data in albums:
                album_name = album_data.get('name', '')
                artists = album_data.get('artists', [])
                artist_name = artists[0].get('name', '') if artists else ''
                
                # Check if this matches (normalized comparison)
                if (normalize_string(album_name) == normalize_string(album) and
                    normalize_string(artist_name) == normalize_string(artist)):
                    release_date = album_data.get('release_date', '')
                    if release_date and len(release_date) >= 4:
                        try:
                            year = int(release_date[:4])
                            self._year_validation_cache[cache_key] = year
                            return year
                        except ValueError:
                            continue
            
            # If no exact match, try first result
            if albums:
                release_date = albums[0].get('release_date', '')
                if release_date and len(release_date) >= 4:
                    try:
                        year = int(release_date[:4])
                        self._year_validation_cache[cache_key] = year
                        return year
                    except ValueError:
                        pass
            
            self._year_validation_cache[cache_key] = None
            return None
            
        except Exception:
            self._year_validation_cache[cache_key] = None
            return None
    
    def _get_release_year_from_discogs(
        self,
        artist: str,
        album: str,
        release_type: Optional[str] = None
    ) -> Optional[int]:
        """
        Search Discogs for release year validation.
        
        Args:
            artist: Artist name
            album: Album name
            release_type: Optional release type filter
            
        Returns:
            Release year if found, None otherwise
        """
        if not self.discogs_client:
            return None
        
        cache_key = (normalize_string(artist), normalize_string(album), release_type or 'discogs')
        if cache_key in self._year_validation_cache:
            return self._year_validation_cache[cache_key]
        
        try:
            from ..models.song import SongData
            song_data = SongData(
                title="",
                artist=artist,
                album=album
            )
            
            # Search for releases (limit to 5 for performance)
            discogs_results = self.discogs_client.search_release(
                song_data, limit=5, release_type=release_type
            )
            
            if not discogs_results:
                self._year_validation_cache[cache_key] = None
                return None
            
            # Find the best matching release (exact match preferred)
            for result in discogs_results:
                # Check if this matches (normalized comparison)
                if (normalize_string(result.album or "") == normalize_string(album) and
                    normalize_string(result.artist or "") == normalize_string(artist)):
                    if result.year:
                        self._year_validation_cache[cache_key] = result.year
                        return result.year
            
            # If no exact match, use first result's year
            if discogs_results and discogs_results[0].year:
                year = discogs_results[0].year
                self._year_validation_cache[cache_key] = year
                return year
            
            self._year_validation_cache[cache_key] = None
            return None
            
        except Exception:
            self._year_validation_cache[cache_key] = None
            return None
    
    def validate_year(
        self,
        artist: str,
        album: str,
        candidate_years: List[int],
        release_type: Optional[str] = None
    ) -> Optional[int]:
        """
        Cross-reference release year from Spotify and Discogs when there's doubt.
        
        Args:
            artist: Artist name
            album: Album name
            candidate_years: List of candidate years to validate
            release_type: Optional release type filter
            
        Returns:
            Validated year if found, None otherwise
        """
        # Try Spotify first
        spotify_year = self._get_release_year_from_spotify(artist, album)
        if spotify_year and spotify_year in candidate_years:
            return spotify_year
        
        # Try Discogs (with release_type filter)
        discogs_year = self._get_release_year_from_discogs(artist, album, release_type)
        if discogs_year and discogs_year in candidate_years:
            return discogs_year
        
        # If both agree (even if not in candidates), prefer that
        if spotify_year and discogs_year and spotify_year == discogs_year:
            return spotify_year
        
        # Return the most authoritative source (Spotify preferred)
        return spotify_year or discogs_year
    
    def get_release_year(
        self,
        artist: str,
        album: str,
        release_type: Optional[str] = None
    ) -> Optional[int]:
        """
        Get release year from external sources.
        
        Args:
            artist: Artist name
            album: Album name
            release_type: Optional release type filter
            
        Returns:
            Release year if found, None otherwise
        """
        # Try Spotify first
        spotify_year = self._get_release_year_from_spotify(artist, album)
        if spotify_year:
            return spotify_year
        
        # Try Discogs
        discogs_year = self._get_release_year_from_discogs(artist, album, release_type)
        return discogs_year

