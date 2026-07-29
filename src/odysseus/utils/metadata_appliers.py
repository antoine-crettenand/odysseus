"""
Format-specific metadata appliers for audio files.
Consolidates format-specific metadata application logic.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
import logging
from ..models.song import AudioMetadata

logger = logging.getLogger(__name__)


class FormatMetadataApplier(ABC):
    """Base class for format-specific metadata appliers."""

    def __init__(self, metadata: AudioMetadata):
        self.metadata = metadata

    @abstractmethod
    def apply_tags(self, audio_file) -> None:
        pass

    @abstractmethod
    def apply_cover_art(self, audio_file, file_path: Path, mime_type: str, quiet: bool) -> None:
        pass

    @abstractmethod
    def save(self, audio_file, file_path: Path) -> None:
        pass

    def _format_track_number(self) -> str:
        if self.metadata.track_number:
            return f"{self.metadata.track_number}/{self.metadata.total_tracks}" if self.metadata.total_tracks else str(self.metadata.track_number)
        return ""

    def _apply_common_tags(self, audio_file) -> None:
        """Apply common tags shared by most formats."""
        if self.metadata.title:
            audio_file['title'] = self.metadata.title
        if self.metadata.artist:
            audio_file['artist'] = self.metadata.artist
        if self.metadata.album_artist:
            audio_file['albumartist'] = self.metadata.album_artist
        if self.metadata.album:
            audio_file['album'] = self.metadata.album
        if self.metadata.year:
            audio_file['date'] = str(self.metadata.year)
        if self.metadata.genre:
            audio_file['genre'] = self.metadata.genre
        if self.metadata.track_number:
            track_str = self._format_track_number()
            audio_file['tracknumber'] = track_str
            audio_file['TRCK'] = track_str
        if self.metadata.compilation is not None:
            audio_file['compilation'] = "1" if self.metadata.compilation else "0"
            audio_file['TCMP'] = "1" if self.metadata.compilation else "0"

    @staticmethod
    def _detect_mime_type(cover_art_data: bytes) -> str:
        if cover_art_data.startswith(b'\xff\xd8\xff'):
            return "image/jpeg"
        elif cover_art_data.startswith(b'\x89PNG'):
            return "image/png"
        elif cover_art_data.startswith(b'GIF'):
            return "image/gif"
        elif cover_art_data.startswith(b'RIFF'):
            return "image/webp"
        return "image/jpeg"


class MP3MetadataApplier(FormatMetadataApplier):
    def apply_tags(self, audio_file) -> None:
        from mutagen.id3 import TIT2, TPE1, TPE2, TALB, TYER, TCON, TRCK, TCMP
        try:
            try:
                audio_file.add_tags()
            except:
                pass
            if self.metadata.title:
                audio_file.tags['TIT2'] = TIT2(encoding=3, text=self.metadata.title)
            if self.metadata.artist:
                audio_file.tags['TPE1'] = TPE1(encoding=3, text=self.metadata.artist)
            if self.metadata.album_artist:
                audio_file.tags['TPE2'] = TPE2(encoding=3, text=self.metadata.album_artist)
            if self.metadata.album:
                audio_file.tags['TALB'] = TALB(encoding=3, text=self.metadata.album)
            if self.metadata.year:
                audio_file.tags['TYER'] = TYER(encoding=3, text=str(self.metadata.year))
            if self.metadata.genre:
                audio_file.tags['TCON'] = TCON(encoding=3, text=self.metadata.genre)
            if self.metadata.track_number:
                audio_file.tags['TRCK'] = TRCK(encoding=3, text=self._format_track_number())
            if self.metadata.compilation is not None:
                audio_file.tags['TCMP'] = TCMP(encoding=3, text="1" if self.metadata.compilation else "0")
        except Exception as e:
            logger.warning(f"Error setting ID3 tags: {e}")
            self._apply_fallback(audio_file)

    def _apply_fallback(self, audio_file) -> None:
        self._apply_common_tags(audio_file)
        if self.metadata.album_artist:
            audio_file['TPE2'] = self.metadata.album_artist

    def apply_cover_art(self, audio_file, file_path: Path, mime_type: str, quiet: bool) -> None:
        from mutagen.id3 import APIC
        try:
            try:
                audio_file.add_tags()
            except:
                pass
            if audio_file.tags:
                while True:
                    keys_to_remove = [k for k in audio_file.tags.keys() if k.startswith('APIC') or 'PIC' in k or 'picture' in k.lower()]
                    if not keys_to_remove:
                        break
                    for k in keys_to_remove:
                        try:
                            del audio_file.tags[k]
                        except:
                            pass
                audio_file.tags.add(APIC(encoding=0, mime=mime_type, type=3, desc='Cover', data=self.metadata.cover_art_data))
                if not quiet:
                    print(f"✓ Added cover art to {file_path.name} ({len(self.metadata.cover_art_data)} bytes, {mime_type})")
        except Exception as e:
            if not quiet:
                print(f"⚠ Could not add cover art to MP3 file {file_path.name}: {e}")
            logger.warning(f"Could not add cover art to MP3 file {file_path}: {e}", exc_info=True)

    def save(self, audio_file, file_path: Path) -> None:
        if hasattr(audio_file, 'tags') and audio_file.tags is not None:
            try:
                audio_file.tags.save(str(file_path), v2_version=3)
            except:
                audio_file.save()
        else:
            audio_file.save()


class M4AMetadataApplier(FormatMetadataApplier):
    def apply_tags(self, audio_file) -> None:
        if audio_file.tags is None:
            audio_file.add_tags()
        tags = audio_file.tags
        if self.metadata.title:
            tags['\xa9nam'] = [self.metadata.title]
        if self.metadata.artist:
            tags['\xa9ART'] = [self.metadata.artist]
        if self.metadata.album_artist:
            tags['aART'] = [self.metadata.album_artist]
        if self.metadata.album:
            tags['\xa9alb'] = [self.metadata.album]
        if self.metadata.year:
            tags['\xa9day'] = [str(self.metadata.year)]
        if self.metadata.genre:
            tags['\xa9gen'] = [self.metadata.genre]
        if self.metadata.track_number:
            tags['trkn'] = [
                (self.metadata.track_number, self.metadata.total_tracks or 0)
            ]
        if self.metadata.compilation is not None:
            tags['cpil'] = self.metadata.compilation

    def apply_cover_art(self, audio_file, file_path: Path, mime_type: str, quiet: bool) -> None:
        try:
            from mutagen.mp4 import MP4Cover
            audio_file.tags['covr'] = [MP4Cover(self.metadata.cover_art_data, imageformat=MP4Cover.FORMAT_JPEG if mime_type == 'image/jpeg' else MP4Cover.FORMAT_PNG)]
            if not quiet:
                print(f"✓ Added cover art to {file_path.name} ({len(self.metadata.cover_art_data)} bytes)")
        except Exception as e:
            if not quiet:
                print(f"⚠ Could not add cover art to M4A file {file_path.name}: {e}")
            logger.warning(f"Could not add cover art to M4A file {file_path}: {e}")

    def save(self, audio_file, file_path: Path) -> None:
        audio_file.save()


class FLACMetadataApplier(FormatMetadataApplier):
    def apply_tags(self, audio_file) -> None:
        self._apply_common_tags(audio_file)

    def apply_cover_art(self, audio_file, file_path: Path, mime_type: str, quiet: bool) -> None:
        try:
            from mutagen.flac import Picture
            picture = Picture()
            picture.data, picture.type, picture.mime = self.metadata.cover_art_data, 3, mime_type
            audio_file.clear_pictures()
            audio_file.add_picture(picture)
            audio_file.save()
            if not quiet:
                print(f"✓ Added cover art to {file_path.name} ({len(self.metadata.cover_art_data)} bytes)")
        except Exception as e:
            if not quiet:
                print(f"⚠ Could not add cover art to FLAC file {file_path.name}: {e}")
            logger.warning(f"Could not add cover art to FLAC file {file_path}: {e}")

    def save(self, audio_file, file_path: Path) -> None:
        audio_file.save()


class OGGMetadataApplier(FormatMetadataApplier):
    def apply_tags(self, audio_file) -> None:
        self._apply_common_tags(audio_file)

    def apply_cover_art(self, audio_file, file_path: Path, mime_type: str, quiet: bool) -> None:
        try:
            from mutagen.flac import Picture
            import base64
            picture = Picture()
            picture.data, picture.type, picture.mime = self.metadata.cover_art_data, 3, mime_type
            if hasattr(audio_file.tags, 'add_picture'):
                audio_file.tags.add_picture(picture)
            else:
                encoded_picture = base64.b64encode(picture.write()).decode('ascii')
                audio_file.tags['metadata_block_picture'] = [encoded_picture]
            if not quiet:
                print(f"✓ Added cover art to {file_path.name} ({len(self.metadata.cover_art_data)} bytes)")
        except Exception as e:
            if not quiet:
                print(f"⚠ Could not add cover art to OGG file {file_path.name}: {e}")
            logger.warning(f"Could not add cover art to OGG file {file_path}: {e}")

    def save(self, audio_file, file_path: Path) -> None:
        audio_file.save()


class GenericMetadataApplier(FormatMetadataApplier):
    def apply_tags(self, audio_file) -> None:
        self._apply_common_tags(audio_file)
        if self.metadata.track_number:
            audio_file['tracknumber'] = self._format_track_number()

    def apply_cover_art(self, audio_file, file_path: Path, mime_type: str, quiet: bool) -> None:
        try:
            audio_file['picture'] = self.metadata.cover_art_data
            if not quiet:
                print(f"✓ Added cover art to {file_path.name} ({len(self.metadata.cover_art_data)} bytes)")
        except Exception as e:
            if not quiet:
                print(f"⚠ Could not add cover art using generic method: {e}")
            logger.warning(f"Could not add cover art using generic method: {e}")

    def save(self, audio_file, file_path: Path) -> None:
        audio_file.save()


def get_metadata_applier(file_ext: str, metadata: AudioMetadata) -> FormatMetadataApplier:
    file_ext_lower = file_ext.lower()
    if file_ext_lower == '.mp3':
        return MP3MetadataApplier(metadata)
    elif file_ext_lower in ['.m4a', '.mp4', '.m4p']:
        return M4AMetadataApplier(metadata)
    elif file_ext_lower == '.flac':
        return FLACMetadataApplier(metadata)
    elif file_ext_lower in ['.ogg', '.oga']:
        return OGGMetadataApplier(metadata)
    else:
        return GenericMetadataApplier(metadata)
