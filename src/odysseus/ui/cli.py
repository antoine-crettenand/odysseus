"""
Odysseus CLI Module
A comprehensive command-line interface for music discovery and downloading.
"""

import argparse
import csv
from pathlib import Path
from typing import List, Tuple, Optional

from rich.prompt import Confirm

from ..core.config import PROJECT_NAME, PROJECT_VERSION
from ..core.validation import validate_year, validate_year_range
from ..domain.music.download.download_service import MAX_PARALLEL_DOWNLOADS
from ..models.outcomes import OperationOutcome, OperationStatus


class OdysseusCLI:
    """Main CLI class for Odysseus music discovery tool."""

    def __init__(self, container=None, *, load_services: bool = True):
        """
        Initialize the CLI.

        Args:
            container: Optional DI container instance (uses global container if None)
        """
        if not load_services:
            self.container = container
            return

        if container is None:
            from ..core.container import get_container
            container = get_container()

        self.container = container

        # Get services from container
        self.search_service = container.get("search_service")
        self.download_service = container.get("download_service")
        self.metadata_service = container.get("metadata_service")
        self.display_manager = container.get("display_manager")

        # Get handlers from container
        self.recording_handler = container.get("recording_handler")
        self.release_handler = container.get("release_handler")
        self.discography_handler = container.get("discography_handler")
        self.metadata_handler = container.get("metadata_handler")
        self.spotify_handler = container.get("spotify_handler")

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
  %(prog)s discography --artist "Artist Name" --year-from 1965 --year-to 1975
  %(prog)s spotify --url "https://open.spotify.com/playlist/..."
  %(prog)s spotify --url "https://open.spotify.com/playlist/..." --mode releases
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
            help='Parse Spotify playlist/album URL and download selected tracks or releases (use --mode releases to select albums)'
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
            '--year-from',
            type=int,
            help='Inclusive earliest release year (applies to batch rows without a year)'
        )
        parser.add_argument(
            '--year-to',
            type=int,
            help='Inclusive latest release year (applies to batch rows without a year)'
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
        self._add_parallel_download_args(parser)

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
            '--year-from',
            type=int,
            help='Inclusive earliest release year'
        )
        parser.add_argument(
            '--year-to',
            type=int,
            help='Inclusive latest release year'
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
        self._add_parallel_download_args(parser)

    def _add_spotify_args(self, parser: argparse.ArgumentParser):
        """Add arguments for Spotify mode."""
        parser.add_argument(
            '--url', '-u',
            required=True,
            help='Spotify playlist, album, or track URL'
        )
        parser.add_argument(
            '--mode', '-m',
            dest='spotify_mode',
            choices=['recordings', 'releases'],
            default='recordings',
            help='Mode: "recordings" to select individual tracks (default), "releases" to select albums containing the tracks'
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
        parser.add_argument(
            '--export',
            dest='export_path',
            help='Export unique releases to a file (releases mode)'
        )
        parser.add_argument(
            '--export-format',
            choices=['tsv', 'csv', 'json'],
            default='tsv',
            help='Release export format (default: tsv)'
        )
        parser.add_argument(
            '--collection-type',
            choices=['tracks', 'albums', 'both'],
            default='tracks',
            help='Collection content to export/process for collection URLs'
        )
        self._add_parallel_download_args(parser)

    @staticmethod
    def _add_parallel_download_args(parser: argparse.ArgumentParser):
        """Add the shared bounded-concurrency option to download modes."""
        parser.add_argument(
            '--jobs',
            type=int,
            choices=range(1, MAX_PARALLEL_DOWNLOADS + 1),
            default=1,
            metavar='N',
            help=(
                "Simultaneous independent track downloads, "
                f"1-{MAX_PARALLEL_DOWNLOADS} (default: 1)"
            ),
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

    def run(self, args: List[str] = None) -> int:
        """Run the CLI with given arguments."""
        parser = self.create_parser()
        parsed_args = parser.parse_args(args)
        if parsed_args.mode in {'release', 'discography'}:
            try:
                validate_year_range(
                    getattr(parsed_args, 'year', None),
                    getattr(parsed_args, 'year_from', None),
                    getattr(parsed_args, 'year_to', None),
                )
            except ValueError as error:
                parser.error(str(error))

        try:
            if parsed_args.mode == 'recording':
                outcome = self.recording_handler.handle(
                    title=parsed_args.title,
                    artist=parsed_args.artist,
                    album=parsed_args.album,
                    year=parsed_args.year,
                    quality=parsed_args.quality,
                    no_download=parsed_args.no_download
                )
                return self._outcome_exit_code(outcome)
            elif parsed_args.mode == 'release':
                # Handle batch processing
                if parsed_args.batch:
                    outcome = self._handle_batch_release(
                        batch_file=parsed_args.batch,
                        release_type=parsed_args.type,
                        quality=parsed_args.quality,
                        tracks=parsed_args.tracks,
                        no_download=parsed_args.no_download,
                        auto=getattr(parsed_args, 'auto', False),
                        jobs=parsed_args.jobs,
                        year_from=parsed_args.year_from,
                        year_to=parsed_args.year_to,
                    )
                else:
                    # Validate required arguments for single release
                    if not parsed_args.album or not parsed_args.artist:
                        parser.error("--album and --artist are required unless --batch is used")

                    outcome = self.release_handler.handle(
                        album=parsed_args.album,
                        artist=parsed_args.artist,
                        year=parsed_args.year,
                        year_from=parsed_args.year_from,
                        year_to=parsed_args.year_to,
                        release_type=parsed_args.type,
                        quality=parsed_args.quality,
                        tracks=parsed_args.tracks,
                        no_download=parsed_args.no_download,
                        auto=getattr(parsed_args, 'auto', False),
                        jobs=parsed_args.jobs,
                    )
                return self._outcome_exit_code(outcome)
            elif parsed_args.mode == 'discography':
                # Loop for discography - allow user to go back to discography display
                cached_releases = None
                exit_code = 0
                while True:
                    releases = self.discography_handler.handle(
                        artist=parsed_args.artist,
                        year=parsed_args.year,
                        year_from=parsed_args.year_from,
                        year_to=parsed_args.year_to,
                        release_type=parsed_args.type,
                        quality=parsed_args.quality,
                        no_download=parsed_args.no_download,
                        cached_releases=cached_releases,
                        include_compilations=getattr(parsed_args, 'include_compilations', False),
                        jobs=parsed_args.jobs,
                    )

                    if isinstance(releases, OperationOutcome):
                        exit_code = self._outcome_exit_code(releases)
                        break

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
                return exit_code
            elif parsed_args.mode == 'spotify':
                outcome = self.spotify_handler.handle(
                    url=parsed_args.url,
                    mode=getattr(parsed_args, 'spotify_mode', 'recordings'),
                    quality=parsed_args.quality,
                    tracks=parsed_args.tracks,
                    no_download=parsed_args.no_download,
                    export_path=parsed_args.export_path,
                    export_format=parsed_args.export_format,
                    collection_type=parsed_args.collection_type,
                    jobs=parsed_args.jobs,
                )
                return self._outcome_exit_code(outcome)
            elif parsed_args.mode == 'metadata':
                outcome = self.metadata_handler.handle(
                    file_path=parsed_args.file,
                    album=parsed_args.album,
                    artist=parsed_args.artist,
                    year=parsed_args.year,
                    mbid=parsed_args.mbid
                )
                return self._outcome_exit_code(outcome)
        except KeyboardInterrupt:
            self.display_manager.console.print("\n[yellow]⚠[/yellow] Operation cancelled by user.")
            return 1
        except Exception as e:
            self.display_manager.console.print(f"[bold red]✗[/bold red] An error occurred: {e}")
            return 1
        return 0

    @staticmethod
    def _outcome_exit_code(outcome) -> int:
        """Translate structured handler outcomes while tolerating legacy callers."""
        if isinstance(outcome, OperationOutcome):
            return 0 if outcome.succeeded else 1
        return 0

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
            # Detect from the first content line. Human-readable entries may
            # contain commas in artist names, so a comma alone is not enough
            # to classify a text file as CSV.
            first_line = next(
                (
                    line.strip()
                    for line in f
                    if line.strip() and not line.lstrip().startswith('#')
                ),
                '',
            )
            f.seek(0)  # Reset to beginning

            import re

            def parse_batch_year(value: str, line_number: int) -> int:
                """Parse and validate an explicitly supplied batch year."""
                try:
                    year_value = int(value.strip())
                except ValueError as error:
                    raise ValueError(
                        f"Invalid year on line {line_number}: {value!r}"
                    ) from error
                try:
                    return validate_year(year_value)
                except ValueError as error:
                    raise ValueError(
                        f"Invalid year on line {line_number}: {error}"
                    ) from error

            human_pattern = re.compile(
                r'^(.+?)\s+-\s+(.+?)(?:\s+\((\d{4})\))?\s*$'
            )
            first_row = next(csv.reader([first_line]), []) if first_line else []
            has_csv_header = (
                len(first_row) >= 2
                and first_row[0].strip().lower() in {'artist', 'artists'}
                and first_row[1].strip().lower() in {'album', 'release'}
            )
            if '\t' in first_line:
                delimiter = '\t'
            elif batch_path.suffix.lower() == '.csv' or has_csv_header:
                delimiter = ','
            elif ',' in first_line and not human_pattern.fullmatch(first_line):
                delimiter = ','
            else:
                delimiter = None

            if delimiter:
                reader = csv.reader(f, delimiter=delimiter)
                for row in reader:
                    if not row or not any(value.strip() for value in row):
                        continue
                    if row[0].lstrip().startswith('#'):
                        continue
                    if (
                        len(row) >= 2
                        and row[0].strip().lower() in {'artist', 'artists'}
                        and row[1].strip().lower() in {'album', 'release'}
                    ):
                        continue
                    if len(row) < 2:
                        continue
                    artist = row[0].strip()
                    album = row[1].strip()
                    year = None
                    if len(row) >= 3 and row[2].strip():
                        year = parse_batch_year(row[2], reader.line_num)
                    if artist and album:
                        entries.append((artist, album, year))
            else:
                for line_num, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    # Pattern: "Artist - Album (Year)" or "Artist - Album"
                    match = human_pattern.fullmatch(line)
                    if match:
                        artist = match.group(1).strip()
                        album = match.group(2).strip()
                        year_str = match.group(3)
                        year = (
                            parse_batch_year(year_str, line_num)
                            if year_str
                            else None
                        )

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
        auto: bool = False,
        jobs: int = 1,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
    ) -> OperationOutcome:
        """Handle batch processing of releases from a file."""
        console = self.display_manager.console

        try:
            validate_year_range(None, year_from, year_to)
        except ValueError as error:
            console.print(f"[bold red]✗[/bold red] Invalid year range: {error}")
            return OperationOutcome.failure(str(error), error=error)

        try:
            entries = self._parse_batch_file(batch_file)
        except Exception as e:
            console.print(f"[bold red]✗[/bold red] Failed to parse batch file: {e}")
            return OperationOutcome.failure(str(e), error=e)

        console.print()
        console.print(self.display_manager.create_header_panel(
            f"📦 {PROJECT_NAME} - Batch Release Processing",
            f"Found {len(entries)} releases to process"
        ))
        console.print()

        successful = 0
        failed = 0
        skipped = 0

        for idx, (artist, album, year) in enumerate(entries, start=1):
            console.print()
            console.print(f"[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]")
            console.print(f"[bold]Processing [{idx}/{len(entries)}]:[/bold] [yellow]{album}[/yellow] by [green]{artist}[/green]" + (f" ({year})" if year else ""))
            console.print(f"[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]")

            try:
                outcome = self.release_handler.handle(
                    album=album,
                    artist=artist,
                    year=year,
                    year_from=None if year is not None else year_from,
                    year_to=None if year is not None else year_to,
                    release_type=release_type,
                    quality=quality,
                    tracks=tracks,
                    no_download=no_download,
                    auto=auto,
                    jobs=jobs,
                )
                if not isinstance(outcome, OperationOutcome):
                    outcome = OperationOutcome.failure(
                        "Release handler returned no structured outcome"
                    )
                if outcome.status is OperationStatus.SUCCESS:
                    successful += 1
                elif outcome.status is OperationStatus.SKIPPED:
                    skipped += 1
                else:
                    failed += 1
            except KeyboardInterrupt:
                console.print("\n[yellow]⚠[/yellow] Batch processing cancelled by user.")
                console.print(
                    f"\n[blue]ℹ[/blue] Processed: {successful} successful, "
                    f"{skipped} skipped, {failed} failed"
                )
                raise
            except Exception as e:
                console.print(f"[bold red]✗[/bold red] Failed to process {album} by {artist}: {e}")
                failed += 1
                # Continue with next entry
                continue

        console.print()
        console.print(f"[bold green]✓[/bold green] Batch processing complete!")
        console.print(f"  Successful: [green]{successful}[/green]")
        if skipped > 0:
            console.print(f"  Skipped: [yellow]{skipped}[/yellow]")
        if failed > 0:
            console.print(f"  Failed: [red]{failed}[/red]")
        if failed:
            return OperationOutcome.failure(
                f"{failed} release(s) failed",
                processed=successful,
                failed=failed,
            )
        if skipped and not successful:
            return OperationOutcome.skipped(f"{skipped} release(s) skipped")
        return OperationOutcome.success(
            "Batch processing complete",
            processed=successful,
        )
