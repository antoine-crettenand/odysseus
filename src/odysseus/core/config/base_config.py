"""
Base configuration for Odysseus.
Contains project information, paths, and common constants.
"""

import os
from pathlib import Path

# Project Information
PROJECT_NAME = "Odysseus"
PROJECT_VERSION = "1.0.0"
PROJECT_DESCRIPTION = "Music Discovery Tool - Search MusicBrainz, find YouTube videos, and download music"

# File Paths
def _get_base_dir() -> Path:
    """Get the base directory for the project."""
    downloads_env = os.getenv("ODYSSEUS_DOWNLOADS_DIR")
    if downloads_env:
        return Path(downloads_env).parent

    current = Path(__file__).resolve()
    for parent in [current.parent, current.parent.parent, current.parent.parent.parent, current.parent.parent.parent.parent]:
        if (parent / "pyproject.toml").exists() or (parent / "README.md").exists():
            return parent

    return Path.cwd()

BASE_DIR = _get_base_dir()
DOWNLOADS_DIR = Path(os.getenv("ODYSSEUS_DOWNLOADS_DIR", BASE_DIR / "downloads"))
CONFIG_DIR = Path(os.getenv("ODYSSEUS_CONFIG_DIR", BASE_DIR / "config"))

# Error Messages
ERROR_MESSAGES = {
    "INVALID_YEAR": "Invalid year format. Proceeding without year.",
    "NO_RESULTS": "No results found.",
    "INVALID_SELECTION": "Please enter a valid number or 'q' to quit",
    "DOWNLOAD_FAILED": "Download failed.",
    "NETWORK_ERROR": "Network error occurred.",
    "INVALID_URL": "Invalid URL provided.",
    "MISSING_DEPENDENCY": "Required dependency not found.",
}

# Success Messages
SUCCESS_MESSAGES = {
    "DOWNLOAD_COMPLETE": "Download completed successfully!",
    "SEARCH_COMPLETE": "Search completed successfully!",
    "INSTALLATION_COMPLETE": "Installation completed successfully!",
}

# File Extensions
FILE_EXTENSIONS = {
    "AUDIO": [".mp3", ".wav", ".flac", ".aac", ".ogg"],
    "VIDEO": [".mp4", ".webm", ".mkv", ".avi"],
    "SUBTITLES": [".srt", ".vtt"],
}

# Quality Presets
QUALITY_PRESETS = {
    "BEST": "best",
    "WORST": "worst",
    "AUDIO_ONLY": "audio",
    "VIDEO_ONLY": "video",
}

# Search Types
SEARCH_TYPES = {
    "RECORDING": "recording",
    "RELEASE": "release",
    "ARTIST": "artist",
    "LABEL": "label",
}

# Logging Configuration
LOGGING_CONFIG = {
    "LEVEL": os.getenv("ODYSSEUS_LOG_LEVEL", "WARNING"),
    "FORMAT": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
}

# API Limits
API_LIMITS = {
    "MUSICBRAINZ_REQUESTS_PER_SECOND": 1,
    "YOUTUBE_REQUESTS_PER_MINUTE": 100,
    "MAX_RETRIES": 3,
    "BACKOFF_FACTOR": 2,
}

# Default Values
DEFAULTS = {
    "ARTIST": "Unknown Artist",
    "TITLE": "Unknown Title",
    "ALBUM": "Unknown Album",
    "YEAR": None,
    "DURATION": "Unknown",
    "VIEWS": "Unknown",
    "CHANNEL": "Unknown Channel",
}

# Validation Rules
VALIDATION_RULES = {
    "MIN_YEAR": 1900,
    "MAX_YEAR": 2030,
    "MIN_TITLE_LENGTH": 1,
    "MAX_TITLE_LENGTH": 200,
    "MIN_ARTIST_LENGTH": 1,
    "MAX_ARTIST_LENGTH": 100,
}

# Duration Validation Thresholds
DURATION_VALIDATION_THRESHOLDS = {
    "LONGER_THRESHOLD": 0.10,
    "SHORTER_THRESHOLD": 0.25,
    "WARNING_THRESHOLD": 0.05,
}

# Color Codes for Terminal Output
COLORS = {
    "RED": "\033[91m",
    "GREEN": "\033[92m",
    "YELLOW": "\033[93m",
    "BLUE": "\033[94m",
    "MAGENTA": "\033[95m",
    "CYAN": "\033[96m",
    "WHITE": "\033[97m",
    "BOLD": "\033[1m",
    "UNDERLINE": "\033[4m",
    "END": "\033[0m",
}

# Menu Options
MENU_OPTIONS = {
    "DOWNLOAD": {
        "BEST_QUALITY": "1",
        "AUDIO_ONLY": "2",
        "SPECIFIC_QUALITY": "3",
    },
    "SEARCH": {
        "RECORDINGS": "1",
        "RELEASES": "2",
        "ARTISTS": "3",
    },
    "EXIT": "q",
    "QUIT": "quit",
}

# Help Text
HELP_TEXT = {
    "MAIN": f"""
{PROJECT_NAME} - Music Discovery Tool v{PROJECT_VERSION}

This tool helps you:
1. Search for music information using MusicBrainz
2. Find corresponding YouTube videos
3. Download videos or audio files

Usage: python3 main.py
""",
    "SEARCH": """
Search Options:
- Enter song title and artist (minimum required)
- Album name (optional)
- Release year (optional)
""",
    "DOWNLOAD": """
Download Options:
1. Best quality video
2. Audio only (MP3)
3. Specific quality (shows available formats)
""",
}
