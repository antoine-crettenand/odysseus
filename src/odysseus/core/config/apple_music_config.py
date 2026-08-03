"""Apple Music catalog API configuration."""

import os

from .base_config import PROJECT_NAME, PROJECT_VERSION


APPLE_MUSIC_CONFIG = {
    "BASE_URL": os.getenv("APPLE_MUSIC_BASE_URL", "https://api.music.apple.com/v1"),
    "DEVELOPER_TOKEN": os.getenv("APPLE_MUSIC_DEVELOPER_TOKEN", ""),
    "STOREFRONT": os.getenv("APPLE_MUSIC_STOREFRONT", "us").lower(),
    "USER_AGENT": f"{PROJECT_NAME}/{PROJECT_VERSION}",
    "REQUEST_DELAY": float(os.getenv("APPLE_MUSIC_REQUEST_DELAY", "0.1")),
    "MAX_RESULTS": int(os.getenv("APPLE_MUSIC_MAX_RESULTS", "10")),
    "TIMEOUT": int(os.getenv("APPLE_MUSIC_TIMEOUT", "30")),
}
