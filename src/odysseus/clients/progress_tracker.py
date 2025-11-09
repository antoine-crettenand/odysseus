"""
Progress Tracker Module
Handles parsing and tracking of yt-dlp download progress.
"""

import re
import subprocess
import threading
import time
from queue import Queue
from typing import Dict, Any, Optional, List, Callable


class ProgressTracker:
    """Tracks and parses download progress from yt-dlp output."""
    
    @staticmethod
    def convert_size_to_bytes(size_str: str) -> Optional[float]:
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
    
    @staticmethod
    def parse_progress_line(line: str, progress_callback: Optional[Callable] = None) -> Optional[Dict[str, Any]]:
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
                total_size_bytes = ProgressTracker.convert_size_to_bytes(total_size_str)
            
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
                    speed_bytes_per_sec = ProgressTracker.convert_size_to_bytes(f"{speed_val} {speed_unit.rstrip('/s')}")
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
    
    @staticmethod
    def run_download_with_progress(
        cmd: List[str],
        progress_callback: Optional[Callable] = None,
        start_time: Optional[float] = None,
        max_total_time: Optional[float] = None,
        timeout: int = 600
    ) -> subprocess.CompletedProcess:
        """
        Run download command with progress tracking and timeout protection.
        
        Args:
            cmd: Command to run
            progress_callback: Optional callback for progress updates
            start_time: Optional start time for total timeout tracking
            max_total_time: Optional maximum total time limit
            timeout: Per-attempt timeout in seconds
        """
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
                            ProgressTracker.parse_progress_line(line, progress_callback)
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
                            ProgressTracker.parse_progress_line(line, progress_callback)
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

