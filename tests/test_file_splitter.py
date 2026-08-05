"""Tests for FileSplitter and full-album split metadata application."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from odysseus.clients.file_splitter import FileSplitter
from odysseus.domain.music.download.strategies.full_album import FullAlbumDownloadPipeline
from odysseus.models.releases import ReleaseInfo, Track

def _tracks(count: int, duration: str = "03:00"):
    return [
        Track(position=index, title=f"Track {index}", artist="Artist", duration=duration)
        for index in range(1, count + 1)
    ]

def test_file_splitter_keeps_failed_slots_index_aligned(tmp_path):
    video = tmp_path / "album.mp3"
    video.write_bytes(b"fake")
    tracks = _tracks(3)
    timestamps = [
        {"start_time": 0, "end_time": 60, "track": tracks[0]},
        {"start_time": 60, "end_time": 120, "track": tracks[1]},
        {"start_time": 120, "end_time": 180, "track": tracks[2]},
    ]
    metadata = [
        {"title": track.title, "track_number": track.position}
        for track in tracks
    ]

    def fake_run(cmd, **kwargs):
        output = Path(cmd[-1])
        # Fail only the middle track.
        if "02 - Track 2.mp3" in output.name:
            raise subprocess.CalledProcessError(1, cmd, stderr="ffmpeg failed")
        output.write_bytes(b"ok")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    with patch("odysseus.clients.file_splitter.subprocess.run", side_effect=fake_run):
        results = FileSplitter.split_video_into_tracks(
            video,
            timestamps,
            tmp_path,
            metadata,
        )

    assert len(results) == 3
    assert results[0] is not None and results[0].name.startswith("01 -")
    assert results[1] is None
    assert results[2] is not None and results[2].name.startswith("03 -")

def test_metadata_application_skips_failed_split_slots():
    pipeline = FullAlbumDownloadPipeline.__new__(FullAlbumDownloadPipeline)
    pipeline.presenter = MagicMock()
    pipeline.presenter.create_download_progress_bar.return_value = (
        MagicMock(),
        "task",
    )
    pipeline.metadata_service = MagicMock()
    pipeline.path_manager = MagicMock()
    tracks = _tracks(3)
    timestamps = [{"track": track} for track in tracks]
    split_files = [
        Path("/tmp/01.mp3"),
        None,
        Path("/tmp/03.mp3"),
    ]

    downloaded, failed = pipeline._apply_metadata_to_split_files(
        split_files,
        timestamps,
        ReleaseInfo(title="Album", artist="Artist", tracks=tracks),
        cover_art_data=None,
        existing_files_before_split=set(),
        youtube_url="https://youtube.test/v",
        silent=True,
    )

    assert downloaded == 2
    assert failed == 1
    applied_paths = [
        call.args[0]
        for call in pipeline.metadata_service.apply_metadata_with_cover_art.call_args_list
    ]
    assert applied_paths == [Path("/tmp/01.mp3"), Path("/tmp/03.mp3")]

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
