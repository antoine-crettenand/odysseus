"""
Display management for Odysseus CLI with Rich components.
Modern, beautiful terminal interface with animations and colors.
"""

from typing import List, Optional, Any, Dict, Union, Tuple
from rich.console import Console

from ..models.search_results import SearchResult, MusicBrainzSong, YouTubeVideo
from ..models.releases import ReleaseInfo
from .formatters import DisplayFormatters
from .input_handlers import InputHandlers
from .progress_displays import ProgressDisplays
from .styling import Styling


class DisplayManager:
    """Manages display formatting for search results and other UI elements using Rich."""
    
    def __init__(self):
        self.console = Console()
        self.separator_length = 60
        
        # Initialize sub-modules
        self.formatters = DisplayFormatters(self.console)
        self.input_handlers = InputHandlers(self.console, self.formatters)
        self.progress_displays = ProgressDisplays(self.console)
        self.styling = Styling(self.console)
    
    # Delegate to formatters
    def _create_header_panel(self, title: str, subtitle: Optional[str] = None):
        """Create a styled header panel (backward compatibility)."""
        return self.formatters.create_header_panel(title, subtitle)
    
    def _format_score(self, score: int):
        """Format score with color (backward compatibility)."""
        return self.formatters.format_score(score)
    
    def display_search_results(self, results: List[SearchResult], search_type: str):
        """Display search results in a beautiful table."""
        self.formatters.display_search_results(results, search_type)
    
    def display_youtube_results(self, videos: List[YouTubeVideo]):
        """Display YouTube search results in a beautiful table."""
        self.formatters.display_youtube_results(videos)
    
    def display_track_listing(self, release_info: ReleaseInfo):
        """Display the track listing for a release in a beautiful format."""
        self.formatters.display_track_listing(release_info)
    
    def display_discography(self, releases: List[MusicBrainzSong]):
        """Display discography grouped by year with global numbering."""
        return self.formatters.display_discography(releases)
    
    def display_download_progress(self, current: int, total: int, release_name: str):
        """Display download progress for releases."""
        self.formatters.display_download_progress(current, total, release_name)
    
    def display_track_listing_simple(self, tracks: List[Any], release_name: str):
        """Display a simple track listing for download progress."""
        self.formatters.display_track_listing_simple(tracks, release_name)
    
    def display_download_options(self):
        """Display download options."""
        self.formatters.display_download_options()
    
    def display_download_summary(self, downloaded: int, failed: int, total: int):
        """Display final download summary."""
        self.formatters.display_download_summary(downloaded, failed, total)
    
    def display_track_download_progress(self, track_num: int, track_title: str):
        """Display individual track download progress."""
        self.formatters.display_track_download_progress(track_num, track_title)
    
    def display_track_download_result(self, track_title: str, success: bool, path: Optional[str] = None, file_existed: bool = False):
        """Display track download result."""
        self.formatters.display_track_download_result(track_title, success, path, file_existed)
    
    def display_download_strategy_attempt(self, strategy_num: int, total_strategies: int):
        """Display download strategy attempt."""
        self.formatters.display_download_strategy_attempt(strategy_num, total_strategies)
    
    def display_download_strategy_result(self, strategy_num: int, success: bool, error: Optional[str] = None):
        """Display download strategy result."""
        self.formatters.display_download_strategy_result(strategy_num, success, error)
    
    def display_download_info(self, url: str, quality: str, audio_only: bool, save_location: str, metadata: Optional[Dict[str, Any]] = None):
        """Display download information."""
        self.formatters.display_download_info(url, quality, audio_only, save_location, metadata)
    
    def _format_track_number(self, number: int) -> str:
        """Format track number with color (backward compatibility)."""
        return self.formatters.format_track_number(number)
    
    # Delegate to input handlers
    def get_user_selection(self, results: List[SearchResult], prompt: str = "Select a result", allow_reshuffle: bool = True) -> Union[Optional[SearchResult], str]:
        """Get user selection from search results."""
        return self.input_handlers.get_user_selection(results, prompt, allow_reshuffle)
    
    def get_video_selection(self, videos: List[YouTubeVideo], allow_reshuffle: bool = True) -> Union[Optional[YouTubeVideo], str]:
        """Get user selection from YouTube video results."""
        return self.input_handlers.get_video_selection(videos, allow_reshuffle)
    
    def get_release_selection(self, releases: List[MusicBrainzSong], quality: str = "audio", search_service=None) -> Tuple[List[MusicBrainzSong], bool]:
        """Get user selection for releases to download."""
        return self.input_handlers.get_release_selection(releases, quality, search_service)
    
    # Delegate to progress displays
    def show_loading_spinner(self, message: str, task_func, *args, **kwargs):
        """Show a loading spinner while executing a task."""
        return self.progress_displays.show_loading_spinner(message, task_func, *args, **kwargs)
    
    def create_progress_bar(self, total: int, description: str = "Processing"):
        """Create a progress bar for tracking downloads."""
        return self.progress_displays.create_progress_bar(total, description)
    
    def create_download_progress_bar(self, description: str = "Downloading", total: Optional[float] = None):
        """Create a progress bar specifically for file downloads."""
        return self.progress_displays.create_download_progress_bar(description, total)
