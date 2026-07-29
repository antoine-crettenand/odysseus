"""
Handler for Spotify playlist/album mode (parse Spotify URL and download tracks).
"""

from typing import Optional, List, Tuple
from rich.table import Table
from rich.prompt import Prompt
from .base_handler import BaseHandler
from .release_handler import ReleaseHandler
from ...clients.spotify import SpotifyClient
from ...ui.user_interaction import UserInteraction
from ...core.config import PROJECT_NAME, ERROR_MESSAGES
from ...utils.release_exporter import export_releases
from ..selection import parse_numeric_selection


class SpotifyHandler(BaseHandler):
    """Handler for Spotify URL parsing and track download mode."""

    def __init__(
        self,
        *args,
        spotify_client=None,
        release_handler=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.spotify_client = spotify_client or SpotifyClient()
        self.user_interaction = UserInteraction(self.display_manager)
        self.release_handler = release_handler or ReleaseHandler(
            self.search_service,
            self.download_service,
            self.metadata_service,
            self.display_manager,
            download_orchestrator=self.download_orchestrator,
        )

    def handle(
        self,
        url: str,
        mode: str = "recordings",
        quality: str = "audio",
        tracks: Optional[str] = None,
        no_download: bool = False,
        export_path: Optional[str] = None,
        export_format: str = "tsv",
        collection_type: str = "tracks",
    ):
        """Handle Spotify URL parsing and track download."""
        if mode == "releases":
            self._handle_releases_mode(
                url,
                quality,
                tracks,
                no_download,
                export_path,
                export_format,
                collection_type,
            )
        else:
            self._handle_recordings_mode(url, quality, tracks, no_download)

    def _handle_recordings_mode(
        self,
        url: str,
        quality: str = "audio",
        tracks: Optional[str] = None,
        no_download: bool = False,
        export_path: Optional[str] = None,
        export_format: str = "tsv",
        collection_type: str = "tracks",
    ):
        """Handle Spotify URL parsing and track download (recordings mode)."""
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

    def _handle_releases_mode(
        self,
        url: str,
        quality: str = "audio",
        tracks: Optional[str] = None,
        no_download: bool = False
    ):
        """Handle Spotify URL parsing and release selection (releases mode)."""
        console = self.display_manager.console
        console.print()
        console.print(self.display_manager._create_header_panel(
            f"💿 {PROJECT_NAME} - Spotify Releases",
            f"Extracting releases from Spotify URL: {url}"
        ))
        console.print()

        # Parse the Spotify URL
        parsed = self.spotify_client.parse_spotify_url(url)
        if not parsed:
            console.print(f"[bold red]✗[/bold red] Invalid Spotify URL: {url}")
            return

        if parsed["type"] not in {"playlist", "collection"}:
            console.print(f"[bold red]✗[/bold red] Releases mode supports playlist and collection URLs. Got: {parsed['type']}")
            console.print("[blue]ℹ[/blue] Use recordings mode (default) for album and track URLs.")
            return

        # Extract unique releases from playlist
        try:
            if parsed["type"] == "collection":
                import os

                access_token = os.getenv("SPOTIFY_USER_ACCESS_TOKEN")
                if not access_token:
                    raise ValueError(
                        "SPOTIFY_USER_ACCESS_TOKEN is required for collection URLs"
                    )
                releases = self.display_manager.show_loading_spinner(
                    "Extracting releases from Spotify collection...",
                    self.spotify_client.get_user_collection_releases,
                    access_token,
                    collection_type,
                )
            else:
                releases = self.display_manager.show_loading_spinner(
                    "Extracting unique releases from playlist...",
                    self.spotify_client.get_playlist_releases,
                    parsed["id"],
                )
        except Exception as e:
            error_msg = str(e)
            if "authentication required" in error_msg.lower():
                console.print(f"[bold red]✗[/bold red] Spotify API authentication required.")
                console.print("[yellow]⚠[/yellow] Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables.")
                console.print("[blue]ℹ[/blue] You can get these from: https://developer.spotify.com/dashboard")
                console.print("[blue]ℹ[/blue] Create an app and add the credentials as environment variables.")
            else:
                console.print(f"[bold red]✗[/bold red] Failed to extract releases: {error_msg}")
            return

        if not releases:
            console.print("[bold red]✗[/bold red] No releases found in the playlist.")
            return

        # Display the releases
        console.print()
        console.print(self.display_manager._create_header_panel(
            "📦 SPOTIFY RELEASES",
            f"Found {len(releases)} unique release{'s' if len(releases) != 1 else ''} in playlist"
        ))
        console.print()

        self._display_releases(releases)

        if export_path:
            exported = export_releases(releases, export_path, export_format)
            console.print(
                f"[bold green]✓[/bold green] Exported {exported} releases to "
                f"[cyan]{export_path}[/cyan]"
            )

        if no_download:
            console.print("[blue]ℹ[/blue] Release listing completed. Use without --no-download to download.")
            return

        # Get release selection from user
        selected_releases = self._get_release_selection(releases)

        if not selected_releases:
            console.print("[yellow]⚠[/yellow] No releases selected for download.")
            return

        # Download each selected release
        for idx, (artist, album, year) in enumerate(selected_releases, start=1):
            console.print()
            console.print(f"[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]")
            console.print(f"[bold]Processing [{idx}/{len(selected_releases)}]:[/bold] [yellow]{album}[/yellow] by [green]{artist}[/green]" + (f" ({year})" if year else ""))
            console.print(f"[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]")

            try:
                self.release_handler.handle(
                    album=album,
                    artist=artist,
                    year=year,
                    release_type=None,
                    quality=quality,
                    tracks=tracks,
                    no_download=no_download
                )
            except KeyboardInterrupt:
                console.print("\n[yellow]⚠[/yellow] Download cancelled by user.")
                break
            except Exception as e:
                console.print(f"[bold red]✗[/bold red] Failed to process {album} by {artist}: {e}")
                continue

    def _display_releases(self, releases: List[Tuple[str, str, Optional[int]]]):
        """Display releases in a table."""
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="cyan", width=4)
        table.add_column("Artist", style="green")
        table.add_column("Album", style="white")
        table.add_column("Year", style="yellow", width=6)

        for idx, (artist, album, year) in enumerate(releases, start=1):
            year_str = str(year) if year else "N/A"
            table.add_row(str(idx), artist, album, year_str)

        self.display_manager.console.print(table)
        self.display_manager.console.print()

    def _get_release_selection(self, releases: List[Tuple[str, str, Optional[int]]]) -> List[Tuple[str, str, Optional[int]]]:
        """Get user selection for releases to download."""
        console = self.display_manager.console

        while True:
            try:
                selection = Prompt.ask(
                    f"[cyan]Select releases to download (e.g., 1,3,5 or 1-5 or 'all')[/cyan]",
                    default="all"
                ).strip().lower()

                if selection == "all":
                    return releases

                selected_indices = self._parse_selection(selection, len(releases))
                if selected_indices:
                    return [releases[i - 1] for i in selected_indices]
                else:
                    console.print("[yellow]⚠[/yellow] Invalid selection. Please try again.")
            except KeyboardInterrupt:
                return []

    def _parse_selection(self, selection: str, max_num: int) -> List[int]:
        """Parse user selection string (e.g., '1,3,5' or '1-5')."""
        try:
            return parse_numeric_selection(selection, max_num)
        except ValueError:
            return []
