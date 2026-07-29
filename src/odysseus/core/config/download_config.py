"""
Download configuration.
"""

import os
from .base_config import DOWNLOADS_DIR

DOWNLOAD_CONFIG = {
    "DEFAULT_QUALITY": os.getenv("ODYSSEUS_DEFAULT_QUALITY", "best"),
    "AUDIO_FORMAT": os.getenv("ODYSSEUS_AUDIO_FORMAT", "mp3"),
    "DEFAULT_DIR": str(DOWNLOADS_DIR),
    "MAX_CONCURRENT_DOWNLOADS": int(os.getenv("ODYSSEUS_MAX_CONCURRENT_DOWNLOADS", "3")),
    "TIMEOUT": int(os.getenv("ODYSSEUS_DOWNLOAD_TIMEOUT", "300")),
}
