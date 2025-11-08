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
    
    def fetch_cover_art(self, mbid: str, console=None) -> Optional[bytes]:
        """Fetch cover art from MusicBrainz Cover Art Archive."""
        if not mbid or not mbid.strip():
            if console:
                console.print(f"[yellow]⚠[/yellow] No MBID provided for cover art fetch")
            return None
            
        try:
            # Use HTTPS and add User-Agent header
            cover_art_url = f"https://coverartarchive.org/release/{mbid}"
            headers = {
                'User-Agent': 'Odysseus/1.0 (https://github.com/yourusername/odysseus)'
            }
            response = requests.get(cover_art_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                images = data.get('images', [])
                
                if not images:
                    if console:
                        console.print(f"[yellow]⚠[/yellow] No images found in Cover Art Archive for MBID: {mbid}")
                    return None
                
                # Look for front cover
                for image in images:
                    if image.get('front', False):
                        image_url = image.get('image')
                        if image_url:
                            img_response = requests.get(image_url, headers=headers, timeout=10)
                            if img_response.status_code == 200:
                                if console:
                                    console.print(f"[blue]ℹ[/blue] Fetched front cover art ({len(img_response.content)} bytes)")
                                return img_response.content
                
                # If no front cover, use first image
                if images:
                    image_url = images[0].get('image')
                    if image_url:
                        img_response = requests.get(image_url, headers=headers, timeout=10)
                        if img_response.status_code == 200:
                            if console:
                                console.print(f"[blue]ℹ[/blue] Fetched cover art (first available, {len(img_response.content)} bytes)")
                            return img_response.content
            elif response.status_code == 404:
                if console:
                    console.print(f"[yellow]⚠[/yellow] Cover art not found in archive for MBID: {mbid}")
            else:
                if console:
                    console.print(f"[yellow]⚠[/yellow] Cover Art Archive returned status {response.status_code} for MBID: {mbid}")
        except requests.exceptions.RequestException as e:
            if console:
                console.print(f"[yellow]⚠[/yellow] Network error fetching cover art: {e}")
        except Exception as e:
            if console:
                console.print(f"[yellow]⚠[/yellow] Error fetching cover art: {e}")
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
            # MusicBrainz MBIDs are UUIDs (format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
            # Discogs IDs are just numbers, so we can check the format
            cover_art_fetched = False
            mbid = release_info.mbid.strip() if release_info.mbid else ""
            
            # Check if MBID looks like a MusicBrainz UUID (has dashes)
            is_musicbrainz_mbid = mbid and '-' in mbid and len(mbid) == 36
            
            if mbid and is_musicbrainz_mbid:
                if console:
                    console.print(f"[blue]ℹ[/blue] Fetching cover art for {track.title}...")
                cover_art_data = self.fetch_cover_art(mbid, console)
                if cover_art_data:
                    metadata.cover_art_data = cover_art_data
                    cover_art_fetched = True
                elif console:
                    console.print(f"[yellow]⚠[/yellow] Cover art not available for this release")
            elif mbid and not is_musicbrainz_mbid:
                # This is likely a Discogs ID, not a MusicBrainz MBID
                if console:
                    console.print(f"[yellow]⚠[/yellow] MBID appears to be from Discogs (not MusicBrainz). Cover art requires MusicBrainz MBID.")
            elif console:
                console.print(f"[yellow]⚠[/yellow] No MBID available for cover art (release: {release_info.title})")
            
            # Apply metadata (quiet=True to suppress messages when progress bars are active)
            self.merger.set_final_metadata(metadata)
            success = self.merger.apply_metadata_to_file(str(file_path), quiet=True)
            
            if success:
                if console:
                    if cover_art_fetched:
                        console.print(f"[blue]ℹ[/blue] ✓ Applied metadata and cover art to [white]{track.title}[/white]")
                    else:
                        console.print(f"[blue]ℹ[/blue] ✓ Applied metadata to [white]{track.title}[/white]")
            else:
                if console:
                    console.print(f"[yellow]⚠[/yellow] Failed to apply metadata to {track.title}")
                raise Exception("Metadata application returned False")
            
        except Exception as e:
            if console:
                console.print(f"[yellow]⚠[/yellow] Could not apply metadata and cover art to {track.title}: {e}")
            raise  # Re-raise to allow caller to handle
