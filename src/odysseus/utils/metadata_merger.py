"""
Metadata Merger Module
Collects metadata from various sources and selects the best metadata
to apply to audio files.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
import logging
import requests
from ..models.song import AudioMetadata

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
            self.metadata.composer, self.metadata.publisher
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
            return AudioMetadata()
        
        # Sort sources by combined score (confidence * completeness)
        sorted_sources = sorted(
            self.sources,
            key=lambda s: s.confidence * s.completeness,
            reverse=True
        )
        
        # Start with the best source as base
        best_source = sorted_sources[0]
        merged_metadata = AudioMetadata(
            title=best_source.metadata.title,
            artist=best_source.metadata.artist,
            album=best_source.metadata.album,
            album_artist=best_source.metadata.album_artist,
            track_number=best_source.metadata.track_number,
            total_tracks=best_source.metadata.total_tracks,
            disc_number=best_source.metadata.disc_number,
            total_discs=best_source.metadata.total_discs,
            year=best_source.metadata.year,
            genre=best_source.metadata.genre,
            comment=best_source.metadata.comment,
            composer=best_source.metadata.composer,
            conductor=best_source.metadata.conductor,
            performer=best_source.metadata.performer,
            publisher=best_source.metadata.publisher,
            copyright=best_source.metadata.copyright,
            isrc=best_source.metadata.isrc,
            bpm=best_source.metadata.bpm,
            key=best_source.metadata.key,
            mood=best_source.metadata.mood,
            source=f"merged_from_{best_source.source_name}"
        )
        
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
            if target.title is None and source.title is not None:
                target.title = source.title
            if target.artist is None and source.artist is not None:
                target.artist = source.artist
            if target.album is None and source.album is not None:
                target.album = source.album
            if target.year is None and source.year is not None:
                target.year = source.year
            if target.genre is None and source.genre is not None:
                target.genre = source.genre
    
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
                print(f"   Cover Art: Available")
            print("-" * 40)
    
    def get_user_metadata_selection(self) -> AudioMetadata:
        """Allow user to select metadata from available sources."""
        if not self.sources:
            print("No metadata sources available.")
            return AudioMetadata()
        
        self.display_metadata_sources()
        
        # Get user selection for each field
        selected_metadata = AudioMetadata()
        
        print("\n" + "="*80)
        print("METADATA SELECTION")
        print("="*80)
        print("Choose the source for each metadata field (or press Enter to skip):")
        
        # Title selection
        title_options = [(i, source) for i, source in enumerate(self.sources, 1) if source.metadata.title]
        if title_options:
            print(f"\nTitle options:")
            for i, source in title_options:
                print(f"  {i}. {source.metadata.title} (from {source.source_name})")
            
            while True:
                try:
                    choice = input(f"Select title (1-{len(title_options)}) or Enter to skip: ").strip()
                    if not choice:
                        break
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(title_options):
                        selected_metadata.title = title_options[choice_num - 1][1].metadata.title
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(title_options)}")
                except ValueError:
                    print("Please enter a valid number or press Enter to skip")
        
        # Artist selection
        artist_options = [(i, source) for i, source in enumerate(self.sources, 1) if source.metadata.artist]
        if artist_options:
            print(f"\nArtist options:")
            for i, source in artist_options:
                print(f"  {i}. {source.metadata.artist} (from {source.source_name})")
            
            while True:
                try:
                    choice = input(f"Select artist (1-{len(artist_options)}) or Enter to skip: ").strip()
                    if not choice:
                        break
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(artist_options):
                        selected_metadata.artist = artist_options[choice_num - 1][1].metadata.artist
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(artist_options)}")
                except ValueError:
                    print("Please enter a valid number or press Enter to skip")
        
        # Album selection
        album_options = [(i, source) for i, source in enumerate(self.sources, 1) if source.metadata.album]
        if album_options:
            print(f"\nAlbum/Release options:")
            for i, source in album_options:
                print(f"  {i}. {source.metadata.album} (from {source.source_name})")
            
            while True:
                try:
                    choice = input(f"Select album (1-{len(album_options)}) or Enter to skip: ").strip()
                    if not choice:
                        break
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(album_options):
                        selected_metadata.album = album_options[choice_num - 1][1].metadata.album
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(album_options)}")
                except ValueError:
                    print("Please enter a valid number or press Enter to skip")
        
        # Year selection
        year_options = [(i, source) for i, source in enumerate(self.sources, 1) if source.metadata.year]
        if year_options:
            print(f"\nYear options:")
            for i, source in year_options:
                print(f"  {i}. {source.metadata.year} (from {source.source_name})")
            
            while True:
                try:
                    choice = input(f"Select year (1-{len(year_options)}) or Enter to skip: ").strip()
                    if not choice:
                        break
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(year_options):
                        selected_metadata.year = year_options[choice_num - 1][1].metadata.year
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(year_options)}")
                except ValueError:
                    print("Please enter a valid number or press Enter to skip")
        
        # Copy cover art from the first available source
        for source in self.sources:
            if source.metadata.cover_art_data:
                selected_metadata.cover_art_data = source.metadata.cover_art_data
                selected_metadata.cover_art_url = source.metadata.cover_art_url
                break
        
        # Set source as manual selection
        selected_metadata.source = "manual_selection"
        
        print(f"\nSelected metadata:")
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
    
    def apply_metadata_to_file(self, file_path) -> bool:
        """Apply the merged metadata to an audio file."""
        if not self.final_metadata:
            logger.error("No merged metadata available")
            return False
        
        try:
            # Try to import mutagen for metadata writing
            from mutagen import File as MutagenFile
            from mutagen.id3 import APIC, TIT2, TPE1, TALB, TYER, TCON, TRCK, ID3NoHeaderError
            
            # Convert to Path if it's a string
            if isinstance(file_path, str):
                file_path = Path(file_path)
            
            audio_file = MutagenFile(str(file_path))
            if audio_file is None:
                logger.error(f"Could not load audio file: {file_path}")
                return False
            
            file_ext = file_path.suffix.lower()
            
            # Handle MP3 files with ID3 tags differently
            if file_ext == '.mp3':
                try:
                    # Ensure ID3 tags exist
                    try:
                        audio_file.add_tags()
                    except:
                        pass  # Tags already exist
                    
                    # Use proper ID3 frames for MP3
                    if self.final_metadata.title:
                        audio_file.tags['TIT2'] = TIT2(encoding=3, text=self.final_metadata.title)
                    if self.final_metadata.artist:
                        audio_file.tags['TPE1'] = TPE1(encoding=3, text=self.final_metadata.artist)
                    if self.final_metadata.album:
                        audio_file.tags['TALB'] = TALB(encoding=3, text=self.final_metadata.album)
                    if self.final_metadata.year:
                        audio_file.tags['TYER'] = TYER(encoding=3, text=str(self.final_metadata.year))
                    if self.final_metadata.genre:
                        audio_file.tags['TCON'] = TCON(encoding=3, text=self.final_metadata.genre)
                    # Track number: format as "1/10" if total_tracks available, else just "1"
                    if self.final_metadata.track_number:
                        if self.final_metadata.total_tracks:
                            track_str = f"{self.final_metadata.track_number}/{self.final_metadata.total_tracks}"
                        else:
                            track_str = str(self.final_metadata.track_number)
                        audio_file.tags['TRCK'] = TRCK(encoding=3, text=track_str)
                except Exception as e:
                    logger.warning(f"Error setting ID3 tags: {e}")
                    # Fallback to simple assignment
                    if self.final_metadata.title:
                        audio_file['title'] = self.final_metadata.title
                    if self.final_metadata.artist:
                        audio_file['artist'] = self.final_metadata.artist
                    if self.final_metadata.album:
                        audio_file['album'] = self.final_metadata.album
                    if self.final_metadata.year:
                        audio_file['date'] = str(self.final_metadata.year)
                    if self.final_metadata.genre:
                        audio_file['genre'] = self.final_metadata.genre
                    # Track number: format as "1/10" if total_tracks available, else just "1"
                    if self.final_metadata.track_number:
                        if self.final_metadata.total_tracks:
                            track_str = f"{self.final_metadata.track_number}/{self.final_metadata.total_tracks}"
                        else:
                            track_str = str(self.final_metadata.track_number)
                        audio_file['TRCK'] = track_str
            else:
                # For other formats, use simple assignment
                if self.final_metadata.title:
                    audio_file['title'] = self.final_metadata.title
                if self.final_metadata.artist:
                    audio_file['artist'] = self.final_metadata.artist
                if self.final_metadata.album:
                    audio_file['album'] = self.final_metadata.album
                if self.final_metadata.year:
                    audio_file['date'] = str(self.final_metadata.year)
                if self.final_metadata.genre:
                    audio_file['genre'] = self.final_metadata.genre
                # Track number: format as "1/10" if total_tracks available, else just "1"
                if self.final_metadata.track_number:
                    if self.final_metadata.total_tracks:
                        track_str = f"{self.final_metadata.track_number}/{self.final_metadata.total_tracks}"
                    else:
                        track_str = str(self.final_metadata.track_number)
                    # Try common tag names for track number
                    audio_file['tracknumber'] = track_str
                    audio_file['TRCK'] = track_str
            
            # Apply cover art if available
            if self.final_metadata.cover_art_data:
                try:
                    # Determine MIME type from cover art data
                    mime_type = "image/jpeg"  # Default to JPEG
                    if self.final_metadata.cover_art_data.startswith(b'\xff\xd8\xff'):
                        mime_type = "image/jpeg"
                    elif self.final_metadata.cover_art_data.startswith(b'\x89PNG'):
                        mime_type = "image/png"
                    elif self.final_metadata.cover_art_data.startswith(b'GIF'):
                        mime_type = "image/gif"
                    elif self.final_metadata.cover_art_data.startswith(b'RIFF'):
                        mime_type = "image/webp"
                    
                    # Handle MP3 files with ID3 tags
                    if file_ext == '.mp3':
                        try:
                            # Ensure ID3 tags exist
                            try:
                                audio_file.add_tags()
                            except:
                                pass  # Tags already exist
                            
                            # Remove existing APIC frames to avoid duplicates
                            if 'APIC' in audio_file.tags:
                                del audio_file.tags['APIC']
                            
                            # Add the cover art
                            apic = APIC(
                                encoding=3,  # UTF-8
                                mime=mime_type,
                                type=3,  # Cover (front)
                                desc='Cover',
                                data=self.final_metadata.cover_art_data
                            )
                            audio_file.tags.add(apic)
                            
                            message = f"✓ Added cover art to {file_path.name} ({len(self.final_metadata.cover_art_data)} bytes)"
                            print(message)
                            logger.debug(f"Added cover art to {file_path} ({len(self.final_metadata.cover_art_data)} bytes)")
                            
                        except Exception as e:
                            message = f"⚠ Could not add cover art to MP3 file {file_path.name}: {e}"
                            print(message)
                            logger.warning(f"Could not add cover art to MP3 file {file_path}: {e}")
                    
                    # Handle other formats (M4A, OGG, FLAC, etc.)
                    else:
                        # For formats that support embedded pictures
                        if hasattr(audio_file, 'tags') and audio_file.tags is not None:
                            # Handle M4A/MP4 files
                            if file_ext in ['.m4a', '.mp4', '.m4p']:
                                try:
                                    from mutagen.mp4 import MP4Cover
                                    image_format = MP4Cover.FORMAT_JPEG if mime_type == 'image/jpeg' else MP4Cover.FORMAT_PNG
                                    cover = MP4Cover(self.final_metadata.cover_art_data, imageformat=image_format)
                                    audio_file.tags['covr'] = [cover]
                                    message = f"✓ Added cover art to {file_path.name} ({len(self.final_metadata.cover_art_data)} bytes)"
                                    print(message)
                                    logger.debug(f"Added cover art to {file_path} ({len(self.final_metadata.cover_art_data)} bytes)")
                                except Exception as e:
                                    message = f"⚠ Could not add cover art to M4A file {file_path.name}: {e}"
                                    print(message)
                                    logger.warning(f"Could not add cover art to M4A file {file_path}: {e}")
                            
                            # Handle FLAC files
                            elif file_ext == '.flac':
                                try:
                                    from mutagen.flac import FLAC, Picture
                                    flac_file = FLAC(str(file_path))
                                    picture = Picture()
                                    picture.data = self.final_metadata.cover_art_data
                                    picture.type = 3  # Cover (front)
                                    picture.mime = mime_type
                                    flac_file.add_picture(picture)
                                    flac_file.save()
                                    message = f"✓ Added cover art to {file_path.name} ({len(self.final_metadata.cover_art_data)} bytes)"
                                    print(message)
                                    logger.debug(f"Added cover art to {file_path} ({len(self.final_metadata.cover_art_data)} bytes)")
                                except Exception as e:
                                    message = f"⚠ Could not add cover art to FLAC file {file_path.name}: {e}"
                                    print(message)
                                    logger.warning(f"Could not add cover art to FLAC file {file_path}: {e}")
                            
                            # Handle OGG files
                            elif file_ext in ['.ogg', '.oga']:
                                try:
                                    from mutagen.flac import Picture
                                    picture = Picture()
                                    picture.data = self.final_metadata.cover_art_data
                                    picture.type = 3  # Cover (front)
                                    picture.mime = mime_type
                                    if hasattr(audio_file.tags, 'add_picture'):
                                        audio_file.tags.add_picture(picture)
                                    else:
                                        # Alternative method for OGG
                                        import base64
                                        picture_data = base64.b64encode(self.final_metadata.cover_art_data).decode('ascii')
                                        audio_file.tags['metadata_block_picture'] = [picture_data]
                                    message = f"✓ Added cover art to {file_path.name} ({len(self.final_metadata.cover_art_data)} bytes)"
                                    print(message)
                                    logger.debug(f"Added cover art to {file_path} ({len(self.final_metadata.cover_art_data)} bytes)")
                                except Exception as e:
                                    message = f"⚠ Could not add cover art to OGG file {file_path.name}: {e}"
                                    print(message)
                                    logger.warning(f"Could not add cover art to OGG file {file_path}: {e}")
                            
                            # Fallback: try generic picture tag
                            else:
                                try:
                                    audio_file['picture'] = self.final_metadata.cover_art_data
                                    message = f"✓ Added cover art to {file_path.name} ({len(self.final_metadata.cover_art_data)} bytes)"
                                    print(message)
                                    logger.debug(f"Added cover art to {file_path} ({len(self.final_metadata.cover_art_data)} bytes)")
                                except Exception as e:
                                    message = f"⚠ Could not add cover art using generic method for {file_ext}: {e}"
                                    print(message)
                                    logger.warning(f"Could not add cover art using generic method for {file_ext}: {e}")
                        else:
                            message = f"⚠ Audio file {file_path.name} does not support tags"
                            print(message)
                            logger.warning(f"Audio file {file_path} does not support tags")
                        
                except Exception as e:
                    message = f"⚠ Could not add cover art to {file_path.name}: {e}"
                    print(message)
                    logger.warning(f"Could not add cover art to {file_path}: {e}")
            
            # Save the file (this will save metadata changes)
            audio_file.save()
            message = f"✓ Applied metadata to {file_path.name}"
            print(message)
            logger.debug(f"Applied metadata to {file_path}")
            return True
            
        except ImportError:
            logger.error("mutagen library not available. Install with: pip install mutagen")
            return False
        except Exception as e:
            logger.error(f"Error applying metadata to {file_path}: {e}")
            return False
