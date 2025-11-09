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
from typing import Dict, Any, Optional, List, Callable, Tuple
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
            return json.loads(result.stdout)  # Parse JSON output
            
        except subprocess.CalledProcessError as e:
            print(f"Error getting video info: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
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
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        if len(track_timestamps) != len(metadata_list):
            raise ValueError("track_timestamps and metadata_list must have the same length")
        
        output_files = []
        
        for i, (timestamp_info, metadata) in enumerate(zip(track_timestamps, metadata_list)):
            start_time = timestamp_info.get('start_time', 0)
            end_time = timestamp_info.get('end_time')
            
            # Create output filename
            title = self._sanitize_filename(metadata.get('title', f'track_{i+1}'))
            track_number = metadata.get('track_number', i + 1)
            track_prefix = f"{track_number:02d} - " if track_number else ""
            output_filename = f"{track_prefix}{title}.mp3"
            output_path = output_dir / output_filename
            
            # Build ffmpeg command
            cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-ss', str(start_time),  # Start time
                '-acodec', 'libmp3lame',
                '-ab', '320k',  # High quality audio
                '-y',  # Overwrite output file
            ]
            
            # Add end time if specified
            if end_time:
                duration = end_time - start_time
                cmd.extend(['-t', str(duration)])
            
            cmd.append(str(output_path))
            
            # Run ffmpeg
            try:
                if progress_callback:
                    # For splitting, we can estimate progress based on track number
                    progress = (i / len(track_timestamps)) * 100
                    progress_callback({
                        'percent': progress,
                        'status': 'splitting',
                        'speed': None,
                        'eta': None
                    })
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=300  # 5 minute timeout per track
                )
                
                if output_path.exists():
                    output_files.append(output_path)
                    
            except subprocess.CalledProcessError as e:
                print(f"Error splitting track {i+1}: {e.stderr if e.stderr else e}")
                continue
            except subprocess.TimeoutExpired:
                print(f"Timeout splitting track {i+1}")
                continue
        
        if progress_callback:
            progress_callback({
                'percent': 100.0,
                'status': 'completed',
                'speed': None,
                'eta': None
            })
        
        return output_files
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to prevent path traversal and filesystem issues.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename safe for filesystem use
        """
        if not filename:
            return "unknown"
        
        # Prevent path traversal attacks by removing .. sequences
        sanitized = filename.replace('..', '_')
        
        # Remove or replace invalid characters for filesystem
        invalid_chars = r'[<>:"/\\|?*]'
        sanitized = re.sub(invalid_chars, '_', sanitized)
        
        # Remove multiple consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        
        # Remove leading/trailing underscores and dots
        sanitized = sanitized.strip('_.')
        
        # Limit filename length to prevent filesystem issues (255 chars is common limit)
        max_length = 200  # Leave room for extension
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        # Ensure filename is not empty after sanitization
        if not sanitized:
            return "unknown"
        
        return sanitized
    
    def _create_organized_path(self, metadata: Optional[Dict[str, Any]] = None) -> Path:
        """
        Create organized directory path for downloads.
        
        Args:
            metadata: Optional metadata dictionary
            
        Returns:
            Path object for the organized directory
            
        Security: This method ensures paths stay within the download directory
        to prevent path traversal attacks.
        """
        if not metadata:
            return self.download_dir
        
        # Extract metadata fields
        artist = metadata.get('artist', 'Unknown Artist')
        album = metadata.get('album', 'Unknown Album')
        year = metadata.get('year')
        title = metadata.get('title', 'Unknown Title')
        
        # Sanitize all components (this also prevents path traversal)
        artist = self._sanitize_filename(artist)
        album = self._sanitize_filename(album)
        title = self._sanitize_filename(title)
        
        # Create folder structure: Artist/LP (release year)/
        artist_dir = self.download_dir / artist
        
        if year:
            lp_folder_name = f"{album} ({year})"
        else:
            lp_folder_name = album
        
        # Sanitize the folder name as well
        lp_folder_name = self._sanitize_filename(lp_folder_name)
        
        # Create the organized directory structure
        organized_dir = artist_dir / lp_folder_name
        
        # Security: Resolve the path and ensure it's still within download_dir
        # This prevents path traversal even if sanitization somehow fails
        try:
            resolved_path = organized_dir.resolve()
            download_dir_resolved = self.download_dir.resolve()
            
            # Check that the resolved path is within the download directory
            if not str(resolved_path).startswith(str(download_dir_resolved)):
                # Fallback to download_dir if path traversal detected
                return self.download_dir
        except (OSError, ValueError):
            # If resolution fails, fallback to download_dir
            return self.download_dir
        
        organized_dir.mkdir(parents=True, exist_ok=True)
        
        return organized_dir
    
    def _convert_size_to_bytes(self, size_str: str) -> Optional[float]:
        """Convert size string (e.g., '5.2MiB', '1.5GB') to bytes."""
        if not size_str:
            return None
        
        # Remove ~ prefix if present
        size_str = size_str.strip().lstrip('~')
        
        # Match number and unit
        match = re.match(r'([\d.]+)\s*([KMGT]?i?B)', size_str, re.IGNORECASE)
        if not match:
            return None
        
        value = float(match.group(1))
        unit = match.group(2).upper()
        
        # Convert to bytes
        multipliers = {
            'B': 1,
            'KB': 1024,
            'KIB': 1024,
            'MB': 1024 ** 2,
            'MIB': 1024 ** 2,
            'GB': 1024 ** 3,
            'GIB': 1024 ** 3,
            'TB': 1024 ** 4,
            'TIB': 1024 ** 4,
        }
        
        multiplier = multipliers.get(unit, 1)
        return value * multiplier
    
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
            
            # Extract total file size (e.g., "of 5.2MiB" or "of ~5.2MiB")
            total_size_bytes = None
            total_size_match = re.search(r'of\s+(~?[\d.]+\s*[KMGT]?i?B)', line, re.IGNORECASE)
            if total_size_match:
                total_size_str = total_size_match.group(1)
                total_size_bytes = self._convert_size_to_bytes(total_size_str)
            
            # Calculate downloaded bytes from percentage and total
            downloaded_bytes = None
            if total_size_bytes and percent:
                downloaded_bytes = (percent / 100.0) * total_size_bytes
            
            # Try to extract speed (various formats) and convert to bytes/s
            speed_bytes_per_sec = None
            speed_str = None
            speed_patterns = [
                r'at\s+([\d.]+)\s*([KMGT]?i?B/s)',  # "at 1.5MiB/s"
                r'([\d.]+)\s*([KMGT]?i?B/s)',        # "1.5MiB/s"
            ]
            for pattern in speed_patterns:
                speed_match = re.search(pattern, line, re.IGNORECASE)
                if speed_match:
                    speed_val = float(speed_match.group(1))
                    speed_unit = speed_match.group(2)
                    speed_str = f"{speed_val} {speed_unit}"
                    # Convert to bytes/s for Rich progress bar
                    speed_bytes_per_sec = self._convert_size_to_bytes(f"{speed_val} {speed_unit.rstrip('/s')}")
                    break
            
            # Try to extract ETA (various formats) and convert to seconds
            eta_seconds = None
            eta_str = None
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
                        eta_str = f"{minutes}:{seconds.zfill(2)}"
                        eta_seconds = int(minutes) * 60 + int(seconds)
                    elif 'h' in pattern:
                        hours, minutes = eta_match.groups()
                        eta_str = f"{hours}h {minutes}m"
                        eta_seconds = int(hours) * 3600 + int(minutes) * 60
                    else:
                        minutes, seconds = eta_match.groups()
                        eta_str = f"{minutes}m {seconds}s"
                        eta_seconds = int(minutes) * 60 + int(seconds)
                    break
            
            progress_info = {
                'percent': percent,
                'total_bytes': total_size_bytes,
                'downloaded_bytes': downloaded_bytes,
                'speed': speed_str,
                'speed_bytes_per_sec': speed_bytes_per_sec,
                'eta': eta_str,
                'eta_seconds': eta_seconds,
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
                      quiet: bool = False, progress_callback: Optional[Callable] = None) -> Tuple[Optional[Path], bool]:
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
                        return potential_file, True
                
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
                    return existing_file, True
            
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
                        return downloaded_file, False
                        
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
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
            
            # Parse JSON lines (one per video)
            videos = []
            output_lines = result.stdout.strip().split('\n')
            
            if output_lines and output_lines[0].strip():
                for line in output_lines:
                    if line.strip():
                        try:
                            video_info = json.loads(line)
                            # With --flat-playlist, some fields might be missing
                            # Extract what we can
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
                            # Skip invalid JSON lines
                            continue
                
                if videos:
                    return videos
        except subprocess.CalledProcessError as e:
            # Check if it's a fatal error (playlist doesn't exist, etc.)
            error_msg = (e.stderr or '').lower()
            if 'playlist does not exist' in error_msg or 'does not exist' in error_msg:
                # Playlist doesn't exist, don't try fallback
                return None
            # For other errors, try fallback
            pass
        except (subprocess.TimeoutExpired, Exception):
            # Try fallback
            pass
        
        # Fallback: Try without --flat-playlist (slower but more reliable, gets full info)
        # Limit to first 50 videos to avoid timeout
        try:
            cmd = [
                'yt-dlp',
                '--dump-json',
                '--no-download',
                '--no-warnings',
                '--playlist-end', '50',  # Limit to first 50 videos
                url
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=120)
            
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
            # Both methods failed
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
