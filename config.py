#!/usr/bin/env python3
"""
Configuration file for Odysseus Music Discovery Tool
Contains all constants, settings, and global parameters.
"""

import os
from pathlib import Path

# Project Information
PROJECT_NAME = "Odysseus"
PROJECT_VERSION = "1.0.0"
PROJECT_DESCRIPTION = "Music Discovery Tool - Search MusicBrainz, find YouTube videos, and download music"

# File Paths
BASE_DIR = Path(__file__).parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
CONFIG_DIR = BASE_DIR / "config"
LOGS_DIR = BASE_DIR / "logs"

# Create directories if they don't exist
DOWNLOADS_DIR.mkdir(exist_ok=True)
CONFIG_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# MusicBrainz Configuration
MUSICBRAINZ_CONFIG = {
    "BASE_URL": "https://musicbrainz.org/ws/2",
    "USER_AGENT": f"{PROJECT_NAME}/{PROJECT_VERSION} (contact@example.com)",
    "REQUEST_DELAY": 1.0,  # Rate limiting - MusicBrainz allows 1 request per second
    "MAX_RESULTS": 3,
    "TIMEOUT": 30,
}

# YouTube Configuration
YOUTUBE_CONFIG = {
    "BASE_URL": "https://www.youtube.com",
    "USER_AGENT": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0 Safari/537.36"
    ),
    "MAX_RESULTS": 3,
    "MAX_RETRIES": 3,
    "TIMEOUT": 30,
}

# Download Configuration
DOWNLOAD_CONFIG = {
    "DEFAULT_QUALITY": "best",
    "AUDIO_FORMAT": "mp3",
    "DEFAULT_DIR": str(DOWNLOADS_DIR),
    "MAX_CONCURRENT_DOWNLOADS": 3,
    "TIMEOUT": 300,  # 5 minutes
}

# User Interface Configuration
UI_CONFIG = {
    "SEPARATOR_LENGTH": 60,
    "MAX_DISPLAY_RESULTS": 3,
    "PROMPT_TIMEOUT": 30,  # seconds
}

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
    "LEVEL": "INFO",
    "FORMAT": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "FILE": str(LOGS_DIR / "odysseus.log"),
    "MAX_SIZE": 10 * 1024 * 1024,  # 10MB
    "BACKUP_COUNT": 5,
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

# Color Codes for Terminal Output (if supported)
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
