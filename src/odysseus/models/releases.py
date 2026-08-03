"""
Release and track models.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Track:
    """Track information from a release."""
    position: int
    title: str
    artist: str
    duration: Optional[str] = None
    mbid: Optional[str] = None
    isrc: Optional[str] = None
    source_id: Optional[str] = None
    disc_number: Optional[int] = None
    disc_track_number: Optional[int] = None
    disc_total_tracks: Optional[int] = None


@dataclass
class ReleaseInfo:
    """Detailed release information with tracks."""
    title: str
    artist: str
    release_date: Optional[str] = None
    original_release_date: Optional[str] = None  # Original release date from release-group (first-release-date)
    genre: Optional[str] = None
    release_type: Optional[str] = None  # e.g., "Album", "Single", "EP", "Compilation", "Live", etc.
    release_status: Optional[str] = None
    country: Optional[str] = None
    label: Optional[str] = None
    catalog_number: Optional[str] = None
    barcode: Optional[str] = None
    media_format: Optional[str] = None
    mbid: str = ""
    url: str = ""
    cover_art_url: Optional[str] = None  # URL to cover art (e.g., from Spotify)
    tracks: List[Track] = None
    copyright: Optional[str] = None
    total_discs: Optional[int] = None
    source: str = "unknown"
    
    def __post_init__(self):
        """Initialize tracks list if not provided."""
        if self.tracks is None:
            self.tracks = []
