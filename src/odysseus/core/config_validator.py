"""
Configuration validation utilities.
"""
from typing import List
from .exceptions import ConfigurationError
from .config import (
    MUSICBRAINZ_CONFIG,
    DISCOGS_CONFIG,
    DOWNLOAD_CONFIG,
    VALIDATION_RULES
)


def validate_config() -> None:
    """
    Validate all configuration values.
    
    Raises:
        ConfigurationError: If any configuration value is invalid
    """
    errors: List[str] = []
    
    # Validate MusicBrainz config
    if MUSICBRAINZ_CONFIG["REQUEST_DELAY"] < 0:
        errors.append("MUSICBRAINZ_REQUEST_DELAY must be >= 0")
    
    if MUSICBRAINZ_CONFIG["TIMEOUT"] <= 0:
        errors.append("MUSICBRAINZ_TIMEOUT must be > 0")
    
    if MUSICBRAINZ_CONFIG["MAX_RESULTS"] <= 0:
        errors.append("MUSICBRAINZ_MAX_RESULTS must be > 0")
    
    # Validate Discogs config
    if DISCOGS_CONFIG["REQUEST_DELAY"] < 0:
        errors.append("DISCOGS_REQUEST_DELAY must be >= 0")
    
    if DISCOGS_CONFIG["TIMEOUT"] <= 0:
        errors.append("DISCOGS_TIMEOUT must be > 0")
    
    if DISCOGS_CONFIG["MAX_RESULTS"] <= 0:
        errors.append("DISCOGS_MAX_RESULTS must be > 0")
    
    # Validate Download config
    if DOWNLOAD_CONFIG["MAX_CONCURRENT_DOWNLOADS"] <= 0:
        errors.append("MAX_CONCURRENT_DOWNLOADS must be > 0")
    
    if DOWNLOAD_CONFIG["TIMEOUT"] <= 0:
        errors.append("DOWNLOAD_TIMEOUT must be > 0")
    
    # Validate validation rules
    min_year = VALIDATION_RULES.get("MIN_YEAR", 1900)
    max_year = VALIDATION_RULES.get("MAX_YEAR", 2030)
    
    if min_year >= max_year:
        errors.append("MIN_YEAR must be less than MAX_YEAR")
    
    if min_year < 1900 or max_year > 2100:
        errors.append("Year range should be reasonable (1900-2100)")
    
    if errors:
        raise ConfigurationError(
            "Configuration validation failed",
            details={"errors": errors}
        )


def validate_musicbrainz_config() -> None:
    """Validate MusicBrainz configuration only."""
    errors: List[str] = []
    
    if MUSICBRAINZ_CONFIG["REQUEST_DELAY"] < 0:
        errors.append("MUSICBRAINZ_REQUEST_DELAY must be >= 0")
    
    if MUSICBRAINZ_CONFIG["TIMEOUT"] <= 0:
        errors.append("MUSICBRAINZ_TIMEOUT must be > 0")
    
    if MUSICBRAINZ_CONFIG["MAX_RESULTS"] <= 0:
        errors.append("MUSICBRAINZ_MAX_RESULTS must be > 0")
    
    if errors:
        raise ConfigurationError(
            "MusicBrainz configuration validation failed",
            details={"errors": errors}
        )


def validate_discogs_config() -> None:
    """Validate Discogs configuration only."""
    errors: List[str] = []
    
    if DISCOGS_CONFIG["REQUEST_DELAY"] < 0:
        errors.append("DISCOGS_REQUEST_DELAY must be >= 0")
    
    if DISCOGS_CONFIG["TIMEOUT"] <= 0:
        errors.append("DISCOGS_TIMEOUT must be > 0")
    
    if DISCOGS_CONFIG["MAX_RESULTS"] <= 0:
        errors.append("DISCOGS_MAX_RESULTS must be > 0")
    
    if errors:
        raise ConfigurationError(
            "Discogs configuration validation failed",
            details={"errors": errors}
        )


def validate_download_config() -> None:
    """Validate download configuration only."""
    errors: List[str] = []
    
    if DOWNLOAD_CONFIG["MAX_CONCURRENT_DOWNLOADS"] <= 0:
        errors.append("MAX_CONCURRENT_DOWNLOADS must be > 0")
    
    if DOWNLOAD_CONFIG["TIMEOUT"] <= 0:
        errors.append("DOWNLOAD_TIMEOUT must be > 0")
    
    if errors:
        raise ConfigurationError(
            "Download configuration validation failed",
            details={"errors": errors}
        )

