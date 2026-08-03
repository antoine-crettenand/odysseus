"""Coverage for enriched catalog metadata and format-specific tag mappings."""

from pathlib import Path
from unittest.mock import MagicMock

from mutagen.id3 import ID3

from odysseus.clients.discogs import DiscogsClient
from odysseus.clients.musicbrainz import MusicBrainzClient
from odysseus.clients.spotify import SpotifyClient
from odysseus.domain.music.metadata.metadata_service import MetadataService
from odysseus.models.releases import ReleaseInfo, Track
from odysseus.models.song import AudioMetadata
from odysseus.utils.metadata_appliers import (
    FLACMetadataApplier,
    M4AMetadataApplier,
    MP3MetadataApplier,
)


class _CaptureMerger:
    def __init__(self):
        self.final_metadata = None

    def set_final_metadata(self, metadata):
        self.final_metadata = metadata

    def apply_metadata_to_file(self, _path, quiet=False):
        return True


class _FakeID3Audio:
    def __init__(self):
        self.tags = ID3()

    def add_tags(self):
        if self.tags is None:
            self.tags = ID3()


class _FakeMP4Audio:
    def __init__(self):
        self.tags = {}

    def add_tags(self):
        self.tags = {}


def _enriched_metadata():
    return AudioMetadata(
        title="Track",
        artist="Artist",
        album="Album",
        album_artist="Album Artist",
        track_number=2,
        total_tracks=7,
        disc_number=2,
        total_discs=3,
        year=1971,
        release_date="1985-03-04",
        original_release_date="1971-10-30",
        genre="Rock",
        publisher="Harvest",
        copyright="℗ 1971 Example Records",
        isrc="GBABC7100001",
        catalog_number="SHVL 795",
        barcode="077774603425",
        release_type="Album",
        release_status="Official",
        release_country="GB",
        media_format='12" Vinyl',
        source_url="https://musicbrainz.org/release/release-id",
        release_id="release-id",
        recording_id="recording-id",
        compilation=False,
        source="musicbrainz",
    )


def test_metadata_service_preserves_retrieved_track_and_edition_fields():
    merger = _CaptureMerger()
    service = MetadataService(
        merger=merger,
        cover_art_fetcher=MagicMock(),
    )
    track = Track(
        position=9,
        title="Track",
        artist="Guest Artist",
        mbid="recording-id",
        isrc="GBABC7100001",
        disc_number=2,
        disc_track_number=2,
        disc_total_tracks=7,
    )
    release = ReleaseInfo(
        title="Album",
        artist="Album Artist",
        release_date="1985-03-04",
        original_release_date="1971-10-30",
        genre="Rock",
        release_type="Album",
        release_status="Official",
        country="GB",
        label="Harvest",
        catalog_number="SHVL 795",
        barcode="077774603425",
        media_format='12" Vinyl',
        mbid="release-id",
        url="https://musicbrainz.org/release/release-id",
        tracks=[track],
        copyright="℗ 1971 Example Records",
        total_discs=3,
        source="musicbrainz",
    )

    service.apply_metadata_with_cover_art(
        Path("track.mp3"),
        track,
        release,
        cover_art_data=b"cover",
    )

    metadata = merger.final_metadata
    assert metadata.track_number == 2
    assert metadata.total_tracks == 7
    assert metadata.disc_number == 2
    assert metadata.total_discs == 3
    assert metadata.isrc == "GBABC7100001"
    assert metadata.publisher == "Harvest"
    assert metadata.catalog_number == "SHVL 795"
    assert metadata.barcode == "077774603425"
    assert metadata.release_id == "release-id"
    assert metadata.recording_id == "recording-id"
    assert metadata.original_release_date == "1971-10-30"

    split_metadata = service.prepare_track_metadata_list(
        [{"track": track}], release
    )[0]
    assert split_metadata["track_number"] == 9
    assert split_metadata["disc_track_number"] == 2


def test_mp3_writes_standard_and_musicbrainz_extended_tags():
    audio = _FakeID3Audio()

    MP3MetadataApplier(_enriched_metadata()).apply_tags(audio)

    assert str(audio.tags["TDRC"]) == "1971-10-30"
    assert str(audio.tags["TRCK"]) == "2/7"
    assert str(audio.tags["TPOS"]) == "2/3"
    assert str(audio.tags["TSRC"]) == "GBABC7100001"
    assert str(audio.tags["TPUB"]) == "Harvest"
    assert str(audio.tags["TCOP"]) == "℗ 1971 Example Records"
    user_text = {frame.desc: str(frame) for frame in audio.tags.getall("TXXX")}
    assert user_text["MusicBrainz Album Id"] == "release-id"
    assert user_text["MusicBrainz Track Id"] == "recording-id"
    assert user_text["CATALOGNUMBER"] == "SHVL 795"
    assert user_text["BARCODE"] == "077774603425"


