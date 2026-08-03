"""
Unified release info fetcher with Spotify fallback logic.
"""

from typing import Optional, Tuple
from ..models.releases import ReleaseInfo
from ..models.search_results import MusicBrainzSong
from ..models.song import SongData
from ..domain.music.common.date_utils import get_original_release_year
from ..domain.music.search.search_service import SearchService
from .display import DisplayManager
from ..domain.music.identity import select_best_release_match


class ReleaseInfoFetcher:
    """
    Unified fetcher for release information with Spotify fallback.

    This class handles:
    1. Fetching release info from primary source
    2. Falling back to Spotify if primary source fails
    3. Normalizing artist information
    """

    def __init__(self, search_service: SearchService, display_manager: DisplayManager):
        self.search_service = search_service
        self.display_manager = display_manager
        self.console = display_manager.console

    def fetch_release_info(
        self,
        release: MusicBrainzSong,
        batch_progress: Optional[Tuple[int, int]] = None,
        fallback_to_spotify: bool = True
    ) -> Optional[ReleaseInfo]:
        """
        Fetch release information with Spotify fallback.

        Args:
            release: Release to fetch info for
            batch_progress: Optional tuple (current, total) for batch operations
            fallback_to_spotify: Whether to try Spotify fallback if primary source fails

        Returns:
            ReleaseInfo object or None if failed
        """
        source = getattr(release, 'source', 'musicbrainz')

        # Try primary source first
        release_info = self.display_manager.show_loading_spinner(
            f"Fetching release details for: {release.album}",
            self.search_service.get_release_info,
            release.mbid,
            batch_progress=batch_progress,
            source=source
        )

        # Try Spotify fallback if primary source failed
        if not release_info and fallback_to_spotify and source != "spotify":
            release_info = self._try_spotify_fallback(release, batch_progress)

        if not release_info:
            if batch_progress:
                self.console.print(f"[{batch_progress[0]}/{batch_progress[1]}] [bold red]✗[/bold red] Failed to get release details for: [yellow]{release.album}[/yellow]")
            else:
                self.console.print("[bold red]✗[/bold red] Failed to get release details.")
            return None

        # Normalize artist information
        self._normalize_artist_info(release_info, release)

        return release_info

    def _try_spotify_fallback(
        self,
        release: MusicBrainzSong,
        batch_progress: Optional[Tuple[int, int]] = None
    ) -> Optional[ReleaseInfo]:
        """
        Try to fetch release info from Spotify as fallback.

        Args:
            release: Release to fetch info for
            batch_progress: Optional tuple (current, total) for batch operations

        Returns:
            ReleaseInfo object or None if failed
        """
        spotify_client = self.search_service._get_spotify_client()
        if not spotify_client or not spotify_client.is_authenticated():
            return None

        progress_prefix = f"[{batch_progress[0]}/{batch_progress[1]}] " if batch_progress else ""
        self.console.print(f"{progress_prefix}[yellow]⚠[/yellow] Primary source failed, trying Spotify fallback...")

        try:
            release_year = get_original_release_year(release)

            # Create SongData for Spotify search
            song_data = SongData(
                title="",
                artist=release.artist or "",
                album=release.album or "",
                release_year=release_year
            )

            # Search Spotify for the release
            spotify_results = spotify_client.search_release(
                album=song_data.album or "",
                artist=song_data.artist or "",
                release_year=song_data.release_year,
                limit=5
            )

            if spotify_results:
                match = select_best_release_match(
                    spotify_results,
                    expected_album=song_data.album or "",
                    expected_artist=song_data.artist or "",
                    expected_year=song_data.release_year,
                )
                spotify_id = match.get("spotify_id") if match else None
                if spotify_id:
                    release_info = spotify_client.get_album_tracks(spotify_id)
                    if release_info:
                        progress_prefix = f"[{batch_progress[0]}/{batch_progress[1]}] " if batch_progress else ""
                        self.console.print(f"{progress_prefix}[bold green]✓[/bold green] Found release on Spotify!")
                        return release_info
        except Exception as e:
            progress_prefix = f"[{batch_progress[0]}/{batch_progress[1]}] " if batch_progress else ""
            self.console.print(f"{progress_prefix}[dim]Spotify fallback failed: {e}[/dim]")

        return None

    def _normalize_artist_info(self, release_info: ReleaseInfo, release: MusicBrainzSong) -> None:
        """
        Normalize artist information in release_info.

        If release_info.artist is empty, use the artist from release.
        This handles cases where the API response doesn't include artist-credit data.

        Args:
            release_info: ReleaseInfo to normalize
            release: Original release object with artist information
        """
        if not release_info.artist and release.artist:
            release_info.artist = release.artist
        if not release_info.release_date:
            release_info.release_date = release.release_date
        if not release_info.original_release_date:
            release_info.original_release_date = release.original_release_date
