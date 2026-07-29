"""
Configuration module for Odysseus.
Imports and combines all domain-specific configurations.
"""

# Import base config first
from .base_config import (
    PROJECT_NAME,
    PROJECT_VERSION,
    PROJECT_DESCRIPTION,
    BASE_DIR,
    DOWNLOADS_DIR,
    CONFIG_DIR
)

# Import domain-specific configs
from .musicbrainz_config import MUSICBRAINZ_CONFIG
from .discogs_config import DISCOGS_CONFIG
from .youtube_config import YOUTUBE_CONFIG
from .download_config import DOWNLOAD_CONFIG
from .ui_config import UI_CONFIG
from .cache_config import CACHE_CONFIG
from .retry_config import RETRY_CONFIG

# Import other configs
from .base_config import (
    ERROR_MESSAGES,
    SUCCESS_MESSAGES,
    FILE_EXTENSIONS,
    QUALITY_PRESETS,
    SEARCH_TYPES,
    LOGGING_CONFIG,
    API_LIMITS,
    DEFAULTS,
    VALIDATION_RULES,
    DURATION_VALIDATION_THRESHOLDS,
    COLORS,
    MENU_OPTIONS,
    HELP_TEXT
)

__all__ = [
    'PROJECT_NAME',
    'PROJECT_VERSION',
    'PROJECT_DESCRIPTION',
    'BASE_DIR',
    'DOWNLOADS_DIR',
    'CONFIG_DIR',
    'MUSICBRAINZ_CONFIG',
    'DISCOGS_CONFIG',
    'YOUTUBE_CONFIG',
    'DOWNLOAD_CONFIG',
    'UI_CONFIG',
    'CACHE_CONFIG',
    'RETRY_CONFIG',
    'ERROR_MESSAGES',
    'SUCCESS_MESSAGES',
    'FILE_EXTENSIONS',
    'QUALITY_PRESETS',
    'SEARCH_TYPES',
    'LOGGING_CONFIG',
    'API_LIMITS',
    'DEFAULTS',
    'VALIDATION_RULES',
    'DURATION_VALIDATION_THRESHOLDS',
    'COLORS',
    'MENU_OPTIONS',
    'HELP_TEXT'
]
