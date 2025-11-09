"""
Path and file management utilities for downloads.
"""

from typing import List, Optional, Dict
from pathlib import Path
from ..models.releases import ReleaseInfo
from ..utils.string_utils import normalize_string


class PathManager:
    """Manages file paths and tracks existing files."""
    
    def __init__(self, download_service):
        """
        Initialize path manager.
        
        Args:
            download_service: DownloadService instance
        """
        self.download_service = download_service
    
    def is_compilation(self, release_info: ReleaseInfo) -> bool:
        """
        Check if a release is a compilation (has multiple different artists).
        
        A compilation has different artists on different tracks.
        A collaboration album has the same collaborating artists on all tracks.
        
        Returns True if there are at least 2 tracks with different artists.
        """
        if not release_info.tracks or len(release_info.tracks) < 2:
            return False
        
        # Normalize artist names for comparison (case-insensitive, strip whitespace)
        artists = set()
        for track in release_info.tracks:
            artist = normalize_string(track.artist) if track.artist else ""
            if artist:  # Only count non-empty artists
                artists.add(artist)
        
        # If all tracks have the same artist (even if it's "Artist A & Artist B"),
        # it's a collaboration album, not a compilation
        if len(artists) == 1:
            return False
        
        # If we have 2 or more different artists across tracks, it's a compilation
        # This means different tracks have different artists (not just different artist names)
        return len(artists) >= 2
    
    def get_release_folder_path(self, release_info: ReleaseInfo) -> Path:
        """
        Get the folder path where tracks for this release would be saved.
        
        Args:
            release_info: Release information
            
        Returns:
            Path to the release folder
        """
        # Check if this is a Spotify playlist (only Spotify sets release_type to "Playlist")
        # Also verify URL to ensure it's from Spotify (extra safeguard)
        is_spotify_playlist = (
            release_info.release_type == "Playlist" and 
            release_info.url and 
            "spotify.com" in release_info.url
        )
        
        if is_spotify_playlist:
            playlist_metadata = {
                'is_playlist': True,
                'playlist_name': release_info.title,
                'album': release_info.title,
            }
            return self.download_service.downloader._create_organized_path(playlist_metadata)
        
        # Regular album structure
        is_compilation = self.is_compilation(release_info)
        folder_artist = "Various Artists" if is_compilation else release_info.artist
        album_metadata = {
            'title': release_info.title,
            'artist': folder_artist,
            'album': release_info.title,
            'year': int(release_info.release_date[:4]) if release_info.release_date and len(release_info.release_date) >= 4 else None,
        }
        return self.download_service.downloader._create_organized_path(album_metadata)
    
    def check_existing_tracks(
        self,
        release_info: ReleaseInfo,
        track_numbers: List[int]
    ) -> Optional[Dict[int, Path]]:
        """
        Check if all selected tracks already exist in the release folder.
        
        Args:
            release_info: Release information
            track_numbers: List of track numbers to check
            
        Returns:
            Dictionary mapping track numbers to file paths if all tracks exist, None otherwise
        """
        output_dir = self.get_release_folder_path(release_info)
        
        if not output_dir.exists():
            return None
        
        audio_extensions = ['.mp3', '.m4a', '.ogg', '.opus', '.flac', '.wav', '.aac', '.webm']
        system_files = {'.DS_Store', '.Thumbs.db', 'desktop.ini'}
        
        existing_tracks = {}
        is_compilation = self.is_compilation(release_info)
        folder_artist = "Various Artists" if is_compilation else release_info.artist
        
        for track_num in track_numbers:
            # Find the track
            track = None
            for t in release_info.tracks:
                if t.position == track_num:
                    track = t
                    break
            
            if not track:
                continue
            
            # Build expected filename
            title = self.download_service.downloader._sanitize_filename(track.title)
            track_prefix = f"{track_num:02d} - "
            expected_base = f"{track_prefix}{title}"
            
            # Check for existing files matching the expected pattern
            found = False
            for ext in audio_extensions:
                potential_file = output_dir / f"{expected_base}{ext}"
                if potential_file.exists() and potential_file.is_file():
                    existing_tracks[track_num] = potential_file
                    found = True
                    break
            
            # If not found with exact match, try glob pattern
            if not found:
                existing_files = [
                    f for f in output_dir.glob(f"{expected_base}*")
                    if f.is_file()
                    and f.suffix.lower() in audio_extensions
                    and f.name not in system_files
                ]
                if existing_files:
                    existing_tracks[track_num] = existing_files[0]
                    found = True
            
            # If any track is missing, return None
            if not found:
                return None
        
        # All tracks exist
        return existing_tracks if len(existing_tracks) == len(track_numbers) else None

