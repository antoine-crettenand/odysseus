"""
Shared pytest fixtures and configuration for test suite.
"""

import pytest
import sys
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from typing import Generator

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def temp_downloads_dir(temp_dir: Path) -> Path:
    """Create a temporary downloads directory."""
    downloads_dir = temp_dir / "downloads"
    downloads_dir.mkdir(exist_ok=True)
    return downloads_dir


@pytest.fixture
def temp_config_dir(temp_dir: Path) -> Path:
    """Create a temporary config directory."""
    config_dir = temp_dir / "config"
    config_dir.mkdir(exist_ok=True)
    return config_dir


@pytest.fixture
def mock_container():
    """Create a mock dependency injection container."""
    container = MagicMock()
    return container


@pytest.fixture
def mock_spotify_client():
    """Create a mock Spotify client."""
    client = MagicMock()
    client.parse_spotify_url = MagicMock()
    client.get_playlist_tracks = MagicMock()
    client.get_album_tracks = MagicMock()
    client.get_track_info = MagicMock()
    return client


@pytest.fixture
def mock_youtube_downloader():
    """Create a mock YouTube downloader."""
    downloader = MagicMock()
    downloader.download_audio = MagicMock()
    downloader.get_video_info = MagicMock()
    return downloader


@pytest.fixture
def mock_search_service():
    """Create a mock search service."""
    service = MagicMock()
    service.search_recording = MagicMock()
    service.search_release = MagicMock()
    service.search_discography = MagicMock()
    return service


@pytest.fixture
def mock_download_service():
    """Create a mock download service."""
    service = MagicMock()
    service.download_track = MagicMock()
    service.download_release = MagicMock()
    return service


@pytest.fixture
def mock_metadata_service():
    """Create a mock metadata service."""
    service = MagicMock()
    service.apply_metadata = MagicMock()
    service.get_cover_art = MagicMock()
    return service


@pytest.fixture
def sample_track_data():
    """Sample track data for testing."""
    return {
        "title": "Test Song",
        "artist": "Test Artist",
        "album": "Test Album",
        "year": "2020",
        "duration": 180,
        "track_number": 1,
        "total_tracks": 10,
    }


@pytest.fixture
def sample_release_data():
    """Sample release data for testing."""
    return {
        "title": "Test Album",
        "artist": "Test Artist",
        "year": "2020",
        "tracks": [
            {"title": "Track 1", "duration": 180, "track_number": 1},
            {"title": "Track 2", "duration": 200, "track_number": 2},
        ],
    }


@pytest.fixture
def sample_spotify_track():
    """Sample Spotify track data."""
    return {
        "name": "Test Song",
        "artists": [{"name": "Test Artist"}],
        "album": {"name": "Test Album", "release_date": "2020"},
        "duration_ms": 180000,
        "track_number": 1,
        "external_urls": {"spotify": "https://open.spotify.com/track/123"},
    }


@pytest.fixture
def mock_requests_get():
    """Mock requests.get for HTTP testing."""
    with patch("requests.get") as mock_get:
        yield mock_get


@pytest.fixture
def mock_requests_post():
    """Mock requests.post for HTTP testing."""
    with patch("requests.post") as mock_post:
        yield mock_post


@pytest.fixture
def mock_subprocess_run():
    """Mock subprocess.run for command execution testing."""
    with patch("subprocess.run") as mock_run:
        yield mock_run


@pytest.fixture
def mock_path_exists():
    """Mock Path.exists for file system testing."""
    with patch("pathlib.Path.exists") as mock_exists:
        yield mock_exists


@pytest.fixture
def mock_path_mkdir():
    """Mock Path.mkdir for directory creation testing."""
    with patch("pathlib.Path.mkdir") as mock_mkdir:
        yield mock_mkdir


@pytest.fixture(autouse=True)
def reset_environment(monkeypatch):
    """Reset environment variables before each test."""
    # Store original values
    env_vars = [
        "ODYSSEUS_CONFIG_DIR",
        "SPOTIFY_CLIENT_ID",
        "SPOTIFY_CLIENT_SECRET",
        "YOUTUBE_API_KEY",
        "DISCOGS_USER_TOKEN",
        "APPLE_MUSIC_DEVELOPER_TOKEN",
        "APPLE_MUSIC_STOREFRONT",
        "ACOUSTID_API_KEY",
        "MUSICBRAINZ_BASE_URL",
        "MUSICBRAINZ_REQUEST_DELAY",
    ]
    original_values = {}
    for var in env_vars:
        original_values[var] = os.environ.get(var)
        monkeypatch.delenv(var, raising=False)

    yield

    # Restore original values
    for var, value in original_values.items():
        if value is not None:
            monkeypatch.setenv(var, value)
        else:
            monkeypatch.delenv(var, raising=False)


@pytest.fixture
def mock_logger():
    """Mock logger for testing."""
    logger = MagicMock()
    logger.debug = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.exception = MagicMock()
    return logger
