"""Regression tests for YouTube downloader initialization."""

from unittest.mock import MagicMock, patch

from odysseus.clients.download_strategies import DownloadStrategies, STRATEGIES
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
