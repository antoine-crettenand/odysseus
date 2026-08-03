"""
Client modules for external APIs.
"""

from .musicbrainz import MusicBrainzClient
from .discogs import DiscogsClient
from .youtube import YouTubeClient
from .youtube_downloader import YouTubeDownloader
from .spotify import SpotifyClient
from .apple_music import AppleMusicClient
from .acoustid import AcoustIDClient, AudioVerification

__all__ = [
    'MusicBrainzClient',
    'DiscogsClient',
    'YouTubeClient',
    'YouTubeDownloader',
    'SpotifyClient',
    'AppleMusicClient',
    'AcoustIDClient',
    'AudioVerification',
]
