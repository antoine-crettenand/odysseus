"""
Base class for download strategies.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
from .....models.releases import ReleaseInfo


class BaseDownloadStrategy(ABC):
    """Base class for download strategies."""

    def __init__(
        self,
        download_service,
        metadata_service,
        search_service,
        presenter,
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
            presenter: DownloadPresenter instance
            video_validator: VideoValidator instance
            title_matcher: TitleMatcher instance
            path_manager: PathManager instance
        """
        self.download_service = download_service
        self.metadata_service = metadata_service
        self.search_service = search_service
        self.presenter = presenter
        self.video_validator = video_validator
        self.title_matcher = title_matcher
        self.path_manager = path_manager
        self.failed_track_numbers: List[int] = []

    def _start_attempt(self, track_numbers: List[int]) -> None:
        """Remember every requested track until that track is downloaded."""
        self.failed_track_numbers = list(dict.fromkeys(track_numbers))

    def _mark_track_downloaded(self, track_number: int) -> None:
        """Remove a successfully downloaded track from the failure set."""
        self.failed_track_numbers = [
            number
            for number in self.failed_track_numbers
            if number != track_number
        ]

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
