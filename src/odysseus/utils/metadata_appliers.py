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

SUPPORTED_METADATA_EXTENSIONS = frozenset({
    '.mp3',
    '.m4a',
    '.mp4',
    '.m4p',
    '.flac',
    '.ogg',
    '.oga',
    '.opus',
    '.wav',
})


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

    def _format_disc_number(self) -> str:
        if self.metadata.disc_number:
            return f"{self.metadata.disc_number}/{self.metadata.total_discs}" if self.metadata.total_discs else str(self.metadata.disc_number)
        return ""

    def _date_value(self) -> Optional[str]:
        return (
            self.metadata.original_release_date
            or self.metadata.release_date
            or (str(self.metadata.year) if self.metadata.year else None)
        )

    def _extended_tag_values(self) -> dict:
        """Return portable names for edition and provider identifiers."""
        values = {
            "ORIGINALDATE": self.metadata.original_release_date,
            "RELEASEDATE": self.metadata.release_date,
            "CATALOGNUMBER": self.metadata.catalog_number,
            "BARCODE": self.metadata.barcode,
            "RELEASETYPE": self.metadata.release_type,
            "RELEASESTATUS": self.metadata.release_status,
            "RELEASECOUNTRY": self.metadata.release_country,
            "MEDIA": self.metadata.media_format,
            "SOURCEURL": self.metadata.source_url,
            "METADATA_SOURCE": (
                self.metadata.source
                if self.metadata.source and self.metadata.source != "unknown"
                else None
            ),
        }
        source = (self.metadata.source or "").casefold()
        if source == "musicbrainz":
            values["MUSICBRAINZ_ALBUMID"] = self.metadata.release_id
            values["MUSICBRAINZ_TRACKID"] = self.metadata.recording_id
        elif source == "discogs":
            values["DISCOGS_RELEASE_ID"] = self.metadata.release_id
        elif source == "spotify":
            release_type = (self.metadata.release_type or "").casefold()
            if release_type == "playlist":
                values["SPOTIFY_PLAYLIST_ID"] = self.metadata.release_id
            elif release_type == "track":
                values["SPOTIFY_TRACK_ID"] = self.metadata.release_id
            else:
                values["SPOTIFY_ALBUM_ID"] = self.metadata.release_id
            if self.metadata.recording_id:
                values["SPOTIFY_TRACK_ID"] = self.metadata.recording_id
        elif source == "applemusic":
            values["APPLE_MUSIC_ALBUM_ID"] = self.metadata.release_id
        return {key: value for key, value in values.items() if value}

    @staticmethod
    def _friendly_tag_description(name: str) -> str:
        """Use the established Picard names for MusicBrainz freeform tags."""
        return {
            "MUSICBRAINZ_ALBUMID": "MusicBrainz Album Id",
            "MUSICBRAINZ_TRACKID": "MusicBrainz Track Id",
        }.get(name, name)

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
        date_value = self._date_value()
        if date_value:
            audio_file['date'] = date_value
        if self.metadata.genre:
            audio_file['genre'] = self.metadata.genre
        if self.metadata.track_number:
            audio_file['tracknumber'] = str(self.metadata.track_number)
            audio_file['TRCK'] = self._format_track_number()
        if self.metadata.total_tracks:
            audio_file['tracktotal'] = str(self.metadata.total_tracks)
            audio_file['totaltracks'] = str(self.metadata.total_tracks)
        if self.metadata.disc_number:
            audio_file['discnumber'] = str(self.metadata.disc_number)
        if self.metadata.total_discs:
            audio_file['disctotal'] = str(self.metadata.total_discs)
            audio_file['totaldiscs'] = str(self.metadata.total_discs)
        if self.metadata.compilation is not None:
            audio_file['compilation'] = "1" if self.metadata.compilation else "0"
            audio_file['TCMP'] = "1" if self.metadata.compilation else "0"
        common_values = {
            'comment': self.metadata.comment,
            'composer': self.metadata.composer,
            'conductor': self.metadata.conductor,
            'performer': self.metadata.performer,
            'publisher': self.metadata.publisher,
            'label': self.metadata.publisher,
            'copyright': self.metadata.copyright,
            'isrc': self.metadata.isrc,
            'bpm': self.metadata.bpm,
            'initialkey': self.metadata.key,
            'mood': self.metadata.mood,
        }
        for key, value in common_values.items():
            if value is not None:
                audio_file[key] = str(value)
        for key, value in self._extended_tag_values().items():
            audio_file[key.lower()] = str(value)

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
        from mutagen.id3 import (
            COMM,
            TALB,
            TBPM,
            TCOM,
            TCON,
            TCOP,
            TDRC,
            TIT2,
            TKEY,
            TMOO,
            TPE1,
            TPE2,
            TPE3,
            TPOS,
            TPUB,
            TRCK,
            TSRC,
            TCMP,
            TXXX,
        )
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
            date_value = self._date_value()
            if date_value:
                audio_file.tags['TDRC'] = TDRC(encoding=3, text=date_value)
            if self.metadata.genre:
                audio_file.tags['TCON'] = TCON(encoding=3, text=self.metadata.genre)
            if self.metadata.track_number:
                audio_file.tags['TRCK'] = TRCK(encoding=3, text=self._format_track_number())
            if self.metadata.disc_number:
                audio_file.tags['TPOS'] = TPOS(encoding=3, text=self._format_disc_number())
            if self.metadata.compilation is not None:
                audio_file.tags['TCMP'] = TCMP(encoding=3, text="1" if self.metadata.compilation else "0")
            if self.metadata.comment:
                audio_file.tags['COMM::eng'] = COMM(
                    encoding=3, lang='eng', desc='', text=self.metadata.comment
                )
            if self.metadata.composer:
                audio_file.tags['TCOM'] = TCOM(encoding=3, text=self.metadata.composer)
            if self.metadata.conductor:
                audio_file.tags['TPE3'] = TPE3(encoding=3, text=self.metadata.conductor)
            if self.metadata.publisher:
                audio_file.tags['TPUB'] = TPUB(encoding=3, text=self.metadata.publisher)
            if self.metadata.copyright:
                audio_file.tags['TCOP'] = TCOP(encoding=3, text=self.metadata.copyright)
            if self.metadata.isrc:
                audio_file.tags['TSRC'] = TSRC(encoding=3, text=self.metadata.isrc)
            if self.metadata.bpm:
                audio_file.tags['TBPM'] = TBPM(encoding=3, text=str(self.metadata.bpm))
            if self.metadata.key:
                audio_file.tags['TKEY'] = TKEY(encoding=3, text=self.metadata.key)
            if self.metadata.mood:
                audio_file.tags['TMOO'] = TMOO(encoding=3, text=self.metadata.mood)
            if self.metadata.performer:
                audio_file.tags.add(
                    TXXX(
                        encoding=3,
                        desc='PERFORMER',
                        text=self.metadata.performer,
                    )
                )
            for description, value in self._extended_tag_values().items():
                audio_file.tags.add(
                    TXXX(
                        encoding=3,
                        desc=self._friendly_tag_description(description),
                        text=str(value),
                    )
                )
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
        date_value = self._date_value()
        if date_value:
            tags['\xa9day'] = [date_value]
        if self.metadata.genre:
            tags['\xa9gen'] = [self.metadata.genre]
        if self.metadata.track_number:
            tags['trkn'] = [
                (self.metadata.track_number, self.metadata.total_tracks or 0)
            ]
        if self.metadata.disc_number:
            tags['disk'] = [
                (self.metadata.disc_number, self.metadata.total_discs or 0)
            ]
        if self.metadata.compilation is not None:
            tags['cpil'] = self.metadata.compilation
        if self.metadata.comment:
            tags['\xa9cmt'] = [self.metadata.comment]
        if self.metadata.composer:
            tags['\xa9wrt'] = [self.metadata.composer]
        if self.metadata.copyright:
            tags['cprt'] = [self.metadata.copyright]
        if self.metadata.bpm:
            tags['tmpo'] = [self.metadata.bpm]
        freeform_values = {
            'ISRC': self.metadata.isrc,
            'LABEL': self.metadata.publisher,
            'CONDUCTOR': self.metadata.conductor,
            'PERFORMER': self.metadata.performer,
            'INITIALKEY': self.metadata.key,
            'MOOD': self.metadata.mood,
            **self._extended_tag_values(),
        }
        for description, value in freeform_values.items():
            if value is not None:
                friendly_description = self._friendly_tag_description(
                    description
                )
                tags[f'----:com.apple.iTunes:{friendly_description}'] = [
                    str(value).encode('utf-8')
                ]

    def apply_cover_art(self, audio_file, file_path: Path, mime_type: str, quiet: bool) -> None:
        try:
            from mutagen.mp4 import MP4Cover
            image_formats = {
                'image/jpeg': MP4Cover.FORMAT_JPEG,
                'image/png': MP4Cover.FORMAT_PNG,
            }
            image_format = image_formats.get(mime_type)
            if image_format is None:
                if not quiet:
                    print(
                        f"⚠ Could not add {mime_type} cover art to "
                        f"{file_path.name}; M4A supports JPEG and PNG"
                    )
                logger.warning(
                    "Skipping unsupported M4A cover-art type %s for %s",
                    mime_type,
                    file_path,
                )
                return
            audio_file.tags['covr'] = [
                MP4Cover(self.metadata.cover_art_data, imageformat=image_format)
            ]
            if not quiet:
                print(f"✓ Added cover art to {file_path.name} ({len(self.metadata.cover_art_data)} bytes)")
        except Exception as e:
            if not quiet:
                print(f"⚠ Could not add cover art to M4A file {file_path.name}: {e}")
            logger.warning(f"Could not add cover art to M4A file {file_path}: {e}")

    def save(self, audio_file, file_path: Path) -> None:
        audio_file.save()


class WAVMetadataApplier(MP3MetadataApplier):
    """Apply ID3 metadata through Mutagen's WAVE container support."""

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
    elif file_ext_lower in ['.ogg', '.oga', '.opus']:
        return OGGMetadataApplier(metadata)
    elif file_ext_lower == '.wav':
        return WAVMetadataApplier(metadata)
    else:
        return GenericMetadataApplier(metadata)
