"""
Progress Tracker Module
Handles parsing and tracking of yt-dlp download progress.
"""

import re
from typing import Dict, Any, Optional, Callable, Tuple

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
