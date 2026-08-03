"""
Configuration module for Odysseus.
Imports and combines all domain-specific configurations.
"""

# Import base config first
from .base_config import (
    PROJECT_NAME,
    PROJECT_VERSION,
    PROJECT_DESCRIPTION,
    PROJECT_ROOT,
    PROJECT_DOWNLOADS_DIR,
    BASE_DIR,
    DOWNLOADS_DIR,
    CONFIG_DIR
)

# Import domain-specific configs
from .musicbrainz_config import MUSICBRAINZ_CONFIG
from .discogs_config import DISCOGS_CONFIG
from .youtube_config import YOUTUBE_CONFIG
from .download_config import DOWNLOAD_CONFIG
from .cache_config import CACHE_CONFIG
from .retry_config import RETRY_CONFIG
from .apple_music_config import APPLE_MUSIC_CONFIG
from .acoustid_config import ACOUSTID_CONFIG

# Import other configs
from .base_config import (
    ERROR_MESSAGES,
    LOGGING_CONFIG,
    VALIDATION_RULES,
    DURATION_VALIDATION_THRESHOLDS,
)

__all__ = [
    'PROJECT_NAME',
    'PROJECT_VERSION',
    'PROJECT_DESCRIPTION',
    'PROJECT_ROOT',
    'PROJECT_DOWNLOADS_DIR',
    'BASE_DIR',
    'DOWNLOADS_DIR',
    'CONFIG_DIR',
    'MUSICBRAINZ_CONFIG',
    'DISCOGS_CONFIG',
    'YOUTUBE_CONFIG',
    'DOWNLOAD_CONFIG',
    'CACHE_CONFIG',
    'RETRY_CONFIG',
    'APPLE_MUSIC_CONFIG',
    'ACOUSTID_CONFIG',
    'ERROR_MESSAGES',
    'LOGGING_CONFIG',
    'VALIDATION_RULES',
    'DURATION_VALIDATION_THRESHOLDS',
]
