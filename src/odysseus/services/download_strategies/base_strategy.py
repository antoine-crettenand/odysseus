"""
Base class for download strategies.
"""

from abc import ABC, abstractmethod
from typing import Tuple, Optional
from ...models.releases import ReleaseInfo


class BaseDownloadStrategy(ABC):
    """Base class for download strategies."""
    
    def __init__(
        self,
        download_service,
        metadata_service,
        search_service,
        display_manager,
        video_validator,
        title_matcher,
        path_manager
    ):
        """
        Initialize base strategy.
        
        Args:
            download_service: DownloadService instance
            metadata_service: MetadataService instance
            search_service: SearchService instance
            display_manager: DisplayManager instance
            video_validator: VideoValidator instance
            title_matcher: TitleMatcher instance
            path_manager: PathManager instance
        """
        self.download_service = download_service
        self.metadata_service = metadata_service
        self.search_service = search_service
        self.display_manager = display_manager
        self.video_validator = video_validator
        self.title_matcher = title_matcher
        self.path_manager = path_manager
    
    @abstractmethod
    def download(
        self,
        release_info: ReleaseInfo,
        track_numbers: list,
        quality: str,
        silent: bool = False
    ) -> Tuple[Optional[int], Optional[int]]:
        """
        Download tracks using this strategy.
        
        Args:
            release_info: Release information
            track_numbers: List of track numbers to download
            quality: Download quality
            silent: Whether to suppress output
            
        Returns:
            Tuple of (downloaded_count, failed_count) or (None, None) if strategy failed
        """
        pass

