"""
YouTube Downloader Module
A module to download YouTube videos using yt-dlp.
"""

import os
import subprocess
import json
from typing import Dict, Any, Optional, List, Callable, Tuple
from pathlib import Path
from ..core.config import DOWNLOAD_CONFIG
from ..utils.colors import Colors
from ..utils.error_formatter import ErrorFormatter
from .yt_dlp_manager import YtDlpManager
from .cookie_manager import CookieManager
from .path_utils import PathUtils
from .download_strategies import DownloadStrategies
from ..core.retry import SubprocessRetryStrategy
from .progress_tracker import ProgressTracker
from .file_splitter import FileSplitter


class YouTubeDownloader:
    """YouTube video downloader using yt-dlp."""

    def __init__(self, download_dir: Optional[str] = None):
        self.download_dir = Path(download_dir or DOWNLOAD_CONFIG["DEFAULT_DIR"])
        self.download_dir.mkdir(exist_ok=True)

        self.default_quality = DOWNLOAD_CONFIG["DEFAULT_QUALITY"]
        self.audio_format = DOWNLOAD_CONFIG["AUDIO_FORMAT"]
        self.timeout = DOWNLOAD_CONFIG["TIMEOUT"]

        # Initialize helper modules
        self.yt_dlp_manager = YtDlpManager()
        self.cookie_manager = CookieManager()
        self.path_utils = PathUtils()
        self.download_strategies = DownloadStrategies(self.cookie_manager)

        # Retry configuration for robust downloads
        self.max_retries = 5
        self.base_retry_delay = 2.0
        self.max_retry_delay = 60.0
        self.max_total_time = 1800

        # Initialize retry strategy
        self.retry_strategy = SubprocessRetryStrategy(
            max_retries=self.max_retries,
            base_delay=self.base_retry_delay,
            max_delay=self.max_retry_delay,
            max_total_time=self.max_total_time,
            timeout=self.timeout,
            progress_parser=ProgressTracker.parse_progress_line,
        )

        # yt-dlp is checked by configuration validation and updated only when
        # explicitly requested or when a signature failure requires it.

    def update_yt_dlp(self) -> bool:
        """
        Manually update yt-dlp.

        Call this method explicitly if a diagnostic recommends an update.

        Returns:
            True if update was successful, False otherwise
        """
        return self.yt_dlp_manager.update()

    def _try_get_video_info_with_client(self, url: str, client_type: str, operation_name: str,
                                        extra_args: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Try to get video info with a specific client type."""
        cmd = ['yt-dlp', '--dump-json', '--no-download', '--no-warnings']
        if client_type == 'android_music':
            cmd.extend(['--user-agent', 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                       '--extractor-args', 'youtube:player_client=android_music'])
        elif client_type == 'android':
            cmd.extend(['--user-agent', 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                       '--extractor-args', 'youtube:player_client=android'])
        elif client_type == 'web':
            cmd.extend(['--extractor-args', 'youtube:player_client=web'])
            if extra_args:
                cmd.extend(extra_args)
        cmd.append(url)

        try:
            result = self.retry_strategy.execute_with_progress(cmd, operation_name=operation_name, quiet=True)
            return json.loads(result.stdout)
        except Exception:
            return None

    def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Get video information with robust retry logic."""
        try:
            # Try android_music first (fastest, most reliable)
            result = self._try_get_video_info_with_client(url, 'android_music', f"getting video info for {url[:50]}")
            if result:
                return result

            # Try android client as fallback
            result = self._try_get_video_info_with_client(url, 'android', f"getting video info (android fallback) for {url[:50]}")
            if result:
                return result

            # Last resort: try web client with cookies
            cookie_browser = self.cookie_manager.get_cookie_browser()
            if cookie_browser:
                result = self._try_get_video_info_with_client(
                    url, 'web', f"getting video info (web with cookies) for {url[:50]}",
                    extra_args=['--cookies-from-browser', cookie_browser]
                )
                if result:
                    return result

            print(f"Error getting video info: Failed with all client types")
            return None
        except FileNotFoundError:
            print("Error: yt-dlp command not found. Please install it with: pip install yt-dlp")
            return None
        except subprocess.TimeoutExpired:
            print("Error: yt-dlp command timed out while getting video info")
            return None
        except Exception as e:
            print(f"Unexpected error getting video info: {e}")
            return None

    def get_video_chapters(self, url: str) -> Optional[List[Dict[str, Any]]]:
        """
        Extract chapters from a YouTube video.
        Returns list of chapters with start_time and title, or None if no chapters.
        """
        try:
            video_info = self.get_video_info(url)
            if not video_info:
                return None

            # yt-dlp provides chapters in the 'chapters' field
            chapters = video_info.get('chapters', [])
            if not chapters:
                return None

            # Keep explicit end times when yt-dlp provides them. They are needed
            # to validate chapter durations before splitting an album.
            formatted_chapters = []
            for chapter in chapters:
                start_time = chapter.get('start_time', 0)
                end_time = chapter.get('end_time')
                title = chapter.get('title', '')
                formatted_chapters.append({
                    'start_time': start_time,
                    'end_time': end_time,
                    'title': title
                })

            return formatted_chapters if formatted_chapters else None

        except Exception as e:
            print(f"Error extracting chapters: {e}")
            return None

    def split_video_into_tracks(
        self,
        video_path: Path,
        track_timestamps: List[Dict[str, Any]],
        output_dir: Path,
        metadata_list: List[Dict[str, Any]],
        progress_callback: Optional[Callable] = None
    ) -> List[Path]:
        """
        Split a full album video into individual tracks using ffmpeg.

        Args:
            video_path: Path to the full album video file
            track_timestamps: List of dicts with 'start_time' (seconds) and 'end_time' (seconds) for each track
            output_dir: Directory to save split tracks
            metadata_list: List of metadata dicts for each track (must match track_timestamps length)
            progress_callback: Optional callback for progress updates

        Returns:
            List of paths to the split track files
        """
        return FileSplitter.split_video_into_tracks(
            video_path,
            track_timestamps,
            output_dir,
            metadata_list,
            progress_callback
        )

    _AUDIO_EXTENSIONS = ['.mp3', '.m4a', '.ogg', '.opus', '.flac', '.wav', '.aac', '.webm']
    _SYSTEM_FILES = {'.DS_Store', '.Thumbs.db', 'desktop.ini'}

    def _get_expected_base(self, metadata: Optional[Dict[str, Any]]) -> Optional[str]:
        """Get expected filename base from metadata."""
        if not metadata or not metadata.get('title'):
            return None
        title = self.path_utils.sanitize_filename(metadata['title'])
        track_number = metadata.get('track_number')
        return f"{track_number:02d} - {title}" if track_number else title

    def _get_audio_files(self, download_dir: Path) -> List[Path]:
        """Get all audio files in directory."""
        return [f for f in download_dir.glob("*") if f.is_file() and f.suffix.lower() in self._AUDIO_EXTENSIONS and f.name not in self._SYSTEM_FILES]

    def _find_file_by_metadata(self, download_dir: Path, metadata: Optional[Dict[str, Any]],
                               existing_files: Optional[set] = None, check_exact: bool = True) -> Optional[Path]:
        """
        Unified method to find files by metadata.

        Args:
            download_dir: Directory to search
            metadata: Metadata dict with title/track_number
            existing_files: Optional set of existing file names to exclude
            check_exact: If True, check for exact matches first; if False, only check new files

        Returns:
            Path to found file, or None
        """
        expected_base = self._get_expected_base(metadata)
        if not expected_base:
            return None

        audio_files = self._get_audio_files(download_dir)

        if check_exact:
            # Check for exact matches
            for ext in self._AUDIO_EXTENSIONS:
                potential_file = download_dir / f"{expected_base}{ext}"
                if potential_file.exists() and potential_file.is_file():
                    return potential_file

            # Check for partial matches
            partial = [f for f in audio_files if f.stem.startswith(expected_base)]
            if partial:
                return partial[0]
        else:
            # Find from new files (not in existing_files)
            if existing_files:
                new_files = [f for f in audio_files if f.name not in existing_files]
            else:
                new_files = audio_files

            if new_files:
                matching = [f for f in new_files if f.stem == expected_base]
                if matching:
                    return max(matching, key=os.path.getctime)
                partial = [f for f in new_files if f.stem.startswith(expected_base)]
                if partial:
                    return max(partial, key=os.path.getctime)
                return max(new_files, key=os.path.getctime)

        return None

    def _check_existing_file(self, download_dir: Path, metadata: Optional[Dict[str, Any]],
                            progress_callback: Optional[Callable], quiet: bool) -> Optional[Tuple[Path, bool]]:
        """Check if file already exists and return it if found."""
        existing_file = self._find_file_by_metadata(download_dir, metadata, check_exact=True)
        if existing_file:
            if progress_callback:
                progress_callback({'percent': 100.0, 'status': 'completed', 'speed': None, 'eta': None})
            if not quiet:
                print(f"{Colors.yellow('⏭')} Skipping download - file already exists: {Colors.blue(str(existing_file))}")
            return existing_file, True
        return None

    def _find_downloaded_file(self, download_dir: Path, existing_files: set, metadata: Optional[Dict[str, Any]]) -> Optional[Path]:
        """Find the downloaded file from new files."""
        return self._find_file_by_metadata(download_dir, metadata, existing_files, check_exact=False)

    def _format_error_message(self, error: Exception, strategy_num: int, quiet: bool,
                             progress_callback: Optional[Callable], has_next: bool) -> str:
        """Format error message for display."""
        return ErrorFormatter.format_strategy_error(error, strategy_num, quiet, progress_callback, has_next)

    def _execute_download_strategy(self, strategy: Callable, strategy_num: int, url: str, quality: str,
                                   audio_only: bool, output_template: str, download_dir: Path,
                                   metadata: Optional[Dict[str, Any]], progress_callback: Optional[Callable],
                                   quiet: bool, total_strategies: int) -> Tuple[Optional[Path], Optional[str]]:
        """Execute a single download strategy and return result."""
        if not quiet and not progress_callback:
            try:
                from rich.console import Console
                Console().print(f"[blue]Trying strategy [bold white]{strategy_num}[/bold white]...[/blue]")
            except ImportError:
                print(f"Trying strategy {Colors.bold(Colors.white(str(strategy_num)))}...")

        cmd = strategy(url, quality, audio_only, output_template)
        existing_files = {f.name for f in self._get_audio_files(download_dir)}

        try:
            result = self.retry_strategy.execute_with_progress(cmd, progress_callback=progress_callback,
                                                              quiet=quiet, operation_name=f"download (strategy {strategy_num})")
        except Exception as e:
            return None, self._format_error_message(e, strategy_num, quiet, progress_callback, strategy_num < total_strategies)

        downloaded_file = self._find_downloaded_file(download_dir, existing_files, metadata)
        if downloaded_file:
            if not quiet and not progress_callback:
                try:
                    from rich.console import Console
                    Console().print(f"[bold green]✓[/bold green] Success with strategy {strategy_num}")
                except ImportError:
                    print(f"{Colors.green('✅')} Success with strategy {strategy_num}")
            return downloaded_file, None

        error_msg = (result.stderr if hasattr(result, 'stderr') and result.stderr
                    else "Download completed but no file was created")
        self._format_error_message(Exception(error_msg), strategy_num, quiet, progress_callback, strategy_num < total_strategies)
        return None, error_msg

    def download(self, url: str, quality: str = "bestaudio",
                      audio_only: bool = True, metadata: Optional[Dict[str, Any]] = None,
                      quiet: bool = False, progress_callback: Optional[Callable] = None) -> Tuple[Optional[Path], bool]:
        try:
            download_dir = self.path_utils.create_organized_path(self.download_dir, metadata)

            # Create filename template
            expected_base = self._get_expected_base(metadata)
            filename_template = f"{expected_base}.%(ext)s" if expected_base else "%(title)s.%(ext)s"
            output_template = str(download_dir / filename_template)

            # Check if file already exists
            existing_result = self._check_existing_file(download_dir, metadata, progress_callback, quiet)
            if existing_result:
                return existing_result

            # Print download info
            if not quiet:
                print(f"Downloading: {Colors.blue(url)}")
                print(f"Quality: {Colors.cyan(quality)}")
                print(f"Audio only: {Colors.cyan(str(audio_only))}")
                print(f"Save location: {Colors.blue(str(download_dir))}")
                if metadata:
                    artist = metadata.get('artist', 'Unknown')
                    album = metadata.get('album', 'Unknown')
                    year = metadata.get('year', 'Unknown Year')
                    title = metadata.get('title', 'Unknown Title')
                    print(f"Organized as: {Colors.green(artist)}/{Colors.yellow(album)} ({Colors.cyan(str(year))})/{Colors.white(title)}")
                print()

            # Try strategies
            strategies = self.download_strategies.get_all_strategies()
            last_strategy_error = None

            for i, strategy in enumerate(strategies, 1):
                downloaded_file, error_msg = self._execute_download_strategy(
                    strategy, i, url, quality, audio_only, output_template,
                    download_dir, metadata, progress_callback, quiet, len(strategies)
                )

                if downloaded_file:
                    return downloaded_file, False

                if error_msg:
                    last_strategy_error = error_msg
                    if i < len(strategies):
                        continue
                    else:
                        raise Exception(f"All download strategies failed. Last error: {last_strategy_error[:200]}")

            # All strategies failed
            final_error = last_strategy_error or "All strategies failed without creating files"
            raise Exception(f"All download strategies failed. {final_error[:200]}")

        except Exception as e:
            error_msg = ErrorFormatter.format_download_error(e, url)
            raise Exception(f"Error downloading video: {error_msg}") from e

    def download_high_quality_audio(self, url: str, metadata: Optional[Dict[str, Any]] = None,
                                     quiet: bool = False, progress_callback: Optional[Callable] = None) -> Tuple[Optional[Path], bool]:
        """
        Download high-quality audio from YouTube video.

        Args:
            url: YouTube video URL
            metadata: Optional metadata for organized file structure
            quiet: If True, suppress console output (for Rich UI)
            progress_callback: Optional callback function for progress updates

        Returns:
            Tuple of (Path to downloaded audio file or None if failed, bool indicating if file already existed)
        """
        return self.download(url, quality="bestaudio", audio_only=True, metadata=metadata,
                           quiet=quiet, progress_callback=progress_callback)

    def _parse_playlist_output(self, stdout: str) -> List[Dict[str, Any]]:
        """Parse playlist output from yt-dlp JSON lines."""
        videos = []
        output_lines = stdout.strip().split('\n')

        if output_lines and output_lines[0].strip():
            for line in output_lines:
                if line.strip():
                    try:
                        video_info = json.loads(line)
                        video_id = video_info.get('id') or video_info.get('url', '')
                        if not video_id:
                            continue

                        videos.append({
                            'title': video_info.get('title', ''),
                            'url': video_info.get('url', ''),
                            'id': video_id,
                            'playlist_index': video_info.get('playlist_index', video_info.get('playlist_auto_number', 0)),
                            'duration': video_info.get('duration'),
                            'webpage_url': video_info.get('webpage_url', video_info.get('url', ''))
                        })
                    except json.JSONDecodeError:
                        continue

        return videos

    def get_playlist_info(self, url: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get information about videos in a YouTube playlist.

        Args:
            url: YouTube playlist URL

        Returns:
            List of video information dicts with 'title', 'url', 'playlist_index', 'id', etc.
        """
        # Try with --flat-playlist first (faster, less info)
        try:
            cmd = [
                'yt-dlp', '--dump-json', '--flat-playlist', '--no-download', '--no-warnings',
                '--user-agent', 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                '--extractor-args', 'youtube:player_client=android_music',
                url
            ]

            result = self.retry_strategy.execute_with_progress(
                cmd, operation_name=f"getting playlist info for {url[:50]}", quiet=True
            )

            videos = self._parse_playlist_output(result.stdout)
            if videos:
                return videos
        except subprocess.CalledProcessError as e:
            error_msg = (e.stderr or '').lower()
            if 'playlist does not exist' in error_msg or 'does not exist' in error_msg:
                return None
        except (subprocess.TimeoutExpired, Exception):
            pass

        # Fallback: Try without --flat-playlist
        try:
            cmd = [
                'yt-dlp', '--dump-json', '--no-download', '--no-warnings', '--playlist-end', '50',
                '--user-agent', 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                '--extractor-args', 'youtube:player_client=android',
                url
            ]

            result = self.retry_strategy.execute_with_progress(
                cmd, operation_name=f"getting playlist info (fallback) for {url[:50]}", quiet=True
            )

            videos = self._parse_playlist_output(result.stdout)
            if videos:
                return videos
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, Exception):
            return None

        return None

    def download_playlist(self, url: str, quality: str = "bestaudio") -> List[str]:
        """
        Download a YouTube playlist.

        Args:
            url: YouTube playlist URL
            quality: Video quality preference

        Returns:
            List of paths to downloaded files
        """
        try:
            cmd = [
                'yt-dlp',
                '-o', str(self.download_dir / "%(playlist_index)s - %(title)s.%(ext)s"),
                '-f', quality,
                url
            ]

            print(f"Downloading playlist: {Colors.blue(url)}")
            print(f"Quality: {Colors.cyan(quality)}")
            print(f"Save location: {Colors.blue(str(self.download_dir))}")
            print()

            subprocess.run(cmd, check=True)

            # Return list of downloaded files
            downloaded_files = list(self.download_dir.glob("*"))
            return [str(f) for f in downloaded_files]

        except subprocess.CalledProcessError as e:
            print(f"Playlist download failed: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error during playlist download: {e}")
            return []

    def get_available_formats(self, url: str) -> List[Dict[str, Any]]:
        """
        Get available formats for a video.

        Args:
            url: YouTube video URL

        Returns:
            List of available formats
        """
        try:
            cmd = [
                'yt-dlp',
                '--list-formats',
                url
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Parse the output to extract format information
            formats = []
            lines = result.stdout.split('\n')

            for line in lines:
                if 'format code' in line.lower() or 'extension' in line.lower():
                    continue
                if line.strip() and ' ' in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        formats.append({
                            'format_code': parts[0],
                            'extension': parts[1],
                            'resolution': parts[2] if len(parts) > 2 else 'unknown',
                            'note': ' '.join(parts[3:]) if len(parts) > 3 else ''
                        })

            return formats

        except subprocess.CalledProcessError as e:
            print(f"Error getting formats: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error: {e}")
            return []
