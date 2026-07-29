"""
MusicBrainz API configuration.
"""

import os
from .base_config import PROJECT_NAME, PROJECT_VERSION

MUSICBRAINZ_CONFIG = {
    "BASE_URL": os.getenv("MUSICBRAINZ_BASE_URL", "https://musicbrainz.org/ws/2"),
    "USER_AGENT": os.getenv(
        "MUSICBRAINZ_USER_AGENT",
        f"{PROJECT_NAME}/{PROJECT_VERSION} "
        "(https://github.com/antoine-crettenand/odysseus)"
    ),
    "REQUEST_DELAY": float(os.getenv("MUSICBRAINZ_REQUEST_DELAY", "1.0")),
    "MAX_RESULTS": int(os.getenv("MUSICBRAINZ_MAX_RESULTS", "3")),
    "TIMEOUT": int(os.getenv("MUSICBRAINZ_TIMEOUT", "30")),
}
