"""Regression tests for YouTube downloader initialization."""

from unittest.mock import patch

from odysseus.clients.youtube_downloader import YouTubeDownloader


def test_initialization_does_not_upgrade_yt_dlp(temp_dir):
    """Constructing a downloader must not mutate the Python environment."""
    with patch(
        "odysseus.clients.youtube_downloader.YtDlpManager.update"
    ) as update:
        YouTubeDownloader(download_dir=str(temp_dir))

    update.assert_not_called()
