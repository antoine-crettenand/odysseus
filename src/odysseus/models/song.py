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
        from ..core.validation import validate_user_input, validate_year
        from ..core.config import VALIDATION_RULES

        # Validate user-facing identity fields strictly. Invalid values must
        # never be restored after validation rejects them.
        if self.title:
            self.title = validate_user_input(
                "title", self.title, VALIDATION_RULES.get("MAX_TITLE_LENGTH", 200)
            )

        if self.artist:
            self.artist = validate_user_input(
                "artist", self.artist, VALIDATION_RULES.get("MAX_ARTIST_LENGTH", 100)
            )

        if self.album:
            self.album = validate_user_input("album", self.album, 200)

        # Validate that we have required fields
        if not self.title and not self.album:
            raise ValueError("Either title or album must be provided")
        if not self.artist:
            raise ValueError("Artist must be provided")

        # Soft-coerce invalid years so model construction stays resilient
        self.release_year = validate_year(self.release_year, coerce=True)


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
        from ..core.validation import validate_year, validate_user_input
        from ..core.config import VALIDATION_RULES

        # Optional metadata fields normalize blank values to None. Filesystem
        # sanitization is deliberately not performed at the metadata boundary.
        if self.title:
            self.title = validate_user_input(
                "title", self.title, VALIDATION_RULES.get("MAX_TITLE_LENGTH", 200)
            )

        if self.artist:
            self.artist = validate_user_input(
                "artist", self.artist, VALIDATION_RULES.get("MAX_ARTIST_LENGTH", 100)
            )

        if self.album:
            self.album = validate_user_input("album", self.album, 200)

        # Soft-coerce invalid years so model construction stays resilient
        self.year = validate_year(self.year, coerce=True)

        if self.track_number is not None and self.track_number < 1:
            logger.debug(f"Invalid track number: {self.track_number}")
            self.track_number = None

        if self.total_tracks is not None and self.total_tracks < 1:
            logger.debug(f"Invalid total tracks: {self.total_tracks}")
            self.total_tracks = None
