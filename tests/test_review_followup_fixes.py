"""Regression coverage for the two code-review passes."""

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from mutagen.flac import Picture
from mutagen.mp4 import MP4Cover

from odysseus.clients.discogs import DiscogsClient
from odysseus.clients.download_strategies import DownloadStrategies, STRATEGIES
from odysseus.domain.media.cover_art.fetcher import CoverArtFetcher
from odysseus.domain.music.metadata.duration_recovery import (
    DurationRecoveryService,
)
from odysseus.domain.music.search.deduplicator import ResultDeduplicator
from odysseus.domain.music.search.search_service import SearchService
from odysseus.models.outcomes import OperationOutcome
from odysseus.models.releases import ReleaseInfo, Track
from odysseus.models.search_results import MusicBrainzSong
from odysseus.models.song import AudioMetadata, SongData
from odysseus.ui.cli import OdysseusCLI
from odysseus.ui.handlers.metadata_handler import MetadataHandler
from odysseus.utils.metadata_appliers import (
    M4AMetadataApplier,
    OGGMetadataApplier,
    SUPPORTED_METADATA_EXTENSIONS,
    WAVMetadataApplier,
    get_metadata_applier,
)


def _release(album, release_type="Album", source="musicbrainz", mbid="id"):
    return MusicBrainzSong(
        title=album,
        artist="Artist",
        album=album,
        release_type=release_type,
        mbid=mbid,
        source=source,
    )


def _search_service(mb_results, *, spotify_results=None, max_results=3):
    service = SearchService.__new__(SearchService)
    service.musicbrainz_client = MagicMock(max_results=max_results)
    service.musicbrainz_client.search_release.return_value = mb_results
    service.discogs_client = MagicMock()
    service.discogs_client.search_release.return_value = []
    service._spotify_client = None
    if spotify_results is not None:
        service._spotify_client = MagicMock()
        service._spotify_client.is_authenticated.return_value = True
        service._spotify_client.search_release.return_value = spotify_results
    service.deduplicator = ResultDeduplicator()
    return service


def test_download_strategies_keep_certificate_verification_enabled():
    strategies = DownloadStrategies(MagicMock())

    command = strategies.build_strategy(
        STRATEGIES[0],
        "https://example.test/video",
        "best",
        True,
        "%(title)s.%(ext)s",
    )

    assert "--no-check-certificate" not in command


def test_discogs_details_use_artist_fields_and_preserve_hyphenated_title():
    client = DiscogsClient.__new__(DiscogsClient)

    release = client._parse_release_info(
        {
            "id": 123,
            "title": "Part One - Part Two",
            "year": 2020,
            "artists": [
                {"name": "First Artist", "join": "&"},
                {"name": "Second Artist"},
            ],
            "formats": [{"name": "CD", "descriptions": ["Album"]}],
            "tracklist": [],
        }
    )

    assert release.title == "Part One - Part Two"
    assert release.artist == "First Artist & Second Artist"


def test_release_search_applies_default_limit():
    service = _search_service(
        [_release(f"Album {index}", mbid=str(index)) for index in range(9)]
    )

    results = service.search_releases(
        SongData(title="", artist="Artist", album="Album")
    )

    assert len(results) == 3


def test_release_type_is_filtered_before_provider_deduplication():
    ep = _release("Shared Title", release_type="EP", mbid="ep")
    service = _search_service(
        [ep],
        spotify_results=[
            {
                "album": "Shared Title",
                "artist": "Artist",
                "release_type": "album",
                "spotify_id": "wrong-type",
            }
        ],
    )

    results = service.search_releases(
        SongData(title="", artist="Artist", album="Shared Title"),
        release_type="EP",
    )

    assert [result.mbid for result in results] == ["ep"]
    assert service.musicbrainz_client.search_release.call_args.args[3] == "EP"


def test_metadata_handler_uses_plural_release_search(tmp_path):
    audio_file = tmp_path / "track.mp3"
    audio_file.touch()
    handler = MetadataHandler.__new__(MetadataHandler)
    handler.search_service = MagicMock()
    handler.search_service.search_releases.return_value = []
    handler.display_manager = MagicMock()
    handler.display_manager.show_loading_spinner.side_effect = (
        lambda _message, function, *args, **kwargs: function(*args, **kwargs)
    )

    outcome = handler.handle(
        str(audio_file),
        artist="Artist",
        album="Album",
    )

    assert outcome.succeeded is False
    handler.search_service.search_releases.assert_called_once()
    handler.search_service.search_release.assert_not_called()


