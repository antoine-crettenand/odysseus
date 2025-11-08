"""
Handler for recording mode (single song search and download).
"""

from typing import Optional
from .base_handler import BaseHandler
from ...models.song import SongData
from ...models.search_results import MusicBrainzSong
from ...services.download_orchestrator import DownloadOrchestrator
from ...core.config import PROJECT_NAME, ERROR_MESSAGES, YOUTUBE_CONFIG


class RecordingHandler(BaseHandler):
    """Handler for recording search and download mode."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.download_orchestrator = DownloadOrchestrator(
            self.download_service,
            self.metadata_service,
            self.search_service,
            self.display_manager
        )
    
    def handle(
        self,
        title: str,
        artist: str,
        album: Optional[str] = None,
        year: Optional[int] = None,
        quality: str = "audio",
        no_download: bool = False
    ):
        """Handle recording search and download."""
        console = self.display_manager.console
        console.print()
        console.print(self.display_manager._create_header_panel(
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
        
        offset = 0
        while True:
            if offset > 0:
                console.print(f"[blue]ℹ[/blue] Showing results starting from position {offset + 1}")
            
            results = self.display_manager.show_loading_spinner(
                f"Searching MusicBrainz for: {song_data.title} by {song_data.artist}",
                self.search_service.search_recordings,
                song_data,
                offset=offset
            )
        
            if not results:
                if offset == 0:
                    console.print(f"[bold red]✗[/bold red] {ERROR_MESSAGES['NO_RESULTS']}")
                    return
                else:
                    console.print("[yellow]⚠[/yellow] No more results available. Starting from beginning...")
                    offset = 0
                    continue
            
            self.display_manager.display_search_results(results, "RECORDINGS")
            
            selected_song = self.display_manager.get_user_selection(results)
            
            if selected_song == 'RESHUFFLE':
                offset += len(results)
                console.print()
                continue
            elif not selected_song:
                console.print("[yellow]⚠[/yellow] No selection made. Exiting.")
                return
            
            if no_download:
                console.print("[blue]ℹ[/blue] Search completed. Use without --no-download to download.")
                return
            
            self._search_and_download_recording(selected_song, quality)
            break
    
    def _search_and_download_recording(self, selected_song: MusicBrainzSong, quality: str):
        """Search YouTube and download a recording."""
        console = self.display_manager.console
        search_query = f"{selected_song.artist} {selected_song.title}"
        
        console.print()
        console.print(self.display_manager._create_header_panel(
            "🔍 SEARCHING YOUTUBE",
            f"Search query: {search_query}"
        ))
        console.print()
        
        try:
            while True:
                videos = self.display_manager.show_loading_spinner(
                    f"Searching YouTube for: {search_query}",
                    self.search_service.search_youtube,
                    search_query,
                    YOUTUBE_CONFIG["MAX_RESULTS"]
                )
                
                if not videos:
                    console.print(f"[bold red]✗[/bold red] {ERROR_MESSAGES['NO_RESULTS']}")
                    return
                
                self.display_manager.display_youtube_results(videos)
                
                selected_video = self.display_manager.get_video_selection(videos)
                
                if selected_video == 'RESHUFFLE':
                    console.print("[blue]ℹ[/blue] Searching again for different results...")
                    console.print()
                    continue
                elif not selected_video:
                    console.print("[yellow]⚠[/yellow] No video selected for download.")
                    return
                
                break
            
            song_data = SongData(
                title=selected_song.title,
                artist=selected_song.artist,
                album=selected_song.album,
                release_year=selected_song.release_date
            )
            
            self.download_orchestrator.download_recording(
                song_data, selected_video, selected_song, quality
            )
            
        except Exception as e:
            console.print(f"[bold red]✗[/bold red] Error searching YouTube: {e}")

