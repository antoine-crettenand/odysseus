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
import time
import random
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
        
        # Retry configuration for robust downloads
        self.max_retries = 5  # Increased retries for connection errors
        self.base_retry_delay = 2.0  # Base delay in seconds
        self.max_retry_delay = 60.0  # Maximum delay between retries
        self.max_total_time = 1800  # Maximum total time for all retries (30 minutes)
        self.yt_dlp_update_attempted = False  # Track if we've tried updating
        
        # Check and update yt-dlp if needed
        self._ensure_yt_dlp_updated()
    
    def _ensure_yt_dlp_updated(self):
        """Ensure yt-dlp is up to date to avoid 403 errors."""
        try:
            print("Checking yt-dlp version...")
            result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                current_version = result.stdout.strip()
                print(f"Current yt-dlp version: {current_version}")
                
                # Try to update yt-dlp
                print("Updating yt-dlp to latest version...")
                update_result = subprocess.run(['pip3', 'install', '--upgrade', 'yt-dlp'], 
                                             capture_output=True, text=True, timeout=120)
                if update_result.returncode == 0:
                    print("✅ yt-dlp updated successfully")
                else:
                    print("⚠️  Could not update yt-dlp, continuing with current version")
            else:
                print("❌ yt-dlp not found, please install it with: pip install yt-dlp")
        except subprocess.TimeoutExpired:
            print("⚠️  yt-dlp version check timed out, continuing...")
        except Exception as e:
            print(f"⚠️  Could not check yt-dlp version: {e}")
    
    def _force_update_yt_dlp(self) -> bool:
        """Force update yt-dlp (used when signature extraction fails)."""
        if self.yt_dlp_update_attempted:
            return False  # Already tried updating
        
        self.yt_dlp_update_attempted = True
        try:
            print("🔄 Signature extraction failed - updating yt-dlp...")
            print("   This usually happens when YouTube changes their API. Updating yt-dlp should fix it.")
            print("   Note: Known issue as of 2025 - yt-dlp team is working on fixes.")
            result = subprocess.run(
                ['pip3', 'install', '--upgrade', '--no-cache-dir', 'yt-dlp'], 
                capture_output=True, 
                text=True, 
                timeout=180,
                check=True
            )
            print("✅ yt-dlp updated successfully")
            
            # Check if update was successful and get version
            try:
                version_result = subprocess.run(
                    ['yt-dlp', '--version'], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                if version_result.returncode == 0:
                    version = version_result.stdout.strip()
                    print(f"   Updated to version: {version}")
                    # Warn about future Deno requirement if version is recent
                    if version >= "2025.10.22":
                        print("   ⚠️  Note: Future versions may require Deno (JavaScript runtime) for YouTube downloads")
            except:
                pass
            
            print("   Retrying download with updated version...")
            # Reset flag after successful update to allow future updates
            time.sleep(2)  # Give yt-dlp a moment to be ready
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, Exception) as e:
            print(f"⚠️  Could not automatically update yt-dlp: {e}")
            print("   You may need to manually update yt-dlp:")
            print("   Run: pip3 install --upgrade yt-dlp")
            print("   Or: pip install --upgrade yt-dlp")
            print("   Or use: yt-dlp -U (if installed via standalone)")
            print("   Known issues: Check https://github.com/yt-dlp/yt-dlp/issues for updates")
            return False
    
    def _is_retryable_error(self, error_output: str) -> Tuple[bool, Optional[str]]:
        """
        Determine if an error is retryable and return error type.
        
        Returns:
            Tuple of (is_retryable, error_type)
        """
        error_lower = error_output.lower()
        
        # HTTP 403/401 errors - retryable (often bot detection or access denied)
        # Check this first as it's a common YouTube blocking mechanism
        # yt-dlp may format these as: "HTTP Error 403", "403 Forbidden", "Unauthorized", etc.
        if any(keyword in error_lower for keyword in [
            '403', '401', 'forbidden', 'unauthorized', 'access denied',
            'http error 403', 'http error 401', 'http 403', 'http 401',
            'error 403', 'error 401', 'status code 403', 'status code 401'
        ]):
            return True, 'bot_detection'  # Treat as bot detection to trigger cookie usage
        
        # Connection errors - definitely retryable
        if any(keyword in error_lower for keyword in [
            'connection', 'network', 'timeout', 'timed out', 
            'unreachable', 'refused', 'reset', 'broken pipe'
        ]):
            return True, 'connection'
        
        # Signature extraction errors - retryable after update
        if any(keyword in error_lower for keyword in [
            'signature extraction', 'signature', 'player', 'extractor',
            'unable to extract', 'could not extract'
        ]):
            return True, 'signature'
        
        # Rate limiting - retryable with backoff
        if any(keyword in error_lower for keyword in [
            'rate limit', '429', 'too many requests', 'quota'
        ]):
            return True, 'rate_limit'
        
        # HTTP 5xx errors - retryable
        if any(keyword in error_lower for keyword in [
            '500', '502', '503', '504', 'internal server error',
            'bad gateway', 'service unavailable', 'gateway timeout'
        ]):
            return True, 'server_error'
        
        # Bot detection - might be retryable with cookies
        if any(keyword in error_lower for keyword in [
            'bot', 'sign in to confirm', 'captcha', 'verify'
        ]):
            return True, 'bot_detection'
        
        # Video unavailable - not retryable
        if any(keyword in error_lower for keyword in [
            'video unavailable', 'private video', 'deleted', 'removed',
            'not available', 'does not exist'
        ]):
            return False, 'unavailable'
        
        # Default: retryable for unknown errors
        return True, 'unknown'
    
    def _calculate_retry_delay(self, attempt: int, error_type: str) -> float:
        """
        Calculate retry delay with exponential backoff and jitter.
        
        Args:
            attempt: Current attempt number (0-indexed)
            error_type: Type of error encountered
            
        Returns:
            Delay in seconds
        """
        # Base exponential backoff
        delay = min(
            self.base_retry_delay * (2 ** attempt),
            self.max_retry_delay
        )
        
        # Adjust delay based on error type
        if error_type == 'rate_limit':
            delay = max(delay, 10.0)  # Longer delay for rate limits
        elif error_type == 'signature':
            delay = max(delay, 3.0)  # Shorter delay for signature errors
        elif error_type == 'connection':
            delay = max(delay, 5.0)  # Medium delay for connection errors
        
        # Add jitter (random 0-20% of delay) to prevent thundering herd
        jitter = random.uniform(0, delay * 0.2)
        return delay + jitter
    
    def _run_yt_dlp_with_retry(
        self,
        cmd: List[str],
        operation_name: str = "yt-dlp operation",
        progress_callback: Optional[Callable] = None,
        quiet: bool = False
    ) -> subprocess.CompletedProcess:
        """
        Run yt-dlp command with comprehensive retry logic and error handling.
        
        This method implements:
        - Exponential backoff with jitter
        - Automatic yt-dlp updates on signature errors
        - Connection error recovery
        - Rate limit handling
        - Timeout protection (per attempt and total time limit)
        
        Args:
            cmd: Command to run
            operation_name: Name of operation for error messages
            progress_callback: Optional callback for progress updates
            quiet: If True, suppress non-critical output
            
        Returns:
            CompletedProcess object
            
        Raises:
            subprocess.CalledProcessError: If all retries fail
            subprocess.TimeoutExpired: If operation times out
        """
        last_error = None
        last_error_type = None
        signature_error_occurred = False
        start_time = time.time()  # Track total elapsed time
        
        for attempt in range(self.max_retries):
            # Check if we've exceeded maximum total time
            elapsed_time = time.time() - start_time
            if elapsed_time > self.max_total_time:
                if not quiet:
                    total_minutes = self.max_total_time / 60
                    print(f"⏱️  Maximum total time ({total_minutes:.0f} minutes) exceeded for {operation_name}")
                    print(f"   Elapsed time: {elapsed_time / 60:.1f} minutes")
                    print(f"   This download is taking too long and may be stuck.")
                raise subprocess.TimeoutExpired(
                    cmd, 
                    self.max_total_time, 
                    f"Total time limit ({self.max_total_time}s) exceeded after {attempt} attempts"
                )
            try:
                # If this is a retry, add a delay
                if attempt > 0:
                    if last_error_type:
                        delay = self._calculate_retry_delay(attempt - 1, last_error_type)
                        if not quiet:
                            error_type_msg = {
                                'connection': 'Connection error',
                                'signature': 'Signature extraction error',
                                'rate_limit': 'Rate limit',
                                'server_error': 'Server error',
                                'timeout': 'Timeout',
                                'bot_detection': 'Bot detection',
                                'unknown': 'Error'
                            }.get(last_error_type, 'Error')
                            print(f"⏳ {error_type_msg} - Retrying {operation_name} in {delay:.1f} seconds... (attempt {attempt + 1}/{self.max_retries})")
                        time.sleep(delay)
                    
                    # If signature error occurred, try updating yt-dlp
                    if signature_error_occurred and not self.yt_dlp_update_attempted:
                        self._force_update_yt_dlp()
                
                # Run the command
                if progress_callback:
                    # Use progress tracking method with timeout tracking
                    result = self._run_download_with_progress(
                        cmd, 
                        progress_callback,
                        start_time=start_time,
                        max_total_time=self.max_total_time
                    )
                    # Check return code for progress-based downloads
                    if result.returncode != 0:
                        # Download failed - raise exception to trigger retry
                        error_output = result.stderr if result.stderr else (result.stdout if result.stdout else f"yt-dlp exited with code {result.returncode}")
                        raise subprocess.CalledProcessError(result.returncode, cmd, stderr=error_output, output=result.stdout)
                else:
                    # Use standard subprocess
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=self.timeout,
                        check=True
                    )
                
                # Success - reset update flag for future errors
                if signature_error_occurred:
                    self.yt_dlp_update_attempted = False
                
                return result
                
            except subprocess.TimeoutExpired as e:
                last_error = str(e)
                last_error_type = 'timeout'
                elapsed_time = time.time() - start_time
                
                if attempt < self.max_retries - 1:
                    # Check if we have enough time left for another retry
                    if elapsed_time + self.timeout + self.max_retry_delay > self.max_total_time:
                        if not quiet:
                            print(f"⏱️  Timeout on {operation_name} (attempt {attempt + 1})")
                            print(f"   Elapsed time: {elapsed_time / 60:.1f} minutes")
                            print(f"   Not enough time remaining for another retry (max {self.max_total_time / 60:.0f} minutes)")
                        raise
                    
                    if not quiet:
                        remaining_time = (self.max_total_time - elapsed_time) / 60
                        print(f"⏱️  Timeout on {operation_name} (attempt {attempt + 1}/{self.max_retries})")
                        print(f"   Elapsed: {elapsed_time / 60:.1f} min, Remaining: {remaining_time:.1f} min")
                        print(f"   Will retry...")
                    continue
                else:
                    if not quiet:
                        print(f"⏱️  Timeout on {operation_name} after {self.max_retries} attempts")
                        print(f"   Total elapsed time: {elapsed_time / 60:.1f} minutes")
                        print(f"   Maximum allowed time: {self.max_total_time / 60:.0f} minutes")
                        print(f"   This download may be stuck or your connection is too slow.")
                        print(f"   Try again later or check your internet connection.")
                    raise
                    
            except subprocess.CalledProcessError as e:
                error_output = e.stderr if e.stderr else (e.stdout if e.stdout else str(e))
                last_error = error_output
                
                # Check if error is retryable
                is_retryable, error_type = self._is_retryable_error(error_output)
                last_error_type = error_type
                
                # Track signature errors for update
                if error_type == 'signature':
                    signature_error_occurred = True
                
                if not is_retryable:
                    # Non-retryable error - fail immediately
                    if not quiet:
                        print(f"❌ {operation_name} failed with non-retryable error: {error_output[:200]}")
                    raise
                
                # Retryable error - continue to next attempt
                if attempt < self.max_retries - 1:
                    if not quiet:
                        error_preview = error_output[:150].replace('\n', ' ')
                        print(f"⚠️  {operation_name} failed ({error_type}): {error_preview}")
                        if error_type == 'signature' and not signature_error_occurred:
                            print("   This usually means yt-dlp needs to be updated. Will try updating...")
                        print(f"   Retrying... (attempt {attempt + 2}/{self.max_retries})")
                    continue
                else:
                    # Last attempt failed
                    if not quiet:
                        print(f"❌ {operation_name} failed after {self.max_retries} attempts")
                        if error_type == 'signature':
                            print("\n💡 Signature extraction errors usually mean yt-dlp needs updating.")
                            print("   Try manually updating: pip3 install --upgrade yt-dlp")
                            print("   Or if that doesn't work, sign in to YouTube in Chrome/Firefox")
                            print("   to use cookies (helps bypass YouTube's bot detection)")
                        elif error_type == 'bot_detection':
                            # Check if it was a 403/401 error
                            if any(keyword in (last_error or '').lower() for keyword in ['403', '401', 'forbidden', 'unauthorized']):
                                print("\n💡 YouTube blocked the request (403/401 Forbidden).")
                                print("   This usually means YouTube detected automated access.")
                                print("   Solutions:")
                                print("   1. Sign in to YouTube in Chrome or Firefox")
                                print("   2. The system will automatically use your browser cookies")
                                print("   3. Or wait a few minutes and try again")
                            else:
                                print("\n💡 YouTube bot detection triggered.")
                                print("   Try signing in to YouTube in Chrome/Firefox to use cookies")
                                print("   (helps bypass YouTube's bot detection)")
                    raise
                    
            except Exception as e:
                # Unexpected error - treat as retryable
                last_error = str(e)
                last_error_type = 'unknown'
                if attempt < self.max_retries - 1:
                    if not quiet:
                        print(f"⚠️  Unexpected error in {operation_name}: {e}")
                        print(f"   Retrying... (attempt {attempt + 2}/{self.max_retries})")
                    time.sleep(self._calculate_retry_delay(attempt, 'unknown'))
                    continue
                else:
                    raise
        
        # Should never reach here, but just in case
        raise subprocess.CalledProcessError(
            1,
            cmd,
            stderr=last_error or "Unknown error",
            output=""
        )
    
    def update_yt_dlp(self) -> bool:
        """
        Manually update yt-dlp.
        
        Call this method if you're experiencing signature extraction errors
        and the automatic update didn't work.
        
        Returns:
            True if update was successful, False otherwise
        """
        try:
            print("🔄 Updating yt-dlp...")
            # Reset the update flag to allow manual updates
            self.yt_dlp_update_attempted = False
            result = subprocess.run(
                ['pip3', 'install', '--upgrade', '--no-cache-dir', 'yt-dlp'], 
                capture_output=True, 
                text=True, 
                timeout=180,
                check=True
            )
            print("✅ yt-dlp updated successfully")
            print("   You can now retry your download.")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to update yt-dlp: {e}")
            print("   Try running manually: pip3 install --upgrade yt-dlp")
            return False
        except subprocess.TimeoutExpired:
            print("❌ Update timed out. Try running manually: pip3 install --upgrade yt-dlp")
            return False
        except Exception as e:
            print(f"❌ Unexpected error updating yt-dlp: {e}")
            return False
    
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
            # Don't use cookies with mobile clients (causes failures)
            cmd.extend([
                '--user-agent', 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                '--extractor-args', 'youtube:player_client=android_music'
            ])
            
            # Use robust retry wrapper
            result = self._run_yt_dlp_with_retry(
                cmd,
                operation_name=f"getting video info for {url[:50]}",
                quiet=True
            )
            return json.loads(result.stdout)  # Parse JSON output
            
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
                    result = self._run_yt_dlp_with_retry(
                        cmd,
                        operation_name=f"getting video info (android fallback) for {url[:50]}",
                        quiet=True
                    )
                    return json.loads(result.stdout)
                except Exception:
                    pass
            
            # Last resort: try web client with cookies
            cookie_browser = self._get_cookie_browser()
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
                    result = self._run_yt_dlp_with_retry(
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
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        if len(track_timestamps) != len(metadata_list):
            raise ValueError("track_timestamps and metadata_list must have the same length")
        
        output_files = []
        audio_extensions = ['.mp3', '.m4a', '.ogg', '.opus', '.flac', '.wav', '.aac', '.webm']
        system_files = {'.DS_Store', '.Thumbs.db', 'desktop.ini'}
        
        for i, (timestamp_info, metadata) in enumerate(zip(track_timestamps, metadata_list)):
            start_time = timestamp_info.get('start_time', 0)
            end_time = timestamp_info.get('end_time')
            
            # Create output filename
            title = self._sanitize_filename(metadata.get('title', f'track_{i+1}'))
            track_number = metadata.get('track_number', i + 1)
            track_prefix = f"{track_number:02d} - " if track_number else ""
            expected_base = f"{track_prefix}{title}"
            
            # Check if file already exists (try different extensions)
            output_path = None
            file_already_exists = False
            
            for ext in audio_extensions:
                potential_file = output_dir / f"{expected_base}{ext}"
                if potential_file.exists() and potential_file.is_file():
                    output_path = potential_file
                    file_already_exists = True
                    break
            
            # If not found with exact match, try glob pattern
            if not output_path:
                existing_files = [
                    f for f in output_dir.glob(f"{expected_base}*")
                    if f.is_file()
                    and f.suffix.lower() in audio_extensions
                    and f.name not in system_files
                ]
                if existing_files:
                    output_path = existing_files[0]
                    file_already_exists = True
            
            # If file doesn't exist, create the path for splitting
            if not output_path:
                output_filename = f"{expected_base}.mp3"
                output_path = output_dir / output_filename
            
            # If file already exists, skip splitting and add to output list
            if file_already_exists:
                output_files.append(output_path)
                if progress_callback:
                    # Update progress
                    progress = ((i + 1) / len(track_timestamps)) * 100
                    progress_callback({
                        'percent': progress,
                        'status': 'skipped',
                        'speed': None,
                        'eta': None
                    })
                continue
            
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
        Also removes sub-parts (a), b), c), etc.) from track titles to keep filenames shorter.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename safe for filesystem use
        """
        if not filename:
            return "unknown"
        
        sanitized = filename
        
        # Remove sub-parts like "a) ... / b) ... / c) ..." to shorten filenames
        # Pattern matches: "a) Title / b) Title / c) Title" or "a) Title, b) Title, c) Title"
        # This handles cases like "Alan's Psychedelic Breakfast: a) Rise and Shine / b) Sunny Side Up / c) Morning Glory"
        # Match pattern: colon (optional) followed by letter) followed by text, optionally repeated with / or ,
        # The pattern captures: ": a) ... / b) ... / c) ..." or just "a) ... / b) ... / c) ..."
        sub_part_pattern = r'(?::\s*)?[a-z]\)\s+[^/]+(?:\s*[/,]\s*[a-z]\)\s+[^/]+)*'
        
        # Try to match and remove sub-parts
        # First try with colon (most common case)
        if re.search(r':\s*[a-z]\)', sanitized, re.IGNORECASE):
            # Remove everything from colon onwards if it matches the sub-part pattern
            sanitized = re.sub(r':\s*[a-z]\)\s+[^/]+(?:\s*[/,]\s*[a-z]\)\s+[^/]+)*', '', sanitized, flags=re.IGNORECASE)
        # If no colon, try to match sub-parts at the end
        elif re.search(r'\s+[a-z]\)\s+', sanitized, re.IGNORECASE):
            # Remove sub-parts pattern from the end
            sanitized = re.sub(r'\s+[a-z]\)\s+[^/]+(?:\s*[/,]\s*[a-z]\)\s+[^/]+)*$', '', sanitized, flags=re.IGNORECASE)
        
        # Clean up any trailing separators
        sanitized = re.sub(r'[:;]\s*$', '', sanitized)
        sanitized = sanitized.strip()
        
        # Prevent path traversal attacks by removing .. sequences
        sanitized = sanitized.replace('..', '_')
        
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
                - If 'is_playlist' is True, creates Playlists/[playlist_name]/ structure
                - Otherwise, creates Artist/Album (year)/ structure
            
        Returns:
            Path object for the organized directory
            
        Security: This method ensures paths stay within the download directory
        to prevent path traversal attacks.
        """
        if not metadata:
            return self.download_dir
        
        # Check if this is a playlist (e.g., from Spotify)
        is_playlist = metadata.get('is_playlist', False)
        if is_playlist:
            playlist_name = metadata.get('playlist_name', metadata.get('album', 'Unknown Playlist'))
            playlist_name = self._sanitize_filename(playlist_name)
            
            # Create folder structure: Playlists/[Playlist Name]/
            organized_dir = self.download_dir / "Playlists" / playlist_name
            
            # Security: Resolve the path and ensure it's still within download_dir
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
        
        # Extract metadata fields for regular album structure
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
            
            # Detect different stages of the download process
            status = 'downloading'
            if '[extractaudio]' in line_lower or 'extracting' in line_lower:
                status = 'extracting'
            elif '[mergeformat]' in line_lower or 'merging' in line_lower:
                status = 'merging'
            elif '[download]' in line_lower:
                status = 'downloading'
            elif '[info]' in line_lower:
                if 'downloading' in line_lower:
                    status = 'downloading'
                elif 'extracting' in line_lower:
                    status = 'extracting'
            
            # Check if this is a download progress line
            # yt-dlp can output progress in various formats
            # Also check for extractor progress: [extractor] or [ExtractAudio]
            if '[download]' not in line_lower and '[extractaudio]' not in line_lower:
                # Also check for percentage without [download] tag (some formats)
                if '%' in line and ('downloading' in line_lower or 'of' in line_lower):
                    pass  # Might be a progress line
                else:
                    # Check if it's a status message we should report
                    if any(keyword in line_lower for keyword in ['extracting', 'merging', 'downloading', 'converting']):
                        # Return a status update even without percentage
                        if progress_callback:
                            progress_callback({
                                'percent': 0,
                                'status': status,
                                'speed': None,
                                'eta': None,
                                'message': line.strip()
                            })
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
                'status': status if percent < 100 else 'completed'
            }
            
            if progress_callback:
                progress_callback(progress_info)
            
            return progress_info
            
        except Exception:
            # Silently fail - not a progress line or parsing error
            pass
        
        return None
    
    def _run_download_with_progress(self, cmd: List[str], progress_callback: Optional[Callable] = None, start_time: Optional[float] = None, max_total_time: Optional[float] = None) -> subprocess.CompletedProcess:
        """
        Run download command with progress tracking and timeout protection.
        
        Args:
            cmd: Command to run
            progress_callback: Optional callback for progress updates
            start_time: Optional start time for total timeout tracking
            max_total_time: Optional maximum total time limit
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
        download_start_time = time.time()  # Start time for this download attempt
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
        download_start_time = time.time()
        
        stdout_lines = []
        stderr_lines = []
        
        while not (stdout_done and stderr_done):
            current_time = time.time()
            
            # Check for overall timeout (per attempt)
            elapsed = current_time - download_start_time
            if elapsed > timeout:
                process.kill()
                raise subprocess.TimeoutExpired(cmd, timeout, f"Download operation timed out after {timeout}s")
            
            # Check for maximum total time (across all retries)
            if start_time and max_total_time:
                total_elapsed = current_time - start_time
                if total_elapsed > max_total_time:
                    process.kill()
                    raise subprocess.TimeoutExpired(
                        cmd, 
                        max_total_time, 
                        f"Maximum total time ({max_total_time}s) exceeded. Download may be stuck."
                    )
            
            # Check for no activity timeout (process might be stuck)
            if current_time - last_activity_time > no_activity_timeout:
                # Check if process is still running
                if process.poll() is None:
                    process.kill()
                    raise subprocess.TimeoutExpired(
                        cmd, 
                        no_activity_timeout, 
                        f"Download operation appears stuck (no output for {no_activity_timeout}s)"
                    )
            
            # Check stdout
            if not stdout_done:
                try:
                    item_type, line = stdout_queue.get(timeout=0.1)
                    if item_type == 'done':
                        stdout_done = True
                    else:
                        stdout_lines.append(line)
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
                        stderr_lines.append(line)
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
        
        # Create CompletedProcess-like object with proper stdout/stderr separation
        result = subprocess.CompletedProcess(
            modified_cmd,
            process.returncode,
            stdout='\n'.join(stdout_lines),
            stderr='\n'.join(stderr_lines)
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
            # Prioritized based on analysis: android_music > android > fallbacks
            strategies = [
                self._build_command_strategy_1,  # android_music (fastest, ~9.74s)
                self._build_command_strategy_2,  # android (reliable, ~10.69s)
                self._build_command_strategy_3,  # android_music with retries
                self._build_command_strategy_4,  # android with retries
                self._build_command_strategy_5   # web with cookies (last resort)
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
                    
                    # Run download with robust retry logic
                    last_error = None
                    try:
                        # Use robust retry wrapper (handles both progress and non-progress cases)
                        result = self._run_yt_dlp_with_retry(
                            cmd,
                            operation_name=f"download (strategy {i})",
                            progress_callback=progress_callback,
                            quiet=quiet
                        )
                    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                        # Download failed - capture error message
                        last_error = e.stderr if hasattr(e, 'stderr') and e.stderr else (e.stdout if hasattr(e, 'stdout') and e.stdout else str(e))
                        last_strategy_error = last_error
                        # Continue to next strategy
                        continue
                    except Exception as e:
                        # Unexpected error
                        last_error = str(e)
                        last_strategy_error = last_error
                        continue
                    
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
                        # No new files created - download likely failed even though returncode was 0
                        # This can happen if yt-dlp reports success but doesn't actually download
                        downloaded_file = None
                        # Capture error from stderr if available
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
                    else:
                        # No file was downloaded even though returncode was 0
                        # Log this and continue to next strategy
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
                        # Continue to next strategy
                        if i < len(strategies):
                            continue
                        else:
                            # Last strategy failed - raise exception with last error
                            final_error = last_error or last_strategy_error or "All strategies completed but no files were downloaded"
                            raise Exception(f"All download strategies failed. Last error: {final_error[:200]}")
                        
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                    error_msg = e.stderr if hasattr(e, 'stderr') and e.stderr else (e.stdout if hasattr(e, 'stdout') and e.stdout else str(e))
                    last_strategy_error = error_msg
                    # Only print error messages if not in quiet mode and no progress callback
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
                    # Check which command was not found
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
            # Extract more meaningful error message
            error_str = str(e)
            if "No such file or directory" in error_str:
                # Try to extract the command name
                if "youtube-dl" in error_str:
                    error_str = "youtube-dl not found. Please install yt-dlp with: pip install yt-dlp"
                elif "yt-dlp" in error_str:
                    error_str = "yt-dlp not found. Please install it with: pip install yt-dlp"
            raise Exception(f"Error downloading video: {error_str}") from e
        
        # If we get here, all strategies were tried but none succeeded
        # This should not happen (should raise exception above), but just in case:
        final_error = last_strategy_error if 'last_strategy_error' in locals() else "All strategies failed without creating files"
        raise Exception(f"All download strategies failed. {final_error[:200]}")
    
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
    
    def _has_firefox_cookies(self) -> bool:
        """Check if Firefox cookies database exists."""
        firefox_cookie_paths = [
            Path.home() / "Library/Application Support/Firefox/Profiles",
            Path.home() / ".mozilla/firefox",
            Path.home() / "AppData/Roaming/Mozilla/Firefox/Profiles",
        ]
        
        for path in firefox_cookie_paths:
            if path.exists() and path.is_dir():
                # Check if there are any profile directories
                profiles = [p for p in path.iterdir() if p.is_dir()]
                if profiles:
                    return True
        return False
    
    def _get_cookie_browser(self) -> Optional[str]:
        """Get the first available browser for cookies (Chrome preferred, then Firefox)."""
        if self._has_chrome_cookies():
            return 'chrome'
        elif self._has_firefox_cookies():
            return 'firefox'
        return None
    
    def _build_command_strategy_1(self, url: str, quality: str, audio_only: bool, output_template: str) -> List[str]:
        """Strategy 1: android_music client (fastest, ~9.74s, 0.69 MB/s) - NO COOKIES"""
        # Analysis shows android_music is fastest and most reliable
        # Cookies with mobile clients actually cause failures, so we skip them
        cmd = [
            'yt-dlp',
            '--user-agent', 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            '--no-check-certificate',
            '--ignore-errors',
            '--no-warnings',
            '--extractor-args', 'youtube:player_client=android_music'  # Fastest player client
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
    
    def _build_command_strategy_2(self, url: str, quality: str, audio_only: bool, output_template: str) -> List[str]:
        """Strategy 2: android client (reliable, ~10.69s, 0.57 MB/s) - NO COOKIES"""
        # Analysis shows android client is reliable fallback
        # Cookies with mobile clients cause failures, so we skip them
        cmd = [
            'yt-dlp',
            '--user-agent', 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            '--no-check-certificate',
            '--ignore-errors',
            '--no-warnings',
            '--extractor-args', 'youtube:player_client=android'  # Reliable mobile client
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
        """Strategy 3: android_music with increased retries (fallback for unstable connections)"""
        # Use android_music with retries for better reliability
        cmd = [
            'yt-dlp',
            '--user-agent', 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            '--no-check-certificate',
            '--ignore-errors',
            '--no-warnings',
            '--extractor-args', 'youtube:player_client=android_music',
            '--retries', '10',
            '--fragment-retries', '10',
            '--extractor-retries', '3'
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
        """Strategy 4: android client with retries and request delays (fallback)"""
        # Use android with retries and delays for rate-limited scenarios
        cmd = [
            'yt-dlp',
            '--user-agent', 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            '--no-check-certificate',
            '--ignore-errors',
            '--no-warnings',
            '--extractor-args', 'youtube:player_client=android',
            '--retries', '10',
            '--fragment-retries', '10',
            '--sleep-requests', '1',  # Add delay between requests to avoid rate limiting
            '--sleep-interval', '1'
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
        """Strategy 5: Web client with cookies (last resort - web client has low success rate)"""
        # Web client is last resort as it has lower success rate
        # Only use cookies with web client (cookies break mobile clients)
        cmd = [
            'yt-dlp',
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            '--no-check-certificate',
            '--ignore-errors',
            '--no-warnings',
            '--extractor-args', 'youtube:player_client=web'
        ]
        
        # Only add cookies if available (cookies work with web client, not mobile)
        cookie_browser = self._get_cookie_browser()
        if cookie_browser:
            cmd.extend(['--cookies-from-browser', cookie_browser])
        
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
            
            # Use android_music client first (fastest, most reliable)
            # Don't use cookies with mobile clients (causes failures)
            cmd.extend([
                '--user-agent', 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                '--extractor-args', 'youtube:player_client=android_music'
            ])
            
            # Use robust retry wrapper
            result = self._run_yt_dlp_with_retry(
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
            
            # Try android client as fallback (android_music already tried above)
            cmd.extend([
                '--user-agent', 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                '--extractor-args', 'youtube:player_client=android'
            ])
            
            # Use robust retry wrapper
            result = self._run_yt_dlp_with_retry(
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
