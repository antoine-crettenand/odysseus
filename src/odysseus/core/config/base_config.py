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
def _get_project_root() -> Path:
    """Locate the project root independently of the launch directory."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").is_file():
            return parent

    return Path.cwd()


PROJECT_ROOT = _get_project_root()
PROJECT_DOWNLOADS_DIR = PROJECT_ROOT / "downloads"

# Backward-compatible names for callers that import the original constants.
BASE_DIR = PROJECT_ROOT
DOWNLOADS_DIR = PROJECT_DOWNLOADS_DIR
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

# Logging Configuration
LOGGING_CONFIG = {
    "LEVEL": os.getenv("ODYSSEUS_LOG_LEVEL", "WARNING"),
    "FORMAT": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
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
