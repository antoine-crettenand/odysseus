"""
Progress Tracker Module
Handles parsing and tracking of yt-dlp download progress.
"""

import re
import subprocess
import threading
import time
from queue import Queue
from typing import Dict, Any, Optional, List, Callable, Tuple

# Regex patterns
PERCENT_PATTERN = r'(\d+\.?\d*)%'
TOTAL_SIZE_PATTERN = r'of\s+(~?[\d.]+\s*[KMGT]?i?B)'
SPEED_PATTERN = r'(?:at\s+)?([\d.]+)\s*([KMGT]?i?B/s)'
ETA_PATTERNS = [
    (r'ETA\s+(\d+):(\d+)', lambda m: (f"{m.group(1)}:{m.group(2).zfill(2)}", int(m.group(1)) * 60 + int(m.group(2)))),
    (r'ETA\s+(\d+)h\s*(\d+)m', lambda m: (f"{m.group(1)}h {m.group(2)}m", int(m.group(1)) * 3600 + int(m.group(2)) * 60)),
    (r'ETA\s+(\d+)m\s*(\d+)s', lambda m: (f"{m.group(1)}m {m.group(2)}s", int(m.group(1)) * 60 + int(m.group(2))))
]

# Size multipliers
SIZE_MULTIPLIERS = {
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


class ProgressTracker:
    """Tracks and parses download progress from yt-dlp output."""

    @staticmethod
    def convert_size_to_bytes(size_str: str) -> Optional[float]:
        """Convert size string (e.g., '5.2MiB', '1.5GB') to bytes."""
        if not size_str:
            return None

        size_str = size_str.strip().lstrip('~')
        match = re.match(r'([\d.]+)\s*([KMGT]?i?B)', size_str, re.IGNORECASE)
        if not match:
            return None

        value = float(match.group(1))
        unit = match.group(2).upper()
        return value * SIZE_MULTIPLIERS.get(unit, 1)

    @staticmethod
    def _detect_status(line_lower: str) -> str:
        """Detect status from line content."""
        if '[extractaudio]' in line_lower or 'extracting' in line_lower:
            return 'extracting'
        if '[mergeformat]' in line_lower or 'merging' in line_lower:
            return 'merging'
        return 'downloading'

    @staticmethod
    def _parse_speed(line: str) -> Tuple[Optional[str], Optional[float]]:
        """Parse speed from line."""
        match = re.search(SPEED_PATTERN, line, re.IGNORECASE)
        if match:
            speed_val, speed_unit = float(match.group(1)), match.group(2)
            speed_str = f"{speed_val} {speed_unit}"
            speed_bytes = ProgressTracker.convert_size_to_bytes(f"{speed_val} {speed_unit.rstrip('/s')}")
            return speed_str, speed_bytes
        return None, None

    @staticmethod
    def _parse_eta(line: str) -> Tuple[Optional[str], Optional[int]]:
        """Parse ETA from line and return (eta_str, eta_seconds)."""
        for pattern, parser in ETA_PATTERNS:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                return parser(match)
        return None, None

    @staticmethod
    def parse_progress_line(line: str, progress_callback: Optional[Callable] = None) -> Optional[Dict[str, Any]]:
        """Parse yt-dlp progress output line."""
        if not line or not line.strip():
            return None

        try:
            line_lower = line.lower()
            status = ProgressTracker._detect_status(line_lower)

            # Check if this is a progress line
            if '[download]' not in line_lower and '[extractaudio]' not in line_lower:
                if '%' not in line or ('downloading' not in line_lower and 'of' not in line_lower):
                    if any(kw in line_lower for kw in ['extracting', 'merging', 'downloading', 'converting']):
                        if progress_callback:
                            progress_callback({'percent': 0, 'status': status, 'speed': None, 'eta': None, 'message': line.strip()})
                    return None

            # Extract percentage
            percent_match = re.search(PERCENT_PATTERN, line)
            if not percent_match:
                return None

            percent = float(percent_match.group(1))
            total_size_bytes = None
            total_size_match = re.search(TOTAL_SIZE_PATTERN, line, re.IGNORECASE)
            if total_size_match:
                total_size_bytes = ProgressTracker.convert_size_to_bytes(total_size_match.group(1))

            speed_str, speed_bytes_per_sec = ProgressTracker._parse_speed(line)
            eta_str, eta_seconds = ProgressTracker._parse_eta(line)

            progress_info = {
                'percent': percent,
                'total_bytes': total_size_bytes,
                'downloaded_bytes': (percent / 100.0) * total_size_bytes if total_size_bytes and percent else None,
                'speed': speed_str,
                'speed_bytes_per_sec': speed_bytes_per_sec,
                'eta': eta_str,
                'eta_seconds': eta_seconds,
                'status': 'completed' if percent >= 100 else status
            }

            if progress_callback:
                progress_callback(progress_info)

            return progress_info
        except Exception:
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

        def read_stream(stream, queue):
            """Read from a stream and put lines in queue."""
            try:
                for line in iter(stream.readline, ''):
                    if line:
                        queue.put(('line', line.rstrip('\r\n')))
            except Exception:
                pass
            finally:
                queue.put(('done', None))

        stdout_queue, stderr_queue = Queue(), Queue()
        stdout_thread = threading.Thread(target=read_stream, args=(process.stdout, stdout_queue), daemon=True)
        stderr_thread = threading.Thread(target=read_stream, args=(process.stderr, stderr_queue), daemon=True)
        stdout_thread.start()
        stderr_thread.start()

        stdout_done = stderr_done = False
        stdout_lines, stderr_lines = [], []
        last_activity_time = download_start_time = time.time()
        no_activity_timeout = 60

        def process_queue(queue, lines_list, done_flag):
            """Process a queue and return (done, line)."""
            try:
                item_type, line = queue.get(timeout=0.1)
                if item_type == 'done':
                    return True, None
                lines_list.append(line)
                if progress_callback:
                    ProgressTracker.parse_progress_line(line, progress_callback)
                return False, line
            except:
                return False, None

        while not (stdout_done and stderr_done):
            current_time = time.time()
            elapsed = current_time - download_start_time

            if elapsed > timeout:
                process.kill()
                raise subprocess.TimeoutExpired(cmd, timeout, f"Download operation timed out after {timeout}s")

            if start_time and max_total_time and (current_time - start_time) > max_total_time:
                process.kill()
                raise subprocess.TimeoutExpired(cmd, max_total_time, f"Maximum total time ({max_total_time}s) exceeded")

            if current_time - last_activity_time > no_activity_timeout and process.poll() is None:
                process.kill()
                raise subprocess.TimeoutExpired(cmd, no_activity_timeout, f"Download appears stuck (no output for {no_activity_timeout}s)")

            if not stdout_done:
                stdout_done, _ = process_queue(stdout_queue, stdout_lines, stdout_done)
                if not stdout_done:
                    last_activity_time = time.time()

            if not stderr_done:
                stderr_done, _ = process_queue(stderr_queue, stderr_lines, stderr_done)
                if not stderr_done:
                    last_activity_time = time.time()

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

