"""Application configuration and dependency validation."""

import importlib
import subprocess
import tempfile
from typing import List, Tuple

from ..config import (
    CONFIG_DIR,
    DISCOGS_CONFIG,
    DOWNLOAD_CONFIG,
    DOWNLOADS_DIR,
    LOGGING_CONFIG,
    MUSICBRAINZ_CONFIG,
    VALIDATION_RULES,
)
from ..exceptions import ConfigurationError


def check_dependencies() -> Tuple[bool, List[str]]:
    """Return whether all runtime dependencies are importable and executable."""
    required_packages = {
        "requests": "requests",
        "mutagen": "mutagen",
        "yt_dlp": "yt-dlp",
        "rich": "rich",
    }

    missing = []
    for module_name, package_name in required_packages.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(package_name)

    required_executables = {
        "yt-dlp": (["yt-dlp", "--version"], "yt-dlp (command line tool)"),
        "ffmpeg": (["ffmpeg", "-version"], "ffmpeg (audio transcoder)"),
    }
    for command, label in required_executables.values():
        try:
            subprocess.run(
                command,
                capture_output=True,
                check=True,
                timeout=5,
            )
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            missing.append(label)

    return not missing, missing


def _validate_directories(errors: List[str]) -> None:
    """Create configured directories and verify that each is writable."""
    for directory in (DOWNLOADS_DIR, CONFIG_DIR):
        try:
            directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=directory,
                prefix=".odysseus-write-test-",
            ):
                pass
        except (PermissionError, OSError) as error:
            errors.append(f"Cannot write to directory {directory}: {error}")


def _validate_api_config(name: str, config: dict, errors: List[str]) -> None:
    """Validate settings shared by the MusicBrainz and Discogs clients."""
    if config["REQUEST_DELAY"] < 0:
        errors.append(f"{name} REQUEST_DELAY must be >= 0")
    if config["MAX_RESULTS"] < 1:
        errors.append(f"{name} MAX_RESULTS must be >= 1")
    if config["TIMEOUT"] < 1:
        errors.append(f"{name} TIMEOUT must be >= 1")


def validate_configuration() -> Tuple[bool, List[str]]:
    """Return whether the complete application configuration is valid."""
    errors: List[str] = []

    dependencies_ok, missing_dependencies = check_dependencies()
    if not dependencies_ok:
        errors.append(
            f"Missing required dependencies: {', '.join(missing_dependencies)}. "
            'Please install them with: python -m pip install -e "."'
        )

    _validate_directories(errors)
    _validate_api_config("MusicBrainz", MUSICBRAINZ_CONFIG, errors)
    _validate_api_config("Discogs", DISCOGS_CONFIG, errors)

    valid_qualities = {"best", "audio", "worst", "bestaudio"}
    if DOWNLOAD_CONFIG["DEFAULT_QUALITY"] not in valid_qualities:
        errors.append(
            f"DEFAULT_QUALITY must be one of: {', '.join(sorted(valid_qualities))}"
        )

    valid_formats = {"mp3", "wav", "flac", "ogg"}
    if DOWNLOAD_CONFIG["AUDIO_FORMAT"] not in valid_formats:
        errors.append(
            f"AUDIO_FORMAT must be one of: {', '.join(sorted(valid_formats))}"
        )
    if DOWNLOAD_CONFIG["MAX_CONCURRENT_DOWNLOADS"] < 1:
        errors.append("MAX_CONCURRENT_DOWNLOADS must be >= 1")
    if DOWNLOAD_CONFIG["TIMEOUT"] < 1:
        errors.append("DOWNLOAD TIMEOUT must be >= 1")

    valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if LOGGING_CONFIG["LEVEL"] not in valid_log_levels:
        errors.append(
            f"LOG_LEVEL must be one of: {', '.join(sorted(valid_log_levels))}"
        )

    min_year = VALIDATION_RULES.get("MIN_YEAR", 1900)
    max_year = VALIDATION_RULES.get("MAX_YEAR", 2030)
    if min_year >= max_year:
        errors.append("MIN_YEAR must be less than MAX_YEAR")
    if min_year < 1900 or max_year > 2100:
        errors.append("Year range should be reasonable (1900-2100)")

    return not errors, errors


def validate_config() -> None:
    """Raise :class:`ConfigurationError` when configuration is invalid."""
    is_valid, errors = validate_configuration()
    if not is_valid:
        raise ConfigurationError(
            "Configuration validation failed",
            details={"errors": errors},
        )


def validate_and_raise() -> None:
    """Validate startup configuration and raise on failure."""
    validate_config()


def _validate_named_api_config(name: str, config: dict) -> None:
    errors: List[str] = []
    _validate_api_config(name, config, errors)
    if errors:
        raise ConfigurationError(
            f"{name} configuration validation failed",
            details={"errors": errors},
        )


def validate_musicbrainz_config() -> None:
    """Validate MusicBrainz configuration only."""
    _validate_named_api_config("MusicBrainz", MUSICBRAINZ_CONFIG)


def validate_discogs_config() -> None:
    """Validate Discogs configuration only."""
    _validate_named_api_config("Discogs", DISCOGS_CONFIG)


def validate_download_config() -> None:
    """Validate download configuration only."""
    errors: List[str] = []
    if DOWNLOAD_CONFIG["MAX_CONCURRENT_DOWNLOADS"] < 1:
        errors.append("MAX_CONCURRENT_DOWNLOADS must be >= 1")
    if DOWNLOAD_CONFIG["TIMEOUT"] < 1:
        errors.append("DOWNLOAD TIMEOUT must be >= 1")
    if errors:
        raise ConfigurationError(
            "Download configuration validation failed",
            details={"errors": errors},
        )
