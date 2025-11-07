"""
Odysseus CLI Module
A comprehensive command-line interface for music discovery and downloading.
"""

import argparse
import sys
import logging
import subprocess
import requests
from typing import List, Optional, Dict, Any
from pathlib import Path

from ..models.song import SongData
from ..models.search_results import MusicBrainzSong, YouTubeVideo
from ..models.releases import ReleaseInfo
from ..services.search_service import SearchService
from ..services.download_service import DownloadService
from ..services.metadata_service import MetadataService
from ..ui.display import DisplayManager
from rich.table import Table
from rich.panel import Panel
from rich import box
from ..core.config import (
    PROJECT_NAME, PROJECT_VERSION, UI_CONFIG, ERROR_MESSAGES, 
    SUCCESS_MESSAGES, MENU_OPTIONS, HELP_TEXT, VALIDATION_RULES,
    QUALITY_PRESETS, YOUTUBE_CONFIG
)


class OdysseusCLI:
    """Main CLI class for Odysseus music discovery tool."""
    
    def __init__(self):
        """Initialize the CLI."""
        self.search_service = SearchService()
        self.download_service = DownloadService()
        self.metadata_service = MetadataService()
        self.display_manager = DisplayManager()
    
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
            """
        )
        
        # Add version
        parser.add_argument(
            '--version', 
            action='version', 
            version=f'{PROJECT_NAME} {PROJECT_VERSION}'
        )
        
        # Create subparsers for different modes
        subparsers = parser.add_subparsers(
            dest='mode',
            help='Available modes',
            required=True
        )
        
        # Recording mode (current main.py functionality)
        recording_parser = subparsers.add_parser(
            'recording',
            help='Search and download a specific recording/song'
        )
        self._add_recording_args(recording_parser)
        
        # Release mode (LP/album search and download)
        release_parser = subparsers.add_parser(
            'release',
            help='Search and download tracks from a release/album'
        )
        self._add_release_args(release_parser)
        
        # Discography mode (artist discography lookup and selective download)
        discography_parser = subparsers.add_parser(
            'discography',
            help='Browse artist discography and download selected releases'
        )
        self._add_discography_args(discography_parser)
        
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
    
    def run(self, args: List[str] = None):
        """Run the CLI with given arguments."""
        parser = self.create_parser()
        parsed_args = parser.parse_args(args)
        
        try:
            if parsed_args.mode == 'recording':
                self._handle_recording_mode(parsed_args)
            elif parsed_args.mode == 'release':
                self._handle_release_mode(parsed_args)
            elif parsed_args.mode == 'discography':
                self._handle_discography_mode(parsed_args)
        except KeyboardInterrupt:
            self.display_manager.console.print("\n[yellow]⚠[/yellow] Operation cancelled by user.")
            sys.exit(1)
        except Exception as e:
            self.display_manager.console.print(f"[bold red]✗[/bold red] An error occurred: {e}")
            sys.exit(1)
    
    def _handle_recording_mode(self, args):
        """Handle recording search and download mode."""
        console = self.display_manager.console
        console.print()
        console.print(self.display_manager._create_header_panel(
            f"🎵 {PROJECT_NAME} - Recording Search",
            f"Searching for: {args.title} by {args.artist}"
        ))
        console.print()
        
        # Create song data
        song_data = SongData(
            title=args.title,
            artist=args.artist,
            album=args.album,
            release_year=args.year
        )
        
        # Search loop with reshuffle support
        offset = 0
        while True:
            # Search MusicBrainz with loading spinner
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
        
            # Display results
            self.display_manager.display_search_results(results, "RECORDINGS")
            
            # Get user selection
            selected_song = self.display_manager.get_user_selection(results)
            
            if selected_song == 'RESHUFFLE':
                # Move to next page of results
                offset += len(results)
                console.print()
                continue
            elif not selected_song:
                console.print("[yellow]⚠[/yellow] No selection made. Exiting.")
                return
            
            if args.no_download:
                console.print("[blue]ℹ[/blue] Search completed. Use without --no-download to download.")
                return
            
            # Search YouTube and download
            self._search_and_download_recording(selected_song, args.quality)
            break
    
    def _handle_release_mode(self, args):
        """Handle release/album search and download mode."""
        console = self.display_manager.console
        console.print()
        console.print(self.display_manager._create_header_panel(
            f"💿 {PROJECT_NAME} - Release Search",
            f"Searching for release: {args.album} by {args.artist}"
        ))
        console.print()
        
        # Create song data for release search
        song_data = SongData(
            title="",  # No title for release search
            artist=args.artist,
            album=args.album,
            release_year=args.year
        )
        
        # Search loop with reshuffle support
        offset = 0
        while True:
            # Search MusicBrainz for releases with loading spinner
            if offset > 0:
                console.print(f"[blue]ℹ[/blue] Showing results starting from position {offset + 1}")
            
            results = self.display_manager.show_loading_spinner(
                f"Searching MusicBrainz releases: {song_data.album} by {song_data.artist}",
                self.search_service.search_releases,
                song_data,
                offset=offset,
                release_type=args.type
            )
        
            if not results:
                if offset == 0:
                    console.print(f"[bold red]✗[/bold red] {ERROR_MESSAGES['NO_RESULTS']}")
                    return
                else:
                    console.print("[yellow]⚠[/yellow] No more results available. Starting from beginning...")
                    offset = 0
                    continue
        
            # Display results
            self.display_manager.display_search_results(results, "RELEASES")
            
            # Get user selection
            selected_release = self.display_manager.get_user_selection(results)
            
            if selected_release == 'RESHUFFLE':
                # Move to next page of results
                offset += len(results)
                console.print()
                continue
            elif not selected_release:
                console.print("[yellow]⚠[/yellow] No selection made. Exiting.")
                return
            
            if args.no_download:
                console.print("[blue]ℹ[/blue] Search completed. Use without --no-download to download.")
                return
            
            # Get track listing and download selected tracks
            self._search_and_download_release(selected_release, args.quality, args.tracks)
            break
    
    def _handle_discography_mode(self, args):
        """Handle discography browse and download mode."""
        console = self.display_manager.console
        console.print()
        subtitle = f"Searching discography for: {args.artist}"
        if args.year:
            subtitle += f" (Year: {args.year})"
        if args.type:
            subtitle += f" (Type: {args.type})"
        console.print(self.display_manager._create_header_panel(
            f"📚 {PROJECT_NAME} - Discography Browse",
            subtitle
        ))
        console.print()
        
        # Search for artist releases with loading spinner
        releases = self.display_manager.show_loading_spinner(
            f"Searching discography for: {args.artist}",
            self.search_service.search_artist_releases,
            args.artist,
            year=args.year,
            release_type=args.type
        )
        
        if not releases:
            console.print(f"[bold red]✗[/bold red] {ERROR_MESSAGES['NO_RESULTS']}")
            return
        
        # Display releases grouped by year
        ordered_releases = self.display_manager.display_discography(releases)
        
        if args.no_download:
            console.print("[blue]ℹ[/blue] Discography browse completed. Use without --no-download to download releases.")
            return
        
        # Get user selection for releases to download
        selected_releases, auto_download_all_tracks = self.display_manager.get_release_selection(
            ordered_releases, args.quality, self.search_service
        )
        
        if not selected_releases:
            console.print("[yellow]⚠[/yellow] No releases selected for download.")
            return
        
        # Download selected releases
        self._download_selected_releases(selected_releases, args.quality, auto_download_all_tracks=auto_download_all_tracks)
    
    def _search_and_download_recording(self, selected_song: MusicBrainzSong, quality: str):
        """Search YouTube and download a recording."""
        console = self.display_manager.console
        # Create search query
        search_query = f"{selected_song.artist} {selected_song.title}"
        
        console.print()
        console.print(self.display_manager._create_header_panel(
            "🔍 SEARCHING YOUTUBE",
            f"Search query: {search_query}"
        ))
        console.print()
        
        try:
            # YouTube search loop with reshuffle support
            while True:
                # Search YouTube with loading spinner
                videos = self.display_manager.show_loading_spinner(
                    f"Searching YouTube for: {search_query}",
                    self.search_service.search_youtube,
                    search_query,
                    YOUTUBE_CONFIG["MAX_RESULTS"]
                )
                
                if not videos:
                    console.print(f"[bold red]✗[/bold red] {ERROR_MESSAGES['NO_RESULTS']}")
                    return
                
                # Display YouTube results
                self.display_manager.display_youtube_results(videos)
                
                # Get video selection
                selected_video = self.display_manager.get_video_selection(videos)
                
                if selected_video == 'RESHUFFLE':
                    # Search again for different results
                    console.print("[blue]ℹ[/blue] Searching again for different results...")
                    console.print()
                    continue
                elif not selected_video:
                    console.print("[yellow]⚠[/yellow] No video selected for download.")
                    return
                
                # Proceed with download
                break
            
            # Create song data for download
            song_data = SongData(
                title=selected_song.title,
                artist=selected_song.artist,
                album=selected_song.album,
                release_year=selected_song.release_date
            )
            
            # Download the video
            self._download_video(song_data, selected_video, selected_song, quality)
            
        except Exception as e:
            console.print(f"[bold red]✗[/bold red] Error searching YouTube: {e}")
    
    def _search_and_download_release(self, selected_release: MusicBrainzSong, quality: str, tracks: Optional[str]):
        """Search and download tracks from a release."""
        console = self.display_manager.console
        console.print()
        console.print(self.display_manager._create_header_panel(
            "📥 RELEASE DOWNLOAD",
            f"Release: {selected_release.album} by {selected_release.artist}"
        ))
        console.print()
        
        # Get detailed release information with tracks
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
        
        # Display track listing
        self.display_manager.display_track_listing(release_info)
        
        # Parse track selection
        track_numbers = self._parse_track_selection(tracks, len(release_info.tracks))
        
        if not track_numbers:
            console.print("[yellow]⚠[/yellow] No tracks selected for download.")
            return
        
        # Download selected tracks
        self._download_release_tracks(release_info, track_numbers, quality)
    
    def _download_selected_releases(self, releases: List[MusicBrainzSong], quality: str, auto_download_all_tracks: bool = False):
        """
        Download selected releases.
        
        Args:
            releases: List of releases to download
            quality: Download quality
            auto_download_all_tracks: If True, automatically download all tracks from all releases
                                     without prompting for each release
        """
        console = self.display_manager.console
        console.print()
        console.print(self.display_manager._create_header_panel(
            "⬇️  DOWNLOADING RELEASES",
            f"Releases to download: {len(releases)} | Quality: {quality}" + 
            (f" | [bold green]Auto-download all tracks[/bold green]" if auto_download_all_tracks else "")
        ))
        console.print()
        
        total_downloaded = 0
        total_failed = 0
        
        for i, release in enumerate(releases, 1):
            self.display_manager.display_download_progress(i, len(releases), release.album)
            
            # Get detailed release information with batch progress
            source = getattr(release, 'source', 'musicbrainz')
            release_info = self.display_manager.show_loading_spinner(
                f"Fetching release details: {release.album}",
                self.search_service.get_release_info,
                release.mbid,
                batch_progress=(i, len(releases)),
                source=source
            )
            if not release_info:
                console.print(f"[bold red]✗[/bold red] Failed to get details for: [yellow]{release.album}[/yellow]")
                total_failed += 1
                continue
            
            # Display track listing
            self.display_manager.display_track_listing_simple(release_info.tracks, release.album)
            
            # If auto_download_all_tracks is True, skip manual selection and download all tracks
            if auto_download_all_tracks:
                console.print(f"[cyan]Auto-downloading all {len(release_info.tracks)} track{'s' if len(release_info.tracks) != 1 else ''}...[/cyan]")
                track_numbers = list(range(1, len(release_info.tracks) + 1))
                downloaded, failed = self._download_release_tracks_silent(release_info, track_numbers, quality)
                total_downloaded += downloaded
                total_failed += failed
            else:
                # Ask if user wants to download all tracks or select specific ones
                self.display_manager.display_download_options()
                
                from rich.prompt import Prompt
                while True:
                    choice = Prompt.ask("[bold]Choose option[/bold]", choices=["1", "2", "3"], default="3")
                    
                    if choice == '1':
                        # Download all tracks
                        track_numbers = list(range(1, len(release_info.tracks) + 1))
                        downloaded, failed = self._download_release_tracks_silent(release_info, track_numbers, quality)
                        total_downloaded += downloaded
                        total_failed += failed
                        break
                    elif choice == '2':
                        # Select specific tracks
                        track_numbers = self._parse_track_selection(None, len(release_info.tracks))
                        if track_numbers:
                            downloaded, failed = self._download_release_tracks_silent(release_info, track_numbers, quality)
                            total_downloaded += downloaded
                            total_failed += failed
                        break
                    elif choice == '3':
                        console.print(f"[yellow]⚠[/yellow] Skipped: [yellow]{release.album}[/yellow]")
                        break
        
        # Final summary
        self.display_manager.display_download_summary(total_downloaded, total_failed, len(releases))
    
    def _download_release_tracks_silent(self, release_info: ReleaseInfo, track_numbers: List[int], quality: str) -> tuple[int, int]:
        """Download tracks with progress bars and return counts."""
        console = self.display_manager.console
        downloaded_count = 0
        failed_count = 0
        
        # Create progress bar for overall track progress
        progress = self.display_manager.create_progress_bar(len(track_numbers), f"Downloading {release_info.title}")
        
        with progress:
            task = progress.add_task("[cyan]Downloading tracks...", total=len(track_numbers))
            
            for track_num in track_numbers:
                # Find the track
                track = None
                for t in release_info.tracks:
                    if t.position == track_num:
                        track = t
                        break
                
                if not track:
                    failed_count += 1
                    progress.update(task, advance=1)
                    continue
                
                progress.update(task, description=f"[cyan]Downloading: {track.title[:40]}")
                
                # Search YouTube for this track
                search_query = f"{track.artist} {track.title}"
                try:
                    videos = self.search_service.search_youtube(search_query, 1)  # Only get the best match
                    
                    if not videos:
                        failed_count += 1
                        progress.update(task, advance=1)
                        continue
                    
                    # Use the first (best) result
                    selected_video = videos[0]
                    
                    # Create metadata for download
                    metadata_dict = {
                        'title': track.title,
                        'artist': track.artist,
                        'album': release_info.title,
                        'year': int(release_info.release_date[:4]) if release_info.release_date and len(release_info.release_date) >= 4 else None,
                        'track_number': track.position,
                        'total_tracks': len(release_info.tracks)
                    }
                    
                    # Create nested progress bar for file download
                    file_progress, file_task_id = self.display_manager.create_download_progress_bar(
                        f"Track {track.position}: {track.title[:40]}"
                    )
                    
                    # Progress callback for file download
                    def update_file_progress(progress_info: Dict[str, Any]):
                        """Update file-level progress bar."""
                        percent = progress_info.get('percent', 0)
                        speed = progress_info.get('speed', '')
                        eta = progress_info.get('eta', '')
                        
                        file_progress.update(file_task_id, completed=percent)
                        
                        desc = f"Track {track.position}: {track.title[:35]}"
                        if speed:
                            desc += f" @ {speed}"
                        if eta:
                            desc += f" ETA: {eta}"
                        file_progress.update(file_task_id, description=desc)
                    
                    # Download the track with progress
                    youtube_url = selected_video.youtube_url
                    
                    with file_progress:
                        if quality == 'audio':
                            downloaded_path = self.download_service.download_high_quality_audio(
                                youtube_url, 
                                metadata=metadata_dict, 
                                quiet=True,
                                progress_callback=update_file_progress
                            )
                        else:
                            downloaded_path = self.download_service.download_video(
                                youtube_url, 
                                quality=quality, 
                                audio_only=(quality == 'audio'), 
                                metadata=metadata_dict, 
                                quiet=True,
                                progress_callback=update_file_progress
                            )
                        
                        file_progress.update(file_task_id, completed=100)
                    
                    if downloaded_path:
                        # Apply metadata with cover art (same as _download_release_tracks)
                        try:
                            self._apply_metadata_with_cover_art(downloaded_path, track, release_info)
                        except Exception:
                            # If metadata application fails, still count as downloaded
                            pass
                        downloaded_count += 1
                    else:
                        failed_count += 1
                        
                except subprocess.TimeoutExpired:
                    # Timeout occurred during download
                    failed_count += 1
                    console.print(f"[yellow]⚠[/yellow] Timeout downloading track {track.position}: {track.title}")
                except Exception as e:
                    # Log other exceptions but continue with next track
                    failed_count += 1
                    console.print(f"[yellow]⚠[/yellow] Error downloading track {track.position}: {track.title} - {str(e)[:50]}")
                
                progress.update(task, advance=1)
        
        return downloaded_count, failed_count
    
    def _download_release_tracks(self, release_info: ReleaseInfo, track_numbers: List[int], quality: str):
        """Download selected tracks from a release."""
        console = self.display_manager.console
        console.print()
        console.print(self.display_manager._create_header_panel(
            "⬇️  DOWNLOADING TRACKS",
            f"Release: {release_info.title} by {release_info.artist}\n"
            f"Tracks: {', '.join(map(str, track_numbers))} | Quality: {quality}"
        ))
        console.print()
        
        downloaded_count = 0
        failed_count = 0
        
        # Create progress bar
        progress = self.display_manager.create_progress_bar(len(track_numbers), "Downloading tracks")
        
        with progress:
            task = progress.add_task("[cyan]Downloading...", total=len(track_numbers))
            
            for track_num in track_numbers:
                # Find the track
                track = None
                for t in release_info.tracks:
                    if t.position == track_num:
                        track = t
                        break
                
                if not track:
                    console.print(f"[bold red]✗[/bold red] Track [bold]{track_num}[/bold] not found.")
                    failed_count += 1
                    progress.update(task, advance=1)
                    continue
                
                progress.update(task, description=f"[cyan]Downloading: {track.title}")
                
                # Search YouTube for this track
                search_query = f"{track.artist} {track.title}"
                try:
                    videos = self.display_manager.show_loading_spinner(
                        f"Searching YouTube for: {track.title}",
                        self.search_service.search_youtube,
                        search_query,
                        1
                    )
                    
                    if not videos:
                        console.print(f"[bold red]✗[/bold red] No YouTube results found for: [white]{track.title}[/white]")
                        failed_count += 1
                        progress.update(task, advance=1)
                        continue
                    
                    # Use the first (best) result
                    selected_video = videos[0]
                    
                    # Create metadata for download
                    metadata_dict = {
                        'title': track.title,
                        'artist': track.artist,
                        'album': release_info.title,
                        'year': int(release_info.release_date[:4]) if release_info.release_date and len(release_info.release_date) >= 4 else None,
                        'track_number': track.position,
                        'total_tracks': len(release_info.tracks)
                    }
                    
                    # Create nested progress bar for file download
                    file_progress, file_task_id = self.display_manager.create_download_progress_bar(
                        f"Track {track.position}: {track.title[:40]}"
                    )
                    
                    # Progress callback for file download
                    def update_file_progress(progress_info: Dict[str, Any]):
                        """Update file-level progress bar."""
                        percent = progress_info.get('percent', 0)
                        speed = progress_info.get('speed', '')
                        eta = progress_info.get('eta', '')
                        
                        file_progress.update(file_task_id, completed=percent)
                        
                        desc = f"Track {track.position}: {track.title[:35]}"
                        if speed:
                            desc += f" @ {speed}"
                        if eta:
                            desc += f" ETA: {eta}"
                        file_progress.update(file_task_id, description=desc)
                    
                    # Download the track with progress
                    youtube_url = selected_video.youtube_url
                    
                    with file_progress:
                        if quality == 'audio':
                            downloaded_path = self.download_service.download_high_quality_audio(
                                youtube_url, 
                                metadata=metadata_dict,
                                quiet=True,
                                progress_callback=update_file_progress
                            )
                        else:
                            downloaded_path = self.download_service.download_video(
                                youtube_url, 
                                quality=quality, 
                                audio_only=(quality == 'audio'), 
                                metadata=metadata_dict,
                                quiet=True,
                                progress_callback=update_file_progress
                            )
                        
                        file_progress.update(file_task_id, completed=100)
                    
                    if downloaded_path:
                        # Apply metadata with cover art
                        self._apply_metadata_with_cover_art(downloaded_path, track, release_info)
                        self.display_manager.display_track_download_result(track.title, True, str(downloaded_path))
                        downloaded_count += 1
                    else:
                        self.display_manager.display_track_download_result(track.title, False)
                        failed_count += 1
                        
                except Exception as e:
                    console.print(f"[bold red]✗[/bold red] Error downloading [white]{track.title}[/white]: {e}")
                    failed_count += 1
                
                progress.update(task, advance=1)
        
        # Summary
        console.print()
        summary_content = f"[bold green]✓[/bold green] Successfully downloaded: [green]{downloaded_count}[/green] track{'s' if downloaded_count != 1 else ''}\n"
        if failed_count > 0:
            summary_content += f"[bold red]✗[/bold red] Failed downloads: [red]{failed_count}[/red] track{'s' if failed_count != 1 else ''}\n"
        summary_content += f"[blue]ℹ[/blue] Total tracks processed: [cyan]{len(track_numbers)}[/cyan]"
        
        console.print(Panel(
            summary_content,
            title="[bold cyan]📊 DOWNLOAD SUMMARY[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2)
        ))
        console.print()
    
    def _download_video(self, song_data: SongData, selected_video: YouTubeVideo, metadata: MusicBrainzSong, quality: str):
        """Download the selected YouTube video."""
        console = self.display_manager.console
        video_id = selected_video.video_id
        if not video_id:
            console.print("[bold red]✗[/bold red] No video ID found.")
            return
        
        youtube_url = selected_video.youtube_url
        video_title = selected_video.title or 'Unknown'
        
        # Display download info
        self.display_manager.display_download_info(
            youtube_url,
            quality,
            quality == 'audio',
            str(self.download_service.downloads_dir),
            {
                'title': song_data.title,
                'artist': song_data.artist,
                'album': song_data.album,
                'year': song_data.release_year
            }
        )
        
        # Create metadata for download
        metadata_dict = {
            'title': song_data.title,
            'artist': song_data.artist,
            'album': song_data.album,
            'year': song_data.release_year
        }
        
        # Download with progress bar
        console.print("[cyan]Starting download...[/cyan]")
        
        # Create progress bar for file download
        progress, task_id = self.display_manager.create_download_progress_bar(
            f"Downloading: {video_title[:50]}"
        )
        
        # Progress callback to update the progress bar
        def update_progress(progress_info: Dict[str, Any]):
            """Update progress bar with download info."""
            percent = progress_info.get('percent', 0)
            speed = progress_info.get('speed', '')
            eta = progress_info.get('eta', '')
            
            # Update progress
            progress.update(task_id, completed=percent)
            
            # Update description with speed and ETA if available
            desc = f"Downloading: {video_title[:40]}"
            if speed:
                desc += f" @ {speed}"
            if eta:
                desc += f" ETA: {eta}"
            progress.update(task_id, description=desc)
        
        # Download with progress tracking
        with progress:
            if quality == 'audio':
                downloaded_path = self.download_service.download_high_quality_audio(
                    youtube_url,
                    metadata=metadata_dict,
                    quiet=True,
                    progress_callback=update_progress
                )
            else:
                downloaded_path = self.download_service.download_video(
                    youtube_url,
                    quality=quality,
                    audio_only=(quality == 'audio'),
                    metadata=metadata_dict,
                    quiet=True,
                    progress_callback=update_progress
                )
            
            # Mark as complete
            progress.update(task_id, completed=100, description=f"Completed: {video_title[:40]}")
        
        if downloaded_path:
            # Apply metadata with cover art (consistent with release mode)
            from ..models.song import AudioMetadata
            audio_metadata = AudioMetadata(
                title=song_data.title,
                artist=song_data.artist,
                album=song_data.album,
                year=song_data.release_year
            )
            # Try to get cover art from MusicBrainz if we have MBID from the metadata parameter (MusicBrainzSong)
            if hasattr(metadata, 'mbid') and metadata.mbid:
                cover_art_data = self._fetch_musicbrainz_cover_art(metadata.mbid)
                if cover_art_data:
                    audio_metadata.cover_art_data = cover_art_data
                    console.print(f"[blue]ℹ[/blue] ✓ Fetched cover art for [white]{song_data.title}[/white]")
            
            self.metadata_service.merger.set_final_metadata(audio_metadata)
            self.metadata_service.apply_metadata_to_file(str(downloaded_path), quiet=True)
            console.print(f"[bold green]✓[/bold green] Download completed: [green]{downloaded_path}[/green]")
        else:
            console.print("[bold red]✗[/bold red] Download failed")
    
    def _fetch_musicbrainz_cover_art(self, mbid: str) -> Optional[bytes]:
        """Fetch cover art from MusicBrainz Cover Art Archive."""
        try:
            cover_art_url = f"http://coverartarchive.org/release/{mbid}"
            response = requests.get(cover_art_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                images = data.get('images', [])
                
                # Look for front cover
                for image in images:
                    if image.get('front', False):
                        image_url = image.get('image')
                        if image_url:
                            img_response = requests.get(image_url, timeout=10)
                            if img_response.status_code == 200:
                                return img_response.content
                
                # If no front cover, use first image
                if images:
                    image_url = images[0].get('image')
                    if image_url:
                        img_response = requests.get(image_url, timeout=10)
                        if img_response.status_code == 200:
                            return img_response.content
        except Exception as e:
            # Silently fail - cover art is optional
            pass
        return None
    
    def _apply_metadata_with_cover_art(self, file_path: Path, track, release_info: ReleaseInfo):
        """Apply metadata including cover art to downloaded file."""
        try:
            from ..models.song import AudioMetadata
            
            # Create metadata
            metadata = AudioMetadata(
                title=track.title,
                artist=track.artist,
                album=release_info.title,
                year=int(release_info.release_date[:4]) if release_info.release_date and len(release_info.release_date) >= 4 else None,
                genre=release_info.genre,
                track_number=track.position,
                total_tracks=len(release_info.tracks)
            )
            
            # Fetch cover art from MusicBrainz if we have MBID
            if release_info.mbid:
                cover_art_data = self._fetch_musicbrainz_cover_art(release_info.mbid)
                if cover_art_data:
                    metadata.cover_art_data = cover_art_data
                    self.display_manager.console.print(f"[blue]ℹ[/blue] ✓ Fetched metadata and cover art for [white]{track.title}[/white]")
            
            # Apply metadata (quiet=True to suppress messages when progress bars are active)
            self.metadata_service.merger.set_final_metadata(metadata)
            self.metadata_service.apply_metadata_to_file(str(file_path), quiet=True)
            
        except Exception as e:
            self.display_manager.console.print(f"[yellow]⚠[/yellow] Could not apply metadata and cover art to {track.title}: {e}")
    
    def _parse_track_selection(self, tracks_arg: Optional[str], total_tracks: int) -> List[int]:
        """Parse track selection from command line argument or user input."""
        console = self.display_manager.console
        if tracks_arg:
            # Parse comma-separated track numbers
            try:
                track_numbers = [int(x.strip()) for x in tracks_arg.split(',')]
                # Validate track numbers
                valid_tracks = [t for t in track_numbers if 1 <= t <= total_tracks]
                if valid_tracks:
                    console.print(f"[blue]ℹ[/blue] Selected tracks: [cyan]{', '.join(map(str, valid_tracks))}[/cyan]")
                    return valid_tracks
                else:
                    console.print(f"[bold red]✗[/bold red] Invalid track numbers. Available tracks: 1-{total_tracks}")
                    return []
            except ValueError:
                console.print("[bold red]✗[/bold red] Invalid track selection format. Use comma-separated numbers (e.g., 1,3,5)")
                return []
        else:
            # Interactive track selection
            console.print("[bold]Select tracks to download:[/bold]")
            options_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
            options_table.add_column("Option", style="cyan")
            options_table.add_row("Enter track numbers separated by commas (e.g., 1,3,5)")
            options_table.add_row("Enter 'all' to download all tracks")
            options_table.add_row("Enter 'q' to cancel")
            console.print(options_table)
            console.print()
            
            from rich.prompt import Prompt
            while True:
                choice = Prompt.ask("[bold]Your selection[/bold]", default="")
                
                if choice.lower() == 'q':
                    return []
                
                if choice.lower() == 'all':
                    return list(range(1, total_tracks + 1))
                
                try:
                    track_numbers = [int(x.strip()) for x in choice.split(',')]
                    valid_tracks = [t for t in track_numbers if 1 <= t <= total_tracks]
                    
                    if len(valid_tracks) == len(track_numbers):
                        console.print(f"[blue]ℹ[/blue] Selected tracks: [cyan]{', '.join(map(str, valid_tracks))}[/cyan]")
                        return valid_tracks
                    else:
                        console.print(f"[bold red]✗[/bold red] Some track numbers are invalid. Available tracks: 1-{total_tracks}")
                        continue
                        
                except ValueError:
                    console.print("[bold red]✗[/bold red] Invalid format. Use comma-separated numbers (e.g., 1,3,5)")
                    continue
