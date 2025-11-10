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


@dataclass
class ReleaseInfo:
    """Detailed release information with tracks."""
    title: str
    artist: str
    release_date: Optional[str] = None
    original_release_date: Optional[str] = None  # Original release date from release-group (first-release-date)
    genre: Optional[str] = None
    release_type: Optional[str] = None  # e.g., "Album", "Single", "EP", "Compilation", "Live", etc.
    mbid: str = ""
    url: str = ""
    cover_art_url: Optional[str] = None  # URL to cover art (e.g., from Spotify)
    tracks: List[Track] = None
    
    def __post_init__(self):
        """Initialize tracks list if not provided."""
        if self.tracks is None:
            self.tracks = []
