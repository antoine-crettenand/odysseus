"""
Spotify Client Module
A client for parsing Spotify URLs and extracting track information.
"""

import re
import requests
import base64
from typing import List, Optional, Dict, Any
from ..models.releases import Track, ReleaseInfo
from ..models.search_results import SpotifyTrack


class SpotifyClient:
    """Spotify client for parsing URLs and extracting track information."""
    
    def __init__(self):
        self.base_url = "https://api.spotify.com/v1"
        self.auth_url = "https://accounts.spotify.com/api/token"
        self.client_id = None
        self.client_secret = None
        self.access_token = None
        self.timeout = 30
        
        # Try to get credentials from environment
        import os
        self.client_id = os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        
        # Authenticate if credentials are available
        if self.client_id and self.client_secret:
            self._authenticate()
    
    def _authenticate(self) -> bool:
        """Authenticate with Spotify API using client credentials flow."""
        if not self.client_id or not self.client_secret:
            return False
        
        try:
            # Encode client credentials
            credentials = f"{self.client_id}:{self.client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {encoded_credentials}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {"grant_type": "client_credentials"}
            
            response = requests.post(
                self.auth_url,
                headers=headers,
                data=data,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get("access_token")
                return True
            else:
                return False
        except Exception:
            return False
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers
    
    def parse_spotify_url(self, url: str) -> Optional[Dict[str, str]]:
        """
        Parse a Spotify URL and extract type and ID.
        
        Supports:
        - Playlist: https://open.spotify.com/playlist/{id}
        - Album: https://open.spotify.com/album/{id}
        - Track: https://open.spotify.com/track/{id}
        - Short URLs: spotify:playlist:{id}, spotify:album:{id}, etc.
        
        Returns:
            Dict with 'type' (playlist/album/track) and 'id', or None if invalid
        """
        if not url:
            return None
        
        # Handle spotify: URIs
        if url.startswith("spotify:"):
            parts = url.split(":")
            if len(parts) >= 3:
                return {"type": parts[1], "id": parts[2].split("?")[0]}
        
        # Handle web URLs (with optional locale prefixes like /intl-fr/, /intl-en/, etc.)
        patterns = [
            r"open\.spotify\.com(?:/[^/]+)?/(playlist|album|track)/([a-zA-Z0-9]+)",
            r"spotify\.com(?:/[^/]+)?/(playlist|album|track)/([a-zA-Z0-9]+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return {"type": match.group(1), "id": match.group(2)}
        
        return None
    
    def get_playlist_tracks(self, playlist_id: str) -> Optional[ReleaseInfo]:
        """
        Get tracks from a Spotify playlist.
        
        Returns:
            ReleaseInfo object with tracks, or None if failed
        """
        if not self.access_token:
            raise Exception("Spotify API authentication required. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables.")
        
        try:
            tracks = []
            url = f"{self.base_url}/playlists/{playlist_id}"
            headers = self._get_headers()
            
            # First, get playlist info
            response = requests.get(url, headers=headers, timeout=self.timeout)
            if response.status_code != 200:
                return None
            
            playlist_data = response.json()
            playlist_name = playlist_data.get("name", "Unknown Playlist")
            playlist_owner = playlist_data.get("owner", {}).get("display_name", "Unknown")
            
            # Extract cover art URL from playlist images
            cover_art_url = None
            images = playlist_data.get("images", [])
            if images:
                # Use the largest image (first one is usually the largest)
                cover_art_url = images[0].get("url")
            
            # Get all tracks (handle pagination)
            tracks_url = f"{url}/tracks"
            offset = 0
            limit = 100
            
            while True:
                params = {"limit": limit, "offset": offset}
                response = requests.get(tracks_url, headers=headers, params=params, timeout=self.timeout)
                
                if response.status_code != 200:
                    break
                
                data = response.json()
                items = data.get("items", [])
                
                if not items:
                    break
                
                for idx, item in enumerate(items, start=len(tracks) + 1):
                    track_data = item.get("track")
                    if not track_data:
                        continue
                    
                    # Handle null tracks (removed tracks)
                    if track_data is None:
                        continue
                    
                    track_name = track_data.get("name", "Unknown")
                    artists = track_data.get("artists", [])
                    artist_name = artists[0].get("name", "Unknown Artist") if artists else "Unknown Artist"
                    
                    # Duration in milliseconds
                    duration_ms = track_data.get("duration_ms", 0)
                    duration = self._format_duration(duration_ms) if duration_ms else None
                    
                    track = Track(
                        position=idx,
                        title=track_name,
                        artist=artist_name,
                        duration=duration
                    )
                    tracks.append(track)
                
                # Check if there are more tracks
                if data.get("next"):
                    offset += limit
                else:
                    break
            
            return ReleaseInfo(
                title=playlist_name,
                artist=playlist_owner,
                release_type="Playlist",
                url=f"https://open.spotify.com/playlist/{playlist_id}",
                cover_art_url=cover_art_url,
                tracks=tracks
            )
            
        except Exception as e:
            raise Exception(f"Failed to get playlist tracks: {str(e)}")
    
    def get_album_tracks(self, album_id: str) -> Optional[ReleaseInfo]:
        """
        Get tracks from a Spotify album.
        
        Returns:
            ReleaseInfo object with tracks, or None if failed
        """
        if not self.access_token:
            raise Exception("Spotify API authentication required. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables.")
        
        try:
            tracks = []
            url = f"{self.base_url}/albums/{album_id}"
            headers = self._get_headers()
            
            # First, get album info
            response = requests.get(url, headers=headers, timeout=self.timeout)
            if response.status_code != 200:
                return None
            
            album_data = response.json()
            album_name = album_data.get("name", "Unknown Album")
            artists = album_data.get("artists", [])
            artist_name = artists[0].get("name", "Unknown Artist") if artists else "Unknown Artist"
            release_date = album_data.get("release_date")
            genres = album_data.get("genres", [])
            genre = genres[0] if genres else None
            
            # Extract cover art URL from album images
            cover_art_url = None
            images = album_data.get("images", [])
            if images:
                # Use the largest image (first one is usually the largest)
                cover_art_url = images[0].get("url")
            
            # Get all tracks (handle pagination)
            tracks_url = f"{url}/tracks"
            offset = 0
            limit = 50
            
            while True:
                params = {"limit": limit, "offset": offset}
                response = requests.get(tracks_url, headers=headers, params=params, timeout=self.timeout)
                
                if response.status_code != 200:
                    break
                
                data = response.json()
                items = data.get("items", [])
                
                if not items:
                    break
                
                for item in items:
                    track_name = item.get("name", "Unknown")
                    track_artists = item.get("artists", [])
                    track_artist_name = track_artists[0].get("name", artist_name) if track_artists else artist_name
                    
                    # Duration in milliseconds
                    duration_ms = item.get("duration_ms", 0)
                    duration = self._format_duration(duration_ms) if duration_ms else None
                    
                    # Track number
                    track_number = item.get("track_number", len(tracks) + 1)
                    
                    track = Track(
                        position=track_number,
                        title=track_name,
                        artist=track_artist_name,
                        duration=duration
                    )
                    tracks.append(track)
                
                # Check if there are more tracks
                if data.get("next"):
                    offset += limit
                else:
                    break
            
            return ReleaseInfo(
                title=album_name,
                artist=artist_name,
                release_date=release_date,
                genre=genre,
                release_type="Album",
                url=f"https://open.spotify.com/album/{album_id}",
                cover_art_url=cover_art_url,
                tracks=tracks
            )
            
        except Exception as e:
            raise Exception(f"Failed to get album tracks: {str(e)}")
    
    def get_track_info(self, track_id: str) -> Optional[ReleaseInfo]:
        """
        Get information for a single Spotify track.
        
        Returns:
            ReleaseInfo object with a single track, or None if failed
        """
        if not self.access_token:
            raise Exception("Spotify API authentication required. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables.")
        
        try:
            url = f"{self.base_url}/tracks/{track_id}"
            headers = self._get_headers()
            
            response = requests.get(url, headers=headers, timeout=self.timeout)
            if response.status_code != 200:
                return None
            
            track_data = response.json()
            track_name = track_data.get("name", "Unknown")
            artists = track_data.get("artists", [])
            artist_name = artists[0].get("name", "Unknown Artist") if artists else "Unknown Artist"
            album = track_data.get("album", {})
            album_name = album.get("name", "Unknown Album")
            
            # Extract cover art URL from album images
            cover_art_url = None
            album_images = album.get("images", [])
            if album_images:
                # Use the largest image (first one is usually the largest)
                cover_art_url = album_images[0].get("url")
            
            # Duration in milliseconds
            duration_ms = track_data.get("duration_ms", 0)
            duration = self._format_duration(duration_ms) if duration_ms else None
            
            track = Track(
                position=1,
                title=track_name,
                artist=artist_name,
                duration=duration
            )
            
            return ReleaseInfo(
                title=album_name,
                artist=artist_name,
                release_type="Track",
                url=f"https://open.spotify.com/track/{track_id}",
                cover_art_url=cover_art_url,
                tracks=[track]
            )
            
        except Exception as e:
            raise Exception(f"Failed to get track info: {str(e)}")
    
    def get_tracks_from_url(self, url: str) -> Optional[ReleaseInfo]:
        """
        Parse a Spotify URL and get tracks from it.
        
        Supports playlists, albums, and tracks.
        
        Returns:
            ReleaseInfo object with tracks, or None if failed
        """
        parsed = self.parse_spotify_url(url)
        if not parsed:
            raise ValueError(f"Invalid Spotify URL: {url}")
        
        url_type = parsed["type"]
        url_id = parsed["id"]
        
        if url_type == "playlist":
            return self.get_playlist_tracks(url_id)
        elif url_type == "album":
            return self.get_album_tracks(url_id)
        elif url_type == "track":
            return self.get_track_info(url_id)
        else:
            raise ValueError(f"Unsupported Spotify URL type: {url_type}")
    
    def _format_duration(self, duration_ms: int) -> str:
        """Format duration from milliseconds to MM:SS format."""
        if not duration_ms:
            return None
        
        total_seconds = duration_ms // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        
        return f"{minutes}:{seconds:02d}"

