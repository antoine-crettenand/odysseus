"""
Tests for search result models.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from odysseus.models.search_results import (
    SearchResult,
    MusicBrainzSong,
    YouTubeVideo,
    DiscogsRelease,
    LastFmTrack,
    SpotifyTrack,
    GeniusSong
)


class TestSearchResult:
    """Tests for SearchResult abstract base class."""
    
    def test_search_result_cannot_be_instantiated(self):
        """Test that SearchResult cannot be instantiated directly."""
        with pytest.raises(TypeError):
            SearchResult(title="Test", artist="Artist", source="test")


class TestMusicBrainzSong:
    """Tests for MusicBrainzSong model."""
    
    def test_musicbrainz_song_creation(self):
        """Test MusicBrainzSong model creation."""
        song = MusicBrainzSong(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            release_date="2020-01-01",
            genre="Rock",
            release_type="Album",
            mbid="test-mbid-123",
            score=100,
            url="https://musicbrainz.org/recording/test-mbid-123"
        )
        
        assert song.title == "Test Song"
        assert song.artist == "Test Artist"
        assert song.album == "Test Album"
        assert song.release_date == "2020-01-01"
        assert song.genre == "Rock"
        assert song.release_type == "Album"
        assert song.mbid == "test-mbid-123"
        assert song.score == 100
        assert song.source == "musicbrainz"
        assert song.url == "https://musicbrainz.org/recording/test-mbid-123"
    
    def test_musicbrainz_song_get_display_name_with_title(self):
        """Test get_display_name with title."""
        song = MusicBrainzSong(title="Test Song", artist="Artist")
        assert song.get_display_name() == "Test Song"
    
    def test_musicbrainz_song_get_display_name_with_album_only(self):
        """Test get_display_name with album only."""
        song = MusicBrainzSong(title="", artist="Artist", album="Test Album")
        assert song.get_display_name() == "Test Album"
    
    def test_musicbrainz_song_get_display_name_fallback(self):
        """Test get_display_name fallback to Unknown."""
        song = MusicBrainzSong(title="", artist="Artist", album="")
        assert song.get_display_name() == "Unknown"
    
    def test_musicbrainz_song_defaults(self):
        """Test MusicBrainzSong with default values."""
        song = MusicBrainzSong(title="Test", artist="Artist")
        assert song.album is None
        assert song.release_date is None
        assert song.genre is None
        assert song.release_type is None
        assert song.mbid == ""
        assert song.score == 0
        assert song.source == "musicbrainz"


class TestYouTubeVideo:
    """Tests for YouTubeVideo model."""
    
    def test_youtube_video_creation(self):
        """Test YouTubeVideo model creation."""
        video = YouTubeVideo(
            title="Test Song",
            artist="Test Artist",
            video_id="test_video_id",
            channel="Test Channel",
            duration="3:45",
            views="1000",
            publish_time="2020-01-01",
            url_suffix="/watch?v=test_video_id",
            score=90
        )
        
        assert video.title == "Test Song"
        assert video.artist == "Test Artist"
        assert video.video_id == "test_video_id"
        assert video.channel == "Test Channel"
        assert video.duration == "3:45"
        assert video.views == "1000"
        assert video.publish_time == "2020-01-01"
        assert video.url_suffix == "/watch?v=test_video_id"
        assert video.score == 90
        assert video.source == "youtube"
    
    def test_youtube_video_youtube_url_property(self):
        """Test youtube_url property."""
        video = YouTubeVideo(
            title="Test",
            artist="Artist",
            video_id="test_video_id"
        )
        assert video.youtube_url == "https://www.youtube.com/watch?v=test_video_id"
    
    def test_youtube_video_youtube_url_property_no_video_id(self):
        """Test youtube_url property with no video_id."""
        video = YouTubeVideo(
            title="Test",
            artist="Artist",
            url_suffix="/watch?v=test"
        )
        assert video.youtube_url == "/watch?v=test"
    
    def test_youtube_video_get_display_name(self):
        """Test get_display_name."""
        video = YouTubeVideo(title="Test Song", artist="Artist")
        assert video.get_display_name() == "Test Song"
    
    def test_youtube_video_get_display_name_fallback(self):
        """Test get_display_name fallback."""
        video = YouTubeVideo(title="", artist="Artist")
        assert video.get_display_name() == "No title"
    
    def test_youtube_video_defaults(self):
        """Test YouTubeVideo with default values."""
        video = YouTubeVideo(title="Test", artist="Artist")
        assert video.video_id == ""
        assert video.channel == ""
        assert video.duration is None
        assert video.views is None
        assert video.publish_time is None
        assert video.url_suffix == ""
        assert video.score == 0
        assert video.source == "youtube"


class TestDiscogsRelease:
    """Tests for DiscogsRelease model."""
    
    def test_discogs_release_creation(self):
        """Test DiscogsRelease model creation."""
        release = DiscogsRelease(
            title="Test Album",
            artist="Test Artist",
            album="Test Album",
            year=2020,
            genre="Rock",
            style="Progressive Rock",
            label="Test Label",
            country="US",
            format="LP",
            cover_art_url="https://example.com/cover.jpg",
            discogs_id="123456",
            score=85
        )
        
        assert release.title == "Test Album"
        assert release.artist == "Test Artist"
        assert release.album == "Test Album"
        assert release.year == 2020
        assert release.genre == "Rock"
        assert release.style == "Progressive Rock"
        assert release.label == "Test Label"
        assert release.country == "US"
        assert release.format == "LP"
        assert release.cover_art_url == "https://example.com/cover.jpg"
        assert release.discogs_id == "123456"
        assert release.score == 85
        assert release.source == "discogs"
    
    def test_discogs_release_get_display_name(self):
        """Test get_display_name."""
        release = DiscogsRelease(title="Test Album", artist="Artist")
        assert release.get_display_name() == "Test Album"
    
    def test_discogs_release_get_display_name_fallback(self):
        """Test get_display_name fallback."""
        release = DiscogsRelease(title="", artist="Artist", album="")
        assert release.get_display_name() == "Unknown"
    
    def test_discogs_release_defaults(self):
        """Test DiscogsRelease with default values."""
        release = DiscogsRelease(title="Test", artist="Artist")
        assert release.album is None
        assert release.year is None
        assert release.genre is None
        assert release.style is None
        assert release.label is None
        assert release.country is None
        assert release.format is None
        assert release.cover_art_url is None
        assert release.discogs_id == ""
        assert release.score == 0
        assert release.source == "discogs"


class TestLastFmTrack:
    """Tests for LastFmTrack model."""
    
    def test_lastfm_track_creation(self):
        """Test LastFmTrack model creation."""
        track = LastFmTrack(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            playcount=1000,
            listeners=500,
            duration=240,
            mbid="test-mbid-123",
            tags=["rock", "alternative"],
            score=80
        )
        
        assert track.title == "Test Song"
        assert track.artist == "Test Artist"
        assert track.album == "Test Album"
        assert track.playcount == 1000
        assert track.listeners == 500
        assert track.duration == 240
        assert track.mbid == "test-mbid-123"
        assert track.tags == ["rock", "alternative"]
        assert track.score == 80
        assert track.source == "lastfm"
    
    def test_lastfm_track_get_display_name(self):
        """Test get_display_name."""
        track = LastFmTrack(title="Test Song", artist="Artist")
        assert track.get_display_name() == "Test Song"
    
    def test_lastfm_track_defaults(self):
        """Test LastFmTrack with default values."""
        track = LastFmTrack(title="Test", artist="Artist")
        assert track.album is None
        assert track.playcount is None
        assert track.listeners is None
        assert track.duration is None
        assert track.mbid is None
        assert track.tags is None
        assert track.score == 0
        assert track.source == "lastfm"


class TestSpotifyTrack:
    """Tests for SpotifyTrack model."""
    
    def test_spotify_track_creation(self):
        """Test SpotifyTrack model creation."""
        track = SpotifyTrack(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            year=2020,
            genre="Rock",
            duration_ms=240000,
            popularity=75,
            spotify_id="test-spotify-id",
            preview_url="https://example.com/preview.mp3",
            cover_art_url="https://example.com/cover.jpg",
            audio_features={"danceability": 0.7},
            score=95
        )
        
        assert track.title == "Test Song"
        assert track.artist == "Test Artist"
        assert track.album == "Test Album"
        assert track.year == 2020
        assert track.genre == "Rock"
        assert track.duration_ms == 240000
        assert track.popularity == 75
        assert track.spotify_id == "test-spotify-id"
        assert track.preview_url == "https://example.com/preview.mp3"
        assert track.cover_art_url == "https://example.com/cover.jpg"
        assert track.audio_features == {"danceability": 0.7}
        assert track.score == 95
        assert track.source == "spotify"
    
    def test_spotify_track_get_display_name(self):
        """Test get_display_name."""
        track = SpotifyTrack(title="Test Song", artist="Artist")
        assert track.get_display_name() == "Test Song"
    
    def test_spotify_track_defaults(self):
        """Test SpotifyTrack with default values."""
        track = SpotifyTrack(title="Test", artist="Artist")
        assert track.album is None
        assert track.year is None
        assert track.genre is None
        assert track.duration_ms is None
        assert track.popularity is None
        assert track.spotify_id == ""
        assert track.preview_url is None
        assert track.cover_art_url is None
        assert track.audio_features is None
        assert track.score == 0
        assert track.source == "spotify"


class TestGeniusSong:
    """Tests for GeniusSong model."""
    
    def test_genius_song_creation(self):
        """Test GeniusSong model creation."""
        song = GeniusSong(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            year=2020,
            lyrics="Test lyrics",
            genius_id="test-genius-id",
            cover_art_url="https://example.com/cover.jpg",
            description="Test description",
            song_art_image_url="https://example.com/art.jpg",
            score=88
        )
        
        assert song.title == "Test Song"
        assert song.artist == "Test Artist"
        assert song.album == "Test Album"
        assert song.year == 2020
        assert song.lyrics == "Test lyrics"
        assert song.genius_id == "test-genius-id"
        assert song.cover_art_url == "https://example.com/cover.jpg"
        assert song.description == "Test description"
        assert song.song_art_image_url == "https://example.com/art.jpg"
        assert song.score == 88
        assert song.source == "genius"
    
    def test_genius_song_get_display_name(self):
        """Test get_display_name."""
        song = GeniusSong(title="Test Song", artist="Artist")
        assert song.get_display_name() == "Test Song"
    
    def test_genius_song_defaults(self):
        """Test GeniusSong with default values."""
        song = GeniusSong(title="Test", artist="Artist")
        assert song.album is None
        assert song.year is None
        assert song.lyrics is None
        assert song.genius_id == ""
        assert song.cover_art_url is None
        assert song.description is None
        assert song.song_art_image_url is None
        assert song.score == 0
        assert song.source == "genius"

