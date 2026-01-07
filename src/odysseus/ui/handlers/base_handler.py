"""
Base handler class for command handlers.
"""

from typing import Optional
from ...services.search_service import SearchService
from ...services.download_service import DownloadService
from ...services.metadata_service import MetadataService
from ...ui.display import DisplayManager
from ...utils.string_utils import normalize_string
from ...core.exceptions import ValidationError
from ...core.config import ERROR_MESSAGES


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
    
    def _validate_search_params(self, artist: Optional[str] = None, **kwargs) -> bool:
        """
        Validate common search parameters.
        
        Args:
            artist: Artist name (required)
            **kwargs: Additional parameters
            
        Returns:
            True if valid, False otherwise
        """
        if not artist or not artist.strip():
            self.display_manager.console.print("[bold red]✗[/bold red] Artist is required")
            return False
        return True
    
    def _normalize_search_string(self, text: Optional[str]) -> str:
        """
        Normalize search string.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized string
        """
        if not text:
            return ""
        return normalize_string(text)
    
    def _handle_no_results(self, search_type: str = "results") -> None:
        """
        Handle no results scenario consistently.
        
        Args:
            search_type: Type of search (for error message)
        """
        self.display_manager.console.print(
            f"[bold red]✗[/bold red] {ERROR_MESSAGES['NO_RESULTS']}"
        )
    
    def _handle_validation_error(self, error: ValidationError) -> None:
        """
        Handle validation errors consistently.
        
        Args:
            error: Validation error to handle
        """
        self.display_manager.console.print(f"[bold red]✗[/bold red] {error.message}")
        if error.details:
            for key, value in error.details.items():
                if key != "errors":  # Skip nested errors list
                    self.display_manager.console.print(f"  [dim]{key}: {value}[/dim]")

