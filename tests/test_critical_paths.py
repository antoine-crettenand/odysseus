"""High-value tests for release identity, file reuse, metadata, and progress."""

import base64
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

import pytest

from odysseus.clients.progress_tracker import ProgressTracker
from odysseus.core.retry import SubprocessRetryStrategy
from odysseus.domain.media.cover_art.fetcher import CoverArtFetcher
from odysseus.domain.music.download.path_manager import PathManager
from odysseus.domain.music.identity import (
    compare_release,
    select_best_release_match,
    track_titles_match,
)
from odysseus.ui.release_validation import ReleaseValidator
from odysseus.models.releases import ReleaseInfo, Track
from odysseus.models.search_results import MusicBrainzSong
from odysseus.models.song import AudioMetadata, SongData
from odysseus.models.outcomes import OperationOutcome
from odysseus.ui.cli import OdysseusCLI
from odysseus.ui.handlers.release_handler import ReleaseHandler
from odysseus.ui.selection import parse_numeric_selection
from odysseus.utils.metadata_appliers import (
    FLACMetadataApplier,
    M4AMetadataApplier,
    OGGMetadataApplier,
)
from odysseus.utils.release_exporter import export_releases


def test_release_identity_requires_album_and_artist():
    candidate = {
        "album": "Blue",
        "artist": "Different Artist",
        "release_year": 2020,
    }

    match = compare_release(
        candidate,
        expected_album="Blue",
        expected_artist="Expected Artist",
        expected_year=2020,
    )

    assert match.album_similarity == 1
    assert match.artist_similarity < 0.82
    assert match.accepted is False


def test_release_identity_selects_best_acceptable_candidate():
    wrong = {"album": "Unrelated", "artist": "Someone", "spotify_id": "wrong"}
    right = {
        "album": "The Album",
        "artist": "The Artist",
        "release_year": 2021,
        "spotify_id": "right",
    }

    selected = select_best_release_match(
        [wrong, right],
        expected_album="The Album",
        expected_artist="Artist",
        expected_year=2021,
    )

    assert selected["spotify_id"] == "right"


def test_release_handler_never_falls_back_to_unrelated_first_result():
    handler = ReleaseHandler.__new__(ReleaseHandler)
    unrelated = MusicBrainzSong(
        title="Other",
        album="Other",
        artist="Someone Else",
        source="musicbrainz",
    )

    selected = handler._find_best_match(
        [unrelated],
        expected_album="Expected",
        expected_artist="Expected Artist",
    )

    assert selected is None


def test_short_track_titles_do_not_fuzzy_match():
    assert track_titles_match("In", "Shine") is False
    assert track_titles_match("The Long Song", "The Long Song") is True


def test_path_manager_does_not_reuse_unrelated_short_title(temp_dir):
    class FakeDownloadService:
        def get_organized_path(self, metadata):
            return temp_dir

        def sanitize_filename(self, filename):
            return filename

    (temp_dir / "01 - Shine.mp3").touch()
    release = ReleaseInfo(
        title="Album",
        artist="Artist",
        tracks=[Track(position=1, title="In", artist="Artist")],
    )

    found = PathManager(FakeDownloadService()).get_existing_tracks(release, [1])

    assert found == {}


def test_release_validator_rejects_artist_mismatch_without_prompt():
    display = MagicMock()
    validator = ReleaseValidator(display)
    expected = MusicBrainzSong(
        title="Blue",
        album="Blue",
        artist="Expected",
        source="musicbrainz",
    )
    fetched = ReleaseInfo(title="Blue", artist="Different")

    with patch(
        "odysseus.ui.release_validation.Prompt.ask"
    ) as prompt:
        accepted = validator.validate_release_match(
            expected,
            fetched,
            skip_on_mismatch=True,
        )

    assert accepted is False
    prompt.assert_not_called()


def test_song_data_rejects_whitespace_artist_and_preserves_metadata_dots():
    with pytest.raises(ValueError):
        SongData(title="Track", artist="   ")

    assert SongData(title="Track..Part", artist="Artist").title == "Track..Part"


class FakeMP4:
    def __init__(self):
        self.tags = {}

    def add_tags(self):
        self.tags = {}


