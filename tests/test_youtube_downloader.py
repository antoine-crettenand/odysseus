"""Regression tests for YouTube downloader initialization."""

from unittest.mock import patch

from odysseus.clients.youtube_downloader import YouTubeDownloader


def test_initialization_does_not_spawn_subprocesses(temp_dir):
    """Constructing a downloader must not mutate the Python environment."""
    with patch("odysseus.clients.youtube_downloader.subprocess.run") as run:
        YouTubeDownloader(download_dir=str(temp_dir))

    run.assert_not_called()
