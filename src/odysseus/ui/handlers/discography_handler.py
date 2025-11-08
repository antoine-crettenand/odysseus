"""
Handler for discography mode (artist discography browse and download).
"""

from typing import Optional, List
from .base_handler import BaseHandler
from ...models.search_results import MusicBrainzSong
from ...services.download_orchestrator import DownloadOrchestrator
from ...ui.user_interaction import UserInteraction
from ...core.config import PROJECT_NAME, ERROR_MESSAGES
from rich.prompt import Prompt, Confirm


class DiscographyHandler(BaseHandler):
    """Handler for discography browse and download mode."""
    
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
        artist: str,
        year: Optional[int] = None,
        release_type: Optional[str] = None,
        quality: str = "audio",
        no_download: bool = False
    ):
        """Handle discography browse and download."""
        console = self.display_manager.console
        console.print()
        subtitle = f"Searching discography for: {artist}"
        if year:
            subtitle += f" (Year: {year})"
        if release_type:
            subtitle += f" (Type: {release_type})"
        console.print(self.display_manager._create_header_panel(
            f"📚 {PROJECT_NAME} - Discography Browse",
            subtitle
        ))
        console.print()
        
        releases = self.display_manager.show_loading_spinner(
            f"Searching discography for: {artist}",
            self.search_service.search_artist_releases,
            artist,
            year=year,
            release_type=release_type
        )
        
        if not releases:
            console.print(f"[bold red]✗[/bold red] {ERROR_MESSAGES['NO_RESULTS']}")
            return
        
        ordered_releases = self.display_manager.display_discography(releases)
        
        if no_download:
            console.print("[blue]ℹ[/blue] Discography browse completed. Use without --no-download to download releases.")
            return
        
        selected_releases, auto_download_all_tracks = self.display_manager.get_release_selection(
            ordered_releases, quality, self.search_service
        )
        
        if not selected_releases:
            console.print("[yellow]⚠[/yellow] No releases selected for download.")
            return
        
        self._download_selected_releases(
            selected_releases, quality, auto_download_all_tracks=auto_download_all_tracks
        )
    
    def _download_selected_releases(
        self,
        releases: List[MusicBrainzSong],
        quality: str,
        auto_download_all_tracks: bool = False
    ):
        """
        Download selected releases.
        
        Args:
            releases: List of releases to download
            quality: Download quality
            auto_download_all_tracks: If True, automatically download all tracks from all releases
                                     without prompting for each release
        """
        console = self.display_manager.console
        total_downloaded = 0
        total_failed = 0
        
        for i, release in enumerate(releases, 1):
            console.print()
            console.print(self.display_manager._create_header_panel(
                "📥 RELEASE DOWNLOAD",
                f"Release {i}/{len(releases)}: {release.album} by {release.artist}"
            ))
            console.print()
            
            source = getattr(release, 'source', 'musicbrainz')
            release_info = self.display_manager.show_loading_spinner(
                f"Fetching release details for: {release.album}",
                self.search_service.get_release_info,
                release.mbid,
                batch_progress=(i, len(releases)),
                source=source
            )
            if not release_info:
                console.print(f"[bold red]✗[/bold red] Failed to get release details for: [yellow]{release.album}[/yellow]")
                total_failed += 1
                continue
            
            self.display_manager.display_track_listing(release_info)
            
            if auto_download_all_tracks:
                console.print(f"[cyan]Auto-downloading all {len(release_info.tracks)} track{'s' if len(release_info.tracks) != 1 else ''}...[/cyan]")
                console.print()
                track_numbers = list(range(1, len(release_info.tracks) + 1))
                downloaded, failed = self.download_orchestrator.download_release_tracks(
                    release_info, track_numbers, quality, silent=False
                )
                total_downloaded += downloaded
                total_failed += failed
            else:
                self.display_manager.display_download_options()
                
                while True:
                    choice = Prompt.ask("[bold]Choose option[/bold]", choices=["1", "2", "3"], default="3")
                    
                    if choice == '1':
                        console.print()
                        track_numbers = list(range(1, len(release_info.tracks) + 1))
                        downloaded, failed = self.download_orchestrator.download_release_tracks(
                            release_info, track_numbers, quality, silent=False
                        )
                        total_downloaded += downloaded
                        total_failed += failed
                        break
                    elif choice == '2':
                        console.print()
                        track_numbers = self.user_interaction.parse_track_selection(
                            None, len(release_info.tracks)
                        )
                        if track_numbers:
                            downloaded, failed = self.download_orchestrator.download_release_tracks(
                                release_info, track_numbers, quality, silent=False
                            )
                            total_downloaded += downloaded
                            total_failed += failed
                        break
                    elif choice == '3':
                        console.print(f"[yellow]⚠[/yellow] Skipped: [yellow]{release.album}[/yellow]")
                        break
        
        console.print()
        self.display_manager.display_download_summary(total_downloaded, total_failed, len(releases))

