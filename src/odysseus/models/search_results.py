"""
Search result models from various sources.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod


@dataclass
class SearchResult(ABC):
    """Abstract base class for search results."""
    title: str
    artist: str
    source: str
    score: int = 0
    url: str = ""
    
    @abstractmethod
    def get_display_name(self) -> str:
        """Get display name for the result."""
        pass


@dataclass
class MusicBrainzSong(SearchResult):
    """MusicBrainz search result."""
    album: Optional[str] = None
    release_date: Optional[str] = None
    genre: Optional[str] = None
    mbid: str = ""
    source: str = "musicbrainz"
    
    def get_display_name(self) -> str:
        """Get display name for the result."""
        return self.title or self.album or "Unknown"


@dataclass
class YouTubeVideo(SearchResult):
    """YouTube video search result."""
    video_id: str = ""
    channel: str = ""
    duration: Optional[str] = None
    views: Optional[str] = None
    publish_time: Optional[str] = None
    url_suffix: str = ""
    source: str = "youtube"
    
    def get_display_name(self) -> str:
        """Get display name for the result."""
        return self.title or "No title"
    
    @property
    def youtube_url(self) -> str:
        """Get full YouTube URL."""
        if self.video_id:
            return f"https://www.youtube.com/watch?v={self.video_id}"
        return self.url_suffix or ""


@dataclass
class DiscogsRelease(SearchResult):
    """Discogs release search result."""
    album: Optional[str] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    style: Optional[str] = None
    label: Optional[str] = None
    country: Optional[str] = None
    format: Optional[str] = None
    cover_art_url: Optional[str] = None
    discogs_id: str = ""
    source: str = "discogs"
    
    def get_display_name(self) -> str:
        """Get display name for the result."""
        return self.title or self.album or "Unknown"


@dataclass
class LastFmTrack(SearchResult):
    """Last.fm track search result."""
    album: Optional[str] = None
    playcount: Optional[int] = None
    listeners: Optional[int] = None
    duration: Optional[int] = None
    mbid: Optional[str] = None
    tags: List[str] = None
    source: str = "lastfm"
    
    def get_display_name(self) -> str:
        """Get display name for the result."""
        return self.title or "Unknown"


@dataclass
class SpotifyTrack(SearchResult):
    """Spotify track search result."""
    album: Optional[str] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    duration_ms: Optional[int] = None
    popularity: Optional[int] = None
    spotify_id: str = ""
    preview_url: Optional[str] = None
    cover_art_url: Optional[str] = None
    audio_features: Optional[Dict[str, Any]] = None
    source: str = "spotify"
    
    def get_display_name(self) -> str:
        """Get display name for the result."""
        return self.title or "Unknown"


@dataclass
class GeniusSong(SearchResult):
    """Genius song search result."""
    album: Optional[str] = None
    year: Optional[int] = None
    lyrics: Optional[str] = None
    genius_id: str = ""
    cover_art_url: Optional[str] = None
    description: Optional[str] = None
    song_art_image_url: Optional[str] = None
    source: str = "genius"
    
    def get_display_name(self) -> str:
        """Get display name for the result."""
        return self.title or "Unknown"
