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
from .yt_dlp_manager import YtDlpManager
from .cookie_manager import CookieManager
from .path_utils import PathUtils
from .download_strategies import DownloadStrategies
from .retry_handler import RetryHandler
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
        
        # Initialize retry handler
        self.retry_handler = RetryHandler(
            max_retries=self.max_retries,
            base_retry_delay=self.base_retry_delay,
            max_retry_delay=self.max_retry_delay,
            max_total_time=self.max_total_time,
            timeout=self.timeout,
            yt_dlp_manager=self.yt_dlp_manager
        )
        
        # Check and update yt-dlp if needed
        self.yt_dlp_manager.ensure_updated()
    
    def update_yt_dlp(self) -> bool:
        """
        Manually update yt-dlp.
        
        Call this method if you're experiencing signature extraction errors
        and the automatic update didn't work.
        
        Returns:
            True if update was successful, False otherwise
        """
        return self.yt_dlp_manager.update()
    
    def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Get video information with robust retry logic."""
        try:
            cmd = [
                'yt-dlp',
                '--dump-json',
                '--no-download',
                '--no-warnings',
                url
            ]
            
            # Use android_music client first (fastest, most reliable)
            cmd.extend([
                '--user-agent', 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                '--extractor-args', 'youtube:player_client=android_music'
            ])
            
            # Use robust retry wrapper
            result = self.retry_handler.run_with_retry(
                cmd,
                operation_name=f"getting video info for {url[:50]}",
                quiet=True
            )
            return json.loads(result.stdout)
            
        except subprocess.CalledProcessError as e:
            error_output = e.stderr if e.stderr else (e.stdout if e.stdout else str(e))
            # If android_music fails, try android client as fallback
            if "Requested format is not available" in error_output or "not available" in error_output.lower():
                try:
                    cmd = [
                        'yt-dlp',
                        '--dump-json',
                        '--no-download',
                        '--no-warnings',
                        '--user-agent', 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                        '--extractor-args', 'youtube:player_client=android',
                        url
                    ]
                    result = self.retry_handler.run_with_retry(
                        cmd,
                        operation_name=f"getting video info (android fallback) for {url[:50]}",
                        quiet=True
                    )
                    return json.loads(result.stdout)
                except Exception:
                    pass
            
            # Last resort: try web client with cookies
            cookie_browser = self.cookie_manager.get_cookie_browser()
            if cookie_browser:
                try:
                    cmd = [
                        'yt-dlp',
                        '--dump-json',
                        '--no-download',
                        '--no-warnings',
                        '--extractor-args', 'youtube:player_client=web',
                        '--cookies-from-browser', cookie_browser,
                        url
                    ]
                    result = self.retry_handler.run_with_retry(
                        cmd,
                        operation_name=f"getting video info (web with cookies) for {url[:50]}",
                        quiet=True
                    )
                    return json.loads(result.stdout)
                except Exception:
                    pass
            
            print(f"Error getting video info: {error_output[:200]}")
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
            
            # Format chapters: [{'start_time': seconds, 'title': 'Chapter Title'}, ...]
            formatted_chapters = []
            for chapter in chapters:
                start_time = chapter.get('start_time', 0)
                title = chapter.get('title', '')
                formatted_chapters.append({
                    'start_time': start_time,
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
    
    def download(self, url: str, quality: str = "bestaudio", 
                      audio_only: bool = True, metadata: Optional[Dict[str, Any]] = None, 
                      quiet: bool = False, progress_callback: Optional[Callable] = None) -> Tuple[Optional[Path], bool]:
        try:
            # Determine download directory based on metadata
            download_dir = self.path_utils.create_organized_path(self.download_dir, metadata)
            
            # Create filename template based on metadata
            if metadata and metadata.get('title'):
                title = self.path_utils.sanitize_filename(metadata['title'])
                
                # Add track number prefix if available
                track_number = metadata.get('track_number')
                if track_number:
                    track_prefix = f"{track_number:02d} - "
                    filename_template = f"{track_prefix}{title}.%(ext)s"
                else:
                    filename_template = f"{title}.%(ext)s"
            else:
                filename_template = "%(title)s.%(ext)s"
            
            # Set output template
            output_template = str(download_dir / filename_template)
            
            # Check if file already exists before attempting download
            audio_extensions = ['.mp3', '.m4a', '.ogg', '.opus', '.flac', '.wav', '.aac', '.webm']
            system_files = {'.DS_Store', '.Thumbs.db', 'desktop.ini'}
            
            if metadata and metadata.get('title'):
                title = self.path_utils.sanitize_filename(metadata['title'])
                track_number = metadata.get('track_number')
                
                if track_number:
                    track_prefix = f"{track_number:02d} - "
                    expected_base = f"{track_prefix}{title}"
                else:
                    expected_base = title
                
                # Check for existing files matching the expected pattern
                for ext in audio_extensions:
                    potential_file = download_dir / f"{expected_base}{ext}"
                    if potential_file.exists() and potential_file.is_file():
                        if progress_callback:
                            progress_callback({
                                'percent': 100.0,
                                'status': 'completed',
                                'speed': None,
                                'eta': None
                            })
                        if not quiet:
                            print(f"{Colors.yellow('⏭')} Skipping download - file already exists: {Colors.blue(str(potential_file))}")
                        return potential_file, True
                
                # Also check for files with similar names
                existing_files = [
                    f for f in download_dir.glob(f"{expected_base}*")
                    if f.is_file() 
                    and f.suffix.lower() in audio_extensions
                    and f.name not in system_files
                ]
                
                if existing_files:
                    existing_file = existing_files[0]
                    if progress_callback:
                        progress_callback({
                            'percent': 100.0,
                            'status': 'completed',
                            'speed': None,
                            'eta': None
                        })
                    if not quiet:
                        print(f"{Colors.yellow('⏭')} Skipping download - file already exists: {Colors.blue(str(existing_file))}")
                    return existing_file, True
            
            # Only print download info if not in quiet mode
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
            
            # Try multiple strategies to bypass 403 errors
            strategies = self.download_strategies.get_all_strategies()
            
            for i, strategy in enumerate(strategies, 1):
                try:
                    if not quiet and not progress_callback:
                        try:
                            from rich.console import Console
                            console = Console()
                            console.print(f"[blue]Trying strategy [bold white]{i}[/bold white]...[/blue]")
                        except ImportError:
                            print(f"Trying strategy {Colors.bold(Colors.white(str(i)))}...")
                    
                    cmd = strategy(url, quality, audio_only, output_template)
                    
                    # List existing files BEFORE download to identify newly created files
                    existing_files = {
                        f.name for f in download_dir.glob("*")
                        if f.is_file() and f.name not in system_files
                    }
                    
                    # Run download with robust retry logic
                    last_error = None
                    try:
                        result = self.retry_handler.run_with_retry(
                            cmd,
                            operation_name=f"download (strategy {i})",
                            progress_callback=progress_callback,
                            quiet=quiet
                        )
                    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                        last_error = e.stderr if hasattr(e, 'stderr') and e.stderr else (e.stdout if hasattr(e, 'stdout') and e.stdout else str(e))
                        last_strategy_error = last_error
                        continue
                    except Exception as e:
                        last_error = str(e)
                        last_strategy_error = last_error
                        continue
                    
                    # Find the downloaded file - look for NEW files that weren't there before
                    all_files = [
                        f for f in download_dir.glob("*")
                        if f.is_file() 
                        and f.suffix.lower() in audio_extensions
                        and f.name not in system_files
                    ]
                    
                    new_files = [
                        f for f in all_files
                        if f.name not in existing_files
                    ]
                    
                    if not new_files:
                        downloaded_file = None
                        if progress_callback and hasattr(result, 'stderr') and result.stderr:
                            last_error = result.stderr
                        elif not progress_callback and hasattr(result, 'stderr') and result.stderr:
                            last_error = result.stderr
                        else:
                            last_error = "Download completed but no file was created (yt-dlp may have failed silently)"
                        last_strategy_error = last_error
                    else:
                        # We have new files - find the one matching our expected pattern
                        if metadata and metadata.get('title'):
                            title = self.path_utils.sanitize_filename(metadata['title'])
                            track_number = metadata.get('track_number')
                            
                            if track_number:
                                track_prefix = f"{track_number:02d} - "
                                expected_base = f"{track_prefix}{title}"
                            else:
                                expected_base = title
                            
                            matching_files = [
                                f for f in new_files
                                if f.stem == expected_base
                            ]
                            
                            if matching_files:
                                downloaded_file = max(matching_files, key=os.path.getctime)
                            else:
                                partial_matches = [
                                    f for f in new_files
                                    if f.stem.startswith(expected_base)
                                ]
                                
                                if partial_matches:
                                    downloaded_file = max(partial_matches, key=os.path.getctime)
                                else:
                                    downloaded_file = max(new_files, key=os.path.getctime)
                        else:
                            downloaded_file = max(new_files, key=os.path.getctime)
                    
                    if downloaded_file:
                        if not quiet and not progress_callback:
                            try:
                                from rich.console import Console
                                console = Console()
                                console.print(f"[bold green]✓[/bold green] Success with strategy {i}")
                            except ImportError:
                                print(f"{Colors.green('✅')} Success with strategy {i}")
                        return downloaded_file, False
                    else:
                        if not quiet and not progress_callback:
                            error_msg = last_error or "Download completed but no file was created"
                            try:
                                from rich.console import Console
                                console = Console()
                                console.print(f"[bold red]✗[/bold red] Strategy {i} failed: {error_msg[:200]}")
                                if i < len(strategies):
                                    console.print("[blue]ℹ[/blue] Trying next strategy...")
                            except ImportError:
                                print(f"{Colors.red('❌')} Strategy {i} failed: {error_msg[:200]}")
                                if i < len(strategies):
                                    print(f"{Colors.blue('ℹ')} Trying next strategy...")
                        if i < len(strategies):
                            continue
                        else:
                            final_error = last_error or last_strategy_error or "All strategies completed but no files were downloaded"
                            raise Exception(f"All download strategies failed. Last error: {final_error[:200]}")
                        
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                    error_msg = e.stderr if hasattr(e, 'stderr') and e.stderr else (e.stdout if hasattr(e, 'stdout') and e.stdout else str(e))
                    last_strategy_error = error_msg
                    if not quiet and not progress_callback:
                        try:
                            from rich.console import Console
                            console = Console()
                            console.print(f"[bold red]✗[/bold red] Strategy {i} failed: {error_msg[:200]}")
                            if i < len(strategies):
                                console.print("[blue]ℹ[/blue] Trying next strategy...")
                        except ImportError:
                            print(f"{Colors.red('❌')} Strategy {i} failed: {error_msg[:200]}")
                            if i < len(strategies):
                                print(f"{Colors.blue('ℹ')} Trying next strategy...")
                    
                    if i < len(strategies):
                        continue
                    else:
                        raise Exception(f"All download strategies failed. Last error: {error_msg[:200]}")
                except FileNotFoundError as e:
                    cmd_name = str(e).split("'")[1] if "'" in str(e) else "command"
                    if "youtube-dl" in cmd_name:
                        install_cmd = "pip install youtube-dl"
                    elif "yt-dlp" in cmd_name:
                        install_cmd = "pip install yt-dlp"
                    else:
                        install_cmd = f"pip install {cmd_name}"
                    error_msg = f"{cmd_name} not found. Please install it with: {install_cmd}"
                    if not quiet and not progress_callback:
                        try:
                            from rich.console import Console
                            console = Console()
                            console.print(f"[bold red]✗[/bold red] Strategy {i} failed: {error_msg}")
                            if i < len(strategies):
                                console.print("[blue]ℹ[/blue] Trying next strategy...")
                        except ImportError:
                            print(f"{Colors.red('❌')} Strategy {i} failed: {error_msg}")
                            if i < len(strategies):
                                print(f"{Colors.blue('ℹ')} Trying next strategy...")
                    
                    if i < len(strategies):
                        continue
                    else:
                        raise Exception(f"All download strategies failed. {error_msg}")
                
        except Exception as e:
            error_str = str(e)
            if "No such file or directory" in error_str:
                if "youtube-dl" in error_str:
                    error_str = "youtube-dl not found. Please install yt-dlp with: pip install yt-dlp"
                elif "yt-dlp" in error_str:
                    error_str = "yt-dlp not found. Please install it with: pip install yt-dlp"
            raise Exception(f"Error downloading video: {error_str}") from e
        
        # If we get here, all strategies were tried but none succeeded
        final_error = last_strategy_error if 'last_strategy_error' in locals() else "All strategies failed without creating files"
        raise Exception(f"All download strategies failed. {final_error[:200]}")
    
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
                'yt-dlp',
                '--dump-json',
                '--flat-playlist',
                '--no-download',
                '--no-warnings',
                url
            ]
            
            cmd.extend([
                '--user-agent', 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                '--extractor-args', 'youtube:player_client=android_music'
            ])
            
            result = self.retry_handler.run_with_retry(
                cmd,
                operation_name=f"getting playlist info for {url[:50]}",
                quiet=True
            )
            
            # Parse JSON lines (one per video)
            videos = []
            output_lines = result.stdout.strip().split('\n')
            
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
                                'webpage_url': video_info.get('webpage_url', '')
                            })
                        except json.JSONDecodeError:
                            continue
                
                if videos:
                    return videos
        except subprocess.CalledProcessError as e:
            error_msg = (e.stderr or '').lower()
            if 'playlist does not exist' in error_msg or 'does not exist' in error_msg:
                return None
            pass
        except (subprocess.TimeoutExpired, Exception):
            pass
        
        # Fallback: Try without --flat-playlist
        try:
            cmd = [
                'yt-dlp',
                '--dump-json',
                '--no-download',
                '--no-warnings',
                '--playlist-end', '50',
                url
            ]
            
            cmd.extend([
                '--user-agent', 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                '--extractor-args', 'youtube:player_client=android'
            ])
            
            result = self.retry_handler.run_with_retry(
                cmd,
                operation_name=f"getting playlist info (fallback) for {url[:50]}",
                quiet=True
            )
            
            videos = []
            output_lines = result.stdout.strip().split('\n')
            
            if output_lines and output_lines[0].strip():
                for line in output_lines:
                    if line.strip():
                        try:
                            video_info = json.loads(line)
                            video_id = video_info.get('id')
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
    
    # Backward compatibility methods for internal use by other modules
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename (backward compatibility wrapper)."""
        return self.path_utils.sanitize_filename(filename)
    
    def _create_organized_path(self, metadata: Optional[Dict[str, Any]] = None) -> Path:
        """Create organized path (backward compatibility wrapper)."""
        return self.path_utils.create_organized_path(self.download_dir, metadata)
