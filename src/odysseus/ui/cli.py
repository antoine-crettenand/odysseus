"""
Odysseus CLI Module
A comprehensive command-line interface for music discovery and downloading.
"""

import argparse
import sys
from typing import List

from rich.prompt import Confirm

from ..services.search_service import SearchService
from ..services.download_service import DownloadService
from ..services.metadata_service import MetadataService
from ..ui.display import DisplayManager
from ..ui.handlers import RecordingHandler, ReleaseHandler, DiscographyHandler, MetadataHandler
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
    
    def create_parser(self) -> argparse.ArgumentParser:
        """Create the argument parser."""
        parser = argparse.ArgumentParser(
            prog=PROJECT_NAME,
            description=f"{PROJECT_NAME} - Music Discovery Tool v{PROJECT_VERSION}",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  %(prog)s recording --title "Bohemian Rhapsody" --artist "Queen"
  %(prog)s release --album "Dark Side of the Moon" --artist "Pink Floyd"
  %(prog)s discography --artist "The Beatles" --year 1965
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
            help='Search and download tracks from a release/album'
        )
        self._add_release_args(release_parser)
        
        discography_parser = subparsers.add_parser(
            'discography',
            help='Browse artist discography and download selected releases'
        )
        self._add_discography_args(discography_parser)
        
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
            required=True,
            help='Album/release name to search for'
        )
        parser.add_argument(
            '--artist', '-a',
            required=True,
            help='Artist name'
        )
        parser.add_argument(
            '--year', '-y',
            type=int,
            help='Release year (optional)'
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
                self.release_handler.handle(
                    album=parsed_args.album,
                    artist=parsed_args.artist,
                    year=parsed_args.year,
                    release_type=parsed_args.type,
                    quality=parsed_args.quality,
                    tracks=parsed_args.tracks,
                    no_download=parsed_args.no_download
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
                        cached_releases=cached_releases
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
