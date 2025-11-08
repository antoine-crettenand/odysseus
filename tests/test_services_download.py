"""
Tests for download service.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from odysseus.services.download_service import DownloadService


class TestDownloadService:
    """Tests for DownloadService class."""
    
    def test_download_service_initialization(self):
        """Test DownloadService initialization."""
        service = DownloadService()
        
        assert service.downloader is not None
        assert service.downloads_dir is not None
    
    def test_download_service_initialization_with_dir(self, temp_dir):
        """Test DownloadService initialization with custom directory."""
        service = DownloadService(download_dir=str(temp_dir))
        
        assert service.downloads_dir == temp_dir
    
    @patch('odysseus.services.download_service.YouTubeDownloader')
    def test_download_video(self, mock_downloader_class):
        """Test download_video method."""
        mock_downloader = Mock()
        mock_downloader.download.return_value = Path("/tmp/test.mp3")
        mock_downloader_class.return_value = mock_downloader
        
        service = DownloadService()
        service.downloader = mock_downloader
        
        result = service.download_video("https://youtube.com/watch?v=test")
        
        assert result == Path("/tmp/test.mp3")
        mock_downloader.download.assert_called_once()
    
    @patch('odysseus.services.download_service.YouTubeDownloader')
    def test_download_high_quality_audio(self, mock_downloader_class):
        """Test download_high_quality_audio method."""
        mock_downloader = Mock()
        mock_downloader.download_high_quality_audio.return_value = Path("/tmp/test.mp3")
        mock_downloader_class.return_value = mock_downloader
        
        service = DownloadService()
        service.downloader = mock_downloader
        
        result = service.download_high_quality_audio("https://youtube.com/watch?v=test")
        
        assert result == Path("/tmp/test.mp3")
        mock_downloader.download_high_quality_audio.assert_called_once()
    
    @patch('odysseus.services.download_service.YouTubeDownloader')
    def test_download_playlist(self, mock_downloader_class):
        """Test download_playlist method."""
        mock_downloader = Mock()
        mock_downloader.download_playlist.return_value = ["file1.mp3", "file2.mp3"]
        mock_downloader_class.return_value = mock_downloader
        
        service = DownloadService()
        service.downloader = mock_downloader
        
        result = service.download_playlist("https://youtube.com/playlist?list=test")
        
        assert len(result) == 2
        mock_downloader.download_playlist.assert_called_once()
    
    @patch('odysseus.services.download_service.YouTubeDownloader')
    def test_get_available_formats(self, mock_downloader_class):
        """Test get_available_formats method."""
        mock_downloader = Mock()
        mock_downloader.get_available_formats.return_value = [
            {"format_id": "140", "ext": "m4a", "abr": 128}
        ]
        mock_downloader_class.return_value = mock_downloader
        
        service = DownloadService()
        service.downloader = mock_downloader
        
        formats = service.get_available_formats("https://youtube.com/watch?v=test")
        
        assert len(formats) == 1
        mock_downloader.get_available_formats.assert_called_once()
    
    @patch('odysseus.services.download_service.YouTubeDownloader')
    def test_get_video_info(self, mock_downloader_class):
        """Test get_video_info method."""
        mock_downloader = Mock()
        mock_downloader.get_video_info.return_value = {
            "title": "Test Video",
            "duration": 180
        }
        mock_downloader_class.return_value = mock_downloader
        
        service = DownloadService()
        service.downloader = mock_downloader
        
        info = service.get_video_info("https://youtube.com/watch?v=test")
        
        assert info["title"] == "Test Video"
        mock_downloader.get_video_info.assert_called_once()
    
    @patch('odysseus.services.download_service.YouTubeDownloader')
    def test_get_video_chapters(self, mock_downloader_class):
        """Test get_video_chapters method."""
        mock_downloader = Mock()
        mock_downloader.get_video_chapters.return_value = [
            {"title": "Chapter 1", "start_time": 0}
        ]
        mock_downloader_class.return_value = mock_downloader
        
        service = DownloadService()
        service.downloader = mock_downloader
        
        chapters = service.get_video_chapters("https://youtube.com/watch?v=test")
        
        assert len(chapters) == 1
        mock_downloader.get_video_chapters.assert_called_once()
    
    @patch('odysseus.services.download_service.YouTubeDownloader')
    def test_get_playlist_info(self, mock_downloader_class):
        """Test get_playlist_info method."""
        mock_downloader = Mock()
        mock_downloader.get_playlist_info.return_value = [
            {"title": "Video 1", "id": "vid1"}
        ]
        mock_downloader_class.return_value = mock_downloader
        
        service = DownloadService()
        service.downloader = mock_downloader
        
        playlist_info = service.get_playlist_info("https://youtube.com/playlist?list=test")
        
        assert len(playlist_info) == 1
        mock_downloader.get_playlist_info.assert_called_once()
    
    @patch('odysseus.services.download_service.YouTubeDownloader')
    def test_split_video_into_tracks(self, mock_downloader_class, temp_dir):
        """Test split_video_into_tracks method."""
        mock_downloader = Mock()
        mock_downloader.split_video_into_tracks.return_value = [
            Path("/tmp/track1.mp3"),
            Path("/tmp/track2.mp3")
        ]
        mock_downloader_class.return_value = mock_downloader
        
        service = DownloadService()
        service.downloader = mock_downloader
        
        video_path = Path("/tmp/video.mp4")
        track_timestamps = [
            {"title": "Track 1", "start": 0, "end": 180},
            {"title": "Track 2", "start": 180, "end": 360}
        ]
        metadata_list = [
            {"title": "Track 1", "artist": "Artist"},
            {"title": "Track 2", "artist": "Artist"}
        ]
        
        tracks = service.split_video_into_tracks(
            video_path, track_timestamps, temp_dir, metadata_list
        )
        
        assert len(tracks) == 2
        mock_downloader.split_video_into_tracks.assert_called_once()

