"""
Tests for release models.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from odysseus.models.releases import Track, ReleaseInfo


class TestTrack:
    """Tests for Track model."""
    
    def test_track_creation(self):
        """Test Track model creation."""
        track = Track(
            position=1,
            title="Test Track",
            artist="Test Artist",
            duration="3:45",
            mbid="test-mbid-123"
        )
        
        assert track.position == 1
        assert track.title == "Test Track"
        assert track.artist == "Test Artist"
        assert track.duration == "3:45"
        assert track.mbid == "test-mbid-123"
    
    def test_track_minimal(self):
        """Test Track with minimal required fields."""
        track = Track(position=1, title="Test", artist="Artist")
        assert track.position == 1
        assert track.title == "Test"
        assert track.artist == "Artist"
        assert track.duration is None
        assert track.mbid is None


class TestReleaseInfo:
    """Tests for ReleaseInfo model."""
    
    def test_release_info_creation(self):
        """Test ReleaseInfo model creation."""
        release = ReleaseInfo(
            title="Test Album",
            artist="Test Artist",
            release_date="2020-01-01",
            genre="Rock",
            release_type="Album",
            mbid="test-mbid-123",
            url="https://example.com/release"
        )
        
        assert release.title == "Test Album"
        assert release.artist == "Test Artist"
        assert release.release_date == "2020-01-01"
        assert release.genre == "Rock"
        assert release.release_type == "Album"
        assert release.mbid == "test-mbid-123"
        assert release.url == "https://example.com/release"
        assert release.tracks == []
    
    def test_release_info_with_tracks(self):
        """Test ReleaseInfo with tracks."""
        tracks = [
            Track(position=1, title="Track 1", artist="Artist"),
            Track(position=2, title="Track 2", artist="Artist"),
        ]
        release = ReleaseInfo(
            title="Test Album",
            artist="Test Artist",
            tracks=tracks
        )
        
        assert len(release.tracks) == 2
        assert release.tracks[0].title == "Track 1"
        assert release.tracks[1].title == "Track 2"
    
    def test_release_info_tracks_initialized_empty(self):
        """Test that tracks list is initialized as empty if not provided."""
        release = ReleaseInfo(title="Test", artist="Artist")
        assert release.tracks == []
        assert isinstance(release.tracks, list)
    
    def test_release_info_minimal(self):
        """Test ReleaseInfo with minimal required fields."""
        release = ReleaseInfo(title="Test", artist="Artist")
        assert release.title == "Test"
        assert release.artist == "Artist"
        assert release.release_date is None
        assert release.genre is None
        assert release.release_type is None
        assert release.mbid == ""
        assert release.url == ""
        assert release.tracks == []
    
    def test_release_info_all_fields(self):
        """Test ReleaseInfo with all fields populated."""
        tracks = [
            Track(position=1, title="Track 1", artist="Artist", duration="3:45"),
            Track(position=2, title="Track 2", artist="Artist", duration="4:20"),
        ]
        release = ReleaseInfo(
            title="Test Album",
            artist="Test Artist",
            release_date="2020-01-01",
            genre="Rock",
            release_type="Album",
            mbid="test-mbid-123",
            url="https://example.com/release",
            tracks=tracks
        )
        
        assert release.title == "Test Album"
        assert release.artist == "Test Artist"
        assert release.release_date == "2020-01-01"
        assert release.genre == "Rock"
        assert release.release_type == "Album"
        assert release.mbid == "test-mbid-123"
        assert release.url == "https://example.com/release"
        assert len(release.tracks) == 2

