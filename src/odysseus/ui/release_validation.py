"""
Unified release validator for consistent release matching.
"""

from typing import Optional
from ..models.releases import ReleaseInfo
from ..models.search_results import MusicBrainzSong
from ..domain.music.identity import compare_release
from .display import DisplayManager
from rich.prompt import Confirm, Prompt


class ReleaseValidator:
    """
    Unified validator for release matching.

    This class validates that fetched release information matches expected release.
    """

    def __init__(self, display_manager: DisplayManager):
        self.display_manager = display_manager
        self.console = display_manager.console

    def validate_release_match(
        self,
        expected_release: MusicBrainzSong,
        fetched_release_info: ReleaseInfo,
        source: str = "musicbrainz",
        skip_on_mismatch: bool = False
    ) -> bool:
        """
        Validate that fetched release matches expected release.

        Args:
            expected_release: Expected release from search results
            fetched_release_info: Fetched release info from API
            source: Source of the fetched release (for error messages)
            skip_on_mismatch: If True, skip silently on mismatch; if False, prompt user for validation

        Returns:
            True if release matches or user confirms, False otherwise
        """
        match = compare_release(
            fetched_release_info,
            expected_album=expected_release.album or expected_release.title or "",
            expected_artist=expected_release.artist or "",
            expected_year=self.extract_release_year(expected_release.release_date),
            expected_type=expected_release.release_type,
        )

        if not match.accepted:
            if skip_on_mismatch:
                self.console.print(f"[bold yellow]⚠[/bold yellow] Warning: Fetched release doesn't match expected release!")
                self.console.print(f"  Expected: [yellow]{expected_release.album}[/yellow] by [green]{expected_release.artist}[/green]")
                self.console.print(f"  Fetched:  [yellow]{fetched_release_info.title}[/yellow] by [green]{fetched_release_info.artist}[/green]")
                self.console.print(f"  Release ID used: [cyan]{expected_release.mbid}[/cyan] (source: {source})")
                self.console.print(f"[yellow]⚠[/yellow] Skipping this release due to mismatch.")
            else:
                self.console.print(f"[bold yellow]⚠[/bold yellow] Warning: Fetched release doesn't match expected release!")
                self.console.print(f"  Expected: [yellow]{expected_release.album}[/yellow] by [green]{expected_release.artist}[/green]")
                self.console.print(f"  Fetched:  [yellow]{fetched_release_info.title}[/yellow] by [green]{fetched_release_info.artist}[/green]")
                self.console.print(f"  Release ID used: [cyan]{expected_release.mbid}[/cyan] (source: {source})")
                self.console.print()

                # Prompt user to validate the download
                self.console.print("[bold]Release mismatch detected. Please validate the download:[/bold]")

                # Ask user to confirm or correct the album title
                corrected_title = Prompt.ask(
                    f"[bold]Enter album title[/bold] (press Enter to use fetched: [cyan]{fetched_release_info.title}[/cyan])",
                    default=fetched_release_info.title or ""
                )

                # Update the fetched release info with user's input
                if corrected_title and corrected_title.strip():
                    fetched_release_info.title = corrected_title.strip()

                self.console.print(f"[green]✓[/green] Using album title: [cyan]{fetched_release_info.title}[/cyan]")

                # Confirm if user wants to proceed
                proceed = Confirm.ask(
                    f"[bold]Proceed with download of '{fetched_release_info.title}' by '{fetched_release_info.artist}'?[/bold]",
                    default=True
                )

                if not proceed:
                    self.console.print(f"[bold red]✗[/bold red] Download cancelled by user.")
                    return False

                self.console.print(f"[green]✓[/green] Proceeding with download...")
                self.console.print()
            return False if skip_on_mismatch else True

        return True

    def extract_release_year(self, release_date: Optional[str]) -> Optional[int]:
        """
        Extract year from release date string.

        Args:
            release_date: Release date string (e.g., "1964" or "2017-06-08")

        Returns:
            Year as integer or None if invalid
        """
        if not release_date:
            return None

        try:
            # Try to extract year from date string (e.g., "1964" or "2017-06-08")
            if isinstance(release_date, str):
                # Extract first 4 digits (year)
                year_str = release_date[:4]
                if year_str.isdigit():
                    return int(year_str)
            elif isinstance(release_date, int):
                return release_date
        except (ValueError, AttributeError):
            pass

        return None
