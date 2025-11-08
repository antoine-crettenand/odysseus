"""
Handler for release mode (album search and download).
"""

from typing import Optional
from .base_handler import BaseHandler
from ...models.song import SongData
from ...models.search_results import MusicBrainzSong
from ...services.download_orchestrator import DownloadOrchestrator
from ...ui.user_interaction import UserInteraction
from ...core.config import PROJECT_NAME, ERROR_MESSAGES


class ReleaseHandler(BaseHandler):
    """Handler for release/album search and download mode."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.download_orchestrator = DownloadOrchestrator(
            self.download_service,
            self.metadata_service,
            self.search_service,
            self.display_manager
        )
        self.user_interaction = UserInteraction(self.display_manager)
    
    def handle(
        self,
        album: str,
        artist: str,
        year: Optional[int] = None,
        release_type: Optional[str] = None,
        quality: str = "audio",
        tracks: Optional[str] = None,
        no_download: bool = False
    ):
        """Handle release search and download."""
        console = self.display_manager.console
        console.print()
        console.print(self.display_manager._create_header_panel(
            f"💿 {PROJECT_NAME} - Release Search",
            f"Searching for release: {album} by {artist}"
        ))
        console.print()
        
        song_data = SongData(
            title="",  # No title for release search
            artist=artist,
            album=album,
            release_year=year
        )
        
        offset = 0
        while True:
            if offset > 0:
                console.print(f"[blue]ℹ[/blue] Showing results starting from position {offset + 1}")
            
            results = self.display_manager.show_loading_spinner(
                f"Searching MusicBrainz releases: {song_data.album} by {song_data.artist}",
                self.search_service.search_releases,
                song_data,
                offset=offset,
                release_type=release_type
            )
        
            if not results:
                if offset == 0:
                    console.print(f"[bold red]✗[/bold red] {ERROR_MESSAGES['NO_RESULTS']}")
                    return
                else:
                    console.print("[yellow]⚠[/yellow] No more results available. Starting from beginning...")
                    offset = 0
                    continue
            
            self.display_manager.display_search_results(results, "RELEASES")
            
            selected_release = self.display_manager.get_user_selection(results)
            
            if selected_release == 'RESHUFFLE':
                offset += len(results)
                console.print()
                continue
            elif not selected_release:
                console.print("[yellow]⚠[/yellow] No selection made. Exiting.")
                return
            
            if no_download:
                console.print("[blue]ℹ[/blue] Search completed. Use without --no-download to download.")
                return
            
            self._search_and_download_release(selected_release, quality, tracks)
            break
    
    def _search_and_download_release(
        self,
        selected_release: MusicBrainzSong,
        quality: str,
        tracks: Optional[str]
    ):
        """Search and download tracks from a release."""
        console = self.display_manager.console
        console.print()
        console.print(self.display_manager._create_header_panel(
            "📥 RELEASE DOWNLOAD",
            f"Release: {selected_release.album} by {selected_release.artist}"
        ))
        console.print()
        
        source = getattr(selected_release, 'source', 'musicbrainz')
        release_info = self.display_manager.show_loading_spinner(
            f"Fetching release details for: {selected_release.album}",
            self.search_service.get_release_info,
            selected_release.mbid,
            source=source
        )
        
        if not release_info:
            console.print("[bold red]✗[/bold red] Failed to get release details.")
            return
        
        self.display_manager.display_track_listing(release_info)
        
        track_numbers = self.user_interaction.parse_track_selection(
            tracks, len(release_info.tracks)
        )
        
        if not track_numbers:
            console.print("[yellow]⚠[/yellow] No tracks selected for download.")
            return
        
        self.download_orchestrator.download_release_tracks(
            release_info, track_numbers, quality, silent=False
        )

