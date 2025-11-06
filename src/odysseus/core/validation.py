"""
Configuration validation utilities.
"""

from pathlib import Path
from typing import List, Tuple
from .config import (
    DOWNLOADS_DIR,
    CONFIG_DIR,
    MUSICBRAINZ_CONFIG,
    DOWNLOAD_CONFIG,
    LOGGING_CONFIG,
    VALIDATION_RULES,
)
from .exceptions import ConfigurationError


def validate_configuration() -> Tuple[bool, List[str]]:
    """
    Validate application configuration.
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Validate directories
    try:
        if not DOWNLOADS_DIR.parent.exists():
            errors.append(f"Base directory does not exist: {DOWNLOADS_DIR.parent}")
        
        # Check if directories are writable (will be created if they don't exist)
        for dir_path in [DOWNLOADS_DIR, CONFIG_DIR]:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                # Try to write a test file
                test_file = dir_path / ".test_write"
                test_file.write_text("test")
                test_file.unlink()
            except (PermissionError, OSError) as e:
                errors.append(f"Cannot write to directory {dir_path}: {e}")
    except Exception as e:
        errors.append(f"Directory validation error: {e}")
    
    # Validate MusicBrainz config
    if MUSICBRAINZ_CONFIG["REQUEST_DELAY"] < 0:
        errors.append("MusicBrainz REQUEST_DELAY must be >= 0")
    
    if MUSICBRAINZ_CONFIG["MAX_RESULTS"] < 1:
        errors.append("MusicBrainz MAX_RESULTS must be >= 1")
    
    if MUSICBRAINZ_CONFIG["TIMEOUT"] < 1:
        errors.append("MusicBrainz TIMEOUT must be >= 1")
    
    # Validate download config
    valid_qualities = ["best", "audio", "worst", "bestaudio"]
    if DOWNLOAD_CONFIG["DEFAULT_QUALITY"] not in valid_qualities:
        errors.append(f"DEFAULT_QUALITY must be one of: {', '.join(valid_qualities)}")
    
    valid_formats = ["mp3", "wav", "flac", "aac", "ogg"]
    if DOWNLOAD_CONFIG["AUDIO_FORMAT"] not in valid_formats:
        errors.append(f"AUDIO_FORMAT must be one of: {', '.join(valid_formats)}")
    
    if DOWNLOAD_CONFIG["MAX_CONCURRENT_DOWNLOADS"] < 1:
        errors.append("MAX_CONCURRENT_DOWNLOADS must be >= 1")
    
    if DOWNLOAD_CONFIG["TIMEOUT"] < 1:
        errors.append("DOWNLOAD TIMEOUT must be >= 1")
    
    # Validate logging config
    valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if LOGGING_CONFIG["LEVEL"] not in valid_log_levels:
        errors.append(f"LOG_LEVEL must be one of: {', '.join(valid_log_levels)}")
    
    is_valid = len(errors) == 0
    return is_valid, errors


def validate_and_raise():
    """
    Validate configuration and raise ConfigurationError if invalid.
    """
    is_valid, errors = validate_configuration()
    if not is_valid:
        error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ConfigurationError(error_msg)

