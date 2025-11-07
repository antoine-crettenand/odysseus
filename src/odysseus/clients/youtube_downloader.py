"""
YouTube Downloader Module
A module to download YouTube videos using yt-dlp.
"""

import os
import subprocess
import sys
import re
import json
import threading
from queue import Queue
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
from ..core.config import (
    DOWNLOAD_CONFIG, ERROR_MESSAGES, SUCCESS_MESSAGES, 
    QUALITY_PRESETS, FILE_EXTENSIONS, DEFAULTS
)
from ..utils.colors import Colors


class YouTubeDownloader:
    """YouTube video downloader using yt-dlp."""
    
    def __init__(self, download_dir: Optional[str] = None):
        self.download_dir = Path(download_dir or DOWNLOAD_CONFIG["DEFAULT_DIR"])
        self.download_dir.mkdir(exist_ok=True)
        
        self.default_quality = DOWNLOAD_CONFIG["DEFAULT_QUALITY"]
        self.audio_format = DOWNLOAD_CONFIG["AUDIO_FORMAT"]
        self.timeout = DOWNLOAD_CONFIG["TIMEOUT"]
        
        # Check and update yt-dlp if needed
        self._ensure_yt_dlp_updated()
    
    def _ensure_yt_dlp_updated(self):
        """Ensure yt-dlp is up to date to avoid 403 errors."""
        try:
            print("Checking yt-dlp version...")
            result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                current_version = result.stdout.strip()
                print(f"Current yt-dlp version: {current_version}")
                
                # Try to update yt-dlp
                print("Updating yt-dlp to latest version...")
                update_result = subprocess.run(['pip3', 'install', '--upgrade', 'yt-dlp'], 
                                             capture_output=True, text=True)
                if update_result.returncode == 0:
                    print("✅ yt-dlp updated successfully")
                else:
                    print("⚠️  Could not update yt-dlp, continuing with current version")
            else:
                print("❌ yt-dlp not found, please install it with: pip install yt-dlp")
        except Exception as e:
            print(f"⚠️  Could not check yt-dlp version: {e}")
    
    def update_yt_dlp(self) -> bool:
        """Manually update yt-dlp."""
        try:
            print("Updating yt-dlp...")
            result = subprocess.run(['pip3', 'install', '--upgrade', 'yt-dlp'], 
                                  capture_output=True, text=True, check=True)
            print("✅ yt-dlp updated successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to update yt-dlp: {e}")
            return False
    
    def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        try:
            cmd = [
                'yt-dlp',
                '--dump-json',
                '--no-download',
                url
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return eval(result.stdout)  # Parse JSON output
            
        except subprocess.CalledProcessError as e:
            print(f"Error getting video info: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None
    
    def _sanitize_filename(self, filename: str) -> str:
        # Remove or replace invalid characters for filesystem
        invalid_chars = r'[<>:"/\\|?*]'
        sanitized = re.sub(invalid_chars, '_', filename)
        # Remove multiple consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        # Remove leading/trailing underscores and dots
        sanitized = sanitized.strip('_.')
        return sanitized
    
    def _create_organized_path(self, metadata: Optional[Dict[str, Any]] = None) -> Path:
        if not metadata:
            return self.download_dir
        
        # Extract metadata fields
        artist = metadata.get('artist', 'Unknown Artist')
        album = metadata.get('album', 'Unknown Album')
        year = metadata.get('year')
        title = metadata.get('title', 'Unknown Title')
        
        # Sanitize all components
        artist = self._sanitize_filename(artist)
        album = self._sanitize_filename(album)
        title = self._sanitize_filename(title)
        
        # Create folder structure: Artist/LP (release year)/
        artist_dir = self.download_dir / artist
        
        if year:
            lp_folder_name = f"{album} ({year})"
        else:
            lp_folder_name = album
        
        # Create the organized directory structure
        organized_dir = artist_dir / lp_folder_name
        organized_dir.mkdir(parents=True, exist_ok=True)
        
        return organized_dir
    
    def _parse_progress_hook(self, line: str, progress_callback: Optional[Callable] = None) -> Optional[Dict[str, Any]]:
        """
        Parse yt-dlp progress output line.
        Returns progress info dict or None if not a progress line.
        Handles multiple yt-dlp progress output formats.
        """
        if not line or not line.strip():
            return None
        
        try:
            # Format 1: [download] X.X% of Y.YMiB at Z.ZMiB/s ETA MM:SS
            # Format 2: [download] X.X% of ~Y.YMiB at Z.ZMiB/s ETA MM:SS
            # Format 3: [download] X.X% at Z.ZMiB/s ETA MM:SS
            # Format 4: [download] 100% of Y.YMiB in MM:SS
            
            line_lower = line.lower()
            
            # Check if this is a download progress line
            # yt-dlp can output progress in various formats
            # Also check for extractor progress: [extractor] or [ExtractAudio]
            if '[download]' not in line_lower and '[extractaudio]' not in line_lower:
                # Also check for percentage without [download] tag (some formats)
                if '%' in line and ('downloading' in line_lower or 'of' in line_lower):
                    pass  # Might be a progress line
                else:
                    return None
            
            # Extract percentage
            percent_match = re.search(r'(\d+\.?\d*)%', line)
            if not percent_match:
                return None
            
            percent = float(percent_match.group(1))
            
            # Try to extract speed (various formats)
            speed = None
            speed_patterns = [
                r'at\s+([\d.]+)\s*([KMGT]?i?B/s)',  # "at 1.5MiB/s"
                r'([\d.]+)\s*([KMGT]?i?B/s)',        # "1.5MiB/s"
            ]
            for pattern in speed_patterns:
                speed_match = re.search(pattern, line, re.IGNORECASE)
                if speed_match:
                    speed_val = float(speed_match.group(1))
                    speed_unit = speed_match.group(2)
                    speed = f"{speed_val} {speed_unit}"
                    break
            
            # Try to extract ETA (various formats)
            eta = None
            eta_patterns = [
                r'ETA\s+(\d+):(\d+)',           # "ETA 01:23"
                r'ETA\s+(\d+)h\s*(\d+)m',       # "ETA 1h 23m"
                r'ETA\s+(\d+)m\s*(\d+)s',       # "ETA 1m 23s"
            ]
            for pattern in eta_patterns:
                eta_match = re.search(pattern, line, re.IGNORECASE)
                if eta_match:
                    if ':' in pattern:
                        minutes, seconds = eta_match.groups()
                        eta = f"{minutes}:{seconds.zfill(2)}"
                    elif 'h' in pattern:
                        hours, minutes = eta_match.groups()
                        eta = f"{hours}h {minutes}m"
                    else:
                        minutes, seconds = eta_match.groups()
                        eta = f"{minutes}m {seconds}s"
                    break
            
            progress_info = {
                'percent': percent,
                'speed': speed,
                'eta': eta,
                'status': 'downloading' if percent < 100 else 'completed'
            }
            
            if progress_callback:
                progress_callback(progress_info)
            
            return progress_info
            
        except Exception:
            # Silently fail - not a progress line or parsing error
            pass
        
        return None
    
    def _run_download_with_progress(self, cmd: List[str], progress_callback: Optional[Callable] = None) -> subprocess.CompletedProcess:
        """
        Run download command with progress tracking and timeout protection.
        """
        import time
        
        # Remove --no-warnings to ensure progress output is visible
        # Also ensure --newline is present for line-by-line output
        modified_cmd = []
        for arg in cmd:
            if arg != '--no-warnings':
                modified_cmd.append(arg)
        
        # Add --newline before the URL (last argument) if not present
        if '--newline' not in modified_cmd:
            modified_cmd.insert(-1, '--newline')
        
        # Run with real-time output processing
        # yt-dlp writes progress to stderr, so we need to capture both
        process = subprocess.Popen(
            modified_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Read output from both stdout and stderr
        output_lines = []
        start_time = time.time()
        timeout = self.timeout
        
        # Use threading to read from both streams simultaneously
        
        def read_stream(stream, queue):
            """Read from a stream and put lines in queue."""
            try:
                # Read line by line, but handle carriage returns for progress updates
                for line in iter(stream.readline, ''):
                    if not line:
                        break
                    # Strip carriage returns and newlines, but keep the content
                    cleaned_line = line.rstrip('\r\n')
                    if cleaned_line:  # Only queue non-empty lines
                        queue.put(('line', cleaned_line))
            except Exception:
                pass
            finally:
                queue.put(('done', None))
        
        # Create queues for stdout and stderr
        stdout_queue = Queue()
        stderr_queue = Queue()
        
        # Start threads to read from both streams
        stdout_thread = threading.Thread(target=read_stream, args=(process.stdout, stdout_queue), daemon=True)
        stderr_thread = threading.Thread(target=read_stream, args=(process.stderr, stderr_queue), daemon=True)
        
        stdout_thread.start()
        stderr_thread.start()
        
        # Process output from both queues with timeout protection
        stdout_done = False
        stderr_done = False
        last_activity_time = time.time()
        no_activity_timeout = 60  # If no output for 60 seconds, consider it stuck
        
        while not (stdout_done and stderr_done):
            # Check for overall timeout
            elapsed = time.time() - start_time
            if elapsed > timeout:
                process.kill()
                raise subprocess.TimeoutExpired(cmd, timeout, "Download operation timed out")
            
            # Check for no activity timeout (process might be stuck)
            if time.time() - last_activity_time > no_activity_timeout:
                # Check if process is still running
                if process.poll() is None:
                    process.kill()
                    raise subprocess.TimeoutExpired(cmd, no_activity_timeout, "Download operation appears stuck (no output)")
            
            # Check stdout
            if not stdout_done:
                try:
                    item_type, line = stdout_queue.get(timeout=0.1)
                    if item_type == 'done':
                        stdout_done = True
                    else:
                        output_lines.append(line)
                        last_activity_time = time.time()  # Update activity time
                        # Some progress might be in stdout too
                        if progress_callback:
                            self._parse_progress_hook(line, progress_callback)
                except:
                    pass
            
            # Check stderr (where progress usually goes)
            if not stderr_done:
                try:
                    item_type, line = stderr_queue.get(timeout=0.1)
                    if item_type == 'done':
                        stderr_done = True
                    else:
                        output_lines.append(line)
                        last_activity_time = time.time()  # Update activity time
                        # Progress output is usually in stderr
                        if progress_callback:
                            self._parse_progress_hook(line, progress_callback)
                except:
                    pass
        
        # Wait for threads to finish
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)
        
        # Wait for process with timeout
        try:
            process.wait(timeout=10)  # Give it 10 seconds to finish after streams close
        except subprocess.TimeoutExpired:
            process.kill()
            raise subprocess.TimeoutExpired(cmd, 10, "Process did not terminate after streams closed")
        
        # Create CompletedProcess-like object
        result = subprocess.CompletedProcess(
            modified_cmd,
            process.returncode,
            stdout='\n'.join(output_lines),
            stderr=''
        )
        
        return result
    
    def download(self, url: str, quality: str = "bestaudio", 
                      audio_only: bool = True, metadata: Optional[Dict[str, Any]] = None, 
                      quiet: bool = False, progress_callback: Optional[Callable] = None) -> Optional[Path]:
        try:
            # Determine download directory based on metadata
            download_dir = self._create_organized_path(metadata)
            
            # Create filename template based on metadata
            if metadata and metadata.get('title'):
                title = self._sanitize_filename(metadata['title'])
                
                # Add track number prefix if available
                track_number = metadata.get('track_number')
                if track_number:
                    # Format with leading zero (e.g., "01", "02", "10")
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
                title = self._sanitize_filename(metadata['title'])
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
                        # File already exists, return it without downloading
                        # Update progress callback to 100% if provided (so UI shows completion)
                        if progress_callback:
                            progress_callback({
                                'percent': 100.0,
                                'status': 'completed',
                                'speed': None,
                                'eta': None
                            })
                        if not quiet:
                            from ..utils.colors import Colors
                            print(f"{Colors.yellow('⏭')} Skipping download - file already exists: {Colors.blue(str(potential_file))}")
                        # Return existing file - metadata will still be applied by the caller
                        return potential_file
                
                # Also check for files with similar names (in case of slight variations)
                # Look for files starting with the expected base name
                existing_files = [
                    f for f in download_dir.glob(f"{expected_base}*")
                    if f.is_file() 
                    and f.suffix.lower() in audio_extensions
                    and f.name not in system_files
                ]
                
                if existing_files:
                    # Return the first matching file (most likely the correct one)
                    existing_file = existing_files[0]
                    # Update progress callback to 100% if provided (so UI shows completion)
                    if progress_callback:
                        progress_callback({
                            'percent': 100.0,
                            'status': 'completed',
                            'speed': None,
                            'eta': None
                        })
                    if not quiet:
                        from ..utils.colors import Colors
                        print(f"{Colors.yellow('⏭')} Skipping download - file already exists: {Colors.blue(str(existing_file))}")
                    # Return existing file - metadata will still be applied by the caller
                    return existing_file
            
            # Only print download info if not in quiet mode (Rich UI handles this)
            if not quiet:
                # Import colors here to avoid circular imports
                from ..utils.colors import Colors
                
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
            strategies = [
                self._build_command_strategy_1,
                self._build_command_strategy_2,
                self._build_command_strategy_3,
                self._build_command_strategy_4,
                self._build_command_strategy_5
            ]
            
            for i, strategy in enumerate(strategies, 1):
                try:
                    # Only print strategy messages if not in quiet mode and no progress callback
                    # (progress bars handle their own display)
                    if not quiet and not progress_callback:
                        try:
                            from rich.console import Console
                            console = Console()
                            console.print(f"[blue]Trying strategy [bold white]{i}[/bold white]...[/blue]")
                        except ImportError:
                            print(f"Trying strategy {Colors.bold(Colors.white(str(i)))}...")
                    
                    cmd = strategy(url, quality, audio_only, output_template)
                    
                    # List existing files BEFORE download to identify newly created files
                    audio_extensions = ['.mp3', '.m4a', '.ogg', '.opus', '.flac', '.wav', '.aac', '.webm']
                    system_files = {'.DS_Store', '.Thumbs.db', 'desktop.ini'}
                    
                    existing_files = {
                        f.name for f in download_dir.glob("*")
                        if f.is_file() and f.name not in system_files
                    }
                    
                    # Run download with progress tracking if callback provided
                    if progress_callback:
                        result = self._run_download_with_progress(cmd, progress_callback)
                        # Check return code for progress-based downloads
                        if result.returncode != 0:
                            # Download failed - continue to next strategy
                            continue
                    else:
                        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=self.timeout)
                    
                    # Find the downloaded file - look for NEW files that weren't there before
                    # Find all audio files in the directory, excluding system files
                    all_files = [
                        f for f in download_dir.glob("*")
                        if f.is_file() 
                        and f.suffix.lower() in audio_extensions
                        and f.name not in system_files
                    ]
                    
                    # Filter to only NEW files (files that didn't exist before download)
                    new_files = [
                        f for f in all_files
                        if f.name not in existing_files
                    ]
                    
                    # CRITICAL: Only return NEW files - if no new files, download failed
                    if not new_files:
                        # No new files created - download likely failed
                        downloaded_file = None
                    else:
                        # We have new files - find the one matching our expected pattern
                        if metadata and metadata.get('title'):
                            title = self._sanitize_filename(metadata['title'])
                            track_number = metadata.get('track_number')
                            
                            if track_number:
                                track_prefix = f"{track_number:02d} - "
                                expected_base = f"{track_prefix}{title}"
                            else:
                                expected_base = title
                            
                            # Look for files matching the expected pattern (stem = filename without extension)
                            matching_files = [
                                f for f in new_files
                                if f.stem == expected_base
                            ]
                            
                            if matching_files:
                                # Among matching files, get the most recently created
                                downloaded_file = max(matching_files, key=os.path.getctime)
                            else:
                                # No exact match found - try partial match
                                partial_matches = [
                                    f for f in new_files
                                    if f.stem.startswith(expected_base)
                                ]
                                
                                if partial_matches:
                                    # Get the most recently created partial match
                                    downloaded_file = max(partial_matches, key=os.path.getctime)
                                else:
                                    # No match found, but we have new files - use the most recently created new file
                                    # This handles cases where yt-dlp modified the filename
                                    downloaded_file = max(new_files, key=os.path.getctime)
                        else:
                            # No metadata - use the most recently created new file
                            downloaded_file = max(new_files, key=os.path.getctime)
                    
                    if downloaded_file:
                        # Only print success message if not in quiet mode and no progress callback
                        if not quiet and not progress_callback:
                            try:
                                from rich.console import Console
                                console = Console()
                                console.print(f"[bold green]✓[/bold green] Success with strategy {i}")
                            except ImportError:
                                print(f"{Colors.green('✅')} Success with strategy {i}")
                        return downloaded_file
                        
                except subprocess.CalledProcessError as e:
                    error_msg = e.stderr if e.stderr else str(e)
                    # Only print error messages if not in quiet mode and no progress callback
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
                        raise Exception(f"All download strategies failed. Last error: {e}")
                
        except Exception as e:
            raise Exception(f"Error downloading video: {e}") from e
    
    def _has_chrome_cookies(self) -> bool:
        """Check if Chrome cookies database exists."""
        chrome_cookie_paths = [
            Path.home() / "Library/Application Support/Google/Chrome/Default/Cookies",
            Path.home() / "Library/Application Support/Google/Chrome/Profile 1/Cookies",
            Path.home() / ".config/google-chrome/Default/Cookies",
            Path.home() / ".config/google-chrome/Profile 1/Cookies",
            Path.home() / "AppData/Local/Google/Chrome/User Data/Default/Cookies",
            Path.home() / "AppData/Local/Google/Chrome/User Data/Profile 1/Cookies",
        ]
        
        for path in chrome_cookie_paths:
            if path.exists():
                return True
        return False
    
    def _build_command_strategy_1(self, url: str, quality: str, audio_only: bool, output_template: str) -> List[str]:
        """Strategy 1: Basic yt-dlp with user agent, optionally with cookies if available"""
        cmd = [
            'yt-dlp',
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            '--no-check-certificate',
            '--ignore-errors',
            '--no-warnings',
            '--extractor-args', 'youtube:player_client=web'
        ]
        
        # Only add cookies if Chrome is available
        if self._has_chrome_cookies():
            cmd.extend(['--cookies-from-browser', 'chrome'])
        
        if audio_only:
            cmd.extend([
                '-x',  # Extract audio
                '--audio-format', 'mp3',
                '--audio-quality', '0',
                '--postprocessor-args', 'ffmpeg:-b:a 320k'
            ])
        else:
            cmd.extend(['-f', quality])
        
        cmd.extend(['-o', output_template, url])
        return cmd
    
    def _build_command_strategy_2(self, url: str, quality: str, audio_only: bool, output_template: str) -> List[str]:
        """Strategy 2: Use different extractor and bypass age restriction"""
        cmd = [
            'yt-dlp',
            '--user-agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            '--age-limit', '0',  # Bypass age restriction
            '--no-check-certificate',
            '--ignore-errors',
            '--extractor-args', 'youtube:player_client=android,web',
            '--no-warnings'
        ]
        
        if audio_only:
            cmd.extend([
                '-x',
                '--audio-format', 'mp3',
                '--audio-quality', '0',
                '--postprocessor-args', 'ffmpeg:-b:a 320k'
            ])
        else:
            cmd.extend(['-f', quality])
        
        cmd.extend(['-o', output_template, url])
        return cmd
    
    def _build_command_strategy_3(self, url: str, quality: str, audio_only: bool, output_template: str) -> List[str]:
        """Strategy 3: Use different player client and referer"""
        cmd = [
            'yt-dlp',
            '--user-agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            '--referer', 'https://www.youtube.com/',
            '--no-check-certificate',
            '--ignore-errors',
            '--extractor-args', 'youtube:player_client=ios',
            '--no-warnings'
        ]
        
        if audio_only:
            cmd.extend([
                '-x',
                '--audio-format', 'mp3',
                '--audio-quality', '0',
                '--postprocessor-args', 'ffmpeg:-b:a 320k'
            ])
        else:
            cmd.extend(['-f', quality])
        
        cmd.extend(['-o', output_template, url])
        return cmd
    
    def _build_command_strategy_4(self, url: str, quality: str, audio_only: bool, output_template: str) -> List[str]:
        """Strategy 4: Use yt-dlp with all bypass options"""
        cmd = [
            'yt-dlp',
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0',
            '--cookies-from-browser', 'firefox',
            '--no-check-certificate',
            '--ignore-errors',
            '--extractor-args', 'youtube:player_client=android_music,web',
            '--sleep-requests', '1',  # Add delay between requests
            '--sleep-interval', '1',
            '--max-sleep-interval', '5',
            '--no-warnings',
            '--retries', '3'
        ]
        
        if audio_only:
            cmd.extend([
                '-x',
                '--audio-format', 'mp3',
                '--audio-quality', '0',
                '--postprocessor-args', 'ffmpeg:-b:a 320k'
            ])
        else:
            cmd.extend(['-f', quality])
        
        cmd.extend(['-o', output_template, url])
        return cmd
    
    def _build_command_strategy_5(self, url: str, quality: str, audio_only: bool, output_template: str) -> List[str]:
        """Strategy 5: Use youtube-dl as fallback with different options"""
        cmd = [
            'youtube-dl',  # Try youtube-dl instead of yt-dlp
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            '--no-check-certificate',
            '--ignore-errors',
            '--no-warnings',
            '--extractor-args', 'youtube:player_client=android,web'
        ]
        
        if audio_only:
            cmd.extend([
                '-x',  # Extract audio
                '--audio-format', 'mp3',
                '--audio-quality', '0',
                '--postprocessor-args', 'ffmpeg:-b:a 320k'
            ])
        else:
            cmd.extend(['-f', quality])
        
        cmd.extend(['-o', output_template, url])
        return cmd
    
    def download_high_quality_audio(self, url: str, metadata: Optional[Dict[str, Any]] = None, 
                                     quiet: bool = False, progress_callback: Optional[Callable] = None) -> Optional[Path]:
        """
        Download high-quality audio from YouTube video.
        
        Args:
            url: YouTube video URL
            metadata: Optional metadata for organized file structure
            quiet: If True, suppress console output (for Rich UI)
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Path to downloaded audio file or None if failed
        """
        return self.download(url, quality="bestaudio", audio_only=True, metadata=metadata, 
                           quiet=quiet, progress_callback=progress_callback)
    
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
            
            # Import colors here to avoid circular imports
            from ..utils.colors import Colors
            
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
