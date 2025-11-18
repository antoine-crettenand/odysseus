"""
Odysseus CLI Module
A comprehensive command-line interface for music discovery and downloading.
"""

import argparse
import sys
import csv
from pathlib import Path
from typing import List, Tuple, Optional

from rich.prompt import Confirm

from ..services.search_service import SearchService
from ..services.download_service import DownloadService
from ..services.metadata_service import MetadataService
from ..ui.display import DisplayManager
from ..ui.handlers import RecordingHandler, ReleaseHandler, DiscographyHandler, MetadataHandler, SpotifyHandler
from ..core.config import PROJECT_NAME, PROJECT_VERSION


class OdysseusCLI:
    """Main CLI class for Odysseus music discovery tool."""
    
    def __init__(self):
        """Initialize the CLI."""
        self.search_service = SearchService()
        self.download_service = DownloadService()
        self.metadata_service = MetadataService()
        self.display_manager = DisplayManager()
        
        self.recording_handler = RecordingHandler(
            self.search_service,
            self.download_service,
            self.metadata_service,
            self.display_manager
        )
        self.release_handler = ReleaseHandler(
            self.search_service,
            self.download_service,
            self.metadata_service,
            self.display_manager
        )
        self.discography_handler = DiscographyHandler(
            self.search_service,
            self.download_service,
            self.metadata_service,
            self.display_manager
        )
        self.metadata_handler = MetadataHandler(
            self.search_service,
            self.download_service,
            self.metadata_service,
            self.display_manager
        )
        self.spotify_handler = SpotifyHandler(
            self.search_service,
            self.download_service,
            self.metadata_service,
            self.display_manager
        )
    
    def create_parser(self) -> argparse.ArgumentParser:
        """Create the argument parser."""
        parser = argparse.ArgumentParser(
            prog=PROJECT_NAME,
            description=f"""{PROJECT_NAME} - Music Discovery Tool v{PROJECT_VERSION}

Available modes:
  recording    - Search and download a specific recording/song
  release      - Search and download tracks from a release/album
  discography  - Browse artist discography and download selected releases
  spotify      - Parse Spotify playlist/album URL and download selected tracks
  metadata     - Apply metadata and cover art to existing audio files""",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=            """
Examples:
  %(prog)s recording --title "Song Title" --artist "Artist Name"
  %(prog)s release --album "Album Name" --artist "Artist Name"
  %(prog)s release --batch playlist_artists_albums.txt
  %(prog)s discography --artist "Artist Name" --year 1970
  %(prog)s spotify --url "https://open.spotify.com/playlist/..."
  %(prog)s metadata /path/to/file.mp3 --album "Album Name" --artist "Artist Name"
  %(prog)s metadata /path/to/directory --album "Album Name" --artist "Artist Name"
            """
        )
        
        parser.add_argument(
            '--version', 
            action='version', 
            version=f'{PROJECT_NAME} {PROJECT_VERSION}'
        )
        
        subparsers = parser.add_subparsers(
            dest='mode',
            help='Available modes',
            required=True
        )
        
        recording_parser = subparsers.add_parser(
            'recording',
            help='Search and download a specific recording/song'
        )
        self._add_recording_args(recording_parser)
        
        release_parser = subparsers.add_parser(
            'release',
            help='Search and download tracks from a release/album (supports batch processing with --batch)'
        )
        self._add_release_args(release_parser)
        
        discography_parser = subparsers.add_parser(
            'discography',
            help='Browse artist discography and download selected releases'
        )
        self._add_discography_args(discography_parser)
        
        spotify_parser = subparsers.add_parser(
            'spotify',
            help='Parse Spotify playlist/album URL and download selected tracks'
        )
        self._add_spotify_args(spotify_parser)
        
        metadata_parser = subparsers.add_parser(
            'metadata',
            help='Apply metadata and cover art to existing audio files'
        )
        self._add_metadata_args(metadata_parser)
        
        return parser
    
    def _add_recording_args(self, parser: argparse.ArgumentParser):
        """Add arguments for recording mode."""
        parser.add_argument(
            '--title', '-t',
            required=True,
            help='Song title to search for'
        )
        parser.add_argument(
            '--artist', '-a',
            required=True,
            help='Artist name'
        )
        parser.add_argument(
            '--album', '-l',
            help='Album name (optional)'
        )
        parser.add_argument(
            '--year', '-y',
            type=int,
            help='Release year (optional)'
        )
        parser.add_argument(
            '--quality', '-q',
            choices=['best', 'audio', 'worst'],
            default='audio',
            help='Download quality (default: audio)'
        )
        parser.add_argument(
            '--no-download',
            action='store_true',
            help='Search only, do not download'
        )
    
    def _add_release_args(self, parser: argparse.ArgumentParser):
        """Add arguments for release mode."""
        parser.add_argument(
            '--album', '-l',
            help='Album/release name to search for (required unless --batch is used)'
        )
        parser.add_argument(
            '--artist', '-a',
            help='Artist name (required unless --batch is used)'
        )
        parser.add_argument(
            '--batch', '-b',
            help='Path to TSV/TXT file with Artist, Album, and optional Year columns for batch processing'
        )
        parser.add_argument(
            '--year', '-y',
            type=int,
            help='Release year (optional, ignored when using --batch)'
        )
        parser.add_argument(
            '--type', '-t',
            choices=['Album', 'Single', 'EP', 'Compilation', 'Live', 'Soundtrack', 'Spokenword', 'Interview', 'Audiobook', 'Other'],
            help='Filter by release type (e.g., Album, Single, EP, Compilation, Live, etc.)'
        )
        parser.add_argument(
            '--quality', '-q',
            choices=['best', 'audio', 'worst'],
            default='audio',
            help='Download quality (default: audio)'
        )
        parser.add_argument(
            '--tracks', '-k',
            help='Comma-separated list of track numbers to download (e.g., 1,3,5)'
        )
        parser.add_argument(
            '--no-download',
            action='store_true',
            help='Search only, do not download'
        )
        parser.add_argument(
            '--auto', '--yes',
            dest='auto',
            action='store_true',
            help='Automatically process without user interaction (select first result and all tracks). Useful for batch processing.'
        )
    
    def _add_discography_args(self, parser: argparse.ArgumentParser):
        """Add arguments for discography mode."""
        parser.add_argument(
            '--artist', '-a',
            required=True,
            help='Artist name to browse discography'
        )
        parser.add_argument(
            '--year', '-y',
            type=int,
            help='Filter releases by year'
        )
        parser.add_argument(
            '--type', '-t',
            choices=['Album', 'Single', 'EP', 'Compilation', 'Live', 'Soundtrack', 'Spokenword', 'Interview', 'Audiobook', 'Other'],
            help='Filter by release type (e.g., Album, Single, EP, Compilation, Live, etc.)'
        )
        parser.add_argument(
            '--include-compilations',
            action='store_true',
            help='Also include compilations where the artist appears as a track artist (not just as main artist)'
        )
        parser.add_argument(
            '--quality', '-q',
            choices=['best', 'audio', 'worst'],
            default='audio',
            help='Download quality (default: audio)'
        )
        parser.add_argument(
            '--no-download',
            action='store_true',
            help='Browse only, do not download'
        )
    
    def _add_spotify_args(self, parser: argparse.ArgumentParser):
        """Add arguments for Spotify mode."""
        parser.add_argument(
            '--url', '-u',
            required=True,
            help='Spotify playlist, album, or track URL'
        )
        parser.add_argument(
            '--quality', '-q',
            choices=['best', 'audio', 'worst'],
            default='audio',
            help='Download quality (default: audio)'
        )
        parser.add_argument(
            '--tracks', '-k',
            help='Comma-separated list of track numbers to download (e.g., 1,3,5)'
        )
        parser.add_argument(
            '--no-download',
            action='store_true',
            help='Parse URL only, do not download'
        )
    
    def _add_metadata_args(self, parser: argparse.ArgumentParser):
        """Add arguments for metadata mode."""
        parser.add_argument(
            'file',
            help='Path to audio file or directory containing audio files'
        )
        parser.add_argument(
            '--album', '-l',
            help='Album name (optional, will try to extract from path)'
        )
        parser.add_argument(
            '--artist', '-a',
            help='Artist name (optional, will try to extract from path)'
        )
        parser.add_argument(
            '--year', '-y',
            type=int,
            help='Release year (optional)'
        )
        parser.add_argument(
            '--mbid', '-m',
            help='MusicBrainz release ID (optional, if provided will skip search)'
        )
    
    def run(self, args: List[str] = None):
        """Run the CLI with given arguments."""
        parser = self.create_parser()
        parsed_args = parser.parse_args(args)
        
        try:
            if parsed_args.mode == 'recording':
                self.recording_handler.handle(
                    title=parsed_args.title,
                    artist=parsed_args.artist,
                    album=parsed_args.album,
                    year=parsed_args.year,
                    quality=parsed_args.quality,
                    no_download=parsed_args.no_download
                )
                # Exit after recording - no search info for another recording
                sys.exit(0)
            elif parsed_args.mode == 'release':
                # Handle batch processing
                if parsed_args.batch:
                    self._handle_batch_release(
                        batch_file=parsed_args.batch,
                        release_type=parsed_args.type,
                        quality=parsed_args.quality,
                        tracks=parsed_args.tracks,
                        no_download=parsed_args.no_download,
                        auto=getattr(parsed_args, 'auto', False)
                    )
                else:
                    # Validate required arguments for single release
                    if not parsed_args.album or not parsed_args.artist:
                        parser.error("--album and --artist are required unless --batch is used")
                    
                    self.release_handler.handle(
                        album=parsed_args.album,
                        artist=parsed_args.artist,
                        year=parsed_args.year,
                        release_type=parsed_args.type,
                        quality=parsed_args.quality,
                        tracks=parsed_args.tracks,
                        no_download=parsed_args.no_download,
                        auto=getattr(parsed_args, 'auto', False)
                    )
                # Exit after release - no search info for another release
                sys.exit(0)
            elif parsed_args.mode == 'discography':
                # Loop for discography - allow user to go back to discography display
                cached_releases = None
                while True:
                    releases = self.discography_handler.handle(
                        artist=parsed_args.artist,
                        year=parsed_args.year,
                        release_type=parsed_args.type,
                        quality=parsed_args.quality,
                        no_download=parsed_args.no_download,
                        cached_releases=cached_releases,
                        include_compilations=getattr(parsed_args, 'include_compilations', False)
                    )
                    
                    # If user cancelled, exit immediately without prompting
                    if releases is None:
                        break
                    
                    # Cache the releases for next iteration (if search was performed)
                    if cached_releases is None:
                        cached_releases = releases
                    
                    # Ask if user wants to go back to discography display
                    self.display_manager.console.print()
                    if not Confirm.ask("[bold]Go back to discography display?[/bold]", default=False):
                        break
                    self.display_manager.console.print()
            elif parsed_args.mode == 'spotify':
                self.spotify_handler.handle(
                    url=parsed_args.url,
                    quality=parsed_args.quality,
                    tracks=parsed_args.tracks,
                    no_download=parsed_args.no_download
                )
                # Exit after spotify - no search info for another spotify URL
                sys.exit(0)
            elif parsed_args.mode == 'metadata':
                self.metadata_handler.handle(
                    file_path=parsed_args.file,
                    album=parsed_args.album,
                    artist=parsed_args.artist,
                    year=parsed_args.year,
                    mbid=parsed_args.mbid
                )
                sys.exit(0)
        except KeyboardInterrupt:
            self.display_manager.console.print("\n[yellow]⚠[/yellow] Operation cancelled by user.")
            sys.exit(1)
        except Exception as e:
            self.display_manager.console.print(f"[bold red]✗[/bold red] An error occurred: {e}")
            sys.exit(1)
    
    def _parse_batch_file(self, batch_file: str) -> List[Tuple[str, str, Optional[int]]]:
        """
        Parse a TSV/TXT file containing Artist, Album, and optional Year columns.
        
        Supports:
        - TSV format: Artist\tAlbum\tYear (with or without header)
        - CSV format: Artist,Album,Year (with or without header)
        - Human-readable format: Artist - Album (Year) or Artist - Album
        
        Returns:
            List of tuples (artist, album, year)
        """
        batch_path = Path(batch_file)
        if not batch_path.exists():
            raise FileNotFoundError(f"Batch file not found: {batch_file}")
        
        entries = []
        
        with open(batch_path, 'r', encoding='utf-8') as f:
            # Try to detect format by reading first line
            first_line = f.readline().strip()
            f.seek(0)  # Reset to beginning
            
            # Check if it's TSV (tab-separated)
            if '\t' in first_line:
                reader = csv.reader(f, delimiter='\t')
                for row_num, row in enumerate(reader, start=1):
                    # Skip header row if it exists
                    if row_num == 1 and row[0].lower() in ['artist', 'artists']:
                        continue
                    
                    if len(row) < 2:
                        continue
                    
                    artist = row[0].strip()
                    album = row[1].strip()
                    year = None
                    
                    # Try to parse year from third column if present
                    if len(row) >= 3 and row[2].strip():
                        try:
                            year = int(row[2].strip())
                        except ValueError:
                            pass
                    
                    if artist and album:
                        entries.append((artist, album, year))
            
            # Check if it's CSV (comma-separated)
            elif ',' in first_line and '\t' not in first_line:
                reader = csv.reader(f)
                for row_num, row in enumerate(reader, start=1):
                    # Skip header row if it exists
                    if row_num == 1 and row[0].lower() in ['artist', 'artists']:
                        continue
                    
                    if len(row) < 2:
                        continue
                    
                    artist = row[0].strip()
                    album = row[1].strip()
                    year = None
                    
                    # Try to parse year from third column if present
                    if len(row) >= 3 and row[2].strip():
                        try:
                            year = int(row[2].strip())
                        except ValueError:
                            pass
                    
                    if artist and album:
                        entries.append((artist, album, year))
            
            # Otherwise, try human-readable format: "Artist - Album (Year)" or "Artist - Album"
            else:
                import re
                for line_num, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    # Pattern: "Artist - Album (Year)" or "Artist - Album"
                    match = re.match(r'^(.+?)\s*-\s*(.+?)(?:\s*\((\d{4})\))?\s*$', line)
                    if match:
                        artist = match.group(1).strip()
                        album = match.group(2).strip()
                        year_str = match.group(3)
                        year = int(year_str) if year_str else None
                        
                        if artist and album:
                            entries.append((artist, album, year))
        
        if not entries:
            raise ValueError(f"No valid entries found in batch file: {batch_file}")
        
        return entries
    
    def _handle_batch_release(
        self,
        batch_file: str,
        release_type: Optional[str],
        quality: str,
        tracks: Optional[str],
        no_download: bool,
        auto: bool = False
    ):
        """Handle batch processing of releases from a file."""
        console = self.display_manager.console
        
        try:
            entries = self._parse_batch_file(batch_file)
        except Exception as e:
            console.print(f"[bold red]✗[/bold red] Failed to parse batch file: {e}")
            return
        
        console.print()
        console.print(self.display_manager._create_header_panel(
            f"📦 {PROJECT_NAME} - Batch Release Processing",
            f"Found {len(entries)} releases to process"
        ))
        console.print()
        
        successful = 0
        failed = 0
        
        for idx, (artist, album, year) in enumerate(entries, start=1):
            console.print()
            console.print(f"[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]")
            console.print(f"[bold]Processing [{idx}/{len(entries)}]:[/bold] [yellow]{album}[/yellow] by [green]{artist}[/green]" + (f" ({year})" if year else ""))
            console.print(f"[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]")
            
            try:
                self.release_handler.handle(
                    album=album,
                    artist=artist,
                    year=year,
                    release_type=release_type,
                    quality=quality,
                    tracks=tracks,
                    no_download=no_download,
                    auto=auto
                )
                successful += 1
            except KeyboardInterrupt:
                console.print("\n[yellow]⚠[/yellow] Batch processing cancelled by user.")
                console.print(f"\n[blue]ℹ[/blue] Processed: {successful} successful, {failed} failed")
                raise
            except Exception as e:
                console.print(f"[bold red]✗[/bold red] Failed to process {album} by {artist}: {e}")
                failed += 1
                # Continue with next entry
                continue
        
        console.print()
        console.print(f"[bold green]✓[/bold green] Batch processing complete!")
        console.print(f"  Successful: [green]{successful}[/green]")
        if failed > 0:
            console.print(f"  Failed: [red]{failed}[/red]")
