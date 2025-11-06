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
    genre: Optional[str] = None
    mbid: str = ""
    url: str = ""
    tracks: List[Track] = None
    
    def __post_init__(self):
        """Initialize tracks list if not provided."""
        if self.tracks is None:
            self.tracks = []
