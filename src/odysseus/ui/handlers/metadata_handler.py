"""
Handler for applying metadata to existing files.
"""

from pathlib import Path
from typing import Optional, List
from rich.prompt import Prompt, Confirm
from rich.table import Table

from ...services.search_service import SearchService
from ...services.download_service import DownloadService
from ...services.metadata_service import MetadataService
from ...ui.display import DisplayManager
from ...ui.handlers.base_handler import BaseHandler
from ...models.song import SongData
from ...models.releases import ReleaseInfo, Track
from ...models.search_results import MusicBrainzSong


class MetadataHandler(BaseHandler):
    """Handler for applying metadata to existing files."""
    
    def handle(
        self,
        file_path: str,
        album: Optional[str] = None,
        artist: Optional[str] = None,
        year: Optional[int] = None,
        mbid: Optional[str] = None
    ):
        """Apply metadata to existing file(s).
        
        Args:
            file_path: Path to file or directory
            album: Album name (optional, will try to extract from filename)
            artist: Artist name (optional, will try to extract from filename)
            year: Release year (optional)
            mbid: MusicBrainz release ID (optional, if provided will skip search)
        """
        console = self.display_manager.console
        path = Path(file_path)
        
        if not path.exists():
            console.print(f"[bold red]✗[/bold red] Path does not exist: {file_path}")
            return
        
        # Collect audio files
        audio_files = []
        if path.is_file():
            if self._is_audio_file(path):
                audio_files = [path]
            else:
                console.print(f"[bold red]✗[/bold red] Not an audio file: {file_path}")
                return
        elif path.is_dir():
            audio_files = self._find_audio_files(path)
            if not audio_files:
                console.print(f"[yellow]⚠[/yellow] No audio files found in directory: {file_path}")
                return
        
        console.print(f"[cyan]Found {len(audio_files)} audio file(s)[/cyan]")
        
        # If MBID is provided, use it directly
        if mbid:
            release_info = self.display_manager.show_loading_spinner(
                "Fetching release information",
                self.search_service.get_release_info,
                mbid
            )
            if not release_info:
                console.print(f"[bold red]✗[/bold red] Failed to get release information for MBID: {mbid}")
                return
            
            self._apply_metadata_to_files(audio_files, release_info, console)
            return
        
        # Try to extract metadata from first file if not provided
        if not artist or not album:
            extracted = self._extract_metadata_from_path(audio_files[0])
            if not artist:
                artist = extracted.get('artist')
            if not album:
                album = extracted.get('album')
        
        if not artist or not album:
            console.print("[yellow]⚠[/yellow] Need at least artist and album to search for metadata.")
            console.print("Please provide --artist and --album, or ensure files are in Artist/Album/ format")
            return
        
        # Search for release
        console.print()
        console.print(self.display_manager._create_header_panel(
            "🔍 SEARCHING FOR RELEASE",
            f"Album: {album} by {artist}"
        ))
        console.print()
        
        song_data = SongData(
            title="",  # Not needed for release search
            artist=artist,
            album=album,
            release_year=year
        )
        
        releases = self.display_manager.show_loading_spinner(
            f"Searching for: {album} by {artist}",
            self.search_service.search_release,
            song_data
        )
        
        if not releases:
            console.print("[bold red]✗[/bold red] No releases found.")
            return
        
        # Let user select release
        selected_release = self._select_release(releases, console)
        if not selected_release:
            return
        
        # Get detailed release info
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
        
        # Store source info for cover art checking
        # Check if this is a MusicBrainz release (needed for cover art)
        is_musicbrainz = source == 'musicbrainz' or 'musicbrainz.org' in release_info.url
        if not is_musicbrainz:
            console.print(f"[yellow]⚠[/yellow] Release is from {source}. Cover art may not be available (requires MusicBrainz MBID).")
        
        # Apply metadata to files
        self._apply_metadata_to_files(audio_files, release_info, console, is_musicbrainz)
    
    def _is_audio_file(self, path: Path) -> bool:
        """Check if file is an audio file."""
        audio_extensions = {'.mp3', '.m4a', '.ogg', '.opus', '.flac', '.wav', '.aac', '.webm', '.mp4'}
        return path.suffix.lower() in audio_extensions
    
    def _find_audio_files(self, directory: Path) -> List[Path]:
        """Find all audio files in directory (recursively)."""
        audio_files = []
        audio_extensions = {'.mp3', '.m4a', '.ogg', '.opus', '.flac', '.wav', '.aac', '.webm', '.mp4'}
        
        for ext in audio_extensions:
            audio_files.extend(directory.rglob(f'*{ext}'))
        
        return sorted(audio_files)
    
    def _extract_metadata_from_path(self, file_path: Path) -> dict:
        """Try to extract artist and album from file path.
        
        Expected structure: Artist/Album/Track.mp3 or Artist/Album (Year)/Track.mp3
        """
        parts = file_path.parts
        metadata = {}
        
        # Try to find artist and album in path
        # Look for pattern: .../Artist/Album/... or .../Artist/Album (Year)/...
        if len(parts) >= 2:
            # Assume last part is filename, second to last might be album, third to last might be artist
            if len(parts) >= 3:
                metadata['artist'] = parts[-3]
                album_part = parts[-2]
                # Remove year from album name if present: "Album (Year)" -> "Album"
                if '(' in album_part and ')' in album_part:
                    album_part = album_part.split('(')[0].strip()
                metadata['album'] = album_part
            elif len(parts) >= 2:
                metadata['album'] = parts[-2]
        
        return metadata
    
    def _select_release(self, releases: List[MusicBrainzSong], console) -> Optional[MusicBrainzSong]:
        """Let user select a release from search results."""
        table = Table(title="Search Results", show_header=True, header_style="bold magenta")
        table.add_column("#", style="cyan", width=4)
        table.add_column("Album", style="white")
        table.add_column("Artist", style="yellow")
        table.add_column("Year", style="green", width=6)
        table.add_column("Type", style="blue", width=12)
        
        for i, release in enumerate(releases[:10], 1):  # Show max 10 results
            year = release.release_date[:4] if release.release_date and len(release.release_date) >= 4 else "N/A"
            release_type = release.release_type or "N/A"
            table.add_row(
                str(i),
                release.album or "N/A",
                release.artist or "N/A",
                year,
                release_type
            )
        
        console.print()
        console.print(table)
        console.print()
        
        while True:
            try:
                choice = Prompt.ask(
                    f"[cyan]Select release (1-{min(len(releases), 10)})[/cyan]",
                    default="1"
                )
                choice_num = int(choice)
                if 1 <= choice_num <= min(len(releases), 10):
                    return releases[choice_num - 1]
                else:
                    console.print(f"[yellow]⚠[/yellow] Please enter a number between 1 and {min(len(releases), 10)}")
            except ValueError:
                console.print("[yellow]⚠[/yellow] Please enter a valid number")
            except KeyboardInterrupt:
                return None
    
    def _apply_metadata_to_files(
        self,
        audio_files: List[Path],
        release_info: ReleaseInfo,
        console,
        is_musicbrainz: bool = True
    ):
        """Apply metadata to list of files."""
        console.print()
        console.print(self.display_manager._create_header_panel(
            "📝 APPLYING METADATA",
            f"Release: {release_info.title} by {release_info.artist}"
        ))
        console.print()
        
        # Check MBID availability for cover art
        if not is_musicbrainz or not release_info.mbid or not release_info.mbid.strip():
            if not is_musicbrainz:
                console.print(f"[yellow]⚠[/yellow] Release is not from MusicBrainz. Cover art will not be available.")
            elif not release_info.mbid or not release_info.mbid.strip():
                console.print(f"[yellow]⚠[/yellow] No MBID available for this release. Cover art will not be available.")
        else:
            console.print(f"[blue]ℹ[/blue] MBID: {release_info.mbid} (cover art will be fetched)")
        
        console.print()
        
        # Create progress bar
        progress = self.display_manager.create_progress_bar(
            len(audio_files),
            "Applying metadata"
        )
        
        success_count = 0
        failed_count = 0
        
        with progress:
            task = progress.add_task("[cyan]Applying metadata...", total=len(audio_files))
            
            for file_path in audio_files:
                # Try to match file to track
                track = self._match_file_to_track(file_path, release_info)
                
                if track:
                    try:
                        self.metadata_service.apply_metadata_with_cover_art(
                            file_path, track, release_info, console
                        )
                        success_count += 1
                    except Exception as e:
                        console.print(f"[yellow]⚠[/yellow] Failed to apply metadata to {file_path.name}: {e}")
                        failed_count += 1
                else:
                    # If we can't match to a track, still try to apply basic metadata
                    console.print(f"[yellow]⚠[/yellow] Could not match {file_path.name} to a track. Applying basic metadata...")
                    try:
                        # Create a dummy track with basic info
                        from ...models.releases import Track
                        dummy_track = Track(
                            position=0,
                            title=file_path.stem,
                            artist=release_info.artist
                        )
                        self.metadata_service.apply_metadata_with_cover_art(
                            file_path, dummy_track, release_info, console
                        )
                        success_count += 1
                    except Exception as e:
                        console.print(f"[yellow]⚠[/yellow] Failed to apply metadata to {file_path.name}: {e}")
                        failed_count += 1
                
                progress.update(task, advance=1)
        
        console.print()
        console.print(f"[bold green]✓[/bold green] Successfully applied metadata to {success_count} file(s)")
        if failed_count > 0:
            console.print(f"[bold red]✗[/bold red] Failed to apply metadata to {failed_count} file(s)")
    
    def _match_file_to_track(self, file_path: Path, release_info: ReleaseInfo) -> Optional[Track]:
        """Try to match a file to a track in the release.
        
        Looks for track number in filename (e.g., "01 - Track Name.mp3" or "Track Name.mp3")
        """
        filename = file_path.stem  # filename without extension
        
        # Try to extract track number from filename
        # Patterns: "01 - Track Name", "1. Track Name", "Track Name"
        track_number = None
        
        # Pattern 1: "01 - Track Name" or "1 - Track Name"
        if ' - ' in filename:
            parts = filename.split(' - ', 1)
            try:
                track_number = int(parts[0].strip())
            except ValueError:
                pass
        
        # Pattern 2: "1. Track Name"
        if track_number is None and '. ' in filename:
            parts = filename.split('. ', 1)
            try:
                track_number = int(parts[0].strip())
            except ValueError:
                pass
        
        # Pattern 3: Just a number at the start
        if track_number is None:
            parts = filename.split(None, 1)
            if parts:
                try:
                    track_number = int(parts[0].strip())
                except ValueError:
                    pass
        
        # Find matching track
        if track_number:
            for track in release_info.tracks:
                if track.position == track_number:
                    return track
        
        # If no track number found, try to match by title
        # Remove track number prefix if present and try to match
        clean_filename = filename
        if ' - ' in filename:
            clean_filename = filename.split(' - ', 1)[1]
        elif '. ' in filename:
            clean_filename = filename.split('. ', 1)[1]
        
        # Try fuzzy matching on title
        from ...utils.string_utils import normalize_string
        normalized_filename = normalize_string(clean_filename)
        
        for track in release_info.tracks:
            normalized_title = normalize_string(track.title)
            if normalized_filename in normalized_title or normalized_title in normalized_filename:
                return track
        
        return None

