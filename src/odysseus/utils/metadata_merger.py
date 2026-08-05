"""
Metadata Merger Module
Collects metadata from various sources and selects the best metadata
to apply to audio files.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, fields, replace
from pathlib import Path
import logging
from ..models.song import AudioMetadata
from .metadata_appliers import get_metadata_applier

# Use module-level logger without basicConfig (will use parent logger configuration)
logger = logging.getLogger(__name__)


@dataclass
class MetadataSource:
    """Represents metadata from a specific source."""
    source_name: str
    metadata: AudioMetadata
    confidence: float = 1.0  # Confidence score (0.0 to 1.0)
    completeness: float = 0.0  # How complete the metadata is (0.0 to 1.0)

    def __post_init__(self):
        """Calculate completeness score."""
        self.completeness = self._calculate_completeness()

    def _calculate_completeness(self) -> float:
        """Calculate how complete the metadata is."""
        fields = [
            self.metadata.title, self.metadata.artist, self.metadata.album,
            self.metadata.year, self.metadata.genre, self.metadata.track_number,
            self.metadata.composer, self.metadata.publisher,
            self.metadata.isrc, self.metadata.disc_number,
            self.metadata.catalog_number, self.metadata.barcode,
        ]
        filled_fields = sum(1 for field in fields if field is not None)
        return filled_fields / len(fields)


class MetadataMerger:
    """Merges metadata from multiple sources and selects the best combination."""

    def __init__(self):
        self.sources: List[MetadataSource] = []
        self.final_metadata: Optional[AudioMetadata] = None

    def add_metadata_source(self, source_name: str, metadata: AudioMetadata, confidence: float = 1.0):
        """Add metadata from a source."""
        source = MetadataSource(
            source_name=source_name,
            metadata=metadata,
            confidence=confidence
        )
        self.sources.append(source)
        logger.debug(f"Added {source_name} metadata: {metadata.title} by {metadata.artist}")

    def merge_metadata(self) -> AudioMetadata:
        """Merge metadata from all sources and return the best combination."""
        if not self.sources:
            logger.warning("No metadata sources available")
            empty_metadata = AudioMetadata()
            self.final_metadata = empty_metadata
            return empty_metadata

        # Sort sources by combined score (confidence * completeness)
        sorted_sources = sorted(
            self.sources,
            key=lambda s: s.confidence * s.completeness,
            reverse=True
        )

        # Start with the best source as base
        best_source = sorted_sources[0]
        # Keep the provider identity so provider-specific IDs can be written
        # using their established tag names after fields are merged.
        merged_metadata = replace(best_source.metadata)

        # Fill in missing fields from other sources
        for source in sorted_sources[1:]:
            self._fill_missing_fields(merged_metadata, source.metadata, source.confidence)

        # Handle cover art merging - prefer sources with cover art
        for source in sorted_sources:
            if source.metadata.cover_art_data and not merged_metadata.cover_art_data:
                merged_metadata.cover_art_data = source.metadata.cover_art_data
                merged_metadata.cover_art_url = source.metadata.cover_art_url
                break

        self.final_metadata = merged_metadata
        logger.debug(f"Merged metadata: {merged_metadata.title} by {merged_metadata.artist}")
        return merged_metadata

    def _fill_missing_fields(self, target: AudioMetadata, source: AudioMetadata, confidence: float) -> None:
        """Fill missing fields in target metadata from source metadata."""
        # Only fill fields that are None in target and have a value in source
        # Use confidence threshold to decide whether to use the source value
        confidence_threshold = 0.5

        if confidence >= confidence_threshold:
            for metadata_field in fields(AudioMetadata):
                field_name = metadata_field.name
                if field_name in {"source", "cover_art_data", "cover_art_url"}:
                    continue
                if (
                    getattr(target, field_name) is None
                    and getattr(source, field_name) is not None
                ):
                    setattr(target, field_name, getattr(source, field_name))

    def get_metadata_summary(self) -> Dict[str, Any]:
        """Get a summary of all metadata sources and the final merged result."""
        summary = {
            "sources": [],
            "final_metadata": None,
            "total_sources": len(self.sources)
        }

        for source in self.sources:
            summary["sources"].append({
                "name": source.source_name,
                "confidence": source.confidence,
                "completeness": source.completeness,
                "metadata": {
                    "title": source.metadata.title,
                    "artist": source.metadata.artist,
                    "album": source.metadata.album,
                    "year": source.metadata.year
                }
            })

        if self.final_metadata:
            summary["final_metadata"] = {
                "title": self.final_metadata.title,
                "artist": self.final_metadata.artist,
                "album": self.final_metadata.album,
                "year": self.final_metadata.year,
                "genre": self.final_metadata.genre,
                "source": self.final_metadata.source,
                "has_cover_art": self.final_metadata.cover_art_data is not None,
                "cover_art_size": len(self.final_metadata.cover_art_data) if self.final_metadata.cover_art_data else 0
            }

        return summary

    def display_metadata_sources(self) -> None:
        """Display all metadata sources in a formatted way for user selection."""
        if not self.sources:
            print("No metadata sources available.")
            return

        print("\n" + "="*80)
        print("METADATA SOURCES")
        print("="*80)

        for i, source in enumerate(self.sources, 1):
            print(f"\n{i}. {source.source_name}")
            print(f"   Confidence: {source.confidence:.2f} | Completeness: {source.completeness:.2f}")
            print(f"   Title: {source.metadata.title or 'N/A'}")
            print(f"   Artist: {source.metadata.artist or 'N/A'}")
            print(f"   Album: {source.metadata.album or 'N/A'}")
            print(f"   Year: {source.metadata.year or 'N/A'}")
            if source.metadata.genre:
                print(f"   Genre: {source.metadata.genre}")
            if source.metadata.cover_art_url:
                print("   Cover Art: Available")
            print("-" * 40)

    def _get_field_selection(self, field_name: str, getter_func) -> Optional[Any]:
        """Helper to get user selection for a metadata field."""
        options = [(i, source) for i, source in enumerate(self.sources, 1) if getter_func(source.metadata)]
        if not options:
            return None
        print(f"\n{field_name} options:")
        for i, source in options:
            print(f"  {i}. {getter_func(source.metadata)} (from {source.source_name})")
        while True:
            try:
                choice = input(f"Select {field_name} (1-{len(options)}) or Enter to skip: ").strip()
                if not choice:
                    return None
                choice_num = int(choice)
                if 1 <= choice_num <= len(options):
                    return getter_func(options[choice_num - 1][1].metadata)
                print(f"Please enter a number between 1 and {len(options)}")
            except ValueError:
                print("Please enter a valid number or press Enter to skip")

    def get_user_metadata_selection(self) -> AudioMetadata:
        """Allow user to select metadata from available sources."""
        if not self.sources:
            print("No metadata sources available.")
            return AudioMetadata()

        self.display_metadata_sources()
        selected_metadata = AudioMetadata()

        print("\n" + "="*80)
        print("METADATA SELECTION")
        print("="*80)
        print("Choose the source for each metadata field (or press Enter to skip):")

        selected_metadata.title = self._get_field_selection("Title", lambda m: m.title)
        selected_metadata.artist = self._get_field_selection("Artist", lambda m: m.artist)
        selected_metadata.album = self._get_field_selection("Album/Release", lambda m: m.album)
        selected_metadata.year = self._get_field_selection("Year", lambda m: m.year)

        for source in self.sources:
            if source.metadata.cover_art_data:
                selected_metadata.cover_art_data = source.metadata.cover_art_data
                selected_metadata.cover_art_url = source.metadata.cover_art_url
                break

        selected_metadata.source = "manual_selection"
        print("\nSelected metadata:")
        print(f"  Title: {selected_metadata.title or 'N/A'}")
        print(f"  Artist: {selected_metadata.artist or 'N/A'}")
        print(f"  Album: {selected_metadata.album or 'N/A'}")
        print(f"  Year: {selected_metadata.year or 'N/A'}")
        if selected_metadata.cover_art_data:
            print(f"  Cover Art: Available ({len(selected_metadata.cover_art_data)} bytes)")

        return selected_metadata

    def set_final_metadata(self, metadata: AudioMetadata) -> None:
        """Set the final metadata manually (e.g., from user selection)."""
        self.final_metadata = metadata
        logger.debug(f"Set final metadata manually: {metadata.title} by {metadata.artist}")

    def apply_metadata_to_file(self, file_path, quiet: bool = False) -> bool:
        """
        Apply the merged metadata to an audio file.

        Args:
            file_path: Path to the audio file
            quiet: If True, suppress success messages (useful when progress bars are active)
        """
        if not self.final_metadata:
            logger.error("No merged metadata available")
            return False

        try:
            # Load audio file
            audio_file, file_path, file_ext = self._load_audio_file(file_path)
            if audio_file is None:
                return False

            # Get format-specific applier
            applier = get_metadata_applier(file_ext, self.final_metadata)

            # Apply metadata tags
            applier.apply_tags(audio_file)

            # Apply cover art if available
            if self.final_metadata.cover_art_data:
                mime_type = applier._detect_mime_type(self.final_metadata.cover_art_data)
                applier.apply_cover_art(audio_file, file_path, mime_type, quiet)

            # Save the file
            applier.save(audio_file, file_path)

            message = f"✓ Applied metadata to {file_path.name}"
            if not quiet:
                print(message)
            logger.debug(f"Applied metadata to {file_path}")
            return True

        except ImportError:
            logger.error("mutagen library not available. Install with: pip install mutagen")
            return False
        except Exception as e:
            logger.error(f"Error applying metadata to {file_path}: {e}")
            return False

    def _load_audio_file(self, file_path):
        """Load audio file and return file object, path, and extension."""
        from mutagen import File as MutagenFile

        if isinstance(file_path, str):
            file_path = Path(file_path)

        audio_file = MutagenFile(str(file_path))
        if audio_file is None:
            logger.error(f"Could not load audio file: {file_path}")
            return None, file_path, None

        file_ext = file_path.suffix.lower()
        return audio_file, file_path, file_ext