def test_m4a_uses_standard_mp4_atoms():
    audio = FakeMP4()
    metadata = AudioMetadata(
        title="Title",
        artist="Artist",
        album="Album",
        album_artist="Album Artist",
        year=2020,
        genre="Rock",
        track_number=2,
        total_tracks=10,
        compilation=True,
    )

    M4AMetadataApplier(metadata).apply_tags(audio)

    assert audio.tags["\xa9nam"] == ["Title"]
    assert audio.tags["\xa9ART"] == ["Artist"]
    assert audio.tags["aART"] == ["Album Artist"]
    assert audio.tags["trkn"] == [(2, 10)]
    assert audio.tags["cpil"] is True
    assert "title" not in audio.tags


def test_ogg_serializes_picture_block_not_raw_image():
    class Tags(dict):
        pass

    audio = MagicMock()
    audio.tags = Tags()
    image = b"\xff\xd8\xffimage"
    metadata = AudioMetadata(cover_art_data=image)

    OGGMetadataApplier(metadata).apply_cover_art(
        audio,
        Path("track.ogg"),
        "image/jpeg",
        quiet=True,
    )

    encoded = audio.tags["metadata_block_picture"][0]
    assert base64.b64decode(encoded) != image


def test_flac_replaces_existing_pictures():
    audio = MagicMock()
    metadata = AudioMetadata(cover_art_data=b"\xff\xd8\xffimage")

    FLACMetadataApplier(metadata).apply_cover_art(
        audio,
        Path("track.flac"),
        "image/jpeg",
        quiet=True,
    )

    audio.clear_pictures.assert_called_once_with()
    audio.add_picture.assert_called_once()


def test_streaming_retry_reports_real_progress():
    updates = []
    strategy = SubprocessRetryStrategy(
        max_retries=0,
        timeout=5,
        progress_parser=ProgressTracker.parse_progress_line,
    )

    result = strategy.execute_with_progress(
        [
            sys.executable,
            "-u",
            "-c",
            "print('[download] 42.0% of 1MiB at 1MiB/s ETA 00:01')",
        ],
        progress_callback=updates.append,
        quiet=True,
    )

    assert result.returncode == 0
    assert any(update.get("percent") == 42.0 for update in updates)
    assert updates[-1]["status"] == "completed"


def test_cover_art_uses_non_spotify_provider_url_first():
    fetcher = CoverArtFetcher.__new__(CoverArtFetcher)
    fetcher.fetch_cover_art_from_url = MagicMock(return_value=b"cover")
    fetcher._fetch_cover_art_from_spotify = MagicMock()
    release = ReleaseInfo(
        title="Album",
        artist="Artist",
        cover_art_url="https://i.discogs.com/cover.jpg",
    )

    result = fetcher.fetch_cover_art_for_release(release)

    assert result == b"cover"
    fetcher.fetch_cover_art_from_url.assert_called_once_with(
        release.cover_art_url,
        None,
    )
    fetcher._fetch_cover_art_from_spotify.assert_not_called()


def test_shared_numeric_selection_supports_ranges_and_rejects_partial_errors():
    assert parse_numeric_selection("1,3-5", 5) == [1, 3, 4, 5]
    assert parse_numeric_selection("all", 3) == [1, 2, 3]
    with pytest.raises(ValueError):
        parse_numeric_selection("1,99", 5)
    with pytest.raises(ValueError):
        parse_numeric_selection("4-2", 5)


def test_release_exporter_writes_deduplicated_tsv(temp_dir):
    output = temp_dir / "releases.tsv"

    count = export_releases(
        [
            ("Artist", "Album", 2020),
            ("Artist", "Album", 2020),
            ("Another", "Second", None),
        ],
        str(output),
    )

    assert count == 2
    assert output.read_text(encoding="utf-8").splitlines() == [
        "Artist\tAlbum\tYear",
        "Another\tSecond\t",
        "Artist\tAlbum\t2020",
    ]


def test_batch_accounting_uses_structured_outcomes():
    cli = OdysseusCLI.__new__(OdysseusCLI)
    cli.display_manager = MagicMock()
    cli.display_manager.create_header_panel.return_value = "header"
    cli._parse_batch_file = MagicMock(
        return_value=[
            ("A", "One", None),
            ("B", "Two", None),
            ("C", "Three", None),
        ]
    )
    cli.release_handler = MagicMock()
    cli.release_handler.handle.side_effect = [
        OperationOutcome.success(processed=1),
        OperationOutcome.skipped("No match"),
        OperationOutcome.failure("Download failed", failed=1),
    ]

    outcome = cli._handle_batch_release(
        "batch.tsv",
        release_type=None,
        quality="audio",
        tracks=None,
        no_download=False,
        auto=True,
    )

    assert outcome.succeeded is False
    assert outcome.processed == 1
    assert outcome.failed == 1
