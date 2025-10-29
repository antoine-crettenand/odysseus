#!/usr/bin/env python3
"""
Discogs Client Module
A client for searching the Discogs database for music information.
"""

import requests
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from config import ERROR_MESSAGES, SUCCESS_MESSAGES, DEFAULTS


@dataclass
class DiscogsRelease:
    """Discogs release information."""
    title: str
    artist: str
    album: Optional[str]
    year: Optional[int]
    genre: Optional[str]
    style: Optional[str]
    label: Optional[str]
    country: Optional[str]
    format: Optional[str]
    cover_art_url: Optional[str]
    discogs_id: str
    url: str
    tracklist: List[Dict[str, Any]] = None
    popularity: Optional[int] = None


@dataclass
class DiscogsMaster:
    """Discogs master release information."""
    title: str
    artist: str
    year: Optional[int]
    genre: Optional[str]
    style: Optional[str]
    cover_art_url: Optional[str]
    discogs_id: str
    url: str
    main_release: Optional[str] = None


class DiscogsClient:
    """Discogs search client."""
    
    def __init__(self, user_token: Optional[str] = None):
        self.base_url = "https://api.discogs.com"
        self.user_agent = "Odysseus/1.0 +https://github.com/yourusername/odysseus"
        self.user_token = user_token
        self.request_delay = 1.2  # Discogs rate limit: 60 requests per minute
        self.timeout = 10
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'application/json'
        })
        
        if self.user_token:
            self.session.headers.update({
                'Authorization': f'Discogs token={self.user_token}'
            })
    
    def search_release(self, title: str, artist: str, album: Optional[str] = None) -> List[DiscogsRelease]:
        """
        Search for releases in Discogs.
        
        Args:
            title: Song title
            artist: Artist name
            album: Album name (optional)
            
        Returns:
            List of Discogs release results
        """
        # Build query string
        query_parts = []
        
        if title:
            query_parts.append(f'"{title}"')
        
        if artist:
            query_parts.append(f'artist:"{artist}"')
        
        if album:
            query_parts.append(f'"{album}"')
        
        query = ' '.join(query_parts)
        
        # Make request
        url = f"{self.base_url}/database/search"
        params = {
            'q': query,
            'type': 'release',
            'per_page': 25
        }
        
        try:
            print(f"Searching Discogs releases with query: {query}")
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            # Rate limiting
            time.sleep(self.request_delay)
            
            data = response.json()
            return self._parse_release_results(data)
            
        except requests.exceptions.RequestException as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return []
    
    def search_master(self, title: str, artist: str, album: Optional[str] = None) -> List[DiscogsMaster]:
        """
        Search for master releases in Discogs.
        
        Args:
            title: Song title
            artist: Artist name
            album: Album name (optional)
            
        Returns:
            List of Discogs master results
        """
        query_parts = []
        
        if title:
            query_parts.append(f'"{title}"')
        
        if artist:
            query_parts.append(f'artist:"{artist}"')
        
        if album:
            query_parts.append(f'"{album}"')
        
        query = ' '.join(query_parts)
        
        url = f"{self.base_url}/database/search"
        params = {
            'q': query,
            'type': 'master',
            'per_page': 25
        }
        
        try:
            print(f"Searching Discogs masters with query: {query}")
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            time.sleep(self.request_delay)
            
            data = response.json()
            return self._parse_master_results(data)
            
        except requests.exceptions.RequestException as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return []
    
    def get_release_details(self, release_id: str) -> Optional[DiscogsRelease]:
        """
        Get detailed release information.
        
        Args:
            release_id: Discogs release ID
            
        Returns:
            Detailed release information or None if failed
        """
        url = f"{self.base_url}/releases/{release_id}"
        
        try:
            print(f"Fetching Discogs release details for ID: {release_id}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            time.sleep(self.request_delay)
            
            data = response.json()
            return self._parse_release_detail(data)
            
        except requests.exceptions.RequestException as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return None
    
    def search_artist_releases(self, artist: str, year: Optional[int] = None) -> List[DiscogsRelease]:
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
            query_parts.append(f'year:{year}')
        
        query = ' '.join(query_parts)
        
        url = f"{self.base_url}/database/search"
        params = {
            'q': query,
            'type': 'release',
            'per_page': 50
        }
        
        try:
            print(f"Searching Discogs releases by artist: {artist}")
            if year:
                print(f"Filtering by year: {year}")
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            time.sleep(self.request_delay)
            
            data = response.json()
            return self._parse_release_results(data)
            
        except requests.exceptions.RequestException as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return []
    
    def _parse_release_results(self, data: Dict[str, Any]) -> List[DiscogsRelease]:
        """Parse release search results."""
        results = []
        
        releases = data.get('results', [])
        for release in releases:
            title = release.get('title', '')
            discogs_id = str(release.get('id', ''))
            year = release.get('year')
            
            # Extract artist from title (format: "Artist - Title")
            artist = ''
            if ' - ' in title:
                parts = title.split(' - ', 1)
                if len(parts) == 2:
                    artist = parts[0].strip()
                    title = parts[1].strip()
            
            # Get additional info
            genre = None
            style = None
            if 'genre' in release:
                genre = ', '.join(release['genre'])
            if 'style' in release:
                style = ', '.join(release['style'])
            
            # Get cover art
            cover_art_url = None
            if 'cover_image' in release:
                cover_art_url = release['cover_image']
            
            # Get label info
            label = None
            if 'label' in release and release['label']:
                if isinstance(release['label'], list) and release['label']:
                    label = release['label'][0]
                elif isinstance(release['label'], str):
                    label = release['label']
            
            # Get format info
            format_info = None
            if 'format' in release and release['format']:
                if isinstance(release['format'], list) and release['format']:
                    format_info = ', '.join(release['format'])
                elif isinstance(release['format'], str):
                    format_info = release['format']
            
            url = f"https://www.discogs.com/release/{discogs_id}"
            
            result = DiscogsRelease(
                title=title,
                artist=artist,
                album=title,  # In Discogs, title often contains album info
                year=year,
                genre=genre,
                style=style,
                label=label,
                country=release.get('country'),
                format=format_info,
                cover_art_url=cover_art_url,
                discogs_id=discogs_id,
                url=url
            )
            results.append(result)
        
        return results
    
    def _parse_master_results(self, data: Dict[str, Any]) -> List[DiscogsMaster]:
        """Parse master search results."""
        results = []
        
        masters = data.get('results', [])
        for master in masters:
            title = master.get('title', '')
            discogs_id = str(master.get('id', ''))
            year = master.get('year')
            
            # Extract artist from title
            artist = ''
            if ' - ' in title:
                parts = title.split(' - ', 1)
                if len(parts) == 2:
                    artist = parts[0].strip()
                    title = parts[1].strip()
            
            # Get genre and style
            genre = None
            style = None
            if 'genre' in master:
                genre = ', '.join(master['genre'])
            if 'style' in master:
                style = ', '.join(master['style'])
            
            # Get cover art
            cover_art_url = None
            if 'cover_image' in master:
                cover_art_url = master['cover_image']
            
            # Get main release
            main_release = None
            if 'main_release' in master:
                main_release = str(master['main_release'])
            
            url = f"https://www.discogs.com/master/{discogs_id}"
            
            result = DiscogsMaster(
                title=title,
                artist=artist,
                year=year,
                genre=genre,
                style=style,
                cover_art_url=cover_art_url,
                discogs_id=discogs_id,
                url=url,
                main_release=main_release
            )
            results.append(result)
        
        return results
    
    def _parse_release_detail(self, data: Dict[str, Any]) -> Optional[DiscogsRelease]:
        """Parse detailed release information."""
        try:
            title = data.get('title', '')
            discogs_id = str(data.get('id', ''))
            year = data.get('year')
            
            # Extract artist
            artist = ''
            if 'artists' in data and data['artists']:
                artist = data['artists'][0].get('name', '')
            
            # Get genre and style
            genre = None
            style = None
            if 'genres' in data:
                genre = ', '.join(data['genres'])
            if 'styles' in data:
                style = ', '.join(data['styles'])
            
            # Get label info
            label = None
            if 'labels' in data and data['labels']:
                label = data['labels'][0].get('name', '')
            
            # Get format info
            format_info = None
            if 'formats' in data and data['formats']:
                format_parts = []
                for fmt in data['formats']:
                    format_parts.append(fmt.get('name', ''))
                format_info = ', '.join(format_parts)
            
            # Get cover art
            cover_art_url = None
            if 'images' in data and data['images']:
                for image in data['images']:
                    if image.get('type') == 'primary':
                        cover_art_url = image.get('uri')
                        break
                if not cover_art_url and data['images']:
                    cover_art_url = data['images'][0].get('uri')
            
            # Get tracklist
            tracklist = []
            if 'tracklist' in data:
                tracklist = data['tracklist']
            
            url = f"https://www.discogs.com/release/{discogs_id}"
            
            return DiscogsRelease(
                title=title,
                artist=artist,
                album=title,
                year=year,
                genre=genre,
                style=style,
                label=label,
                country=data.get('country'),
                format=format_info,
                cover_art_url=cover_art_url,
                discogs_id=discogs_id,
                url=url,
                tracklist=tracklist
            )
            
        except Exception as e:
            print(f"Error parsing release detail: {e}")
            return None


def print_discogs_results(results: List[DiscogsRelease], search_type: str):
    """Print Discogs search results in a formatted way."""
    if not results:
        print(f"No {search_type} results found.")
        return
    
    print(f"\n=== DISCOGS {search_type.upper()} RESULTS ===")
    print("-" * 60)
    
    for i, result in enumerate(results, 1):
        print(f"{i}. {result.title}")
        print(f"   Artist: {result.artist}")
        if result.year:
            print(f"   Year: {result.year}")
        if result.genre:
            print(f"   Genre: {result.genre}")
        if result.style:
            print(f"   Style: {result.style}")
        if result.label:
            print(f"   Label: {result.label}")
        if result.format:
            print(f"   Format: {result.format}")
        print(f"   URL: {result.url}")
        print()
