"""Regression tests for YouTube downloader initialization."""

from pathlib import Path
from unittest.mock import patch

from odysseus.clients.youtube_downloader import YouTubeDownloader
from odysseus.core.config import DOWNLOAD_CONFIG, DOWNLOADS_DIR


def test_default_download_path_is_relative_downloads(temp_dir, monkeypatch):
    """All default downloads should be rooted in ./downloads."""
    monkeypatch.chdir(temp_dir)

    downloader = YouTubeDownloader()

    assert DOWNLOADS_DIR == Path("downloads")
    assert DOWNLOAD_CONFIG["DEFAULT_DIR"] == "downloads"
    assert downloader.download_dir == Path("downloads")
    assert (temp_dir / "downloads").is_dir()


def test_initialization_does_not_spawn_subprocesses(temp_dir):
    """Constructing a downloader must not mutate the Python environment."""
    with patch("odysseus.clients.youtube_downloader.subprocess.run") as run:
        YouTubeDownloader(download_dir=str(temp_dir))

    run.assert_not_called()
