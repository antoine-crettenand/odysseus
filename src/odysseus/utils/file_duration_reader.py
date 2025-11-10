"""
Utility to read actual audio file durations from downloaded files.
"""

from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def get_file_duration(file_path: Path) -> Optional[float]:
    """
    Get the actual duration of an audio file in seconds.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Duration in seconds, or None if unable to read
    """
    try:
        from mutagen import File as MutagenFile
        
        audio_file = MutagenFile(str(file_path))
        if audio_file is None:
            logger.debug(f"Could not load audio file: {file_path}")
            return None
        
        # Get length from mutagen (in seconds)
        if hasattr(audio_file, 'info') and hasattr(audio_file.info, 'length'):
            duration = audio_file.info.length
            if duration and duration > 0:
                return float(duration)
        
        logger.debug(f"No duration found in file: {file_path}")
        return None
        
    except ImportError:
        logger.warning("mutagen library not available. Cannot read file duration.")
        return None
    except Exception as e:
        logger.debug(f"Error reading file duration from {file_path}: {e}")
        return None


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to MM:SS or HH:MM:SS format.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string (MM:SS or HH:MM:SS)
    """
    if seconds is None or seconds < 0:
        return "—"
    
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def parse_duration_to_seconds(duration_str: Optional[str]) -> Optional[float]:
    """
    Parse duration string (MM:SS or HH:MM:SS) to seconds.
    
    Args:
        duration_str: Duration string in MM:SS or HH:MM:SS format
        
    Returns:
        Duration in seconds, or None if unable to parse
    """
    if not duration_str or duration_str == "—":
        return None
    
    try:
        parts = duration_str.split(':')
        if len(parts) == 2:  # MM:SS
            minutes, seconds = map(int, parts)
            return minutes * 60 + seconds
        elif len(parts) == 3:  # HH:MM:SS
            hours, minutes, seconds = map(int, parts)
            return hours * 3600 + minutes * 60 + seconds
    except (ValueError, AttributeError):
        pass
    
    return None

