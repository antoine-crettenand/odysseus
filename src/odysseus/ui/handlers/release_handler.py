"""
Handler for release mode (album search and download).
"""

from typing import Optional, List
from .base_handler import BaseHandler
from ...models.song import SongData
from ...models.search_results import MusicBrainzSong
from ..release_info_flow import ReleaseInfoFetcher
from ...ui.user_interaction import UserInteraction
from ...core.config import PROJECT_NAME, ERROR_MESSAGES
from ...core.validation import validate_required_fields, validate_year_range
from ...core.exceptions import ValidationError
from ...models.outcomes import OperationOutcome
from ...domain.music.identity import select_best_release_match


class ReleaseHandler(BaseHandler):
    """Handler for release/album search and download mode."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_interaction = UserInteraction(self.display_manager)
        self.release_info_fetcher = ReleaseInfoFetcher(self.search_service, self.display_manager)

    def handle(
        self,
        album: str,
        artist: str,
        year: Optional[int] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        release_type: Optional[str] = None,
        quality: str = "audio",
        tracks: Optional[str] = None,
        no_download: bool = False,
        auto: bool = False,
        jobs: int = 1,
    ) -> OperationOutcome:
        """Handle release search and download."""
        # Validate input parameters
        try:
            validate_required_fields(album=album, artist=artist)
            validate_year_range(year, year_from, year_to)
        except (ValidationError, ValueError) as e:
            self._handle_validation_error(e)
            return OperationOutcome.failure(str(e), error=e)

        # Validate search params using base handler method
        if not self._validate_search_params(artist=artist):
            return OperationOutcome.failure("Artist is required")

        console = self.display_manager.console
        console.print()
        search_description = f"Searching for release: {album} by {artist}"
        if year is not None:
            search_description += f" (Year: {year})"
        elif year_from is not None or year_to is not None:
            lower = str(year_from) if year_from is not None else "earliest"
            upper = str(year_to) if year_to is not None else "latest"
            search_description += f" (Years: {lower}–{upper})"
        console.print(self.display_manager.create_header_panel(
            f"💿 {PROJECT_NAME} - Release Search",
            search_description,
        ))
        console.print()

        song_data = SongData(
            title="",  # No title for release search
            artist=artist,
            album=album,
            release_year=year
        )

        # Use unified search flow manager with auto-selection support
        auto_select_func = self._find_best_match if auto else None
        auto_select_args = {
            'expected_album': album,
            'expected_artist': artist,
            'expected_year': year,
            'expected_type': release_type
        } if auto else None

        selected_release = self.search_flow_manager.search_with_pagination(
            self.search_service.search_releases,
            f"Searching MusicBrainz releases: {song_data.album} by {song_data.artist}",
            "RELEASES",
            auto_select_func,
            auto_select_args,
            song_data,
            auto=auto,
            release_type=release_type,
            year_from=year_from,
            year_to=year_to,
        )

        if not selected_release:
            if auto:
                console.print("[bold red]✗[/bold red] No sufficiently close release match found.")
            return OperationOutcome.skipped("No release selected")

        # Check for year mismatch in auto mode
        if auto and year and selected_release.release_date:
            release_year = self.release_validator.extract_release_year(selected_release.release_date)
            if release_year and release_year != year:
                console.print(f"[yellow]⚠[/yellow] Year mismatch: requested {year}, found {release_year}")

        if no_download:
            console.print("[blue]ℹ[/blue] Search completed. Use without --no-download to download.")
            return OperationOutcome.success("Search completed")

        return self._search_and_download_release(
            selected_release,
            quality,
            tracks,
            auto,
            jobs,
        )

    def _search_and_download_release(
        self,
        selected_release: MusicBrainzSong,
        quality: str,
        tracks: Optional[str],
        auto: bool = False,
        jobs: int = 1,
    ) -> OperationOutcome:
        """Search and download tracks from a release."""
        console = self.display_manager.console
        console.print()
        console.print(self.display_manager.create_header_panel(
            "📥 RELEASE DOWNLOAD",
            f"Release: {selected_release.album} by {selected_release.artist}"
        ))
        console.print()

        # Use unified release info fetcher
        source = getattr(selected_release, 'source', 'musicbrainz')
        release_info = self.release_info_fetcher.fetch_release_info(
            selected_release,
            batch_progress=None,
            fallback_to_spotify=True
        )

        if not release_info:
            return OperationOutcome.failure("Failed to fetch release details")

        # Validate release match using unified validator
        if not self.release_validator.validate_release_match(
            selected_release,
            release_info,
            source=source,
            skip_on_mismatch=auto
        ):
            return OperationOutcome.skipped("Fetched release did not match the selection")

        self.display_manager.display_track_listing(release_info)

        track_numbers = self.user_interaction.parse_track_selection(
            tracks, len(release_info.tracks), auto=auto
        )

        if not track_numbers:
            if auto:
                console.print("[bold red]✗[/bold red] No tracks available for download.")
            else:
                console.print("[yellow]⚠[/yellow] No tracks selected for download.")
            return OperationOutcome.skipped("No tracks selected")

        processed, failed = self.download_orchestrator.download_release_tracks(
            release_info,
            track_numbers,
            quality,
            silent=False,
            jobs=jobs,
        )
        if failed:
            return OperationOutcome.failure(
                f"{failed} track(s) failed",
                processed=processed,
                failed=failed,
            )
        return OperationOutcome.success(
            "Release processed",
            processed=processed,
        )

    def _find_best_match(
        self,
        results: List[MusicBrainzSong],
        expected_album: str,
        expected_artist: str,
        expected_year: Optional[int] = None,
        expected_type: Optional[str] = None
    ) -> Optional[MusicBrainzSong]:
        """
        Find the best matching release from search results.

        Scoring:
        - Exact artist match: +10 points
        - Exact album match: +10 points
        - Year match (if specified): +5 points
        - Release type match (if specified): +3 points

        Returns the result with the highest score, or None if no results.
        """
        return select_best_release_match(
            results,
            expected_album=expected_album,
            expected_artist=expected_artist,
            expected_year=expected_year,
            expected_type=expected_type,
        )