@pytest.mark.parametrize(
    ("arguments", "handler_name"),
    [
        (
            ["recording", "--title", "Track", "--artist", "Artist"],
            "recording_handler",
        ),
        (
            ["discography", "--artist", "Artist"],
            "discography_handler",
        ),
        (
            ["spotify", "--url", "https://open.spotify.com/album/id"],
            "spotify_handler",
        ),
        (
            ["metadata", "/tmp/missing.mp3", "--artist", "Artist", "--album", "Album"],
            "metadata_handler",
        ),
    ],
)
def test_cli_returns_nonzero_for_handler_failures(arguments, handler_name):
    cli = OdysseusCLI(load_services=False)
    cli.display_manager = MagicMock()
    handler = MagicMock()
    handler.handle.return_value = OperationOutcome.failure("failed")
    setattr(cli, handler_name, handler)

    assert cli.run(arguments) == 1


def test_human_batch_parser_preserves_commas_and_hyphens(tmp_path):
    batch_file = tmp_path / "batch.txt"
    batch_file.write_text(
        "Earth, Wind & Fire - That's the Way of the World (1975)\n"
        "Jay-Z - The Blueprint (2001)\n",
        encoding="utf-8",
    )

    entries = OdysseusCLI(load_services=False)._parse_batch_file(str(batch_file))

    assert entries == [
        ("Earth, Wind & Fire", "That's the Way of the World", 1975),
        ("Jay-Z", "The Blueprint", 2001),
    ]


def test_batch_parser_recognizes_csv_after_leading_comments(tmp_path):
    batch_file = tmp_path / "batch.txt"
    batch_file.write_text(
        "# albums\nArtist,Album,Year\nArtist One,Album One,2020\n",
        encoding="utf-8",
    )

    entries = OdysseusCLI(load_services=False)._parse_batch_file(str(batch_file))

    assert entries == [("Artist One", "Album One", 2020)]


def test_duration_recovery_skips_unrelated_first_recording():
    wrong = MusicBrainzSong(
        title="Different Song",
        artist="Artist",
        album="Album",
        mbid="wrong",
        score=100,
    )
    right = MusicBrainzSong(
        title="Target",
        artist="Artist",
        album="Album",
        mbid="right",
        score=1,
    )
    musicbrainz = MagicMock(base_url="https://musicbrainz.test")
    musicbrainz.search_recording.return_value = [wrong, right]
    musicbrainz._make_request.side_effect = (
        lambda url, _params: {
            "length": 600000 if url.endswith("wrong") else 180000
        }
    )
    spotify = MagicMock(access_token=None)
    recovery = DurationRecoveryService(musicbrainz, spotify, MagicMock())

    duration = recovery.recover_track_duration(
        Track(position=1, title="Target", artist="Artist"),
        ReleaseInfo(title="Album", artist="Artist"),
    )

    assert duration == "3:00"
    assert "right" in musicbrainz._make_request.call_args.args[0]


def test_metadata_appliers_route_wav_and_opus_to_valid_writers():
    metadata = AudioMetadata(title="Title")

    assert isinstance(get_metadata_applier(".wav", metadata), WAVMetadataApplier)
    assert isinstance(get_metadata_applier(".opus", metadata), OGGMetadataApplier)
    assert ".aac" not in SUPPORTED_METADATA_EXTENSIONS
    assert ".webm" not in SUPPORTED_METADATA_EXTENSIONS


def test_m4a_does_not_mislabel_webp_as_png():
    audio = MagicMock()
    audio.tags = {}
    metadata = AudioMetadata(cover_art_data=b"RIFFxxxxWEBPpayload")

    M4AMetadataApplier(metadata).apply_cover_art(
        audio,
        Path("track.m4a"),
        "image/webp",
        quiet=True,
    )

    assert "covr" not in audio.tags


def test_existing_m4a_cover_is_extracted_as_bytes(tmp_path):
    audio_file = tmp_path / "track.m4a"
    audio_file.touch()
    cover_data = b"\xff\xd8\xffimage"
    audio = MagicMock()
    audio.tags = {
        "covr": [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]
    }
    fetcher = CoverArtFetcher.__new__(CoverArtFetcher)

    with patch("mutagen.mp4.MP4", return_value=audio):
        extracted = fetcher._extract_cover_art_from_folder(tmp_path)

    assert extracted == cover_data


def test_existing_opus_cover_is_considered_for_fallback(tmp_path):
    audio_file = tmp_path / "track.opus"
    audio_file.touch()
    cover_data = b"\x89PNG\r\n\x1a\nimage"
    picture = Picture()
    picture.data = cover_data
    picture.type = 3
    picture.mime = "image/png"
    audio = MagicMock()
    audio.tags = {
        "metadata_block_picture": [
            base64.b64encode(picture.write()).decode("ascii")
        ]
    }
    fetcher = CoverArtFetcher.__new__(CoverArtFetcher)

    with patch("mutagen.File", return_value=audio):
        extracted = fetcher._extract_cover_art_from_folder(tmp_path)

    assert extracted == cover_data
