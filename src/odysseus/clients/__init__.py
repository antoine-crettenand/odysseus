"""
Client modules for external APIs.
"""

from .musicbrainz import MusicBrainzClient
from .youtube import YouTubeClient
from .youtube_downloader import YouTubeDownloader

__all__ = [
    'MusicBrainzClient',
    'YouTubeClient',
    'YouTubeDownloader'
]
