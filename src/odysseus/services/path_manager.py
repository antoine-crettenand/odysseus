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
        An album with featured artists (e.g., "Artist & Guest") is NOT a compilation.
        
        Returns True if there are at least 2 tracks with different primary artists.
        """
        if not release_info.tracks or len(release_info.tracks) < 2:
            return False
        
        # Normalize release artist for comparison
        release_artist_normalized = normalize_string(release_info.artist) if release_info.artist else ""
        
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
        
        # If we have a release artist, check if all track artists contain the release artist
        # This handles cases like "Air" (release) with tracks by "Air" and "Air & Beth Hirsch"
        if release_artist_normalized:
            all_tracks_share_release_artist = True
            for track in release_info.tracks:
                track_artist_normalized = normalize_string(track.artist) if track.artist else ""
                # Check if track artist contains release artist (handles collaborations)
                # Also check if release artist contains track artist (handles cases where release artist is longer)
                if track_artist_normalized and release_artist_normalized:
                    # Extract primary artist from track (before "&" or "and")
                    track_primary = track_artist_normalized.split(' and ')[0].split(' & ')[0].strip()
                    release_primary = release_artist_normalized.split(' and ')[0].split(' & ')[0].strip()
                    
                    # Check if they match or if one contains the other
                    if (track_primary != release_primary and 
                        track_primary not in release_artist_normalized and 
                        release_primary not in track_artist_normalized):
                        all_tracks_share_release_artist = False
                        break
            
            # If all tracks share the release artist, it's not a compilation
            if all_tracks_share_release_artist:
                return False
        
        # If we have 2 or more different primary artists across tracks, it's a compilation
        # Extract primary artists (before "&" or "and") to avoid false positives from collaborations
        primary_artists = set()
        for track in release_info.tracks:
            artist = normalize_string(track.artist) if track.artist else ""
            if artist:
                # Extract primary artist (before "&" or "and")
                primary = artist.split(' and ')[0].split(' & ')[0].strip()
                if primary:
                    primary_artists.add(primary)
        
        # If we have 2 or more different primary artists, it's a compilation
        return len(primary_artists) >= 2
    
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
        
        # Use original_release_date for folder path if available (prefer original year over re-release year)
        # This ensures re-releases are organized by their original release year
        date_to_use = release_info.original_release_date or release_info.release_date
        year = int(date_to_use[:4]) if date_to_use and len(date_to_use) >= 4 else None
        
        album_metadata = {
            'title': release_info.title,
            'artist': folder_artist,
            'album': release_info.title,
            'year': year,
        }
        return self.download_service.downloader._create_organized_path(album_metadata)
    
    def get_existing_tracks(
        self,
        release_info: ReleaseInfo,
        track_numbers: List[int]
    ) -> Dict[int, Path]:
        """
        Check which tracks already exist in the release folder (partial matches allowed).
        Matches tracks by title even if track numbers don't match (handles reordering).
        
        Args:
            release_info: Release information
            track_numbers: List of track numbers to check
            
        Returns:
            Dictionary mapping track numbers to file paths for tracks that exist
        """
        output_dir = self.get_release_folder_path(release_info)
        
        if not output_dir.exists():
            return {}
        
        audio_extensions = ['.mp3', '.m4a', '.ogg', '.opus', '.flac', '.wav', '.aac', '.webm']
        system_files = {'.DS_Store', '.Thumbs.db', 'desktop.ini'}
        
        # First, get all audio files in the directory
        all_audio_files = []
        for ext in audio_extensions:
            all_audio_files.extend(output_dir.glob(f"*{ext}"))
        all_audio_files = [
            f for f in all_audio_files
            if f.is_file() and f.name not in system_files
        ]
        
        existing_tracks = {}
        used_files = set()  # Track which files we've already matched
        
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
            
            # Strategy 1: Try exact match with correct track number
            found = False
            for ext in audio_extensions:
                potential_file = output_dir / f"{expected_base}{ext}"
                if potential_file.exists() and potential_file.is_file() and potential_file not in used_files:
                    existing_tracks[track_num] = potential_file
                    used_files.add(potential_file)
                    found = True
                    break
            
            # Strategy 2: Try glob pattern with correct track number
            if not found:
                existing_files = [
                    f for f in output_dir.glob(f"{expected_base}*")
                    if f.is_file()
                    and f.suffix.lower() in audio_extensions
                    and f.name not in system_files
                    and f not in used_files
                ]
                if existing_files:
                    existing_tracks[track_num] = existing_files[0]
                    used_files.add(existing_files[0])
                    found = True
            
            # Strategy 3: Match by title only (ignore track number) - handles reordering
            if not found:
                # Normalize title for matching
                title_normalized = normalize_string(title).lower()
                
                for audio_file in all_audio_files:
                    if audio_file in used_files:
                        continue
                    
                    # Extract title from filename (remove track number prefix if present)
                    filename_stem = audio_file.stem
                    # Try to remove track number prefix (e.g., "09 - Title" or "9 - Title")
                    if ' - ' in filename_stem:
                        parts = filename_stem.split(' - ', 1)
                        # Check if first part is a number
                        try:
                            int(parts[0].strip())
                            # It's a track number, use the second part as title
                            file_title = parts[1]
                        except ValueError:
                            # Not a track number, use whole filename
                            file_title = filename_stem
                    else:
                        file_title = filename_stem
                    
                    # Normalize and compare
                    file_title_normalized = normalize_string(file_title).lower()
                    
                    # Check if titles match (exact or very similar)
                    if title_normalized == file_title_normalized:
                        # Found a match by title - this track exists but maybe with wrong number
                        existing_tracks[track_num] = audio_file
                        used_files.add(audio_file)
                        found = True
                        break
                    # Also try partial match (in case of slight variations)
                    elif title_normalized in file_title_normalized or file_title_normalized in title_normalized:
                        # Check if the match is significant (at least 80% of shorter string)
                        min_len = min(len(title_normalized), len(file_title_normalized))
                        if min_len > 0:
                            overlap = len(set(title_normalized) & set(file_title_normalized))
                            similarity = overlap / min_len
                            if similarity > 0.8:
                                existing_tracks[track_num] = audio_file
                                used_files.add(audio_file)
                                found = True
                                break
        
        return existing_tracks
    
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
        existing_tracks = self.get_existing_tracks(release_info, track_numbers)
        
        # Return None if not all tracks exist
        if len(existing_tracks) == len(track_numbers):
            return existing_tracks
        return None

