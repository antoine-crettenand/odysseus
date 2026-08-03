"""Regression tests for YouTube downloader initialization."""

from unittest.mock import patch

from odysseus.clients.youtube_downloader import YouTubeDownloader
from odysseus.core.config import DOWNLOAD_CONFIG, PROJECT_DOWNLOADS_DIR, PROJECT_ROOT


def test_default_download_path_is_project_downloads(temp_dir, monkeypatch):
    """The launch directory must not change the project download root."""
    monkeypatch.chdir(temp_dir)

    downloader = YouTubeDownloader()

    expected_dir = PROJECT_ROOT / "downloads"
    assert PROJECT_DOWNLOADS_DIR == expected_dir
    assert DOWNLOAD_CONFIG["DEFAULT_DIR"] == str(expected_dir)
    assert downloader.download_dir == expected_dir
    assert expected_dir.is_dir()
    assert not (temp_dir / "downloads").exists()


def test_initialization_does_not_spawn_subprocesses(temp_dir):
    """Constructing a downloader must not mutate the Python environment."""
    with patch("odysseus.clients.youtube_downloader.subprocess.run") as run:
        YouTubeDownloader(download_dir=str(temp_dir))

    run.assert_not_called()
