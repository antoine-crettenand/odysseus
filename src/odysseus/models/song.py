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
        # Import here to avoid circular imports
        from ..core.validation import validate_user_input, validate_year, VALIDATION_RULES
        
        # Validate and sanitize string inputs
        if self.title:
            try:
                self.title = validate_user_input("title", self.title, VALIDATION_RULES.get("MAX_TITLE_LENGTH", 200))
            except ValueError as e:
                logger.warning(f"Invalid title: {e}")
                self.title = self.title[:200] if len(self.title) > 200 else self.title
        
        if self.artist:
            try:
                self.artist = validate_user_input("artist", self.artist, VALIDATION_RULES.get("MAX_ARTIST_LENGTH", 100))
            except ValueError as e:
                logger.warning(f"Invalid artist: {e}")
                self.artist = self.artist[:100] if len(self.artist) > 100 else self.artist
        
        if self.album:
            try:
                self.album = validate_user_input("album", self.album, 200)
            except ValueError as e:
                logger.warning(f"Invalid album: {e}")
                self.album = self.album[:200] if len(self.album) > 200 else self.album
        
        # Validate that we have required fields
        if not self.title and not self.album:
            raise ValueError("Either title or album must be provided")
        if not self.artist:
            raise ValueError("Artist must be provided")
        
        # Validate year
        self.release_year = validate_year(self.release_year)


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
        # Import here to avoid circular imports
        from ..core.validation import validate_year, validate_user_input, VALIDATION_RULES
        
        # Validate and sanitize string fields
        if self.title:
            try:
                self.title = validate_user_input("title", self.title, VALIDATION_RULES.get("MAX_TITLE_LENGTH", 200))
            except ValueError:
                self.title = self.title[:200] if len(self.title) > 200 else self.title
        
        if self.artist:
            try:
                self.artist = validate_user_input("artist", self.artist, VALIDATION_RULES.get("MAX_ARTIST_LENGTH", 100))
            except ValueError:
                self.artist = self.artist[:100] if len(self.artist) > 100 else self.artist
        
        if self.album:
            try:
                self.album = validate_user_input("album", self.album, 200)
            except ValueError:
                self.album = self.album[:200] if len(self.album) > 200 else self.album
        
        # Validate year
        self.year = validate_year(self.year)
        
        if self.track_number is not None and self.track_number < 1:
            logger.debug(f"Invalid track number: {self.track_number}")
            self.track_number = None
            
        if self.total_tracks is not None and self.total_tracks < 1:
            logger.debug(f"Invalid total tracks: {self.total_tracks}")
            self.total_tracks = None
