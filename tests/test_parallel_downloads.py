"""Tests for bounded parallel download execution and CLI exposure."""

from pathlib import Path
import threading
import time
from unittest.mock import MagicMock

import pytest

from odysseus.domain.music.download.download_service import (
    DownloadRequest,
    DownloadService,
)
from odysseus.ui.cli import OdysseusCLI


class FakeDownloader:
    def __init__(self, download_dir: Path, wait_for_parallel: bool = False):
        self.download_dir = download_dir
        self.wait_for_parallel = wait_for_parallel
        self.lock = threading.Lock()
        self.parallel_gate = threading.Event()
        self.active = 0
        self.entered = 0
        self.max_active = 0
        self.cancelled = False

    def download_high_quality_audio(
        self,
        url,
        metadata,
        quiet=True,
        progress_callback=None,
    ):
        with self.lock:
            self.active += 1
            self.entered += 1
            self.max_active = max(self.max_active, self.active)
            if self.entered >= 2:
                self.parallel_gate.set()

        if self.wait_for_parallel:
            assert self.parallel_gate.wait(timeout=1)
        else:
            time.sleep(0.02)

        if progress_callback:
            progress_callback({"percent": 50})
        with self.lock:
            self.active -= 1
        return self.download_dir / f"{metadata['title']}.mp3", False

    def cancel_active_downloads(self):
        self.cancelled = True


def _request(key, title):
    return DownloadRequest(
        key=key,
        url=f"https://example.test/{key}",
        quality="audio",
        metadata={
            "artist": "Artist",
            "album": "Album",
            "title": title,
        },
    )


def test_download_many_is_bounded_ordered_and_marshals_progress(tmp_path):
    downloader = FakeDownloader(tmp_path, wait_for_parallel=True)
    service = DownloadService(downloader=downloader)
    callback_threads = []

    results = service.download_many(
        [_request(1, "One"), _request(2, "Two"), _request(3, "Three")],
        workers=2,
        progress_callback=lambda key, info: callback_threads.append(
            threading.get_ident()
        ),
    )

    assert downloader.max_active == 2
    assert [result.key for result in results] == [1, 2, 3]
    assert all(result.succeeded for result in results)
    assert callback_threads
    assert set(callback_threads) == {threading.get_ident()}


def test_download_many_serializes_requests_for_the_same_target(tmp_path):
    downloader = FakeDownloader(tmp_path)
    service = DownloadService(downloader=downloader)

    results = service.download_many(
        [_request(1, "Duplicate"), _request(2, "Duplicate")],
        workers=2,
    )

    assert downloader.max_active == 1
    assert all(result.succeeded for result in results)


def test_target_reservation_uses_sanitized_output_filename(tmp_path):
    downloader = FakeDownloader(tmp_path)
    service = DownloadService(downloader=downloader)

    results = service.download_many(
        [_request(1, "A/B"), _request(2, "A:B")],
        workers=2,
    )

    assert downloader.max_active == 1
    assert all(result.succeeded for result in results)


def test_download_many_cancels_active_work_if_progress_handling_is_interrupted(
    tmp_path,
):
    downloader = FakeDownloader(tmp_path, wait_for_parallel=True)
    service = DownloadService(downloader=downloader)

    def interrupt_progress(key, info):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        service.download_many(
            [_request(1, "One"), _request(2, "Two")],
            workers=2,
            progress_callback=interrupt_progress,
        )

    assert downloader.cancelled is True


@pytest.mark.parametrize("jobs", [0, 5, True, 1.5])
def test_worker_count_rejects_unbounded_or_invalid_values(jobs):
    with pytest.raises(ValueError):
        DownloadService.validate_worker_count(jobs)


def test_download_cli_modes_expose_bounded_jobs_option():
    parser = OdysseusCLI(load_services=False).create_parser()

    release = parser.parse_args(
        ["release", "--album", "Album", "--artist", "Artist", "--jobs", "3"]
    )
    discography = parser.parse_args(
        ["discography", "--artist", "Artist", "--jobs", "2"]
    )
    spotify = parser.parse_args(
        ["spotify", "--url", "https://open.spotify.com/album/id", "--jobs", "4"]
    )

    assert release.jobs == 3
    assert discography.jobs == 2
    assert spotify.jobs == 4


def test_jobs_defaults_to_sequential_and_rejects_values_above_limit():
    parser = OdysseusCLI(load_services=False).create_parser()
    parsed = parser.parse_args(
        ["release", "--album", "Album", "--artist", "Artist"]
    )

    assert parsed.jobs == 1
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "release",
                "--album",
                "Album",
                "--artist",
                "Artist",
                "--jobs",
                "5",
            ]
        )


def test_cli_forwards_jobs_to_release_handler():
    cli = OdysseusCLI(load_services=False)

    cli.release_handler = MagicMock()
    cli.display_manager = MagicMock()

    exit_code = cli.run(
        [
            "release",
            "--album",
            "Album",
            "--artist",
            "Artist",
            "--no-download",
            "--jobs",
            "3",
        ]
    )

    assert exit_code == 0
    assert cli.release_handler.handle.call_args.kwargs["jobs"] == 3
