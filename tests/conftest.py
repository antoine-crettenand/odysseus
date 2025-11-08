"""
Pytest configuration and shared fixtures.
"""

import pytest
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
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
def temp_audio_file(temp_dir: Path) -> Path:
    """Create a temporary audio file for testing."""
    audio_file = temp_dir / "test_audio.mp3"
    audio_file.write_bytes(b"fake audio data")
    return audio_file


@pytest.fixture
def mock_requests_get():
    """Mock requests.get for API testing."""
    with patch('requests.get') as mock_get:
        yield mock_get


@pytest.fixture
def mock_requests_post():
    """Mock requests.post for API testing."""
    with patch('requests.post') as mock_post:
        yield mock_post


@pytest.fixture
def mock_musicbrainz_client():
    """Mock MusicBrainz client."""
    client = Mock()
    client.search_recordings = Mock(return_value=[])
    client.search_releases = Mock(return_value=[])
    client.get_release = Mock(return_value=None)
    return client


@pytest.fixture
def mock_discogs_client():
    """Mock Discogs client."""
    client = Mock()
    client.search = Mock(return_value=[])
    client.get_release = Mock(return_value=None)
    return client


@pytest.fixture
def mock_youtube_client():
    """Mock YouTube client."""
    client = Mock()
    client.search = Mock(return_value=[])
    return client


@pytest.fixture
def mock_youtube_downloader():
    """Mock YouTube downloader."""
    downloader = Mock()
    downloader.download = Mock(return_value=None)
    return downloader


@pytest.fixture
def sample_song_data():
    """Sample song data for testing."""
    from odysseus.models.song import SongData
    return SongData(
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
        release_year=2020
    )


@pytest.fixture
def sample_audio_metadata():
    """Sample audio metadata for testing."""
    from odysseus.models.song import AudioMetadata
    return AudioMetadata(
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
        year=2020,
        genre="Rock",
        track_number=1,
        total_tracks=10
    )


@pytest.fixture
def sample_musicbrainz_song():
    """Sample MusicBrainz song result."""
    from odysseus.models.search_results import MusicBrainzSong
    return MusicBrainzSong(
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
        release_date="2020-01-01",
        mbid="test-mbid-123",
        score=100
    )


@pytest.fixture
def sample_youtube_video():
    """Sample YouTube video result."""
    from odysseus.models.search_results import YouTubeVideo
    return YouTubeVideo(
        title="Test Song",
        artist="Test Artist",
        video_id="test_video_id",
        channel="Test Channel",
        duration="3:45",
        views="1000",
        score=90
    )


@pytest.fixture
def sample_discogs_release():
    """Sample Discogs release result."""
    from odysseus.models.search_results import DiscogsRelease
    return DiscogsRelease(
        title="Test Album",
        artist="Test Artist",
        album="Test Album",
        year=2020,
        genre="Rock",
        discogs_id="123456",
        score=85
    )


@pytest.fixture
def sample_release_info():
    """Sample release info with tracks."""
    from odysseus.models.releases import ReleaseInfo, Track
    return ReleaseInfo(
        title="Test Album",
        artist="Test Artist",
        release_date="2020-01-01",
        genre="Rock",
        release_type="Album",
        mbid="test-mbid-123",
        tracks=[
            Track(position=1, title="Track 1", artist="Test Artist", duration="3:45"),
            Track(position=2, title="Track 2", artist="Test Artist", duration="4:20"),
        ]
    )

