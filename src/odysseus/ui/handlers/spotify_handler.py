"""
Handler for Spotify playlist/album mode (parse Spotify URL and download tracks).
"""

from typing import Optional
from .base_handler import BaseHandler
from ...clients.spotify import SpotifyClient
from ...services.download_orchestrator import DownloadOrchestrator
from ...ui.user_interaction import UserInteraction
from ...core.config import PROJECT_NAME, ERROR_MESSAGES


class SpotifyHandler(BaseHandler):
    """Handler for Spotify URL parsing and track download mode."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spotify_client = SpotifyClient()
        self.download_orchestrator = DownloadOrchestrator(
            self.download_service,
            self.metadata_service,
            self.search_service,
            self.display_manager
        )
        self.user_interaction = UserInteraction(self.display_manager)
    
    def handle(
        self,
        url: str,
        quality: str = "audio",
        tracks: Optional[str] = None,
        no_download: bool = False
    ):
        """Handle Spotify URL parsing and track download."""
        console = self.display_manager.console
        console.print()
        console.print(self.display_manager._create_header_panel(
            f"🎵 {PROJECT_NAME} - Spotify Playlist/Album",
            f"Parsing Spotify URL: {url}"
        ))
        console.print()
        
        # Parse the Spotify URL and get tracks
        try:
            release_info = self.display_manager.show_loading_spinner(
                "Fetching tracks from Spotify...",
                self.spotify_client.get_tracks_from_url,
                url
            )
        except ValueError as e:
            console.print(f"[bold red]✗[/bold red] {str(e)}")
            return
        except Exception as e:
            error_msg = str(e)
            if "authentication required" in error_msg.lower():
                console.print(f"[bold red]✗[/bold red] Spotify API authentication required.")
                console.print("[yellow]⚠[/yellow] Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables.")
                console.print("[blue]ℹ[/blue] You can get these from: https://developer.spotify.com/dashboard")
                console.print("[blue]ℹ[/blue] Create an app and add the credentials as environment variables.")
            else:
                console.print(f"[bold red]✗[/bold red] Failed to parse Spotify URL: {error_msg}")
            return
        
        if not release_info:
            console.print(f"[bold red]✗[/bold red] {ERROR_MESSAGES['NO_RESULTS']}")
            return
        
        if not release_info.tracks:
            console.print("[bold red]✗[/bold red] No tracks found in the Spotify URL.")
            return
        
        # Display the tracks
        console.print()
        console.print(self.display_manager._create_header_panel(
            "📋 SPOTIFY TRACKS",
            f"{release_info.title} by {release_info.artist}"
        ))
        console.print()
        
        self.display_manager.display_track_listing(release_info)
        
        if no_download:
            console.print("[blue]ℹ[/blue] Track listing completed. Use without --no-download to download.")
            return
        
        # Get track selection from user
        track_numbers = self.user_interaction.parse_track_selection(
            tracks, len(release_info.tracks)
        )
        
        if not track_numbers:
            console.print("[yellow]⚠[/yellow] No tracks selected for download.")
            return
        
        # Download the selected tracks
        console.print()
        console.print(self.display_manager._create_header_panel(
            "📥 DOWNLOADING TRACKS",
            f"Downloading {len(track_numbers)} track{'s' if len(track_numbers) != 1 else ''} from Spotify playlist/album"
        ))
        console.print()
        
        self.download_orchestrator.download_release_tracks(
            release_info, track_numbers, quality, silent=False
        )

