#!/usr/bin/env python3
"""
Spotify Client Module
A client for searching the Spotify Web API for music information and audio features.
"""

import requests
import json
import time
import base64
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from config import ERROR_MESSAGES, SUCCESS_MESSAGES, DEFAULTS


@dataclass
class SpotifyTrack:
    """Spotify track information."""
    title: str
    artist: str
    album: Optional[str]
    year: Optional[int]
    genre: Optional[str]
    duration_ms: Optional[int]
    popularity: Optional[int]
    spotify_id: str
    url: str
    preview_url: Optional[str] = None
    cover_art_url: Optional[str] = None
    audio_features: Optional[Dict[str, Any]] = None


@dataclass
class SpotifyAlbum:
    """Spotify album information."""
    title: str
    artist: str
    year: Optional[int]
    genre: Optional[str]
    total_tracks: Optional[int]
    popularity: Optional[int]
    spotify_id: str
    url: str
    cover_art_url: Optional[str] = None
    tracks: List[SpotifyTrack] = None


@dataclass
class SpotifyArtist:
    """Spotify artist information."""
    name: str
    popularity: Optional[int]
    genres: List[str] = None
    spotify_id: str = ""
    url: str = ""
    followers: Optional[int] = None


class SpotifyClient:
    """Spotify Web API client."""
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://api.spotify.com/v1"
        self.auth_url = "https://accounts.spotify.com/api/token"
        self.access_token = None
        self.token_expires_at = 0
        self.request_delay = 0.1  # Spotify rate limit: 10 requests per second
        self.timeout = 10
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Odysseus/1.0'
        })
    
    def _get_access_token(self) -> bool:
        """Get Spotify access token using client credentials flow."""
        if self.access_token and time.time() < self.token_expires_at:
            return True
        
        try:
            # Prepare credentials
            credentials = f"{self.client_id}:{self.client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            data = {
                'grant_type': 'client_credentials'
            }
            
            response = requests.post(
                self.auth_url,
                headers=headers,
                data=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            expires_in = token_data.get('expires_in', 3600)
            self.token_expires_at = time.time() + expires_in - 60  # Refresh 1 minute early
            
            # Update session headers
            self.session.headers.update({
                'Authorization': f'Bearer {self.access_token}'
            })
            
            print("Successfully obtained Spotify access token")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Error getting Spotify access token: {e}")
            return False
    
    def search_tracks(self, title: str, artist: str, album: Optional[str] = None) -> List[SpotifyTrack]:
        """
        Search for tracks in Spotify.
        
        Args:
            title: Song title
            artist: Artist name
            album: Album name (optional)
            
        Returns:
            List of Spotify track results
        """
        if not self._get_access_token():
            return []
        
        # Build query string
        query_parts = []
        
        if title:
            query_parts.append(f'track:"{title}"')
        
        if artist:
            query_parts.append(f'artist:"{artist}"')
        
        if album:
            query_parts.append(f'album:"{album}"')
        
        query = ' '.join(query_parts)
        
        url = f"{self.base_url}/search"
        params = {
            'q': query,
            'type': 'track',
            'limit': 20
        }
        
        try:
            print(f"Searching Spotify tracks with query: {query}")
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            time.sleep(self.request_delay)
            
            data = response.json()
            return self._parse_track_results(data)
            
        except requests.exceptions.RequestException as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return []
    
    def search_albums(self, album: str, artist: str) -> List[SpotifyAlbum]:
        """
        Search for albums in Spotify.
        
        Args:
            album: Album name
            artist: Artist name
            
        Returns:
            List of Spotify album results
        """
        if not self._get_access_token():
            return []
        
        query = f'album:"{album}" artist:"{artist}"'
        
        url = f"{self.base_url}/search"
        params = {
            'q': query,
            'type': 'album',
            'limit': 20
        }
        
        try:
            print(f"Searching Spotify albums with query: {query}")
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            time.sleep(self.request_delay)
            
            data = response.json()
            return self._parse_album_results(data)
            
        except requests.exceptions.RequestException as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return []
    
    def search_artists(self, artist: str) -> List[SpotifyArtist]:
        """
        Search for artists in Spotify.
        
        Args:
            artist: Artist name
            
        Returns:
            List of Spotify artist results
        """
        if not self._get_access_token():
            return []
        
        query = f'artist:"{artist}"'
        
        url = f"{self.base_url}/search"
        params = {
            'q': query,
            'type': 'artist',
            'limit': 20
        }
        
        try:
            print(f"Searching Spotify artists with query: {query}")
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            time.sleep(self.request_delay)
            
            data = response.json()
            return self._parse_artist_results(data)
            
        except requests.exceptions.RequestException as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return []
    
    def get_track_audio_features(self, track_id: str) -> Optional[Dict[str, Any]]:
        """
        Get audio features for a track.
        
        Args:
            track_id: Spotify track ID
            
        Returns:
            Audio features dictionary or None if failed
        """
        if not self._get_access_token():
            return None
        
        url = f"{self.base_url}/audio-features/{track_id}"
        
        try:
            print(f"Getting audio features for track: {track_id}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            time.sleep(self.request_delay)
            
            data = response.json()
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return None
    
    def get_album_tracks(self, album_id: str) -> List[SpotifyTrack]:
        """
        Get tracks from an album.
        
        Args:
            album_id: Spotify album ID
            
        Returns:
            List of tracks in the album
        """
        if not self._get_access_token():
            return []
        
        url = f"{self.base_url}/albums/{album_id}/tracks"
        params = {
            'limit': 50
        }
        
        try:
            print(f"Getting tracks for album: {album_id}")
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            time.sleep(self.request_delay)
            
            data = response.json()
            return self._parse_album_tracks(data)
            
        except requests.exceptions.RequestException as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return []
    
    def get_artist_top_tracks(self, artist_id: str, market: str = 'US') -> List[SpotifyTrack]:
        """
        Get top tracks for an artist.
        
        Args:
            artist_id: Spotify artist ID
            market: Market code (default: US)
            
        Returns:
            List of top tracks
        """
        if not self._get_access_token():
            return []
        
        url = f"{self.base_url}/artists/{artist_id}/top-tracks"
        params = {
            'market': market
        }
        
        try:
            print(f"Getting top tracks for artist: {artist_id}")
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            time.sleep(self.request_delay)
            
            data = response.json()
            return self._parse_track_results(data)
            
        except requests.exceptions.RequestException as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return []
    
    def _parse_track_results(self, data: Dict[str, Any]) -> List[SpotifyTrack]:
        """Parse track search results."""
        results = []
        
        tracks = data.get('tracks', {}).get('items', [])
        for track in tracks:
            title = track.get('name', '')
            spotify_id = track.get('id', '')
            popularity = track.get('popularity')
            duration_ms = track.get('duration_ms')
            preview_url = track.get('preview_url')
            external_urls = track.get('external_urls', {})
            url = external_urls.get('spotify', '')
            
            # Get artist information
            artists = track.get('artists', [])
            artist = ''
            if artists:
                artist = artists[0].get('name', '')
            
            # Get album information
            album_info = track.get('album', {})
            album = album_info.get('name')
            year = None
            if 'release_date' in album_info and album_info['release_date']:
                try:
                    year = int(album_info['release_date'][:4])
                except (ValueError, TypeError):
                    pass
            
            # Get cover art
            cover_art_url = None
            images = album_info.get('images', [])
            if images:
                # Get the largest image
                cover_art_url = max(images, key=lambda x: x.get('width', 0)).get('url')
            
            # Get genres from album
            genres = album_info.get('genres', [])
            genre = ', '.join(genres) if genres else None
            
            result = SpotifyTrack(
                title=title,
                artist=artist,
                album=album,
                year=year,
                genre=genre,
                duration_ms=duration_ms,
                popularity=popularity,
                spotify_id=spotify_id,
                url=url,
                preview_url=preview_url,
                cover_art_url=cover_art_url
            )
            results.append(result)
        
        return results
    
    def _parse_album_results(self, data: Dict[str, Any]) -> List[SpotifyAlbum]:
        """Parse album search results."""
        results = []
        
        albums = data.get('albums', {}).get('items', [])
        for album in albums:
            title = album.get('name', '')
            spotify_id = album.get('id', '')
            popularity = album.get('popularity')
            total_tracks = album.get('total_tracks')
            year = None
            
            if 'release_date' in album and album['release_date']:
                try:
                    year = int(album['release_date'][:4])
                except (ValueError, TypeError):
                    pass
            
            # Get artist information
            artists = album.get('artists', [])
            artist = ''
            if artists:
                artist = artists[0].get('name', '')
            
            # Get genres
            genres = album.get('genres', [])
            genre = ', '.join(genres) if genres else None
            
            # Get cover art
            cover_art_url = None
            images = album.get('images', [])
            if images:
                cover_art_url = max(images, key=lambda x: x.get('width', 0)).get('url')
            
            external_urls = album.get('external_urls', {})
            url = external_urls.get('spotify', '')
            
            result = SpotifyAlbum(
                title=title,
                artist=artist,
                year=year,
                genre=genre,
                total_tracks=total_tracks,
                popularity=popularity,
                spotify_id=spotify_id,
                url=url,
                cover_art_url=cover_art_url
            )
            results.append(result)
        
        return results
    
    def _parse_artist_results(self, data: Dict[str, Any]) -> List[SpotifyArtist]:
        """Parse artist search results."""
        results = []
        
        artists = data.get('artists', {}).get('items', [])
        for artist in artists:
            name = artist.get('name', '')
            spotify_id = artist.get('id', '')
            popularity = artist.get('popularity')
            followers = artist.get('followers', {}).get('total')
            genres = artist.get('genres', [])
            external_urls = artist.get('external_urls', {})
            url = external_urls.get('spotify', '')
            
            result = SpotifyArtist(
                name=name,
                popularity=popularity,
                genres=genres,
                spotify_id=spotify_id,
                url=url,
                followers=followers
            )
            results.append(result)
        
        return results
    
    def _parse_album_tracks(self, data: Dict[str, Any]) -> List[SpotifyTrack]:
        """Parse album tracks."""
        results = []
        
        tracks = data.get('items', [])
        for track in tracks:
            title = track.get('name', '')
            spotify_id = track.get('id', '')
            duration_ms = track.get('duration_ms')
            preview_url = track.get('preview_url')
            external_urls = track.get('external_urls', {})
            url = external_urls.get('spotify', '')
            
            # Get artist information
            artists = track.get('artists', [])
            artist = ''
            if artists:
                artist = artists[0].get('name', '')
            
            result = SpotifyTrack(
                title=title,
                artist=artist,
                album=None,  # Will be set by caller
                year=None,
                genre=None,
                duration_ms=duration_ms,
                popularity=None,
                spotify_id=spotify_id,
                url=url,
                preview_url=preview_url
            )
            results.append(result)
        
        return results


def print_spotify_results(results: List[SpotifyTrack], search_type: str):
    """Print Spotify search results in a formatted way."""
    if not results:
        print(f"No {search_type} results found.")
        return
    
    print(f"\n=== SPOTIFY {search_type.upper()} RESULTS ===")
    print("-" * 60)
    
    for i, result in enumerate(results, 1):
        print(f"{i}. {result.title}")
        print(f"   Artist: {result.artist}")
        if result.album:
            print(f"   Album: {result.album}")
        if result.year:
            print(f"   Year: {result.year}")
        if result.genre:
            print(f"   Genre: {result.genre}")
        if result.popularity is not None:
            print(f"   Popularity: {result.popularity}/100")
        if result.duration_ms:
            duration_min = result.duration_ms // 60000
            duration_sec = (result.duration_ms % 60000) // 1000
            print(f"   Duration: {duration_min}:{duration_sec:02d}")
        if result.audio_features:
            print(f"   Audio Features: Available")
        print(f"   URL: {result.url}")
        print()
