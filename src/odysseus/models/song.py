"""
Core song data models.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class SongData:
    """Basic song data structure."""
    title: str
    artist: str
    album: Optional[str] = None
    release_year: Optional[int] = None
    genre: Optional[str] = None
    
    def __post_init__(self):
        """Validate song data after initialization."""
        if not self.title and not self.album:
            raise ValueError("Either title or album must be provided")
        if not self.artist:
            raise ValueError("Artist must be provided")
        
        if self.release_year and not (1900 <= self.release_year <= 2030):
            logger.debug(f"Invalid year: {self.release_year}")
            self.release_year = None


@dataclass
class AudioMetadata:
    """Represents audio file metadata."""
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    album_artist: Optional[str] = None
    track_number: Optional[int] = None
    total_tracks: Optional[int] = None
    disc_number: Optional[int] = None
    total_discs: Optional[int] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    comment: Optional[str] = None
    composer: Optional[str] = None
    conductor: Optional[str] = None
    performer: Optional[str] = None
    publisher: Optional[str] = None
    copyright: Optional[str] = None
    isrc: Optional[str] = None
    bpm: Optional[int] = None
    key: Optional[str] = None
    mood: Optional[str] = None
    cover_art_url: Optional[str] = None
    cover_art_data: Optional[bytes] = None
    compilation: Optional[bool] = None  # For iTunes compilation detection (TCMP tag)
    source: str = "unknown"
    
    def __post_init__(self):
        """Validate metadata after initialization."""
        if self.year and not (1900 <= self.year <= 2030):
            logger.debug(f"Invalid year: {self.year}")
            self.year = None
        
        if self.track_number is not None and self.track_number < 1:
            logger.debug(f"Invalid track number: {self.track_number}")
            self.track_number = None
            
        if self.total_tracks is not None and self.total_tracks < 1:
            logger.debug(f"Invalid total tracks: {self.total_tracks}")
            self.total_tracks = None
