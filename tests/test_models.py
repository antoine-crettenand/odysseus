"""
Tests for data models.
"""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from odysseus.models.song import SongData, AudioMetadata


def test_song_data_creation():
    """Test SongData model creation."""
    song = SongData(
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
        release_year=2020
    )
    
    assert song.title == "Test Song"
    assert song.artist == "Test Artist"
    assert song.album == "Test Album"
    assert song.release_year == 2020


def test_song_data_validation():
    """Test SongData validation."""
    # Valid year
    song = SongData(title="Test", artist="Artist", release_year=2020)
    assert song.release_year == 2020
    
    # Invalid year should be set to None
    song = SongData(title="Test", artist="Artist", release_year=1800)
    assert song.release_year is None


def test_audio_metadata_creation():
    """Test AudioMetadata model creation."""
    metadata = AudioMetadata(
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
        year=2020
    )
    
    assert metadata.title == "Test Song"
    assert metadata.artist == "Test Artist"
    assert metadata.album == "Test Album"
    assert metadata.year == 2020


def test_audio_metadata_validation():
    """Test AudioMetadata validation."""
    # Valid track number
    metadata = AudioMetadata(
        title="Test",
        artist="Artist",
        track_number=5,
        total_tracks=10
    )
    assert metadata.track_number == 5
    
    # Invalid track number should be set to None
    metadata = AudioMetadata(
        title="Test",
        artist="Artist",
        track_number=0,
        total_tracks=10
    )
    assert metadata.track_number is None

