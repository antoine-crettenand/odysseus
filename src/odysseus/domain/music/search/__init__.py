"""
Music search domain module.
"""

from .search_service import SearchService
from .deduplicator import ResultDeduplicator
from .video_searcher import VideoSearcher
from .playlist_checker import PlaylistChecker

__all__ = [
    'SearchService',
    'ResultDeduplicator',
    'VideoSearcher',
    'PlaylistChecker',
]
