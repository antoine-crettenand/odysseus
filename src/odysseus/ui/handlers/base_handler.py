"""
Base handler class for command handlers.
"""

from ...services.search_service import SearchService
from ...services.download_service import DownloadService
from ...services.metadata_service import MetadataService
from ...ui.display import DisplayManager


class BaseHandler:
    """Base class for command handlers."""
    
    def __init__(
        self,
        search_service: SearchService,
        download_service: DownloadService,
        metadata_service: MetadataService,
        display_manager: DisplayManager
    ):
        self.search_service = search_service
        self.download_service = download_service
        self.metadata_service = metadata_service
        self.display_manager = display_manager

