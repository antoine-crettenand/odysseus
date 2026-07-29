"""
YouTube configuration.
"""

import os


YOUTUBE_CONFIG = {
    "BASE_URL": "https://www.youtube.com",
    "API_BASE_URL": "https://www.googleapis.com/youtube/v3",
    "API_KEY": os.getenv("YOUTUBE_API_KEY", ""),
    "USER_AGENT": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0 Safari/537.36"
    ),
    "MAX_RESULTS": 3,
    "MAX_RETRIES": 3,
    "TIMEOUT": 30,
}
