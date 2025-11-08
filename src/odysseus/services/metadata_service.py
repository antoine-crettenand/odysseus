"""
Metadata service for handling and merging metadata from various sources.
"""

import requests
from typing import List, Optional, Dict, Any
from pathlib import Path
from ..models.song import AudioMetadata
from ..models.releases import ReleaseInfo, Track
from ..utils.metadata_merger import MetadataMerger


class MetadataService:
    """Service for handling metadata operations."""
    
    def __init__(self):
        self.merger = MetadataMerger()
    
    def add_metadata_source(self, source_name: str, metadata: AudioMetadata, confidence: float = 1.0):
        """Add metadata from a source."""
        self.merger.add_metadata_source(source_name, metadata, confidence)
    
    def merge_metadata(self) -> AudioMetadata:
        """Merge metadata from all sources."""
        return self.merger.merge_metadata()
    
    def get_metadata_sources(self) -> List[Dict[str, Any]]:
        """Get all metadata sources."""
        return [
            {
                'name': source.source_name,
                'confidence': source.confidence,
                'completeness': source.completeness,
                'metadata': source.metadata
            }
            for source in self.merger.sources
        ]
    
    def apply_metadata_to_file(self, file_path: str, quiet: bool = False) -> bool:
        """Apply merged metadata to a file."""
        return self.merger.apply_metadata_to_file(file_path, quiet=quiet)
    
    def get_user_metadata_selection(self) -> AudioMetadata:
        """Allow user to select metadata from available sources."""
        return self.merger.get_user_metadata_selection()
    
    def set_final_metadata(self, metadata: AudioMetadata):
        """Set the final metadata manually."""
        self.merger.set_final_metadata(metadata)
    
    def fetch_cover_art(self, mbid: str) -> Optional[bytes]:
        """Fetch cover art from MusicBrainz Cover Art Archive."""
        try:
            cover_art_url = f"http://coverartarchive.org/release/{mbid}"
            response = requests.get(cover_art_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                images = data.get('images', [])
                
                # Look for front cover
                for image in images:
                    if image.get('front', False):
                        image_url = image.get('image')
                        if image_url:
                            img_response = requests.get(image_url, timeout=10)
                            if img_response.status_code == 200:
                                return img_response.content
                
                # If no front cover, use first image
                if images:
                    image_url = images[0].get('image')
                    if image_url:
                        img_response = requests.get(image_url, timeout=10)
                        if img_response.status_code == 200:
                            return img_response.content
        except Exception:
            # Silently fail - cover art is optional
            pass
        return None
    
    def apply_metadata_with_cover_art(
        self,
        file_path: Path,
        track: Track,
        release_info: ReleaseInfo,
        console=None
    ):
        """Apply metadata including cover art to downloaded file."""
        try:
            # Create metadata
            metadata = AudioMetadata(
                title=track.title,
                artist=track.artist,
                album=release_info.title,
                year=int(release_info.release_date[:4]) if release_info.release_date and len(release_info.release_date) >= 4 else None,
                genre=release_info.genre,
                track_number=track.position,
                total_tracks=len(release_info.tracks)
            )
            
            # Fetch cover art from MusicBrainz if we have MBID
            if release_info.mbid:
                cover_art_data = self.fetch_cover_art(release_info.mbid)
                if cover_art_data:
                    metadata.cover_art_data = cover_art_data
                    if console:
                        console.print(f"[blue]ℹ[/blue] ✓ Fetched metadata and cover art for [white]{track.title}[/white]")
            
            # Apply metadata (quiet=True to suppress messages when progress bars are active)
            self.merger.set_final_metadata(metadata)
            self.merger.apply_metadata_to_file(str(file_path), quiet=True)
            
        except Exception as e:
            if console:
                console.print(f"[yellow]⚠[/yellow] Could not apply metadata and cover art to {track.title}: {e}")
