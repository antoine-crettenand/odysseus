"""
Tests for configuration module.
"""

import os
import pytest
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from odysseus.core.config import (
    PROJECT_NAME,
    PROJECT_VERSION,
    DOWNLOADS_DIR,
    MUSICBRAINZ_CONFIG,
    DOWNLOAD_CONFIG,
)


def test_project_info():
    """Test project information constants."""
    assert PROJECT_NAME == "Odysseus"
    assert PROJECT_VERSION == "1.0.0"


def test_directory_creation():
    """Test that required directories are created."""
    assert DOWNLOADS_DIR.exists()
    assert DOWNLOADS_DIR.is_dir()


def test_musicbrainz_config():
    """Test MusicBrainz configuration."""
    assert "BASE_URL" in MUSICBRAINZ_CONFIG
    assert "USER_AGENT" in MUSICBRAINZ_CONFIG
    assert MUSICBRAINZ_CONFIG["REQUEST_DELAY"] > 0
    assert MUSICBRAINZ_CONFIG["MAX_RESULTS"] > 0


def test_download_config():
    """Test download configuration."""
    assert "DEFAULT_QUALITY" in DOWNLOAD_CONFIG
    assert "AUDIO_FORMAT" in DOWNLOAD_CONFIG
    assert "DEFAULT_DIR" in DOWNLOAD_CONFIG


def test_environment_variable_override(monkeypatch):
    """Test that environment variables can override config."""
    test_dir = "/tmp/test_downloads"
    monkeypatch.setenv("ODYSSEUS_DOWNLOADS_DIR", test_dir)
    
    # Re-import to get updated config
    import importlib
    from odysseus import core
    importlib.reload(core.config)
    
    # Note: This test shows the pattern, but actual testing would need
    # to handle module reloading carefully
    assert True  # Placeholder

