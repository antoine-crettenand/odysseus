"""
Tests for MusicBrainz client.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from odysseus.clients.musicbrainz import MusicBrainzClient
from odysseus.models.song import SongData
from odysseus.models.search_results import MusicBrainzSong


class TestMusicBrainzClient:
    """Tests for MusicBrainzClient class."""
    
    def test_musicbrainz_client_initialization(self):
        """Test MusicBrainzClient initialization."""
        client = MusicBrainzClient()
        
        assert client.base_url is not None
        assert client.user_agent is not None
        assert client.request_delay > 0
        assert client.max_results > 0
        assert client.timeout > 0
        assert client.session is not None
    
    @patch('odysseus.clients.musicbrainz.MusicBrainzClient._make_request')
    def test_search_recording_success(self, mock_make_request, sample_song_data):
        """Test successful recording search."""
        client = MusicBrainzClient()
        
        # Mock response data
        mock_response = {
            "recordings": [
                {
                    "title": "Test Song",
                    "artist-credit": [{"name": "Test Artist"}],
                    "id": "test-mbid-123",
                    "releases": [{"title": "Test Album", "date": "2020-01-01"}]
                }
            ]
        }
        mock_make_request.return_value = mock_response
        
        results = client.search_recording(sample_song_data)
        
        assert len(results) > 0
        assert isinstance(results[0], MusicBrainzSong)
        mock_make_request.assert_called_once()
    
    @patch('odysseus.clients.musicbrainz.MusicBrainzClient._make_request')
    def test_search_recording_no_results(self, mock_make_request, sample_song_data):
        """Test recording search with no results."""
        client = MusicBrainzClient()
        mock_make_request.return_value = {"recordings": []}
        
        results = client.search_recording(sample_song_data)
        
        assert results == []
    
    @patch('odysseus.clients.musicbrainz.MusicBrainzClient._make_request')
    def test_search_recording_request_failure(self, mock_make_request, sample_song_data):
        """Test recording search when request fails."""
        client = MusicBrainzClient()
        mock_make_request.return_value = None
        
        results = client.search_recording(sample_song_data)
        
        assert results == []
    
    @patch('odysseus.clients.musicbrainz.MusicBrainzClient._make_request')
    def test_search_recording_exception(self, mock_make_request, sample_song_data):
        """Test recording search when exception occurs."""
        client = MusicBrainzClient()
        mock_make_request.side_effect = Exception("Network error")
        
        results = client.search_recording(sample_song_data)
        
        assert results == []
    
    @patch('odysseus.clients.musicbrainz.MusicBrainzClient._make_request')
    def test_search_recording_with_limit(self, mock_make_request, sample_song_data):
        """Test recording search with custom limit."""
        client = MusicBrainzClient()
        mock_response = {
            "recordings": [
                {"title": f"Song {i}", "artist-credit": [{"name": "Artist"}], "id": f"mbid-{i}"}
                for i in range(5)
            ]
        }
        mock_make_request.return_value = mock_response
        
        results = client.search_recording(sample_song_data, limit=3)
        
        # Should respect limit in params
        call_args = mock_make_request.call_args
        # call_args is a tuple (args, kwargs), params is the second positional arg
        params = call_args[0][1] if len(call_args[0]) > 1 else {}
        assert params.get('limit') == 3
    
    @patch('odysseus.clients.musicbrainz.MusicBrainzClient._make_request')
    def test_search_release_success(self, mock_make_request, sample_song_data):
        """Test successful release search."""
        client = MusicBrainzClient()
        
        mock_response = {
            "releases": [
                {
                    "title": "Test Album",
                    "artist-credit": [{"name": "Test Artist"}],
                    "id": "test-mbid-123",
                    "date": "2020-01-01"
                }
            ]
        }
        mock_make_request.return_value = mock_response
        
        results = client.search_release(sample_song_data)
        
        assert len(results) > 0
        assert isinstance(results[0], MusicBrainzSong)
    
    @patch('odysseus.clients.musicbrainz.MusicBrainzClient._make_request')
    def test_search_release_with_type_filter(self, mock_make_request, sample_song_data):
        """Test release search with type filter."""
        client = MusicBrainzClient()
        mock_make_request.return_value = {"releases": []}
        
        client.search_release(sample_song_data, release_type="Album")
        
        call_args = mock_make_request.call_args
        # call_args is a tuple (args, kwargs), params is the second positional arg
        params = call_args[0][1] if len(call_args[0]) > 1 else {}
        query = params.get('query', '')
        assert 'type:"Album"' in query
    
    def test_search_recording_query_building(self, sample_song_data):
        """Test that query is built correctly from song data."""
        client = MusicBrainzClient()
        
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = {"recordings": []}
            
            client.search_recording(sample_song_data)
            
            call_args = mock_request.call_args
            # call_args is a tuple (args, kwargs), params is the second positional arg
            params = call_args[0][1] if len(call_args[0]) > 1 else {}
            query = params.get('query', '')
            assert 'title:"Test Song"' in query
            assert 'artist:"Test Artist"' in query
            assert 'release:"Test Album"' in query
    
    def test_search_recording_query_with_year(self):
        """Test query building with release year."""
        client = MusicBrainzClient()
        song_data = SongData(title="Test", artist="Artist", release_year=2020)
        
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = {"recordings": []}
            
            client.search_recording(song_data)
            
            call_args = mock_request.call_args
            # call_args is a tuple (args, kwargs), params is the second positional arg
            params = call_args[0][1] if len(call_args[0]) > 1 else {}
            query = params.get('query', '')
            assert 'date:2020' in query
    
    @patch('odysseus.clients.musicbrainz.MusicBrainzClient._make_request')
    def test_get_release_success(self, mock_make_request):
        """Test successful release retrieval."""
        client = MusicBrainzClient()
        
        mock_response = {
            "title": "Test Album",
            "artist-credit": [{"name": "Test Artist"}],
            "id": "test-mbid-123",
            "date": "2020-01-01",
            "media": [
                {
                    "tracks": [
                        {
                            "position": 1,
                            "title": "Track 1",
                            "recording": {
                                "title": "Track 1",
                                "artist-credit": [{"name": "Test Artist"}]
                            }
                        }
                    ]
                }
            ]
        }
        mock_make_request.return_value = mock_response
        
        release = client.get_release_info("test-mbid-123")
        
        assert release is not None
        assert release.title == "Test Album"
    
    @patch('odysseus.clients.musicbrainz.MusicBrainzClient._make_request')
    def test_get_release_not_found(self, mock_make_request):
        """Test release retrieval when not found."""
        client = MusicBrainzClient()
        mock_make_request.return_value = None
        
        release = client.get_release_info("invalid-mbid")
        
        assert release is None

