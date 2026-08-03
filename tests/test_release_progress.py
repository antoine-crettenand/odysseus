"""Release-download progress remains useful outside the CLI."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from odysseus.domain.music.download.strategies.full_album_strategy import (
    FullAlbumStrategy,
)


class ProgressStub:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def update(self, *args, **kwargs):
        pass


def test_full_album_forwards_downloader_and_splitter_progress(tmp_path):
    strategy = FullAlbumStrategy.__new__(FullAlbumStrategy)
    strategy.display_manager = SimpleNamespace(
        create_download_progress_bar=lambda description: (ProgressStub(), 1),
    )
    source = tmp_path / "album.webm"
    source.touch()
    split_file = tmp_path / "01 - Track.mp3"

    def download_audio(*args, progress_callback, **kwargs):
        progress_callback(
            {
                "percent": 41,
                "status": "downloading",
                "speed": "2 MiB/s",
                "eta": "00:12",
            }
        )
        return source, False

    def split_audio(*args, progress_callback, **kwargs):
        progress_callback(
            {
                "percent": 50,
                "status": "splitting",
                "message": "Splitting track 1 of 2…",
            }
        )
        return [split_file]

    strategy.download_service = SimpleNamespace(
        download_high_quality_audio=download_audio,
        split_video_into_tracks=split_audio,
    )
    events = []

    path = strategy._download_full_album_video(
        SimpleNamespace(title="Artist - Album"),
        "https://example.test/album",
        {},
        True,
        MagicMock(),
        MagicMock(),
        events.append,
    )
    split_paths = strategy._split_video_into_tracks(
        path,
        [{}],
        tmp_path,
        [{}],
        True,
        events.append,
    )

    assert split_paths == [split_file]
    download_event = next(
        event for event in events
        if event["stage"] == "full_album_download" and event["percent"] == 41
    )
    assert download_event["speed"] == "2 MiB/s"
    assert download_event["eta"] == "00:12"
    assert any(
        event["stage"] == "splitting"
        and event["percent"] == 50
        and "track 1 of 2" in event["message"]
        for event in events
    )


def test_full_album_reports_when_no_complete_video_is_found():
    strategy = FullAlbumStrategy.__new__(FullAlbumStrategy)
    strategy.display_manager = SimpleNamespace(
        console=MagicMock(),
        styling=MagicMock(),
    )
    strategy.path_manager = SimpleNamespace(
        get_release_folder_path=lambda release: Path("/tmp/release")
    )
    strategy._should_skip_strategy = MagicMock(return_value=False)
    strategy._prepare_cover_art = MagicMock(return_value=None)
    strategy._search_full_album_videos = MagicMock(return_value=[])
    events = []

    result = strategy.download(
        SimpleNamespace(title="Album"),
        [1],
        "audio",
        silent=True,
        progress_callback=events.append,
    )

    assert result == (None, None)
    assert events[-1]["stage"] == "full_album_not_found"
    assert events[-1]["status"] == "No full album"
