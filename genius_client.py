#!/usr/bin/env python3
"""
Genius Client Module
A client for searching the Genius API for lyrics and additional song context.
"""

import requests
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from config import ERROR_MESSAGES, SUCCESS_MESSAGES, DEFAULTS


@dataclass
class GeniusSong:
    """Genius song information."""
    title: str
    artist: str
    album: Optional[str]
    year: Optional[int]
    lyrics: Optional[str]
    genius_id: str
    url: str
    cover_art_url: Optional[str] = None
    description: Optional[str] = None
    primary_artist: Optional[Dict[str, Any]] = None
    featured_artists: List[str] = None
    song_art_image_url: Optional[str] = None


@dataclass
class GeniusAlbum:
    """Genius album information."""
    title: str
    artist: str
    year: Optional[int]
    genius_id: str
    url: str
    cover_art_url: Optional[str] = None
    description: Optional[str] = None
    songs: List[GeniusSong] = None


@dataclass
class GeniusArtist:
    """Genius artist information."""
    name: str
    genius_id: str
    url: str
    description: Optional[str] = None
    cover_art_url: Optional[str] = None
    followers_count: Optional[int] = None
    songs: List[GeniusSong] = None


class GeniusClient:
    """Genius API client."""
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api.genius.com"
        self.request_delay = 0.2  # Genius rate limit: 5 requests per second
        self.timeout = 10
        
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.access_token}',
            'User-Agent': 'Odysseus/1.0'
        })
    
    def search_songs(self, title: str, artist: str) -> List[GeniusSong]:
        """
        Search for songs in Genius.
        
        Args:
            title: Song title
            artist: Artist name
            
        Returns:
            List of Genius song results
        """
        query = f"{title} {artist}"
        
        url = f"{self.base_url}/search"
        params = {
            'q': query
        }
        
        try:
            print(f"Searching Genius songs with query: {query}")
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            time.sleep(self.request_delay)
            
            data = response.json()
            return self._parse_song_search_results(data)
            
        except requests.exceptions.RequestException as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return []
    
    def get_song_details(self, song_id: str) -> Optional[GeniusSong]:
        """
        Get detailed song information including lyrics.
        
        Args:
            song_id: Genius song ID
            
        Returns:
            Detailed song information or None if failed
        """
        url = f"{self.base_url}/songs/{song_id}"
        params = {
            'text_format': 'plain'
        }
        
        try:
            print(f"Getting Genius song details for ID: {song_id}")
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            time.sleep(self.request_delay)
            
            data = response.json()
            return self._parse_song_details(data)
            
        except requests.exceptions.RequestException as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return None
    
    def get_song_lyrics(self, song_id: str) -> Optional[str]:
        """
        Get lyrics for a song.
        
        Args:
            song_id: Genius song ID
            
        Returns:
            Song lyrics or None if failed
        """
        # First get the song details to get the URL
        song_details = self.get_song_details(song_id)
        if not song_details or not song_details.url:
            return None
        
        try:
            # Scrape lyrics from the web page
            print(f"Scraping lyrics for song: {song_details.title}")
            response = requests.get(song_details.url, timeout=self.timeout)
            response.raise_for_status()
            
            # Parse lyrics from HTML (simplified - in production you'd use BeautifulSoup)
            # This is a basic implementation - you might want to use a proper HTML parser
            html_content = response.text
            
            # Look for lyrics in the page
            # This is a simplified approach - Genius has anti-scraping measures
            # You might need to use a more sophisticated approach
            lyrics_start = html_content.find('"lyrics"')
            if lyrics_start == -1:
                return None
            
            # Extract lyrics section (this is very basic and might not work reliably)
            # In a real implementation, you'd use BeautifulSoup or similar
            return "Lyrics extraction requires more sophisticated parsing"
            
        except requests.exceptions.RequestException as e:
            print(f"Error scraping lyrics: {e}")
            return None
    
    def search_albums(self, album: str, artist: str) -> List[GeniusAlbum]:
        """
        Search for albums in Genius.
        
        Args:
            album: Album name
            artist: Artist name
            
        Returns:
            List of Genius album results
        """
        query = f"{album} {artist}"
        
        url = f"{self.base_url}/search"
        params = {
            'q': query
        }
        
        try:
            print(f"Searching Genius albums with query: {query}")
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            time.sleep(self.request_delay)
            
            data = response.json()
            return self._parse_album_search_results(data)
            
        except requests.exceptions.RequestException as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return []
    
    def search_artists(self, artist: str) -> List[GeniusArtist]:
        """
        Search for artists in Genius.
        
        Args:
            artist: Artist name
            
        Returns:
            List of Genius artist results
        """
        url = f"{self.base_url}/search"
        params = {
            'q': artist
        }
        
        try:
            print(f"Searching Genius artists with query: {artist}")
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            time.sleep(self.request_delay)
            
            data = response.json()
            return self._parse_artist_search_results(data)
            
        except requests.exceptions.RequestException as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return []
    
    def get_artist_songs(self, artist_id: str, per_page: int = 20) -> List[GeniusSong]:
        """
        Get songs by an artist.
        
        Args:
            artist_id: Genius artist ID
            per_page: Number of songs per page
            
        Returns:
            List of songs by the artist
        """
        url = f"{self.base_url}/artists/{artist_id}/songs"
        params = {
            'per_page': per_page,
            'sort': 'popularity'
        }
        
        try:
            print(f"Getting songs for artist ID: {artist_id}")
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            time.sleep(self.request_delay)
            
            data = response.json()
            return self._parse_artist_songs(data)
            
        except requests.exceptions.RequestException as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return []
    
    def _parse_song_search_results(self, data: Dict[str, Any]) -> List[GeniusSong]:
        """Parse song search results."""
        results = []
        
        hits = data.get('response', {}).get('hits', [])
        for hit in hits:
            song_data = hit.get('result', {})
            if not song_data:
                continue
            
            title = song_data.get('title', '')
            genius_id = str(song_data.get('id', ''))
            url = song_data.get('url', '')
            
            # Get primary artist
            primary_artist = song_data.get('primary_artist', {})
            artist = primary_artist.get('name', '')
            
            # Get featured artists
            featured_artists = []
            if 'featured_artists' in song_data:
                for feat_artist in song_data['featured_artists']:
                    if feat_artist.get('name'):
                        featured_artists.append(feat_artist['name'])
            
            # Get song art
            song_art_image_url = song_data.get('song_art_image_url')
            
            # Get release date info
            release_date = song_data.get('release_date_for_display')
            year = None
            if release_date:
                try:
                    year = int(release_date.split()[-1])  # Extract year from date string
                except (ValueError, IndexError):
                    pass
            
            result = GeniusSong(
                title=title,
                artist=artist,
                album=None,  # Not directly available in search results
                year=year,
                lyrics=None,  # Would need separate call to get lyrics
                genius_id=genius_id,
                url=url,
                song_art_image_url=song_art_image_url,
                primary_artist=primary_artist,
                featured_artists=featured_artists
            )
            results.append(result)
        
        return results
    
    def _parse_song_details(self, data: Dict[str, Any]) -> Optional[GeniusSong]:
        """Parse detailed song information."""
        try:
            song = data.get('response', {}).get('song', {})
            if not song:
                return None
            
            title = song.get('title', '')
            genius_id = str(song.get('id', ''))
            url = song.get('url', '')
            description = song.get('description', {}).get('plain', '')
            
            # Get primary artist
            primary_artist = song.get('primary_artist', {})
            artist = primary_artist.get('name', '')
            
            # Get album info
            album_info = song.get('album', {})
            album = album_info.get('name') if album_info else None
            
            # Get release date
            release_date = song.get('release_date_for_display')
            year = None
            if release_date:
                try:
                    year = int(release_date.split()[-1])
                except (ValueError, IndexError):
                    pass
            
            # Get song art
            song_art_image_url = song.get('song_art_image_url')
            
            # Get featured artists
            featured_artists = []
            if 'featured_artists' in song:
                for feat_artist in song['featured_artists']:
                    if feat_artist.get('name'):
                        featured_artists.append(feat_artist['name'])
            
            return GeniusSong(
                title=title,
                artist=artist,
                album=album,
                year=year,
                lyrics=None,  # Would need separate scraping
                genius_id=genius_id,
                url=url,
                description=description,
                song_art_image_url=song_art_image_url,
                primary_artist=primary_artist,
                featured_artists=featured_artists
            )
            
        except Exception as e:
            print(f"Error parsing song details: {e}")
            return None
    
    def _parse_album_search_results(self, data: Dict[str, Any]) -> List[GeniusAlbum]:
        """Parse album search results."""
        results = []
        
        hits = data.get('response', {}).get('hits', [])
        for hit in hits:
            result_data = hit.get('result', {})
            if not result_data or result_data.get('type') != 'album':
                continue
            
            title = result_data.get('title', '')
            genius_id = str(result_data.get('id', ''))
            url = result_data.get('url', '')
            
            # Get artist info
            artist_info = result_data.get('artist', {})
            artist = artist_info.get('name', '') if artist_info else ''
            
            # Get cover art
            cover_art_url = result_data.get('cover_art_url')
            
            # Get release date
            release_date = result_data.get('release_date_for_display')
            year = None
            if release_date:
                try:
                    year = int(release_date.split()[-1])
                except (ValueError, IndexError):
                    pass
            
            result = GeniusAlbum(
                title=title,
                artist=artist,
                year=year,
                genius_id=genius_id,
                url=url,
                cover_art_url=cover_art_url
            )
            results.append(result)
        
        return results
    
    def _parse_artist_search_results(self, data: Dict[str, Any]) -> List[GeniusArtist]:
        """Parse artist search results."""
        results = []
        
        hits = data.get('response', {}).get('hits', [])
        for hit in hits:
            result_data = hit.get('result', {})
            if not result_data or result_data.get('type') != 'artist':
                continue
            
            name = result_data.get('name', '')
            genius_id = str(result_data.get('id', ''))
            url = result_data.get('url', '')
            
            # Get cover art
            cover_art_url = result_data.get('image_url')
            
            # Get followers count
            followers_count = result_data.get('followers_count')
            
            result = GeniusArtist(
                name=name,
                genius_id=genius_id,
                url=url,
                cover_art_url=cover_art_url,
                followers_count=followers_count
            )
            results.append(result)
        
        return results
    
    def _parse_artist_songs(self, data: Dict[str, Any]) -> List[GeniusSong]:
        """Parse artist songs."""
        results = []
        
        songs = data.get('response', {}).get('songs', [])
        for song in songs:
            title = song.get('title', '')
            genius_id = str(song.get('id', ''))
            url = song.get('url', '')
            
            # Get primary artist
            primary_artist = song.get('primary_artist', {})
            artist = primary_artist.get('name', '')
            
            # Get song art
            song_art_image_url = song.get('song_art_image_url')
            
            # Get release date
            release_date = song.get('release_date_for_display')
            year = None
            if release_date:
                try:
                    year = int(release_date.split()[-1])
                except (ValueError, IndexError):
                    pass
            
            result = GeniusSong(
                title=title,
                artist=artist,
                album=None,
                year=year,
                lyrics=None,
                genius_id=genius_id,
                url=url,
                song_art_image_url=song_art_image_url
            )
            results.append(result)
        
        return results


def print_genius_results(results: List[GeniusSong], search_type: str):
    """Print Genius search results in a formatted way."""
    if not results:
        print(f"No {search_type} results found.")
        return
    
    print(f"\n=== GENIUS {search_type.upper()} RESULTS ===")
    print("-" * 60)
    
    for i, result in enumerate(results, 1):
        print(f"{i}. {result.title}")
        print(f"   Artist: {result.artist}")
        if result.album:
            print(f"   Album: {result.album}")
        if result.year:
            print(f"   Year: {result.year}")
        if result.featured_artists:
            print(f"   Featured Artists: {', '.join(result.featured_artists)}")
        if result.description:
            desc = result.description[:100] + "..." if len(result.description) > 100 else result.description
            print(f"   Description: {desc}")
        if result.lyrics:
            lyrics_preview = result.lyrics[:100] + "..." if len(result.lyrics) > 100 else result.lyrics
            print(f"   Lyrics: {lyrics_preview}")
        print(f"   URL: {result.url}")
        print()
