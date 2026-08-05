"""Regression coverage for the third code-review fix round."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from odysseus.clients.discogs import DiscogsClient
from odysseus.clients.download_strategies import DownloadStrategies, STRATEGIES
from odysseus.clients.file_splitter import FileSplitter
from odysseus.clients.musicbrainz import MusicBrainzClient
from odysseus.core.validation import check_dependencies
from odysseus.domain.music.download.strategies.full_album import ChapterAligner
from odysseus.models.releases import Track
from odysseus.ui.cli import OdysseusCLI


def test_duration_fallback_rejects_unknown_preceding_offset():
    aligner = ChapterAligner.__new__(ChapterAligner)
    aligner.video_validator = MagicMock()
    aligner.video_validator._parse_duration_to_seconds.side_effect = (
        lambda value: None if value is None else 180
    )
    tracks = [
        Track(1, "Unknown", "Artist", None),
        Track(2, "Selected", "Artist", "03:00"),
    ]

    timestamps = aligner._calculate_track_timestamps_from_durations(
        tracks,
        [2],
    )

    assert timestamps == []


def test_duration_fallback_ignores_missing_durations_after_selection():
    aligner = ChapterAligner.__new__(ChapterAligner)
    aligner.video_validator = MagicMock()
    aligner.video_validator._parse_duration_to_seconds.side_effect = (
        lambda value: None if value is None else 60
    )
    tracks = [
        Track(1, "Selected", "Artist", "01:00"),
        Track(2, "Later", "Artist", None),
    ]

    timestamps = aligner._calculate_track_timestamps_from_durations(
        tracks,
        [1],
    )

    assert timestamps[0]["start_time"] == 0
    assert timestamps[0]["end_time"] == 60


def test_discogs_parser_skips_headings_and_flattens_index_subtracks():
    client = DiscogsClient.__new__(DiscogsClient)

    release = client._parse_release_info(
        {
            "id": 1,
            "title": "Album",
            "artists": [{"name": "Artist"}],
            "tracklist": [
                {"type_": "heading", "title": "Side A"},
                {"type_": "track", "title": "First", "duration": "1:00"},
                {
                    "type_": "index",
                    "title": "Suite",
                    "sub_tracks": [
                        {"type_": "track", "title": "Part One"},
                        {"type_": "track", "title": "Part Two"},
                    ],
                },
            ],
        }
    )

    assert [(track.position, track.title) for track in release.tracks] == [
        (1, "First"),
        (2, "Part One"),
        (3, "Part Two"),
    ]


def test_dependency_check_reports_missing_ffmpeg_only():
    def run(command, **kwargs):
        if command[0] == "ffmpeg":
            raise FileNotFoundError("ffmpeg not found")
        return subprocess.CompletedProcess(command, 0)

    with patch.object(subprocess, "run", side_effect=run), patch(
        "importlib.import_module",
        return_value=MagicMock(),
    ):
        installed, missing = check_dependencies()

    assert installed is False
    assert missing == ["ffmpeg (audio transcoder)"]


def test_musicbrainz_artist_credit_preserves_alias_and_joinphrase():
    client = MusicBrainzClient.__new__(MusicBrainzClient)

    artist = client._parse_artist_credit(
        [
            {
                "name": "Credited Artist",
                "artist": {"name": "Canonical Artist"},
                "joinphrase": " feat. ",
            },
            {
                "name": "Guest Alias",
                "artist": {"name": "Canonical Guest"},
                "joinphrase": "",
            },
        ]
    )

    assert artist == "Credited Artist feat. Guest Alias"


def test_batch_parser_rejects_explicit_malformed_year(tmp_path):
    batch_file = tmp_path / "batch.csv"
    batch_file.write_text(
        "Artist,Album,Year\nTest Artist,Test Album,20O1\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid year on line 2"):
        OdysseusCLI(load_services=False)._parse_batch_file(str(batch_file))


def test_download_strategy_honors_configured_audio_format():
    strategies = DownloadStrategies(MagicMock(), audio_format="flac")

    command = strategies.build_strategy(
        STRATEGIES[0],
        "https://example.test/video",
        "audio",
        True,
        "%(title)s.%(ext)s",
    )

    format_index = command.index("--audio-format")
    assert command[format_index + 1] == "flac"
    assert "ffmpeg:-b:a 320k" not in command


def test_file_splitter_uses_configured_format(tmp_path):
    source = tmp_path / "album.webm"
    source.write_bytes(b"source")
    track = Track(1, "Track", "Artist", "01:00")
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        Path(command[-1]).write_bytes(b"audio")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    with patch("odysseus.clients.file_splitter.subprocess.run", side_effect=run):
        results = FileSplitter.split_video_into_tracks(
            source,
            [{"start_time": 0, "end_time": 60, "track": track}],
            tmp_path,
            [{"title": "Track", "track_number": 1}],
            audio_format="flac",
        )

    assert results[0].suffix == ".flac"
    assert "flac" in commands[0]
