"""
Tests for data models.
"""

import pytest
from odysseus.models.song import SongData, AudioMetadata
from odysseus.models.releases import Track, ReleaseInfo


class TestSongData:
    """Tests for SongData model."""

    def test_song_data_basic(self):
        """Test basic SongData creation."""
        song = SongData(title="Test Song", artist="Test Artist")

        assert song.title == "Test Song"
        assert song.artist == "Test Artist"
        assert song.album is None
        assert song.release_year is None

    def test_song_data_full(self):
        """Test SongData with all fields."""
        song = SongData(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            release_year=2020,
            genre="Rock"
        )

        assert song.title == "Test Song"
        assert song.artist == "Test Artist"
        assert song.album == "Test Album"
        assert song.release_year == 2020
        assert song.genre == "Rock"

    def test_song_data_missing_artist(self):
        """Test SongData validation requires artist."""
        with pytest.raises(ValueError, match="Artist must be provided"):
            SongData(title="Test Song", artist="")

    def test_song_data_missing_title_and_album(self):
        """Test SongData validation requires title or album."""
        with pytest.raises(ValueError, match="Either title or album must be provided"):
            SongData(title="", artist="Test Artist", album="")


class TestAudioMetadata:
    """Tests for AudioMetadata model."""

    def test_audio_metadata_basic(self):
        """Test basic AudioMetadata creation."""
        metadata = AudioMetadata()

        assert metadata.title is None
        assert metadata.artist is None
        assert metadata.source == "unknown"

    def test_audio_metadata_full(self):
        """Test AudioMetadata with all fields."""
        metadata = AudioMetadata(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            track_number=1,
            total_tracks=10,
            year=2020,
            genre="Rock"
        )

        assert metadata.title == "Test Song"
        assert metadata.artist == "Test Artist"
        assert metadata.album == "Test Album"
        assert metadata.track_number == 1
        assert metadata.total_tracks == 10
        assert metadata.year == 2020
        assert metadata.genre == "Rock"

    def test_audio_metadata_invalid_track_number(self):
        """Test AudioMetadata with invalid track number."""
        metadata = AudioMetadata(track_number=0)

        assert metadata.track_number is None

    def test_audio_metadata_invalid_total_tracks(self):
        """Test AudioMetadata with invalid total tracks."""
        metadata = AudioMetadata(total_tracks=0)

        assert metadata.total_tracks is None


class TestTrack:
    """Tests for Track model."""

    def test_track_basic(self):
        """Test basic Track creation."""
        track = Track(position=1, title="Test Track", artist="Test Artist")

        assert track.position == 1
        assert track.title == "Test Track"
        assert track.artist == "Test Artist"
        assert track.duration is None
        assert track.mbid is None

    def test_track_full(self):
        """Test Track with all fields."""
        track = Track(
            position=1,
            title="Test Track",
            artist="Test Artist",
            duration="3:45",
            mbid="12345678-1234-1234-1234-123456789012"
        )

        assert track.position == 1
        assert track.title == "Test Track"
        assert track.artist == "Test Artist"
        assert track.duration == "3:45"
        assert track.mbid == "12345678-1234-1234-1234-123456789012"


class TestReleaseInfo:
    """Tests for ReleaseInfo model."""

    def test_release_info_basic(self):
        """Test basic ReleaseInfo creation."""
        release = ReleaseInfo(title="Test Album", artist="Test Artist")

        assert release.title == "Test Album"
        assert release.artist == "Test Artist"
        assert release.tracks == []
        assert release.release_date is None
        assert release.mbid == ""

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

    def test_release_info_full(self):
        """Test ReleaseInfo with all fields."""
        release = ReleaseInfo(
            title="Test Album",
            artist="Test Artist",
            release_date="2020-01-01",
            original_release_date="2019-01-01",
            genre="Rock",
            release_type="Album",
            mbid="12345678-1234-1234-1234-123456789012",
            url="https://example.com/album",
            cover_art_url="https://example.com/cover.jpg"
        )

        assert release.title == "Test Album"
        assert release.artist == "Test Artist"
        assert release.release_date == "2020-01-01"
        assert release.original_release_date == "2019-01-01"
        assert release.genre == "Rock"
        assert release.release_type == "Album"
        assert release.mbid == "12345678-1234-1234-1234-123456789012"
        assert release.url == "https://example.com/album"
        assert release.cover_art_url == "https://example.com/cover.jpg"
