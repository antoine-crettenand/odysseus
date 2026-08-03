"""AcoustID audio-fingerprint verification configuration."""

import os


ACOUSTID_CONFIG = {
    "BASE_URL": os.getenv("ACOUSTID_BASE_URL", "https://api.acoustid.org/v2"),
    "API_KEY": os.getenv("ACOUSTID_API_KEY", ""),
    "FPCALC_PATH": os.getenv("ACOUSTID_FPCALC_PATH", "fpcalc"),
    "MIN_SCORE": float(os.getenv("ACOUSTID_MIN_SCORE", "0.8")),
    # AcoustID asks clients to stay at or below three requests per second.
    "REQUEST_DELAY": float(os.getenv("ACOUSTID_REQUEST_DELAY", "0.34")),
    "TIMEOUT": int(os.getenv("ACOUSTID_TIMEOUT", "30")),
}