def test_m4a_writes_disc_isrc_copyright_and_freeform_identifiers():
    audio = _FakeMP4Audio()

    M4AMetadataApplier(_enriched_metadata()).apply_tags(audio)

    assert audio.tags["\xa9day"] == ["1971-10-30"]
    assert audio.tags["trkn"] == [(2, 7)]
    assert audio.tags["disk"] == [(2, 3)]
    assert audio.tags["cprt"] == ["℗ 1971 Example Records"]
    assert audio.tags["----:com.apple.iTunes:ISRC"] == [b"GBABC7100001"]
    assert audio.tags[
        "----:com.apple.iTunes:MusicBrainz Album Id"
    ] == [b"release-id"]
    assert audio.tags["----:com.apple.iTunes:BARCODE"] == [
        b"077774603425"
    ]


def test_flac_writes_separate_track_disc_and_catalog_fields():
    audio = {}

    FLACMetadataApplier(_enriched_metadata()).apply_tags(audio)

    assert audio["date"] == "1971-10-30"
    assert audio["tracknumber"] == "2"
    assert audio["tracktotal"] == "7"
    assert audio["discnumber"] == "2"
    assert audio["disctotal"] == "3"
    assert audio["isrc"] == "GBABC7100001"
    assert audio["publisher"] == "Harvest"
    assert audio["catalognumber"] == "SHVL 795"
    assert audio["barcode"] == "077774603425"
    assert audio["musicbrainz_albumid"] == "release-id"
    assert audio["musicbrainz_trackid"] == "recording-id"


def test_musicbrainz_keeps_global_selection_and_per_disc_tag_numbers():
    client = MusicBrainzClient.__new__(MusicBrainzClient)
    release = client._parse_release_info(
        {
            "id": "release-id",
            "title": "Double Album",
            "artist-credit": [{"name": "Artist"}],
            "release-group": {"primary-type": "Album"},
            "media": [
                {
                    "position": 1,
                    "tracks": [
                        {
                            "position": 1,
                            "recording": {
                                "id": "recording-1",
                                "title": "Disc One Track",
                                "isrcs": ["ISRC0001"],
                            },
                        }
                    ],
                },
                {
                    "position": 2,
                    "tracks": [
                        {
                            "position": 1,
                            "recording": {
                                "id": "recording-2",
                                "title": "Disc Two Track",
                                "isrcs": ["ISRC0002"],
                            },
                        }
                    ],
                },
            ],
        }
    )

    assert release.total_discs == 2
    assert [track.position for track in release.tracks] == [1, 2]
    assert [track.disc_number for track in release.tracks] == [1, 2]
    assert [track.disc_track_number for track in release.tracks] == [1, 1]
    assert [track.disc_total_tracks for track in release.tracks] == [1, 1]


def test_discogs_details_retain_available_edition_identifiers():
    client = DiscogsClient.__new__(DiscogsClient)
    release = client._parse_release_info(
        {
            "id": 123,
            "title": "Album",
            "year": 1971,
            "country": "UK",
            "status": "Accepted",
            "artists": [{"name": "Artist"}],
            "genres": ["Rock"],
            "labels": [{"name": "Harvest", "catno": "SHVL 795"}],
            "identifiers": [{"type": "Barcode", "value": "077774603425"}],
            "formats": [
                {"name": "Vinyl", "qty": "2", "descriptions": ["Album"]}
            ],
            "tracklist": [],
        }
    )

    assert release.label == "Harvest"
    assert release.catalog_number == "SHVL 795"
    assert release.barcode == "077774603425"
    assert release.country == "UK"
    assert release.media_format == "Vinyl"
    assert release.total_discs == 2
    assert release.source == "discogs"


def test_spotify_track_id_is_not_misrepresented_as_musicbrainz_id():
    client = SpotifyClient.__new__(SpotifyClient)

    track = client._build_track_from_data(
        {
            "id": "spotify-track-id",
            "name": "Track",
            "track_number": 3,
            "disc_number": 2,
            "duration_ms": 180000,
            "artists": [{"name": "Artist"}],
            "external_ids": {"isrc": "GBABC7100001"},
        },
        "Artist",
        position=10,
    )

    assert track.position == 10
    assert track.disc_track_number == 3
    assert track.disc_number == 2
    assert track.isrc == "GBABC7100001"
    assert track.source_id == "spotify-track-id"
    assert track.mbid is None
