"""
Handler for release mode (album search and download).
"""

from typing import Optional, List
from .base_handler import BaseHandler
from ...models.song import SongData
from ...models.search_results import MusicBrainzSong
from ...services.download_orchestrator import DownloadOrchestrator
from ...ui.user_interaction import UserInteraction
from ...core.config import PROJECT_NAME, ERROR_MESSAGES
from ...utils.string_utils import normalize_string


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
        no_download: bool = False,
        auto: bool = False
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
            
            if auto:
                # Automatically select the best matching result
                selected_release = self._find_best_match(results, album, artist, year, release_type)
                if selected_release:
                    console.print(f"[bold green]✓[/bold green] Auto-selected: [white]{selected_release.get_display_name()}[/white] by [green]{selected_release.artist}[/green]")
                    if year and selected_release.release_date:
                        release_year = selected_release.release_date[:4] if len(selected_release.release_date) >= 4 else None
                        if release_year and str(year) != release_year:
                            console.print(f"[yellow]⚠[/yellow] Year mismatch: requested {year}, found {release_year}")
                else:
                    # Fallback to first result if no good match found
                    selected_release = results[0] if results else None
                    if selected_release:
                        console.print(f"[yellow]⚠[/yellow] No perfect match found, using first result: [white]{selected_release.get_display_name()}[/white]")
            else:
                selected_release = self.display_manager.get_user_selection(results)
            
            if not auto and selected_release == 'RESHUFFLE':
                offset += len(results)
                console.print()
                continue
            elif not selected_release:
                if auto:
                    console.print("[bold red]✗[/bold red] No results found.")
                else:
                    console.print("[yellow]⚠[/yellow] No selection made. Exiting.")
                return
            
            if no_download:
                console.print("[blue]ℹ[/blue] Search completed. Use without --no-download to download.")
                return
            
            self._search_and_download_release(selected_release, quality, tracks, auto)
            break
    
    def _search_and_download_release(
        self,
        selected_release: MusicBrainzSong,
        quality: str,
        tracks: Optional[str],
        auto: bool = False
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
        
        # Fallback: If release_info.artist is empty, use the artist from selected_release
        # This handles cases where the API response doesn't include artist-credit data
        if not release_info.artist and selected_release.artist:
            release_info.artist = selected_release.artist
        
        # Validate that the fetched release matches what we expected
        # Normalize strings for comparison (case-insensitive, ignore whitespace)
        from ...utils.string_utils import normalize_string
        expected_album = normalize_string(selected_release.album or "")
        expected_artist = normalize_string(selected_release.artist or "")
        fetched_album = normalize_string(release_info.title or "")
        fetched_artist = normalize_string(release_info.artist or "")
        
        # Check if the fetched release matches the expected one
        if expected_album and fetched_album and expected_album != fetched_album:
            console.print(f"[bold yellow]⚠[/bold yellow] Warning: Fetched release doesn't match expected release!")
            console.print(f"  Expected: [yellow]{selected_release.album}[/yellow] by [green]{selected_release.artist}[/green]")
            console.print(f"  Fetched:  [yellow]{release_info.title}[/yellow] by [green]{release_info.artist}[/green]")
            console.print(f"  Release ID used: [cyan]{selected_release.mbid}[/cyan] (source: {source})")
            console.print(f"[bold red]✗[/bold red] Cannot proceed with download due to release mismatch.")
            return
        
        self.display_manager.display_track_listing(release_info)
        
        track_numbers = self.user_interaction.parse_track_selection(
            tracks, len(release_info.tracks), auto=auto
        )
        
        if not track_numbers:
            if auto:
                console.print("[bold red]✗[/bold red] No tracks available for download.")
            else:
                console.print("[yellow]⚠[/yellow] No tracks selected for download.")
            return
        
        self.download_orchestrator.download_release_tracks(
            release_info, track_numbers, quality, silent=False
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
        if not results:
            return None
        
        expected_album_norm = normalize_string(expected_album)
        expected_artist_norm = normalize_string(expected_artist)
        
        best_match = None
        best_score = -1
        
        for result in results:
            score = 0
            
            # Check artist match
            result_artist_norm = normalize_string(result.artist or "")
            if result_artist_norm == expected_artist_norm:
                score += 10
            elif expected_artist_norm in result_artist_norm or result_artist_norm in expected_artist_norm:
                # Partial match (e.g., "The Beatles" vs "Beatles")
                score += 5
            
            # Check album match
            result_album_norm = normalize_string(result.album or result.title or "")
            if result_album_norm == expected_album_norm:
                score += 10
            elif expected_album_norm in result_album_norm or result_album_norm in expected_album_norm:
                # Partial match
                score += 5
            
            # Check year match (if year was specified)
            if expected_year and result.release_date:
                release_year_str = result.release_date[:4] if len(result.release_date) >= 4 else None
                if release_year_str:
                    try:
                        release_year = int(release_year_str)
                        if release_year == expected_year:
                            score += 5
                        elif abs(release_year - expected_year) <= 1:
                            # Within 1 year (handles re-releases)
                            score += 2
                    except ValueError:
                        pass
            
            # Check release type match (if type was specified)
            if expected_type and result.release_type:
                if result.release_type.lower() == expected_type.lower():
                    score += 3
            
            # Prefer results with higher scores
            if score > best_score:
                best_score = score
                best_match = result
        
        # Only return if we found a reasonable match (at least artist or album match)
        if best_score >= 5:
            return best_match
        
        # Fallback to first result if no good match
        return results[0] if results else None

