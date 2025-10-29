#!/usr/bin/env python3
"""
Last.fm Client Module
A client for searching the Last.fm database for music information and popularity data.
"""

import requests
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from config import ERROR_MESSAGES, SUCCESS_MESSAGES, DEFAULTS


@dataclass
class LastFmTrack:
    """Last.fm track information."""
    title: str
    artist: str
    album: Optional[str]
    playcount: Optional[int]
    listeners: Optional[int]
    duration: Optional[int]
    mbid: Optional[str]
    url: str
    tags: List[str] = None
    wiki: Optional[Dict[str, Any]] = None


@dataclass
class LastFmAlbum:
    """Last.fm album information."""
    title: str
    artist: str
    playcount: Optional[int]
    listeners: Optional[int]
    mbid: Optional[str]
    url: str
    tracks: List[LastFmTrack] = None
    tags: List[str] = None
    wiki: Optional[Dict[str, Any]] = None


@dataclass
class LastFmArtist:
    """Last.fm artist information."""
    name: str
    playcount: Optional[int]
    listeners: Optional[int]
    mbid: Optional[str]
    url: str
    tags: List[str] = None
    bio: Optional[Dict[str, Any]] = None
    similar_artists: List[str] = None


class LastFmClient:
    """Last.fm search client."""
    
    def __init__(self, api_key: str):
        self.base_url = "http://ws.audioscrobbler.com/2.0"
        self.api_key = api_key
        self.request_delay = 0.25  # Last.fm rate limit: 5 requests per second
        self.timeout = 10
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Odysseus/1.0'
        })
    
    def search_track(self, title: str, artist: str, album: Optional[str] = None) -> List[LastFmTrack]:
        """
        Search for tracks in Last.fm.
        
        Args:
            title: Song title
            artist: Artist name
            album: Album name (optional)
            
        Returns:
            List of Last.fm track results
        """
        params = {
            'method': 'track.search',
            'track': title,
            'artist': artist,
            'api_key': self.api_key,
            'format': 'json',
            'limit': 25
        }
        
        if album:
            params['album'] = album
        
        try:
            print(f"Searching Last.fm tracks: {title} by {artist}")
            response = self.session.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            time.sleep(self.request_delay)
            
            data = response.json()
            return self._parse_track_search_results(data)
            
        except requests.exceptions.RequestException as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return []
    
    def get_track_info(self, title: str, artist: str) -> Optional[LastFmTrack]:
        """
        Get detailed track information from Last.fm.
        
        Args:
            title: Song title
            artist: Artist name
            
        Returns:
            Detailed track information or None if failed
        """
        params = {
            'method': 'track.getinfo',
            'track': title,
            'artist': artist,
            'api_key': self.api_key,
            'format': 'json'
        }
        
        try:
            print(f"Getting Last.fm track info: {title} by {artist}")
            response = self.session.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            time.sleep(self.request_delay)
            
            data = response.json()
            return self._parse_track_info(data)
            
        except requests.exceptions.RequestException as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return None
    
    def search_album(self, album: str, artist: str) -> List[LastFmAlbum]:
        """
        Search for albums in Last.fm.
        
        Args:
            album: Album name
            artist: Artist name
            
        Returns:
            List of Last.fm album results
        """
        params = {
            'method': 'album.search',
            'album': album,
            'artist': artist,
            'api_key': self.api_key,
            'format': 'json',
            'limit': 25
        }
        
        try:
            print(f"Searching Last.fm albums: {album} by {artist}")
            response = self.session.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            time.sleep(self.request_delay)
            
            data = response.json()
            return self._parse_album_search_results(data)
            
        except requests.exceptions.RequestException as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return []
    
    def get_album_info(self, album: str, artist: str) -> Optional[LastFmAlbum]:
        """
        Get detailed album information from Last.fm.
        
        Args:
            album: Album name
            artist: Artist name
            
        Returns:
            Detailed album information or None if failed
        """
        params = {
            'method': 'album.getinfo',
            'album': album,
            'artist': artist,
            'api_key': self.api_key,
            'format': 'json'
        }
        
        try:
            print(f"Getting Last.fm album info: {album} by {artist}")
            response = self.session.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            time.sleep(self.request_delay)
            
            data = response.json()
            return self._parse_album_info(data)
            
        except requests.exceptions.RequestException as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return None
    
    def search_artist(self, artist: str) -> List[LastFmArtist]:
        """
        Search for artists in Last.fm.
        
        Args:
            artist: Artist name
            
        Returns:
            List of Last.fm artist results
        """
        params = {
            'method': 'artist.search',
            'artist': artist,
            'api_key': self.api_key,
            'format': 'json',
            'limit': 25
        }
        
        try:
            print(f"Searching Last.fm artists: {artist}")
            response = self.session.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            time.sleep(self.request_delay)
            
            data = response.json()
            return self._parse_artist_search_results(data)
            
        except requests.exceptions.RequestException as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return []
    
    def get_artist_info(self, artist: str) -> Optional[LastFmArtist]:
        """
        Get detailed artist information from Last.fm.
        
        Args:
            artist: Artist name
            
        Returns:
            Detailed artist information or None if failed
        """
        params = {
            'method': 'artist.getinfo',
            'artist': artist,
            'api_key': self.api_key,
            'format': 'json'
        }
        
        try:
            print(f"Getting Last.fm artist info: {artist}")
            response = self.session.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            time.sleep(self.request_delay)
            
            data = response.json()
            return self._parse_artist_info(data)
            
        except requests.exceptions.RequestException as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return None
    
    def get_top_tracks(self, artist: str, limit: int = 10) -> List[LastFmTrack]:
        """
        Get top tracks for an artist.
        
        Args:
            artist: Artist name
            limit: Number of tracks to return
            
        Returns:
            List of top tracks
        """
        params = {
            'method': 'artist.gettoptracks',
            'artist': artist,
            'api_key': self.api_key,
            'format': 'json',
            'limit': limit
        }
        
        try:
            print(f"Getting top tracks for artist: {artist}")
            response = self.session.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            time.sleep(self.request_delay)
            
            data = response.json()
            return self._parse_top_tracks(data)
            
        except requests.exceptions.RequestException as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return []
    
    def _parse_track_search_results(self, data: Dict[str, Any]) -> List[LastFmTrack]:
        """Parse track search results."""
        results = []
        
        try:
            tracks = data.get('results', {}).get('trackmatches', {}).get('track', [])
            if not isinstance(tracks, list):
                tracks = [tracks]
            
            for track in tracks:
                title = track.get('name', '')
                artist = track.get('artist', '')
                listeners = track.get('listeners')
                mbid = track.get('mbid')
                url = track.get('url', '')
                
                # Parse listeners count
                listeners_count = None
                if listeners:
                    try:
                        listeners_count = int(listeners)
                    except (ValueError, TypeError):
                        pass
                
                result = LastFmTrack(
                    title=title,
                    artist=artist,
                    album=None,
                    playcount=None,
                    listeners=listeners_count,
                    duration=None,
                    mbid=mbid,
                    url=url
                )
                results.append(result)
                
        except Exception as e:
            print(f"Error parsing track search results: {e}")
        
        return results
    
    def _parse_track_info(self, data: Dict[str, Any]) -> Optional[LastFmTrack]:
        """Parse detailed track information."""
        try:
            track = data.get('track', {})
            if not track:
                return None
            
            title = track.get('name', '')
            artist = track.get('artist', {}).get('name', '')
            album = track.get('album', {}).get('title') if track.get('album') else None
            playcount = track.get('playcount')
            listeners = track.get('listeners')
            duration = track.get('duration')
            mbid = track.get('mbid')
            url = track.get('url', '')
            
            # Parse counts
            playcount_int = None
            if playcount:
                try:
                    playcount_int = int(playcount)
                except (ValueError, TypeError):
                    pass
            
            listeners_int = None
            if listeners:
                try:
                    listeners_int = int(listeners)
                except (ValueError, TypeError):
                    pass
            
            duration_int = None
            if duration:
                try:
                    duration_int = int(duration)
                except (ValueError, TypeError):
                    pass
            
            # Get tags
            tags = []
            if 'toptags' in track and 'tag' in track['toptags']:
                tag_list = track['toptags']['tag']
                if isinstance(tag_list, list):
                    tags = [tag.get('name', '') for tag in tag_list if tag.get('name')]
                elif isinstance(tag_list, dict) and tag_list.get('name'):
                    tags = [tag_list['name']]
            
            # Get wiki
            wiki = track.get('wiki')
            
            return LastFmTrack(
                title=title,
                artist=artist,
                album=album,
                playcount=playcount_int,
                listeners=listeners_int,
                duration=duration_int,
                mbid=mbid,
                url=url,
                tags=tags,
                wiki=wiki
            )
            
        except Exception as e:
            print(f"Error parsing track info: {e}")
            return None
    
    def _parse_album_search_results(self, data: Dict[str, Any]) -> List[LastFmAlbum]:
        """Parse album search results."""
        results = []
        
        try:
            albums = data.get('results', {}).get('albummatches', {}).get('album', [])
            if not isinstance(albums, list):
                albums = [albums]
            
            for album in albums:
                title = album.get('name', '')
                artist = album.get('artist', '')
                listeners = album.get('listeners')
                mbid = album.get('mbid')
                url = album.get('url', '')
                
                # Parse listeners count
                listeners_count = None
                if listeners:
                    try:
                        listeners_count = int(listeners)
                    except (ValueError, TypeError):
                        pass
                
                result = LastFmAlbum(
                    title=title,
                    artist=artist,
                    playcount=None,
                    listeners=listeners_count,
                    mbid=mbid,
                    url=url
                )
                results.append(result)
                
        except Exception as e:
            print(f"Error parsing album search results: {e}")
        
        return results
    
    def _parse_album_info(self, data: Dict[str, Any]) -> Optional[LastFmAlbum]:
        """Parse detailed album information."""
        try:
            album = data.get('album', {})
            if not album:
                return None
            
            title = album.get('name', '')
            artist = album.get('artist', '')
            playcount = album.get('playcount')
            listeners = album.get('listeners')
            mbid = album.get('mbid')
            url = album.get('url', '')
            
            # Parse counts
            playcount_int = None
            if playcount:
                try:
                    playcount_int = int(playcount)
                except (ValueError, TypeError):
                    pass
            
            listeners_int = None
            if listeners:
                try:
                    listeners_int = int(listeners)
                except (ValueError, TypeError):
                    pass
            
            # Get tracks
            tracks = []
            if 'tracks' in album and 'track' in album['tracks']:
                track_list = album['tracks']['track']
                if isinstance(track_list, list):
                    for track_data in track_list:
                        track = LastFmTrack(
                            title=track_data.get('name', ''),
                            artist=artist,
                            album=title,
                            playcount=None,
                            listeners=None,
                            duration=track_data.get('duration'),
                            mbid=track_data.get('mbid'),
                            url=track_data.get('url', '')
                        )
                        tracks.append(track)
                elif isinstance(track_list, dict):
                    track = LastFmTrack(
                        title=track_list.get('name', ''),
                        artist=artist,
                        album=title,
                        playcount=None,
                        listeners=None,
                        duration=track_list.get('duration'),
                        mbid=track_list.get('mbid'),
                        url=track_list.get('url', '')
                    )
                    tracks.append(track)
            
            # Get tags
            tags = []
            if 'toptags' in album and 'tag' in album['toptags']:
                tag_list = album['toptags']['tag']
                if isinstance(tag_list, list):
                    tags = [tag.get('name', '') for tag in tag_list if tag.get('name')]
                elif isinstance(tag_list, dict) and tag_list.get('name'):
                    tags = [tag_list['name']]
            
            # Get wiki
            wiki = album.get('wiki')
            
            return LastFmAlbum(
                title=title,
                artist=artist,
                playcount=playcount_int,
                listeners=listeners_int,
                mbid=mbid,
                url=url,
                tracks=tracks,
                tags=tags,
                wiki=wiki
            )
            
        except Exception as e:
            print(f"Error parsing album info: {e}")
            return None
    
    def _parse_artist_search_results(self, data: Dict[str, Any]) -> List[LastFmArtist]:
        """Parse artist search results."""
        results = []
        
        try:
            artists = data.get('results', {}).get('artistmatches', {}).get('artist', [])
            if not isinstance(artists, list):
                artists = [artists]
            
            for artist in artists:
                name = artist.get('name', '')
                listeners = artist.get('listeners')
                mbid = artist.get('mbid')
                url = artist.get('url', '')
                
                # Parse listeners count
                listeners_count = None
                if listeners:
                    try:
                        listeners_count = int(listeners)
                    except (ValueError, TypeError):
                        pass
                
                result = LastFmArtist(
                    name=name,
                    playcount=None,
                    listeners=listeners_count,
                    mbid=mbid,
                    url=url
                )
                results.append(result)
                
        except Exception as e:
            print(f"Error parsing artist search results: {e}")
        
        return results
    
    def _parse_artist_info(self, data: Dict[str, Any]) -> Optional[LastFmArtist]:
        """Parse detailed artist information."""
        try:
            artist = data.get('artist', {})
            if not artist:
                return None
            
            name = artist.get('name', '')
            playcount = artist.get('playcount')
            listeners = artist.get('listeners')
            mbid = artist.get('mbid')
            url = artist.get('url', '')
            
            # Parse counts
            playcount_int = None
            if playcount:
                try:
                    playcount_int = int(playcount)
                except (ValueError, TypeError):
                    pass
            
            listeners_int = None
            if listeners:
                try:
                    listeners_int = int(listeners)
                except (ValueError, TypeError):
                    pass
            
            # Get tags
            tags = []
            if 'toptags' in artist and 'tag' in artist['toptags']:
                tag_list = artist['toptags']['tag']
                if isinstance(tag_list, list):
                    tags = [tag.get('name', '') for tag in tag_list if tag.get('name')]
                elif isinstance(tag_list, dict) and tag_list.get('name'):
                    tags = [tag_list['name']]
            
            # Get bio
            bio = artist.get('bio')
            
            # Get similar artists
            similar_artists = []
            if 'similar' in artist and 'artist' in artist['similar']:
                similar_list = artist['similar']['artist']
                if isinstance(similar_list, list):
                    similar_artists = [sim.get('name', '') for sim in similar_list if sim.get('name')]
                elif isinstance(similar_list, dict) and similar_list.get('name'):
                    similar_artists = [similar_list['name']]
            
            return LastFmArtist(
                name=name,
                playcount=playcount_int,
                listeners=listeners_int,
                mbid=mbid,
                url=url,
                tags=tags,
                bio=bio,
                similar_artists=similar_artists
            )
            
        except Exception as e:
            print(f"Error parsing artist info: {e}")
            return None
    
    def _parse_top_tracks(self, data: Dict[str, Any]) -> List[LastFmTrack]:
        """Parse top tracks data."""
        results = []
        
        try:
            tracks = data.get('toptracks', {}).get('track', [])
            if not isinstance(tracks, list):
                tracks = [tracks]
            
            for track in tracks:
                title = track.get('name', '')
                artist = track.get('artist', {}).get('name', '')
                playcount = track.get('playcount')
                listeners = track.get('listeners')
                duration = track.get('duration')
                mbid = track.get('mbid')
                url = track.get('url', '')
                
                # Parse counts
                playcount_int = None
                if playcount:
                    try:
                        playcount_int = int(playcount)
                    except (ValueError, TypeError):
                        pass
                
                listeners_int = None
                if listeners:
                    try:
                        listeners_int = int(listeners)
                    except (ValueError, TypeError):
                        pass
                
                duration_int = None
                if duration:
                    try:
                        duration_int = int(duration)
                    except (ValueError, TypeError):
                        pass
                
                result = LastFmTrack(
                    title=title,
                    artist=artist,
                    album=None,
                    playcount=playcount_int,
                    listeners=listeners_int,
                    duration=duration_int,
                    mbid=mbid,
                    url=url
                )
                results.append(result)
                
        except Exception as e:
            print(f"Error parsing top tracks: {e}")
        
        return results


def print_lastfm_results(results: List[LastFmTrack], search_type: str):
    """Print Last.fm search results in a formatted way."""
    if not results:
        print(f"No {search_type} results found.")
        return
    
    print(f"\n=== LAST.FM {search_type.upper()} RESULTS ===")
    print("-" * 60)
    
    for i, result in enumerate(results, 1):
        print(f"{i}. {result.title}")
        print(f"   Artist: {result.artist}")
        if result.album:
            print(f"   Album: {result.album}")
        if result.playcount:
            print(f"   Playcount: {result.playcount:,}")
        if result.listeners:
            print(f"   Listeners: {result.listeners:,}")
        if result.duration:
            duration_min = result.duration // 60
            duration_sec = result.duration % 60
            print(f"   Duration: {duration_min}:{duration_sec:02d}")
        if result.tags:
            print(f"   Tags: {', '.join(result.tags[:5])}")
        print(f"   URL: {result.url}")
        print()
