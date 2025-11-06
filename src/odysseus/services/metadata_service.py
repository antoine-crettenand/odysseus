"""
Metadata service for handling and merging metadata from various sources.
"""

from typing import List, Optional, Dict, Any
from ..models.song import AudioMetadata
from ..models.search_results import SearchResult
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
    
    def apply_metadata_to_file(self, file_path: str) -> bool:
        """Apply merged metadata to a file."""
        return self.merger.apply_metadata_to_file(file_path)
    
    def get_user_metadata_selection(self) -> AudioMetadata:
        """Allow user to select metadata from available sources."""
        return self.merger.get_user_metadata_selection()
    
    def set_final_metadata(self, metadata: AudioMetadata):
        """Set the final metadata manually."""
        self.merger.set_final_metadata(metadata)
