"""
Handler for release mode (album search and download).
"""

from typing import Optional, List
from .base_handler import BaseHandler
from ...models.song import SongData
from ...models.search_results import MusicBrainzSong
from ...domain.music.search.release_info_fetcher import ReleaseInfoFetcher
from ...ui.user_interaction import UserInteraction
from ...core.config import PROJECT_NAME, ERROR_MESSAGES
from ...utils.string_utils import normalize_string
from ...core.validation import validate_year, validate_required_fields
from ...core.exceptions import ValidationError


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
        release_type: Optional[str] = None,
        quality: str = "audio",
        tracks: Optional[str] = None,
        no_download: bool = False,
        auto: bool = False
    ):
        """Handle release search and download."""
        # Validate input parameters
        try:
            validate_required_fields(album=album, artist=artist)
            if year is not None:
                validate_year(year)
        except ValidationError as e:
            self._handle_validation_error(e)
            return
        
        # Validate search params using base handler method
        if not self._validate_search_params(artist=artist):
            return
        
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
            release_type=release_type
        )
        
        if not selected_release:
            if auto:
                console.print("[bold red]✗[/bold red] No results found.")
            return
        
        # Check for year mismatch in auto mode
        if auto and year and selected_release.release_date:
            release_year = self.release_validator.extract_release_year(selected_release.release_date)
            if release_year and release_year != year:
                console.print(f"[yellow]⚠[/yellow] Year mismatch: requested {year}, found {release_year}")
        
        if no_download:
            console.print("[blue]ℹ[/blue] Search completed. Use without --no-download to download.")
            return
        
        self._search_and_download_release(selected_release, quality, tracks, auto)
    
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
        
        # Use unified release info fetcher
        source = getattr(selected_release, 'source', 'musicbrainz')
        release_info = self.release_info_fetcher.fetch_release_info(
            selected_release,
            batch_progress=None,
            fallback_to_spotify=True
        )
        
        if not release_info:
            return
        
        # Validate release match using unified validator
        if not self.release_validator.validate_release_match(
            selected_release,
            release_info,
            source=source,
            skip_on_mismatch=False
        ):
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

