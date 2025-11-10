"""
Metadata service for handling and merging metadata from various sources.
"""

from typing import List, Optional, Dict, Any
from pathlib import Path
from ..models.song import AudioMetadata, SongData
from ..models.releases import ReleaseInfo, Track
from ..utils.metadata_merger import MetadataMerger
from .cover_art_fetcher import CoverArtFetcher


class MetadataService:
    """Service for handling metadata operations."""
    
    def __init__(self):
        self.merger = MetadataMerger()
        self.cover_art_fetcher = CoverArtFetcher()
    
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
    
    def fetch_cover_art_from_url(self, url: str, console=None, use_cache: bool = True) -> Optional[bytes]:
        """Fetch cover art from a URL (delegates to CoverArtFetcher)."""
        return self.cover_art_fetcher.fetch_cover_art_from_url(url, console, use_cache)
    
    def fetch_cover_art(self, mbid: str, console=None, use_cache: bool = True) -> Optional[bytes]:
        """Fetch cover art from MusicBrainz (delegates to CoverArtFetcher)."""
        return self.cover_art_fetcher.fetch_cover_art(mbid, console, use_cache)
    
    def fetch_cover_art_for_release(self, release_info: ReleaseInfo, console=None, folder_path: Optional[Path] = None) -> Optional[bytes]:
        """Fetch cover art for a release (delegates to CoverArtFetcher)."""
        return self.cover_art_fetcher.fetch_cover_art_for_release(release_info, console, folder_path)
    
    def apply_metadata_with_cover_art(
        self,
        file_path: Path,
        track: Track,
        release_info: ReleaseInfo,
        console=None,
        cover_art_data: Optional[bytes] = None,
        path_manager=None
    ):
        """
        Apply metadata including cover art to downloaded file.
        
        Args:
            file_path: Path to the audio file
            track: Track information
            release_info: Release information
            console: Optional console for output
            cover_art_data: Optional pre-fetched cover art data. If None, will fetch it.
                           It's recommended to fetch cover art once per release and pass it
                           to all tracks in that release for better performance.
            path_manager: Optional PathManager instance for compilation detection
        """
        try:
            # Check if this is a compilation
            # If path_manager is provided, use it; otherwise use a simple check
            if path_manager:
                is_compilation = path_manager.is_compilation(release_info)
            else:
                # Fallback: simple compilation check
                from ..utils.string_utils import normalize_string
                if not release_info.tracks or len(release_info.tracks) < 2:
                    is_compilation = False
                else:
                    artists = set()
                    for t in release_info.tracks:
                        artist = normalize_string(t.artist) if t.artist else ""
                        if artist:
                            artists.add(artist)
                    is_compilation = len(artists) >= 2
            
            # Normalize album name to ensure consistency (strip whitespace)
            album_name = release_info.title.strip() if release_info.title else "Unknown Album"
            
            # Create metadata
            metadata = AudioMetadata(
                title=track.title,
                artist=track.artist,  # Track artist (individual artist for each track)
                album=album_name,  # Normalized album name for consistency
                album_artist="Various Artists" if is_compilation else (release_info.artist.strip() if release_info.artist else "Unknown Artist"),  # Album artist for iTunes grouping
                year=int(release_info.release_date[:4]) if release_info.release_date and len(release_info.release_date) >= 4 else None,
                genre=release_info.genre,
                track_number=track.position,
                total_tracks=len(release_info.tracks),
                compilation=is_compilation  # Set compilation flag for iTunes
            )
            
            # Use provided cover art, or fetch it if not provided
            cover_art_fetched = False
            if cover_art_data:
                metadata.cover_art_data = cover_art_data
                cover_art_fetched = True
            else:
                # Fallback: fetch cover art (this will use cache if available)
                cover_art_data = self.fetch_cover_art_for_release(release_info, console)
                if cover_art_data:
                    metadata.cover_art_data = cover_art_data
                    cover_art_fetched = True
            
            if not cover_art_fetched and console:
                console.print(f"[yellow]⚠[/yellow] No cover art available for this release")
            
            # Apply metadata (quiet=True to suppress messages when progress bars are active)
            self.merger.set_final_metadata(metadata)
            success = self.merger.apply_metadata_to_file(str(file_path), quiet=True)
            
            if success:
                # Check if actual file duration differs significantly from expected duration
                if track.duration and console:
                    from ..utils.file_duration_reader import (
                        get_file_duration, 
                        format_duration, 
                        parse_duration_to_seconds
                    )
                    
                    actual_duration_seconds = get_file_duration(file_path)
                    expected_duration_seconds = parse_duration_to_seconds(track.duration)
                    
                    if actual_duration_seconds and expected_duration_seconds:
                        # Check if durations differ by more than 5% (allowing for small differences)
                        diff_ratio = abs(actual_duration_seconds - expected_duration_seconds) / expected_duration_seconds
                        if diff_ratio > 0.05:  # More than 5% difference
                            actual_duration_str = format_duration(actual_duration_seconds)
                            console.print(
                                f"[yellow]⚠[/yellow] Duration mismatch for [white]{track.title}[/white]: "
                                f"expected [cyan]{track.duration}[/cyan], "
                                f"actual [cyan]{actual_duration_str}[/cyan] "
                                f"(difference: {diff_ratio*100:.1f}%)"
                            )
                
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
