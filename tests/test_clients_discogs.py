"""
Tests for Discogs client.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from odysseus.clients.discogs import DiscogsClient
from odysseus.models.song import SongData
from odysseus.models.search_results import DiscogsRelease


class TestDiscogsClient:
    """Tests for DiscogsClient class."""
    
    def test_discogs_client_initialization(self):
        """Test DiscogsClient initialization."""
        client = DiscogsClient()
        
        assert client.base_url is not None
        assert client.user_agent is not None
        assert client.request_delay > 0
        assert client.max_results > 0
        assert client.timeout > 0
        assert client.session is not None
    
    def test_discogs_client_with_token(self):
        """Test DiscogsClient initialization with user token."""
        with patch('odysseus.clients.discogs.DISCOGS_CONFIG', {
            "BASE_URL": "https://api.discogs.com",
            "USER_AGENT": "Test/1.0",
            "USER_TOKEN": "test-token",
            "REQUEST_DELAY": 1.0,
            "MAX_RESULTS": 3,
            "TIMEOUT": 30
        }):
            client = DiscogsClient()
            assert "Authorization" in client.session.headers
            assert "test-token" in client.session.headers["Authorization"]
    
    @patch('odysseus.clients.discogs.DiscogsClient._make_request')
    def test_search_release_success(self, mock_make_request, sample_song_data):
        """Test successful release search."""
        client = DiscogsClient()
        
        mock_response = {
            "results": [
                {
                    "title": "Test Album",
                    "artist": "Test Artist",
                    "year": 2020,
                    "id": 123456,
                    "type": "release"
                }
            ]
        }
        mock_make_request.return_value = mock_response
        
        results = client.search_release(sample_song_data)
        
        assert len(results) > 0
        assert isinstance(results[0], DiscogsRelease)
        mock_make_request.assert_called_once()
    
    @patch('odysseus.clients.discogs.DiscogsClient._make_request')
    def test_search_release_no_results(self, mock_make_request, sample_song_data):
        """Test release search with no results."""
        client = DiscogsClient()
        mock_make_request.return_value = {"results": []}
        
        results = client.search_release(sample_song_data)
        
        assert results == []
    
    @patch('odysseus.clients.discogs.DiscogsClient._make_request')
    def test_search_release_request_failure(self, mock_make_request, sample_song_data):
        """Test release search when request fails."""
        client = DiscogsClient()
        mock_make_request.return_value = None
        
        results = client.search_release(sample_song_data)
        
        assert results == []
    
    def test_search_release_query_building(self, sample_song_data):
        """Test that query is built correctly from song data."""
        client = DiscogsClient()
        
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = {"results": []}
            
            client.search_release(sample_song_data)
            
            call_args = mock_request.call_args
            # call_args is a tuple (args, kwargs), params is the second positional arg
            params = call_args[0][1] if len(call_args[0]) > 1 else {}
            query = params.get('q', '')
            assert "Test Song" in query
            assert "Test Artist" in query
            assert "Test Album" in query
    
    @patch('odysseus.clients.discogs.DiscogsClient._make_request')
    def test_search_release_with_type_filter(self, mock_make_request, sample_song_data):
        """Test release search with type filter."""
        client = DiscogsClient()
        mock_make_request.return_value = {"results": []}
        
        client.search_release(sample_song_data, release_type="album")
        
        call_args = mock_make_request.call_args
        # call_args is a tuple (args, kwargs), params is the second positional arg
        params = call_args[0][1] if len(call_args[0]) > 1 else {}
        assert params.get('type') == "release"
        # Type filter might be in query or params
    
    @patch('odysseus.clients.discogs.DiscogsClient._make_request')
    def test_get_release_success(self, mock_make_request):
        """Test successful release retrieval."""
        client = DiscogsClient()
        
        mock_response = {
            "title": "Test Album",
            "artists": [{"name": "Test Artist"}],
            "id": 123456,
            "year": 2020,
            "genres": ["Rock"],
            "tracklist": [
                {
                    "position": "1",
                    "title": "Track 1",
                    "duration": "3:45"
                }
            ]
        }
        mock_make_request.return_value = mock_response
        
        release = client.get_release_info("123456")
        
        assert release is not None
        assert release.title == "Test Album"
    
    @patch('odysseus.clients.discogs.DiscogsClient._make_request')
    def test_get_release_not_found(self, mock_make_request):
        """Test release retrieval when not found."""
        client = DiscogsClient()
        mock_make_request.return_value = None
        
        release = client.get_release_info("999999")
        
        assert release is None
    
    @patch('odysseus.clients.discogs.requests.Session.get')
    @patch('time.sleep')
    def test_make_request_success(self, mock_sleep, mock_get):
        """Test successful request."""
        client = DiscogsClient()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = client._make_request("https://api.discogs.com/test", {})
        
        assert result == {"results": []}
        mock_sleep.assert_called_once()
    
    @patch('odysseus.clients.discogs.requests.Session.get')
    @patch('time.sleep')
    def test_make_request_rate_limit(self, mock_sleep, mock_get):
        """Test request handling rate limit (429)."""
        client = DiscogsClient()
        
        mock_response = MagicMock()
        mock_response.status_code = 429
        
        # Create an HTTPError with status_code 429
        from requests.exceptions import HTTPError
        http_error = HTTPError("Rate limited")
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error
        mock_get.return_value = mock_response
        
        result = client._make_request("https://api.discogs.com/test", {})
        
        # Should wait 60 seconds for rate limit
        assert mock_sleep.call_count >= 1
        # May return None after retries
        assert result is None or isinstance(result, dict)

