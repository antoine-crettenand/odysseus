"""
Download strategies for different download approaches.
"""

from .base_strategy import BaseDownloadStrategy
from .full_album_strategy import FullAlbumStrategy
from .playlist_strategy import PlaylistStrategy
from .individual_tracks_strategy import IndividualTracksStrategy

__all__ = [
    'BaseDownloadStrategy',
    'FullAlbumStrategy',
    'PlaylistStrategy',
    'IndividualTracksStrategy',
]

