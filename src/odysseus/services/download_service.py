"""
Download service for handling file downloads.
"""

from typing import Optional, Dict, Any, List
from pathlib import Path
from ..clients.youtube_downloader import YouTubeDownloader


class DownloadService:
    """Service for handling downloads."""
    
    def __init__(self, download_dir: Optional[str] = None):
        self.downloader = YouTubeDownloader(download_dir)
    
    def download_video(self, url: str, quality: str = "best", 
                      audio_only: bool = True, metadata: Optional[Dict[str, Any]] = None) -> Optional[Path]:
        """Download a video from URL."""
        return self.downloader.download(url, quality, audio_only, metadata)
    
    def download_high_quality_audio(self, url: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[Path]:
        """Download high-quality audio from video."""
        return self.downloader.download_high_quality_audio(url, metadata)
    
    def download_playlist(self, url: str, quality: str = "bestaudio") -> List[str]:
        """Download a YouTube playlist."""
        return self.downloader.download_playlist(url, quality)
    
    def get_available_formats(self, url: str) -> List[Dict[str, Any]]:
        """Get available formats for a video."""
        return self.downloader.get_available_formats(url)
    
    def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Get video information."""
        return self.downloader.get_video_info(url)
