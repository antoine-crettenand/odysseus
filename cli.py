#!/usr/bin/env python3
"""
Odysseus CLI Module
A comprehensive command-line interface for music discovery and downloading.
"""

import argparse
import sys
from typing import List, Optional, Dict, Any
from pathlib import Path

from musicbrainz_client import MusicBrainzClient, SongData, MusicBrainzSong, ReleaseInfo, Track
from youtube_client import YouTubeClient, YouTubeVideo
from youtube_downloader import YouTubeDownloader
from metadata_merger import MetadataMerger
from colors import (
    print_header, print_success, print_error, print_warning, print_info,
    print_separator, print_track_number, print_score, print_duration,
    print_views, print_channel, print_artist, print_album, print_title,
    Colors
)
from config import (
    PROJECT_NAME, PROJECT_VERSION, UI_CONFIG, ERROR_MESSAGES, 
    SUCCESS_MESSAGES, MENU_OPTIONS, HELP_TEXT, VALIDATION_RULES,
    QUALITY_PRESETS, YOUTUBE_CONFIG
)


class OdysseusCLI:
    """Main CLI class for Odysseus music discovery tool."""
    
    def __init__(self):
        """Initialize the CLI."""
        self.musicbrainz_client = MusicBrainzClient()
        self.downloader = YouTubeDownloader()
    
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
            print("\n\nOperation cancelled by user.")
            sys.exit(1)
        except Exception as e:
            print(f"An error occurred: {e}")
            sys.exit(1)
    
    def _handle_recording_mode(self, args):
        """Handle recording search and download mode."""
        print_header(f"{PROJECT_NAME} - Recording Search")
        
        # Create song data
        song_data = SongData(
            title=args.title,
            artist=args.artist,
            album=args.album,
            release_year=args.year
        )
        
        # Search MusicBrainz
        print_info(f"Searching for: {print_title(song_data.title)} by {print_artist(song_data.artist)}")
        results = self.musicbrainz_client.search_recording(song_data)
        
        if not results:
            print_error(ERROR_MESSAGES["NO_RESULTS"])
            return
        
        # Display results
        self._display_search_results(results, "RECORDINGS")
        
        # Get user selection
        selected_song = self._get_user_selection(results)
        if not selected_song:
            print_warning("No selection made. Exiting.")
            return
        
        print_success(f"Selected: {print_title(selected_song.title)} by {print_artist(selected_song.artist)}")
        
        if args.no_download:
            print_info("Search completed. Use without --no-download to download.")
            return
        
        # Search YouTube and download
        self._search_and_download_recording(selected_song, args.quality)
    
    def _handle_release_mode(self, args):
        """Handle release/album search and download mode."""
        print_header(f"{PROJECT_NAME} - Release Search")
        
        # TODO adapth data class to release search
        song_data = SongData(
            title="",  # No title for release search
            artist=args.artist,
            album=args.album,
            release_year=args.year
        )
        
        # Search MusicBrainz for releases
        print_info(f"Searching for release: {print_album(song_data.album)} by {print_artist(song_data.artist)}")
        results = self.musicbrainz_client.search_release(song_data)
        
        if not results:
            print_error(ERROR_MESSAGES["NO_RESULTS"])
            return
        
        # Display results
        self._display_search_results(results, "RELEASES")
        
        # Get user selection
        selected_release = self._get_user_selection(results)
        if not selected_release:
            print_warning("No selection made. Exiting.")
            return
        
        print_success(f"Selected: {print_album(selected_release.album)} by {print_artist(selected_release.artist)}")
        
        if args.no_download:
            print_info("Search completed. Use without --no-download to download.")
            return
        
        # Get track listing and download selected tracks
        self._search_and_download_release(selected_release, args.quality, args.tracks)
    
    def _handle_discography_mode(self, args):
        """Handle discography browse and download mode."""
        print_header(f"{PROJECT_NAME} - Discography Browse")
        
        # Search for artist releases
        print_info(f"Searching discography for: {print_artist(args.artist)}")
        if args.year:
            print_info(f"Filtering by year: {Colors.cyan(str(args.year))}")
        
        releases = self.musicbrainz_client.search_artist_releases(args.artist, args.year)
        
        if not releases:
            print_error(ERROR_MESSAGES["NO_RESULTS"])
            return
        
        # Display releases grouped by year
        self._display_discography(releases)
        
        if args.no_download:
            print_info("Discography browse completed. Use without --no-download to download releases.")
            return
        
        # Get user selection for releases to download
        selected_releases = self._get_release_selection(releases)
        
        if not selected_releases:
            print_warning("No releases selected for download.")
            return
        
        # Download selected releases
        self._download_selected_releases(selected_releases, args.quality)
    
    def _display_discography(self, releases: List[MusicBrainzSong]):
        """Display discography grouped by year with global numbering."""
        print_header("DISCOGRAPHY")
        print_separator(UI_CONFIG["SEPARATOR_LENGTH"])
        
        # Group releases by year
        releases_by_year = {}
        for release in releases:
            year = release.release_date[:4] if release.release_date and len(release.release_date) >= 4 else "Unknown Year"
            if year not in releases_by_year:
                releases_by_year[year] = []
            releases_by_year[year].append(release)
        
        # Sort years in descending order
        sorted_years = sorted(releases_by_year.keys(), reverse=True)
        
        # Create ordered list that matches the display order
        ordered_releases = []
        global_counter = 1
        
        for year in sorted_years:
            year_releases = releases_by_year[year]
            print(f"\n{Colors.bold(Colors.cyan(year))}:")
            
            for release in year_releases:
                # Show global number, album, and key details
                print(f"  {Colors.bold(Colors.white(f'{global_counter:2d}'))}. {print_album(release.album)}")
                print(f"      Artist: {print_artist(release.artist)}")
                if release.release_date and len(release.release_date) > 4:
                    print(f"      Release Date: {Colors.cyan(release.release_date)}")
                print(f"      Score: {print_score(release.score)}")
                print()
                
                # Add to ordered list in display order
                ordered_releases.append(release)
                global_counter += 1
        
        print_separator(UI_CONFIG["SEPARATOR_LENGTH"])
        
        # Store the ordered releases for selection
        self._ordered_releases = ordered_releases
    
    def _get_release_selection(self, releases: List[MusicBrainzSong]) -> List[MusicBrainzSong]:
        """Get user selection for releases to download with intuitive interface."""
        # Use the ordered releases that match the display order
        ordered_releases = getattr(self, '_ordered_releases', releases)
        
        print_header("RELEASE SELECTION")
        print_info(f"Found {Colors.bold(str(len(ordered_releases)))} releases. Choose how to select:")
        print()
        
        # Show selection options
        print(f"{Colors.bold(Colors.white('1'))}. {Colors.cyan('Single release')} - Enter one number")
        print(f"{Colors.bold(Colors.white('2'))}. {Colors.cyan('Multiple releases')} - Enter numbers separated by commas (e.g., 1,3,5)")
        print(f"{Colors.bold(Colors.white('3'))}. {Colors.cyan('Range of releases')} - Enter range (e.g., 1-5)")
        print(f"{Colors.bold(Colors.white('4'))}. {Colors.cyan('All releases')} - Download everything")
        print(f"{Colors.bold(Colors.white('5'))}. {Colors.red('Cancel')} - Exit without downloading")
        print()
        
        while True:
            choice = input(f"{Colors.bold('Choose selection mode (1-5): ')}").strip()
            
            if choice == '1':
                return self._select_single_release(ordered_releases)
            elif choice == '2':
                return self._select_multiple_releases(ordered_releases)
            elif choice == '3':
                return self._select_range_releases(ordered_releases)
            elif choice == '4':
                return self._confirm_all_releases(ordered_releases)
            elif choice == '5':
                print_warning("Selection cancelled.")
                return []
            else:
                print_error("Invalid choice. Please enter 1, 2, 3, 4, or 5.")
    
    def _select_single_release(self, releases: List[MusicBrainzSong]) -> List[MusicBrainzSong]:
        """Select a single release."""
        while True:
            try:
                choice = input(f"{Colors.bold('Enter release number (1-{len(releases)}): ')}").strip()
                
                if choice.lower() in ['q', 'quit', 'cancel']:
                    return []
                
                num = int(choice)
                if 1 <= num <= len(releases):
                    selected = releases[num - 1]
                    print_success(f"Selected: {print_album(selected.album)} by {print_artist(selected.artist)}")
                    return [selected]
                else:
                    print_error(f"Please enter a number between 1 and {len(releases)}")
                    
            except ValueError:
                print_error("Please enter a valid number or 'q' to cancel")
    
    def _select_multiple_releases(self, releases: List[MusicBrainzSong]) -> List[MusicBrainzSong]:
        """Select multiple releases by comma-separated numbers."""
        while True:
            try:
                choice = input(f"{Colors.bold('Enter release numbers (e.g., 1,3,5) or ranges (e.g., 1-3,5): ')}").strip()
                
                if choice.lower() in ['q', 'quit', 'cancel']:
                    return []
                
                # Parse both individual numbers and ranges
                numbers = set()
                parts = choice.split(',')
                
                for part in parts:
                    part = part.strip()
                    if '-' in part:
                        # Handle range (e.g., "1-5")
                        start, end = map(int, part.split('-'))
                        numbers.update(range(start, end + 1))
                    else:
                        # Handle single number
                        numbers.add(int(part))
                
                # Validate all numbers
                valid_numbers = [n for n in numbers if 1 <= n <= len(releases)]
                
                if len(valid_numbers) == len(numbers):
                    selected_releases = [releases[n - 1] for n in sorted(valid_numbers)]
                    
                    # Show confirmation
                    print_info(f"Selected {len(selected_releases)} releases:")
                    for i, release in enumerate(selected_releases, 1):
                        print(f"  {i}. {print_album(release.album)} by {print_artist(release.artist)}")
                    
                    confirm = input(f"\n{Colors.bold('Proceed with download? (y/n): ')}").strip().lower()
                    if confirm in ['y', 'yes']:
                        return selected_releases
                    else:
                        print_warning("Selection cancelled.")
                        return []
                else:
                    invalid = numbers - set(valid_numbers)
                    print_error(f"Invalid numbers: {', '.join(map(str, invalid))}. Available: 1-{len(releases)}")
                    
            except ValueError:
                print_error("Invalid format. Use numbers separated by commas (e.g., 1,3,5) or ranges (e.g., 1-3,5)")
    
    def _select_range_releases(self, releases: List[MusicBrainzSong]) -> List[MusicBrainzSong]:
        """Select a range of releases."""
        while True:
            try:
                choice = input(f"{Colors.bold('Enter range (e.g., 1-5): ')}").strip()
                
                if choice.lower() in ['q', 'quit', 'cancel']:
                    return []
                
                if '-' not in choice:
                    print_error("Please enter a range in format 'start-end' (e.g., 1-5)")
                    continue
                
                start, end = map(int, choice.split('-'))
                
                if start < 1 or end > len(releases) or start > end:
                    print_error(f"Invalid range. Please enter numbers between 1 and {len(releases)}")
                    continue
                
                selected_releases = releases[start - 1:end]
                
                # Show confirmation
                print_info(f"Selected releases {start}-{end} ({len(selected_releases)} releases):")
                for i, release in enumerate(selected_releases, start):
                    print(f"  {i}. {print_album(release.album)} by {print_artist(release.artist)}")
                
                confirm = input(f"\n{Colors.bold('Proceed with download? (y/n): ')}").strip().lower()
                if confirm in ['y', 'yes']:
                    return selected_releases
                else:
                    print_warning("Selection cancelled.")
                    return []
                    
            except ValueError:
                print_error("Invalid format. Please enter range as 'start-end' (e.g., 1-5)")
    
    def _confirm_all_releases(self, releases: List[MusicBrainzSong]) -> List[MusicBrainzSong]:
        """Confirm downloading all releases."""
        print_warning(f"This will download ALL {len(releases)} releases!")
        print_info("This may take a very long time and use significant disk space.")
        
        # Show a preview of what will be downloaded
        print(f"\n{Colors.bold('Preview of releases to download:')}")
        for i, release in enumerate(releases[:5], 1):  # Show first 5
            print(f"  {i}. {print_album(release.album)} by {print_artist(release.artist)}")
        
        if len(releases) > 5:
            print(f"  ... and {len(releases) - 5} more releases")
        
        while True:
            confirm = input(f"\n{Colors.bold(Colors.red('Are you sure you want to download ALL releases? (yes/no): '))}").strip().lower()
            
            if confirm in ['yes', 'y']:
                print_success(f"Confirmed! Will download all {len(releases)} releases.")
                return releases
            elif confirm in ['no', 'n']:
                print_warning("Download cancelled.")
                return []
            else:
                print_error("Please enter 'yes' or 'no'")
    
    def _download_selected_releases(self, releases: List[MusicBrainzSong], quality: str):
        """Download selected releases."""
        print(f"\n=== DOWNLOADING RELEASES ===")
        print(f"Releases to download: {len(releases)}")
        print(f"Quality: {quality}")
        print()
        
        total_downloaded = 0
        total_failed = 0
        
        for i, release in enumerate(releases, 1):
            print(f"\n--- Release {i}/{len(releases)}: {release.album} ---")
            
            # Get detailed release information
            release_info = self.musicbrainz_client.get_release_info(release.mbid)
            if not release_info:
                print(f"Failed to get details for: {release.album}")
                total_failed += 1
                continue
            
            # Display track listing
            print(f"Tracks in {release.album}:")
            for track in release_info.tracks:
                duration_str = f" ({track.duration})" if track.duration else ""
                print(f"  {track.position:2d}. {track.title}{duration_str}")
            
            # Ask if user wants to download all tracks or select specific ones
            print("\nDownload options:")
            print("1. Download all tracks")
            print("2. Select specific tracks")
            print("3. Skip this release")
            
            while True:
                choice = input("Choose option (1-3): ").strip()
                
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
                    print(f"Skipped: {release.album}")
                    break
                else:
                    print("Invalid choice. Please enter 1, 2, or 3.")
        
        # Final summary
        print(f"\n=== FINAL DOWNLOAD SUMMARY ===")
        print(f"Total tracks downloaded: {total_downloaded}")
        print(f"Total tracks failed: {total_failed}")
        print(f"Releases processed: {len(releases)}")
    
    def _download_release_tracks_silent(self, release_info: ReleaseInfo, track_numbers: List[int], quality: str) -> tuple[int, int]:
        """Download tracks silently and return counts."""
        downloaded_count = 0
        failed_count = 0
        
        for track_num in track_numbers:
            # Find the track
            track = None
            for t in release_info.tracks:
                if t.position == track_num:
                    track = t
                    break
            
            if not track:
                failed_count += 1
                continue
            
            # Search YouTube for this track
            search_query = f"{track.artist} {track.title}"
            try:
                youtube_client = YouTubeClient(search_query, max_results=1)
                videos = youtube_client.videos
                
                if not videos:
                    failed_count += 1
                    continue
                
                # Use the first (best) result
                selected_video = videos[0]
                
                # Create metadata for download
                metadata_dict = {
                    'title': track.title,
                    'artist': track.artist,
                    'album': release_info.title,
                    'year': int(release_info.release_date[:4]) if release_info.release_date and len(release_info.release_date) >= 4 else None
                }
                
                # Download the track
                youtube_url = f"https://www.youtube.com/watch?v={selected_video.video_id}"
                
                if quality == 'audio':
                    downloaded_path = self.downloader.download_high_quality_audio(youtube_url, metadata=metadata_dict)
                else:
                    downloaded_path = self.downloader.download(youtube_url, quality=quality, audio_only=(quality == 'audio'), metadata=metadata_dict)
                
                if downloaded_path:
                    downloaded_count += 1
                else:
                    failed_count += 1
                    
            except Exception:
                failed_count += 1
        
        return downloaded_count, failed_count
    
    def _download_track_with_metadata_selection(self, song_data: SongData, selected_video: YouTubeVideo, metadata: MusicBrainzSong, quality: str) -> Optional[Path]:
        """Download a track with metadata selection (for release downloads)."""
        video_id = selected_video.video_id
        if not video_id:
            print_error("No video ID found.")
            return None
        
        youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        video_title = selected_video.title or 'Unknown'
        
        print(f"  Preparing download for: {print_title(video_title)}")
        
        # Create metadata merger and gather metadata from all sources
        metadata_merger = MetadataMerger()
        metadata_merger.add_songdata_metadata(song_data)
        metadata_merger.add_youtube_metadata(selected_video)
        metadata_merger.add_musicbrainz_metadata(metadata)
        
        # Search additional sources if available
        metadata_merger.search_all_sources(song_data.title, song_data.artist, song_data.album)
        
        # Let user choose metadata before download
        print(f"  Metadata sources found: {len(metadata_merger.sources)}")
        selected_metadata = metadata_merger.get_user_metadata_selection()
        metadata_merger.set_final_metadata(selected_metadata)
        
        # Create metadata dictionary for downloader
        metadata_dict = {
            'title': selected_metadata.title,
            'artist': selected_metadata.artist,
            'album': selected_metadata.album,
            'year': selected_metadata.year,
            'genre': selected_metadata.genre
        }
        
        # Download based on quality preference
        if quality == 'audio':
            downloaded_path = self.downloader.download_high_quality_audio(youtube_url, metadata=metadata_dict)
        else:
            downloaded_path = self.downloader.download(youtube_url, quality=quality, audio_only=(quality == 'audio'), metadata=metadata_dict)
        
        if downloaded_path:
            # Apply metadata
            success = metadata_merger.apply_metadata_to_file(downloaded_path)
            if success:
                print(f"  ✓ Metadata applied successfully")
            else:
                print(f"  ⚠ Metadata application failed")
        
        return downloaded_path
    
    def _display_search_results(self, results: List[MusicBrainzSong], search_type: str):
        """Display search results in a formatted way."""
        print_header(f"{search_type} SEARCH RESULTS")
        print_separator(UI_CONFIG["SEPARATOR_LENGTH"])
        
        for i, result in enumerate(results, 1):
            print(f"{Colors.bold(Colors.white(str(i)))}. {print_title(result.title or result.album)}")
            print(f"   Artist: {print_artist(result.artist)}")
            if result.album and result.title:  # Only show album if we have a title
                print(f"   Album: {print_album(result.album)}")
            if result.release_date:
                print(f"   Release Date: {Colors.cyan(result.release_date)}")
            print(f"   Score: {print_score(result.score)}")
            print()
    
    def _get_user_selection(self, results: List[MusicBrainzSong]) -> Optional[MusicBrainzSong]:
        """Get user selection from search results with better interface."""
        if not results:
            return None
        
        print_info(f"Select a result (1-{len(results)}) or 'q' to quit:")
        
        while True:
            try:
                choice = input(f"{Colors.bold('Your choice: ')}").strip()
                
                if choice.lower() in ['q', 'quit', 'exit']:
                    print_warning("Selection cancelled.")
                    return None
                
                choice_num = int(choice)
                if 1 <= choice_num <= len(results):
                    selected = results[choice_num - 1]
                    print_success(f"Selected: {print_title(selected.title or selected.album)} by {print_artist(selected.artist)}")
                    return selected
                else:
                    print_error(f"Please enter a number between 1 and {len(results)}")
                    
            except ValueError:
                print_error("Please enter a valid number or 'q' to quit")
    
    def _search_and_download_recording(self, selected_song: MusicBrainzSong, quality: str):
        """Search YouTube and download a recording."""
        # Create search query
        search_query = f"{selected_song.artist} {selected_song.title}"
        
        print_header("SEARCHING YOUTUBE")
        print_info(f"Search query: {Colors.cyan(search_query)}")
        
        try:
            # Search YouTube
            youtube_client = YouTubeClient(search_query, max_results=YOUTUBE_CONFIG["MAX_RESULTS"])
            videos = youtube_client.videos
            
            if not videos:
                print_error(ERROR_MESSAGES["NO_RESULTS"])
                return
            
            # Display YouTube results
            self._display_youtube_results(videos)
            
            # Get video selection
            selected_video = self._get_video_selection(videos)
            if not selected_video:
                print_warning("No video selected for download.")
                return
            
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
            print_error(f"Error searching YouTube: {e}")
    
    def _search_and_download_release(self, selected_release: MusicBrainzSong, quality: str, tracks: Optional[str]):
        """Search and download tracks from a release."""
        print(f"\n=== RELEASE DOWNLOAD ===")
        print(f"Release: {selected_release.album} by {selected_release.artist}")
        
        # Get detailed release information with tracks
        release_info = self.musicbrainz_client.get_release_info(selected_release.mbid)
        if not release_info:
            print("Failed to get release details.")
            return
        
        # Display track listing
        self._display_track_listing(release_info)
        
        # Parse track selection
        track_numbers = self._parse_track_selection(tracks, len(release_info.tracks))
        
        if not track_numbers:
            print("No tracks selected for download.")
            return
        
        # Download selected tracks
        self._download_release_tracks(release_info, track_numbers, quality)
    
    def _display_track_listing(self, release_info: ReleaseInfo):
        """Display the track listing for a release."""
        print_header("TRACK LISTING")
        print(f"Release: {print_album(release_info.title)} by {print_artist(release_info.artist)}")
        if release_info.release_date:
            print(f"Release Date: {Colors.cyan(release_info.release_date)}")
        if release_info.genre:
            print(f"Genre: {Colors.magenta(release_info.genre)}")
        print_separator(UI_CONFIG["SEPARATOR_LENGTH"])
        
        for track in release_info.tracks:
            duration_str = f" ({print_duration(track.duration)})" if track.duration else ""
            print(f"{print_track_number(track.position)} {print_title(track.title)}{duration_str}")
            if track.artist != release_info.artist:
                print(f"    Artist: {print_artist(track.artist)}")
        print()
    
    def _parse_track_selection(self, tracks_arg: Optional[str], total_tracks: int) -> List[int]:
        """Parse track selection from command line argument or user input."""
        if tracks_arg:
            # Parse comma-separated track numbers
            try:
                track_numbers = [int(x.strip()) for x in tracks_arg.split(',')]
                # Validate track numbers
                valid_tracks = [t for t in track_numbers if 1 <= t <= total_tracks]
                if valid_tracks:
                    print(f"Selected tracks: {', '.join(map(str, valid_tracks))}")
                    return valid_tracks
                else:
                    print(f"Invalid track numbers. Available tracks: 1-{total_tracks}")
                    return []
            except ValueError:
                print("Invalid track selection format. Use comma-separated numbers (e.g., 1,3,5)")
                return []
        else:
            # Interactive track selection
            print("Select tracks to download:")
            print("Options:")
            print("  - Enter track numbers separated by commas (e.g., 1,3,5)")
            print("  - Enter 'all' to download all tracks")
            print("  - Enter 'q' to cancel")
            
            while True:
                choice = input("Your selection: ").strip()
                
                if choice.lower() == 'q':
                    return []
                
                if choice.lower() == 'all':
                    return list(range(1, total_tracks + 1))
                
                try:
                    track_numbers = [int(x.strip()) for x in choice.split(',')]
                    valid_tracks = [t for t in track_numbers if 1 <= t <= total_tracks]
                    
                    if len(valid_tracks) == len(track_numbers):
                        print(f"Selected tracks: {', '.join(map(str, valid_tracks))}")
                        return valid_tracks
                    else:
                        print(f"Some track numbers are invalid. Available tracks: 1-{total_tracks}")
                        continue
                        
                except ValueError:
                    print("Invalid format. Use comma-separated numbers (e.g., 1,3,5)")
                    continue
    
    def _download_release_tracks(self, release_info: ReleaseInfo, track_numbers: List[int], quality: str):
        """Download selected tracks from a release."""
        print(f"\n=== DOWNLOADING TRACKS ===")
        print(f"Release: {release_info.title} by {release_info.artist}")
        print(f"Tracks to download: {', '.join(map(str, track_numbers))}")
        print(f"Quality: {quality}")
        print()
        
        downloaded_count = 0
        failed_count = 0
        
        for track_num in track_numbers:
            # Find the track
            track = None
            for t in release_info.tracks:
                if t.position == track_num:
                    track = t
                    break
            
            if not track:
                print(f"Track {track_num} not found.")
                failed_count += 1
                continue
            
            print(f"Downloading track {track_num}: {track.title}")
            
            # Create song data for YouTube search
            song_data = SongData(
                title=track.title,
                artist=track.artist,
                album=release_info.title,
                release_year=int(release_info.release_date[:4]) if release_info.release_date and len(release_info.release_date) >= 4 else None
            )
            
            # Search YouTube for this track
            search_query = f"{track.artist} {track.title}"
            try:
                youtube_client = YouTubeClient(search_query, max_results=1)  # Only get the best match
                videos = youtube_client.videos
                
                if not videos:
                    print(f"  ✗ No YouTube results found for: {track.title}")
                    failed_count += 1
                    continue
                
                # Use the first (best) result
                selected_video = videos[0]
                
                # Create MusicBrainz song data for metadata merger
                musicbrainz_song = MusicBrainzSong(
                    title=track.title,
                    artist=track.artist,
                    album=release_info.title,
                    release_date=release_info.release_date,
                    mbid=track.mbid or "",
                    score=100
                )
                
                # Use the new metadata selection approach
                downloaded_path = self._download_track_with_metadata_selection(
                    song_data, selected_video, musicbrainz_song, quality
                )
                
                if downloaded_path:
                    print(f"  ✓ Downloaded: {downloaded_path}")
                    downloaded_count += 1
                else:
                    print(f"  ✗ Download failed")
                    failed_count += 1
                    
            except Exception as e:
                print(f"  ✗ Error downloading {track.title}: {e}")
                failed_count += 1
        
        # Summary
        print(f"\n=== DOWNLOAD SUMMARY ===")
        print(f"Successfully downloaded: {downloaded_count} tracks")
        print(f"Failed downloads: {failed_count} tracks")
        print(f"Total tracks processed: {len(track_numbers)}")
    
    def _display_youtube_results(self, videos: List[YouTubeVideo]):
        """Display YouTube search results."""
        print_header("YOUTUBE SEARCH RESULTS")
        print_separator(UI_CONFIG["SEPARATOR_LENGTH"])
        
        for i, video in enumerate(videos, 1):
            print(f"{Colors.bold(Colors.white(str(i)))}. {print_title(video.title or 'No title')}")
            print(f"   Channel: {print_channel(video.channel or 'Unknown')}")
            if video.duration:
                print(f"   Duration: {print_duration(video.duration)}")
            if video.views:
                print(f"   Views: {print_views(video.views)}")
            if video.publish_time:
                print(f"   Published: {Colors.cyan(video.publish_time)}")
            
            # Construct full YouTube URL
            if video.video_id:
                youtube_url = f"https://www.youtube.com/watch?v={video.video_id}"
                print(f"   URL: {Colors.blue(youtube_url)}")
            
            print()
    
    def _get_video_selection(self, videos: List[YouTubeVideo]) -> Optional[YouTubeVideo]:
        """Get user selection from YouTube video results with better interface."""
        if not videos:
            return None
        
        print_info(f"Select a video to download (1-{len(videos)}) or 'q' to skip:")
        
        while True:
            try:
                choice = input(f"{Colors.bold('Your choice: ')}").strip()
                
                if choice.lower() in ['q', 'quit', 'skip', 'exit']:
                    print_warning("Video selection skipped.")
                    return None
                
                choice_num = int(choice)
                if 1 <= choice_num <= len(videos):
                    selected = videos[choice_num - 1]
                    print_success(f"Selected: {print_title(selected.title or 'No title')} from {print_channel(selected.channel or 'Unknown')}")
                    return selected
                else:
                    print_error(f"Please enter a number between 1 and {len(videos)}")
                    
            except ValueError:
                print_error("Please enter a valid number or 'q' to skip")
    
    def _download_video(self, song_data: SongData, selected_video: YouTubeVideo, metadata: MusicBrainzSong, quality: str):
        """Download the selected YouTube video."""
        video_id = selected_video.video_id
        if not video_id:
            print_error("No video ID found.")
            return
        
        youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        video_title = selected_video.title or 'Unknown'
        
        print_header("PREPARING DOWNLOAD")
        print(f"Title: {print_title(video_title)}")
        print(f"URL: {Colors.blue(youtube_url)}")
        print(f"Quality: {Colors.cyan(quality)}")
        
        # Create metadata merger and gather metadata from all sources
        metadata_merger = MetadataMerger()
        metadata_merger.add_songdata_metadata(song_data)
        metadata_merger.add_youtube_metadata(selected_video)
        metadata_merger.add_musicbrainz_metadata(metadata)
        
        # Search additional sources if available
        metadata_merger.search_all_sources(song_data.title, song_data.artist, song_data.album)
        
        # Let user choose metadata before download
        print_header("METADATA SELECTION")
        print_info("Please review and select the metadata you want to use for this download:")
        
        selected_metadata = metadata_merger.get_user_metadata_selection()
        metadata_merger.set_final_metadata(selected_metadata)
        
        # Confirm download with selected metadata
        print_header("DOWNLOAD CONFIRMATION")
        print(f"Title: {print_title(selected_metadata.title or 'N/A')}")
        print(f"Artist: {print_artist(selected_metadata.artist or 'N/A')}")
        print(f"Album: {print_album(selected_metadata.album or 'N/A')}")
        print(f"Year: {selected_metadata.year or 'N/A'}")
        print(f"Quality: {Colors.cyan(quality)}")
        
        confirm = input(f"\nProceed with download? (y/n): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print_warning("Download cancelled by user.")
            return
        
        # Create metadata dictionary for downloader
        metadata_dict = {
            'title': selected_metadata.title,
            'artist': selected_metadata.artist,
            'album': selected_metadata.album,
            'year': selected_metadata.year,
            'genre': selected_metadata.genre
        }
        
        print_header("DOWNLOADING")
        
        # Download based on quality preference
        if quality == 'audio':
            downloaded_path = self.downloader.download_high_quality_audio(youtube_url, metadata=metadata_dict)
        else:
            downloaded_path = self.downloader.download(youtube_url, quality=quality, audio_only=(quality == 'audio'), metadata=metadata_dict)
        
        if downloaded_path:
            print_success(f"Download completed: {Colors.green(str(downloaded_path))}")
            
            # Apply metadata
            success = metadata_merger.apply_metadata_to_file(downloaded_path)
            if success:
                print_success("Metadata applied successfully")
            else:
                print_error("Failed to apply metadata")
        else:
            print_error("Download failed")
