"""
Tests for song models.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from odysseus.models.song import SongData, AudioMetadata


class TestSongData:
    """Tests for SongData model."""
    
    def test_song_data_creation(self):
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
    
    def test_song_data_minimal(self):
        """Test SongData with minimal required fields."""
        song = SongData(title="Test", artist="Artist")
        assert song.title == "Test"
        assert song.artist == "Artist"
        assert song.album is None
    
    def test_song_data_validation_valid_year(self):
        """Test SongData with valid year."""
        song = SongData(title="Test", artist="Artist", release_year=2020)
        assert song.release_year == 2020
    
    def test_song_data_validation_invalid_year_too_old(self):
        """Test SongData with invalid year (too old)."""
        song = SongData(title="Test", artist="Artist", release_year=1800)
        assert song.release_year is None
    
    def test_song_data_validation_invalid_year_too_new(self):
        """Test SongData with invalid year (too new)."""
        song = SongData(title="Test", artist="Artist", release_year=2050)
        assert song.release_year is None
    
    def test_song_data_validation_valid_year_boundary(self):
        """Test SongData with valid year at boundaries."""
        song1 = SongData(title="Test", artist="Artist", release_year=1900)
        assert song1.release_year == 1900
        
        song2 = SongData(title="Test", artist="Artist", release_year=2030)
        assert song2.release_year == 2030
    
    def test_song_data_missing_artist_raises_error(self):
        """Test that missing artist raises ValueError."""
        with pytest.raises(ValueError, match="Artist must be provided"):
            SongData(title="Test", artist="")
    
    def test_song_data_missing_title_and_album_raises_error(self):
        """Test that missing both title and album raises ValueError."""
        with pytest.raises(ValueError, match="Either title or album must be provided"):
            SongData(title="", artist="Artist", album="")
    
    def test_song_data_with_album_only(self):
        """Test SongData with only album (no title)."""
        song = SongData(title="", artist="Artist", album="Test Album")
        assert song.album == "Test Album"
        assert song.title == ""


class TestAudioMetadata:
    """Tests for AudioMetadata model."""
    
    def test_audio_metadata_creation(self):
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
    
    def test_audio_metadata_empty(self):
        """Test AudioMetadata with no fields."""
        metadata = AudioMetadata()
        assert metadata.title is None
        assert metadata.artist is None
        assert metadata.source == "unknown"
    
    def test_audio_metadata_validation_valid_year(self):
        """Test AudioMetadata with valid year."""
        metadata = AudioMetadata(title="Test", artist="Artist", year=2020)
        assert metadata.year == 2020
    
    def test_audio_metadata_validation_invalid_year_too_old(self):
        """Test AudioMetadata with invalid year (too old)."""
        metadata = AudioMetadata(title="Test", artist="Artist", year=1800)
        assert metadata.year is None
    
    def test_audio_metadata_validation_invalid_year_too_new(self):
        """Test AudioMetadata with invalid year (too new)."""
        metadata = AudioMetadata(title="Test", artist="Artist", year=2050)
        assert metadata.year is None
    
    def test_audio_metadata_validation_valid_track_number(self):
        """Test AudioMetadata with valid track number."""
        metadata = AudioMetadata(
            title="Test",
            artist="Artist",
            track_number=5,
            total_tracks=10
        )
        assert metadata.track_number == 5
    
    def test_audio_metadata_validation_invalid_track_number_zero(self):
        """Test AudioMetadata with invalid track number (zero)."""
        metadata = AudioMetadata(
            title="Test",
            artist="Artist",
            track_number=0,
            total_tracks=10
        )
        assert metadata.track_number is None
    
    def test_audio_metadata_validation_invalid_track_number_negative(self):
        """Test AudioMetadata with invalid track number (negative)."""
        metadata = AudioMetadata(
            title="Test",
            artist="Artist",
            track_number=-1,
            total_tracks=10
        )
        assert metadata.track_number is None
    
    def test_audio_metadata_validation_invalid_total_tracks_zero(self):
        """Test AudioMetadata with invalid total tracks (zero)."""
        metadata = AudioMetadata(
            title="Test",
            artist="Artist",
            track_number=1,
            total_tracks=0
        )
        assert metadata.total_tracks is None
    
    def test_audio_metadata_validation_invalid_total_tracks_negative(self):
        """Test AudioMetadata with invalid total tracks (negative)."""
        metadata = AudioMetadata(
            title="Test",
            artist="Artist",
            track_number=1,
            total_tracks=-1
        )
        assert metadata.total_tracks is None
    
    def test_audio_metadata_all_fields(self):
        """Test AudioMetadata with all fields populated."""
        metadata = AudioMetadata(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            album_artist="Test Album Artist",
            track_number=1,
            total_tracks=10,
            disc_number=1,
            total_discs=1,
            year=2020,
            genre="Rock",
            comment="Test comment",
            composer="Test Composer",
            conductor="Test Conductor",
            performer="Test Performer",
            publisher="Test Publisher",
            copyright="Test Copyright",
            isrc="USRC17607839",
            bpm=120,
            key="C major",
            mood="Happy",
            cover_art_url="https://example.com/cover.jpg",
            cover_art_data=b"fake image data",
            source="test_source"
        )
        
        assert metadata.title == "Test Song"
        assert metadata.artist == "Test Artist"
        assert metadata.album == "Test Album"
        assert metadata.album_artist == "Test Album Artist"
        assert metadata.track_number == 1
        assert metadata.total_tracks == 10
        assert metadata.disc_number == 1
        assert metadata.total_discs == 1
        assert metadata.year == 2020
        assert metadata.genre == "Rock"
        assert metadata.comment == "Test comment"
        assert metadata.composer == "Test Composer"
        assert metadata.conductor == "Test Conductor"
        assert metadata.performer == "Test Performer"
        assert metadata.publisher == "Test Publisher"
        assert metadata.copyright == "Test Copyright"
        assert metadata.isrc == "USRC17607839"
        assert metadata.bpm == 120
        assert metadata.key == "C major"
        assert metadata.mood == "Happy"
        assert metadata.cover_art_url == "https://example.com/cover.jpg"
        assert metadata.cover_art_data == b"fake image data"
        assert metadata.source == "test_source"

