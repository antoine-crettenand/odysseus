"""
Tests for search service.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from odysseus.services.search_service import SearchService
from odysseus.models.song import SongData
from odysseus.models.search_results import MusicBrainzSong, DiscogsRelease


class TestSearchService:
    """Tests for SearchService class."""
    
    def test_search_service_initialization(self):
        """Test SearchService initialization."""
        service = SearchService()
        
        assert service.musicbrainz_client is not None
        assert service.discogs_client is not None
        assert service.youtube_client is None
    
    def test_get_release_year(self):
        """Test _get_release_year method."""
        service = SearchService()
        
        assert service._get_release_year("2020-01-01") == "2020"
        assert service._get_release_year("2020") == "2020"
        assert service._get_release_year("2020-12") == "2020"
        assert service._get_release_year("") is None
        assert service._get_release_year(None) is None
        assert service._get_release_year("invalid") is None
    
    def test_create_deduplication_key(self):
        """Test _create_deduplication_key method."""
        service = SearchService()
        
        result = MusicBrainzSong(
            title="Test Song",
            artist="Test Artist",
            album="Test Album"
        )
        key = service._create_deduplication_key(result)
        
        assert isinstance(key, tuple)
        assert len(key) == 2
        assert "test album" in key[0].lower() or "test song" in key[0].lower()
        assert "test artist" in key[1].lower()
    
    def test_create_deduplication_key_album_equals_title(self):
        """Test deduplication key when album equals title."""
        service = SearchService()
        
        result = MusicBrainzSong(
            title="Test Album",
            artist="Test Artist",
            album="Test Album"
        )
        key = service._create_deduplication_key(result)
        
        # Should use album as primary key
        assert "test album" in key[0].lower()
    
    def test_parse_release_date(self):
        """Test _parse_release_date method."""
        service = SearchService()
        
        assert service._parse_release_date("2020-01-01") == (2020, 1, 1)
        assert service._parse_release_date("2020-12") == (2020, 12, 1)
        assert service._parse_release_date("2020") == (2020, 1, 1)
        assert service._parse_release_date("") is None
        assert service._parse_release_date(None) is None
        assert service._parse_release_date("invalid") is None
    
    def test_deduplicate_results_empty(self):
        """Test deduplication with empty results."""
        service = SearchService()
        
        results = service._deduplicate_results([])
        assert results == []
    
    def test_deduplicate_results_no_duplicates(self):
        """Test deduplication with no duplicates."""
        service = SearchService()
        
        results = [
            MusicBrainzSong(title="Song 1", artist="Artist", album="Album 1", release_date="2020-01-01"),
            MusicBrainzSong(title="Song 2", artist="Artist", album="Album 2", release_date="2020-02-01")
        ]
        
        deduped = service._deduplicate_results(results)
        assert len(deduped) == 2
    
    def test_deduplicate_results_with_duplicates(self):
        """Test deduplication with duplicates."""
        service = SearchService()
        
        results = [
            MusicBrainzSong(title="Song", artist="Artist", album="Album", release_date="2020-01-01", score=100),
            MusicBrainzSong(title="Song", artist="Artist", album="Album", release_date="2021-01-01", score=90)
        ]
        
        deduped = service._deduplicate_results(results)
        # Should keep earliest date
        assert len(deduped) == 1
        assert deduped[0].release_date == "2020-01-01"
    
    @patch('odysseus.services.search_service.MusicBrainzClient')
    @patch('odysseus.services.search_service.DiscogsClient')
    def test_search_recordings(self, mock_discogs, mock_mb, sample_song_data):
        """Test search_recordings method."""
        service = SearchService()
        
        # Mock clients
        mock_mb_instance = Mock()
        mock_mb_instance.search_recording.return_value = [
            MusicBrainzSong(title="Test Song", artist="Test Artist", mbid="test-123")
        ]
        service.musicbrainz_client = mock_mb_instance
        
        mock_discogs_instance = Mock()
        mock_discogs_instance.search_release.return_value = []
        service.discogs_client = mock_discogs_instance
        
        results = service.search_recordings(sample_song_data)
        
        assert len(results) > 0
        assert isinstance(results[0], MusicBrainzSong)
    
    @patch('odysseus.services.search_service.MusicBrainzClient')
    @patch('odysseus.services.search_service.DiscogsClient')
    def test_search_releases(self, mock_discogs, mock_mb, sample_song_data):
        """Test search_releases method."""
        service = SearchService()
        
        # Mock clients
        mock_mb_instance = Mock()
        mock_mb_instance.search_release.return_value = [
            MusicBrainzSong(title="Test Album", artist="Test Artist", album="Test Album", mbid="test-123")
        ]
        service.musicbrainz_client = mock_mb_instance
        
        mock_discogs_instance = Mock()
        mock_discogs_instance.search_release.return_value = []
        service.discogs_client = mock_discogs_instance
        
        results = service.search_releases(sample_song_data)
        
        assert len(results) > 0
        assert isinstance(results[0], MusicBrainzSong)
    
    def test_deduplicate_with_priority(self):
        """Test _deduplicate_with_priority method."""
        service = SearchService()
        
        mb_results = [
            MusicBrainzSong(title="Album", artist="Artist", album="Album", mbid="mb-1")
        ]
        discogs_results = [
            DiscogsRelease(title="Album", artist="Artist", album="Album", discogs_id="d-1"),
            DiscogsRelease(title="Other Album", artist="Artist", album="Other Album", discogs_id="d-2")
        ]
        
        deduped = service._deduplicate_with_priority(mb_results, discogs_results)
        
        # Should keep MB result and only complementary Discogs results
        assert len(deduped) == 2
        # First should be MB result
        assert isinstance(deduped[0], MusicBrainzSong)
        # Second should be Discogs result that doesn't match MB
        assert isinstance(deduped[1], DiscogsRelease)
        assert deduped[1].album == "Other Album"

