"""
Discogs API configuration.
"""

import os
from .base_config import PROJECT_NAME, PROJECT_VERSION

DISCOGS_CONFIG = {
    "BASE_URL": os.getenv("DISCOGS_BASE_URL", "https://api.discogs.com"),
    "USER_AGENT": os.getenv(
        "DISCOGS_USER_AGENT",
        f"{PROJECT_NAME}/{PROJECT_VERSION} "
        "(https://github.com/antoine-crettenand/odysseus)"
    ),
    "USER_TOKEN": os.getenv("DISCOGS_USER_TOKEN", ""),
    "REQUEST_DELAY": float(os.getenv("DISCOGS_REQUEST_DELAY", "1.0")),
    "MAX_RESULTS": int(os.getenv("DISCOGS_MAX_RESULTS", "3")),
    "TIMEOUT": int(os.getenv("DISCOGS_TIMEOUT", "30")),
}
