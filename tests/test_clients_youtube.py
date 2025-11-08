"""
Tests for YouTube client.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from odysseus.clients.youtube import YouTubeClient
from odysseus.models.search_results import YouTubeVideo


class TestYouTubeClient:
    """Tests for YouTubeClient class."""
    
    @patch('odysseus.clients.youtube.requests.get')
    def test_youtube_client_initialization_success(self, mock_get):
        """Test YouTubeClient initialization with successful search."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<script>var ytInitialData = {"contents": {"twoColumnSearchResultsRenderer": {"primaryContents": {"sectionListRenderer": {"contents": []}}}}};</script>'
        mock_get.return_value = mock_response
        
        client = YouTubeClient("test search")
        
        assert client.search_terms == "test search"
        assert client.max_results > 0
        assert client.base_url is not None
        assert isinstance(client.videos, list)
    
    @patch('odysseus.clients.youtube.requests.get')
    def test_youtube_client_search_success(self, mock_get):
        """Test successful YouTube search."""
        # Mock HTML with video data
        html_content = '''
        <script>
        var ytInitialData = {
            "contents": {
                "twoColumnSearchResultsRenderer": {
                    "primaryContents": {
                        "sectionListRenderer": {
                            "contents": [{
                                "itemSectionRenderer": {
                                    "contents": [{
                                        "videoRenderer": {
                                            "title": {"runs": [{"text": "Test Video"}]},
                                            "longBylineText": {"runs": [{"text": "Test Channel"}]},
                                            "videoId": "test_video_id",
                                            "lengthText": {"simpleText": "3:45"},
                                            "viewCountText": {"simpleText": "1000 views"}
                                        }
                                    }]
                                }
                            }]
                        }
                    }
                }
            }
        };
        </script>
        '''
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response
        
        client = YouTubeClient("test search")
        
        assert len(client.videos) > 0
        assert isinstance(client.videos[0], YouTubeVideo)
        assert client.videos[0].title == "Test Video"
    
    @patch('odysseus.clients.youtube.requests.get')
    def test_youtube_client_search_no_results(self, mock_get):
        """Test YouTube search with no results."""
        html_content = '''
        <script>
        var ytInitialData = {
            "contents": {
                "twoColumnSearchResultsRenderer": {
                    "primaryContents": {
                        "sectionListRenderer": {
                            "contents": []
                        }
                    }
                }
            }
        };
        </script>
        '''
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response
        
        client = YouTubeClient("test search")
        
        assert len(client.videos) == 0
    
    @patch('odysseus.clients.youtube.requests.get')
    def test_youtube_client_search_retries(self, mock_get):
        """Test that YouTube client retries on failure."""
        # First two attempts fail (no ytInitialData), third succeeds
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 200
        mock_response_fail.text = "No ytInitialData here"
        
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        # Need proper HTML structure with ytInitialData and valid JSON ending with };
        # The parser looks for "};" after the JSON, so we need to ensure it's there
        mock_response_success.text = '<script>var ytInitialData = {"contents": {"twoColumnSearchResultsRenderer": {"primaryContents": {"sectionListRenderer": {"contents": []}}}}};</script>'
        
        mock_get.side_effect = [mock_response_fail, mock_response_fail, mock_response_success]
        
        client = YouTubeClient("test search", max_results=3)
        
        assert mock_get.call_count == 3
        assert len(client.videos) == 0  # Empty contents list
    
    @patch('odysseus.clients.youtube.requests.get')
    def test_youtube_client_search_max_retries_exceeded(self, mock_get):
        """Test that exception is raised when max retries exceeded."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "No ytInitialData here"
        mock_get.return_value = mock_response
        
        with pytest.raises(Exception):
            YouTubeClient("test search", max_results=3)
    
    def test_to_list_method(self):
        """Test to_list method."""
        with patch('odysseus.clients.youtube.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '<script>var ytInitialData = {"contents": {"twoColumnSearchResultsRenderer": {"primaryContents": {"sectionListRenderer": {"contents": []}}}}};</script>'
            mock_get.return_value = mock_response
            
            client = YouTubeClient("test search")
            videos = client.to_list()
            
            assert videos == client.videos
    
    @patch('odysseus.clients.youtube.requests.get')
    def test_get_video_info_success(self, mock_get):
        """Test successful video info retrieval."""
        # Mock the search request (for client initialization)
        mock_search_response = MagicMock()
        mock_search_response.status_code = 200
        mock_search_response.text = '<script>var ytInitialData = {"contents": {"twoColumnSearchResultsRenderer": {"primaryContents": {"sectionListRenderer": {"contents": []}}}}};</script>'
        
        # Mock the video page request
        html_content = '''
        <script>
        var ytInitialPlayerResponse = {
            "videoDetails": {
                "title": "Test Video",
                "author": "Test Channel",
                "videoId": "test_video_id",
                "lengthSeconds": "225",
                "viewCount": "1000",
                "publishDate": "2020-01-01"
            }
        };
        </script>
        '''
        
        mock_video_response = MagicMock()
        mock_video_response.status_code = 200
        mock_video_response.text = html_content
        
        # First call is for search, second is for video info
        mock_get.side_effect = [mock_search_response, mock_video_response]
        
        client = YouTubeClient("test")
        video_info = client.get_video_info("/watch?v=test_video_id")
        
        assert isinstance(video_info, YouTubeVideo)
        assert video_info.title == "Test Video"
        assert video_info.channel == "Test Channel"
    
    @patch('odysseus.clients.youtube.requests.get')
    def test_get_video_info_not_found(self, mock_get):
        """Test video info retrieval when video not found."""
        # Mock the search request (for client initialization)
        mock_search_response = MagicMock()
        mock_search_response.status_code = 200
        mock_search_response.text = '<script>var ytInitialData = {"contents": {"twoColumnSearchResultsRenderer": {"primaryContents": {"sectionListRenderer": {"contents": []}}}}};</script>'
        
        # Mock the video page request (404)
        mock_video_response = MagicMock()
        mock_video_response.status_code = 404
        
        # First call is for search, second is for video info
        mock_get.side_effect = [mock_search_response, mock_video_response]
        
        client = YouTubeClient("test")
        
        with pytest.raises(Exception):
            client.get_video_info("/watch?v=invalid")

