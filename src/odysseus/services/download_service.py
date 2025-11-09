"""
Download service for handling file downloads.
"""

from typing import Optional, Dict, Any, List, Callable, Tuple
from pathlib import Path
from ..clients.youtube_downloader import YouTubeDownloader


class DownloadService:
    """Service for handling downloads."""
    
    def __init__(self, download_dir: Optional[str] = None):
        self.downloader = YouTubeDownloader(download_dir)
        self.downloads_dir = self.downloader.download_dir
    
    def download_video(self, url: str, quality: str = "best", 
                      audio_only: bool = True, metadata: Optional[Dict[str, Any]] = None, 
                      quiet: bool = True, progress_callback: Optional[Callable] = None) -> Tuple[Optional[Path], bool]:
        """Download a video from URL."""
        return self.downloader.download(url, quality, audio_only, metadata, quiet=quiet, progress_callback=progress_callback)
    
    def download_high_quality_audio(self, url: str, metadata: Optional[Dict[str, Any]] = None, 
                                     quiet: bool = True, progress_callback: Optional[Callable] = None) -> Tuple[Optional[Path], bool]:
        """Download high-quality audio from video."""
        return self.downloader.download_high_quality_audio(url, metadata, quiet=quiet, progress_callback=progress_callback)
    
    def download_playlist(self, url: str, quality: str = "bestaudio") -> List[str]:
        """Download a YouTube playlist."""
        return self.downloader.download_playlist(url, quality)
    
    def get_available_formats(self, url: str) -> List[Dict[str, Any]]:
        """Get available formats for a video."""
        return self.downloader.get_available_formats(url)
    
    def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Get video information."""
        return self.downloader.get_video_info(url)
    
    def get_video_chapters(self, url: str) -> Optional[List[Dict[str, Any]]]:
        """Get video chapters/timestamps."""
        return self.downloader.get_video_chapters(url)
    
    def get_playlist_info(self, url: str) -> Optional[List[Dict[str, Any]]]:
        """Get information about videos in a YouTube playlist."""
        return self.downloader.get_playlist_info(url)
    
    def split_video_into_tracks(
        self,
        video_path: Path,
        track_timestamps: List[Dict[str, Any]],
        output_dir: Path,
        metadata_list: List[Dict[str, Any]],
        progress_callback: Optional[Callable] = None
    ) -> List[Path]:
        """Split a full album video into individual tracks."""
        return self.downloader.split_video_into_tracks(
            video_path, track_timestamps, output_dir, metadata_list, progress_callback
        )