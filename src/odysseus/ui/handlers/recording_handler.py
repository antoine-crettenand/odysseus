"""
Handler for recording mode (single song search and download).
"""

from typing import Optional
from .base_handler import BaseHandler
from ...models.song import SongData
from ...models.search_results import MusicBrainzSong
from ...core.config import PROJECT_NAME, ERROR_MESSAGES, YOUTUBE_CONFIG
from ...core.validation import validate_year, validate_required_fields
from ...core.exceptions import ValidationError
from ...models.outcomes import OperationOutcome


class RecordingHandler(BaseHandler):
    """Handler for recording search and download mode."""

    def handle(
        self,
        title: str,
        artist: str,
        album: Optional[str] = None,
        year: Optional[int] = None,
        quality: str = "audio",
        no_download: bool = False
    ) -> OperationOutcome:
        """Handle recording search and download."""
        # Validate input parameters
        try:
            validate_required_fields(title=title, artist=artist)
            if year is not None:
                validate_year(year)
        except (ValidationError, ValueError) as e:
            self._handle_validation_error(e)
            return OperationOutcome.failure(str(e), error=e)

        # Validate search params using base handler method
        if not self._validate_search_params(artist=artist):
            return OperationOutcome.failure("Artist is required")

        console = self.display_manager.console
        console.print()
        console.print(self.display_manager.create_header_panel(
            f"🎵 {PROJECT_NAME} - Recording Search",
            f"Searching for: {title} by {artist}"
        ))
        console.print()

        song_data = SongData(
            title=title,
            artist=artist,
            album=album,
            release_year=year
        )

        # Use unified search flow manager
        selected_song = self.search_flow_manager.search_with_pagination(
            self.search_service.search_recordings,
            f"Searching MusicBrainz for: {song_data.title} by {song_data.artist}",
            "RECORDINGS",
            None,  # auto_select_func
            None,  # auto_select_args
            song_data  # Goes into *search_args
        )

        if not selected_song:
            return OperationOutcome.skipped("No recording selected")

        if no_download:
            console.print("[blue]ℹ[/blue] Search completed. Use without --no-download to download.")
            return OperationOutcome.success("Search completed")

        return self._search_and_download_recording(selected_song, quality)

    def _search_and_download_recording(
        self,
        selected_song: MusicBrainzSong,
        quality: str,
    ) -> OperationOutcome:
        """Search YouTube and download a recording."""
        console = self.display_manager.console
        search_query = f"{selected_song.artist} {selected_song.title}"

        console.print()
        console.print(self.display_manager.create_header_panel(
            "🔍 SEARCHING YOUTUBE",
            f"Search query: {search_query}"
        ))
        console.print()

        try:
            offset = 0
            while True:
                videos = self.display_manager.show_loading_spinner(
                    f"Searching YouTube for: {search_query}",
                    self.search_service.search_youtube,
                    search_query,
                    YOUTUBE_CONFIG["MAX_RESULTS"],
                    offset,
                )

                if not videos:
                    if offset == 0:
                        console.print(f"[bold red]✗[/bold red] {ERROR_MESSAGES['NO_RESULTS']}")
                        return OperationOutcome.failure("No YouTube results")
                    console.print(
                        "[yellow]⚠[/yellow] No more YouTube results. Starting from the beginning..."
                    )
                    offset = 0
                    continue

                self.display_manager.display_youtube_results(videos)

                selected_video = self.display_manager.get_video_selection(videos)

                if selected_video == 'RESHUFFLE':
                    offset += len(videos)
                    console.print("[blue]ℹ[/blue] Searching again for different results...")
                    console.print()
                    continue
                elif not selected_video:
                    console.print("[yellow]⚠[/yellow] No video selected for download.")
                    return OperationOutcome.skipped("No video selected")

                break

            # Extract year from release_date using unified validator
            release_year = self.release_validator.extract_release_year(selected_song.release_date)

            song_data = SongData(
                title=selected_song.title,
                artist=selected_song.artist,
                album=selected_song.album,
                release_year=release_year
            )

            downloaded_path = self.download_orchestrator.download_recording(
                song_data, selected_video, selected_song, quality
            )
            if downloaded_path:
                return OperationOutcome.success(
                    "Recording downloaded",
                    processed=1,
                )
            return OperationOutcome.failure(
                "Recording download failed",
                failed=1,
            )

        except Exception as e:
            console.print(f"[bold red]✗[/bold red] Error searching YouTube: {e}")
            return OperationOutcome.failure(str(e), failed=1, error=e)
