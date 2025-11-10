"""
Path Utilities Module
Handles path sanitization and organization for downloads.
"""

import re
from pathlib import Path
from typing import Dict, Any, Optional


class PathUtils:
    """Utility functions for path management."""
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize filename to prevent path traversal and filesystem issues.
        Also removes sub-parts (a), b), c), etc.) from track titles to keep filenames shorter.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename safe for filesystem use
        """
        if not filename:
            return "unknown"
        
        sanitized = filename
        
        # Remove sub-parts like "a) ... / b) ... / c) ..." to shorten filenames
        # Pattern matches: "a) Title / b) Title / c) Title" or "a) Title, b) Title, c) Title"
        # This handles cases like "Alan's Psychedelic Breakfast: a) Rise and Shine / b) Sunny Side Up / c) Morning Glory"
        # Match pattern: colon (optional) followed by letter) followed by text, optionally repeated with / or ,
        # The pattern captures: ": a) ... / b) ... / c) ..." or just "a) ... / b) ... / c) ..."
        sub_part_pattern = r'(?::\s*)?[a-z]\)\s+[^/]+(?:\s*[/,]\s*[a-z]\)\s+[^/]+)*'
        
        # Try to match and remove sub-parts
        # First try with colon (most common case)
        if re.search(r':\s*[a-z]\)', sanitized, re.IGNORECASE):
            # Remove everything from colon onwards if it matches the sub-part pattern
            sanitized = re.sub(r':\s*[a-z]\)\s+[^/]+(?:\s*[/,]\s*[a-z]\)\s+[^/]+)*', '', sanitized, flags=re.IGNORECASE)
        # If no colon, try to match sub-parts at the end
        elif re.search(r'\s+[a-z]\)\s+', sanitized, re.IGNORECASE):
            # Remove sub-parts pattern from the end
            sanitized = re.sub(r'\s+[a-z]\)\s+[^/]+(?:\s*[/,]\s*[a-z]\)\s+[^/]+)*$', '', sanitized, flags=re.IGNORECASE)
        
        # Clean up any trailing separators
        sanitized = re.sub(r'[:;]\s*$', '', sanitized)
        sanitized = sanitized.strip()
        
        # Prevent path traversal attacks by removing .. sequences
        sanitized = sanitized.replace('..', '_')
        
        # Remove or replace invalid characters for filesystem
        invalid_chars = r'[<>:"/\\|?*]'
        sanitized = re.sub(invalid_chars, '_', sanitized)
        
        # Remove multiple consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        
        # Remove leading/trailing underscores and dots
        sanitized = sanitized.strip('_.')
        
        # Limit filename length to prevent filesystem issues (255 chars is common limit)
        max_length = 200  # Leave room for extension
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        # Ensure filename is not empty after sanitization
        if not sanitized:
            return "unknown"
        
        return sanitized
    
    @staticmethod
    def create_organized_path(download_dir: Path, metadata: Optional[Dict[str, Any]] = None) -> Path:
        """
        Create organized directory path for downloads.
        
        Args:
            download_dir: Base download directory
            metadata: Optional metadata dictionary
                - If 'is_playlist' is True, creates Playlists/[playlist_name]/ structure
                - Otherwise, creates Artist/Album (year)/ structure
            
        Returns:
            Path object for the organized directory
            
        Security: This method ensures paths stay within the download directory
        to prevent path traversal attacks.
        """
        if not metadata:
            return download_dir
        
        # Check if this is a playlist (e.g., from Spotify)
        is_playlist = metadata.get('is_playlist', False)
        if is_playlist:
            playlist_name = metadata.get('playlist_name', metadata.get('album', 'Unknown Playlist'))
            playlist_name = PathUtils.sanitize_filename(playlist_name)
            
            # Create folder structure: Playlists/[Playlist Name]/
            organized_dir = download_dir / "Playlists" / playlist_name
            
            # Security: Resolve the path and ensure it's still within download_dir
            try:
                resolved_path = organized_dir.resolve()
                download_dir_resolved = download_dir.resolve()
                
                # Check that the resolved path is within the download directory
                if not str(resolved_path).startswith(str(download_dir_resolved)):
                    # Fallback to download_dir if path traversal detected
                    return download_dir
            except (OSError, ValueError):
                # If resolution fails, fallback to download_dir
                return download_dir
            
            organized_dir.mkdir(parents=True, exist_ok=True)
            return organized_dir
        
        # Extract metadata fields for regular album structure
        # Treat empty strings as missing values (use defaults)
        artist = metadata.get('artist') or 'Unknown Artist'
        album = metadata.get('album') or 'Unknown Album'
        year = metadata.get('year')
        title = metadata.get('title') or 'Unknown Title'
        
        # Sanitize all components (this also prevents path traversal)
        artist = PathUtils.sanitize_filename(artist)
        album = PathUtils.sanitize_filename(album)
        title = PathUtils.sanitize_filename(title)
        
        # Create folder structure: Artist/LP (release year)/
        artist_dir = download_dir / artist
        
        if year:
            lp_folder_name = f"{album} ({year})"
        else:
            lp_folder_name = album
        
        # Sanitize the folder name as well
        lp_folder_name = PathUtils.sanitize_filename(lp_folder_name)
        
        # Create the organized directory structure
        organized_dir = artist_dir / lp_folder_name
        
        # Security: Resolve the path and ensure it's still within download_dir
        # This prevents path traversal even if sanitization somehow fails
        try:
            resolved_path = organized_dir.resolve()
            download_dir_resolved = download_dir.resolve()
            
            # Check that the resolved path is within the download directory
            if not str(resolved_path).startswith(str(download_dir_resolved)):
                # Fallback to download_dir if path traversal detected
                return download_dir
        except (OSError, ValueError):
            # If resolution fails, fallback to download_dir
            return download_dir
        
        organized_dir.mkdir(parents=True, exist_ok=True)
        
        return organized_dir

