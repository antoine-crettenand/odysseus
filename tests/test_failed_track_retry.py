"""Regression tests for the final failed-track retry flow."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from odysseus.domain.music.download.orchestrator import DownloadOrchestrator
from odysseus.models.releases import ReleaseInfo, Track


class StrategyStub:
    def __init__(self, result, failed_track_numbers):
        self.result = result
        self.failed_track_numbers = list(failed_track_numbers)
        self.calls = []

    def download(
        self,
        release_info,
        track_numbers,
        quality,
        silent=False,
        cover_art_data=None,
    ):
        self.calls.append(list(track_numbers))
        return self.result


class FinalRetryStub(StrategyStub):
    def __init__(self, remaining_failures):
        super().__init__((0, len(remaining_failures)), [])
        self.remaining_failures = list(remaining_failures)

    def download(
        self,
        release_info,
        track_numbers,
        quality,
        silent=False,
        cover_art_data=None,
    ):
        self.calls.append(list(track_numbers))
        self.failed_track_numbers = list(self.remaining_failures)
        return (
            len(track_numbers) - len(self.remaining_failures),
            len(self.remaining_failures),
        )


def _release():
    return ReleaseInfo(
        title="Test Album",
        artist="Test Artist",
        tracks=[
            Track(position=1, title="One", artist="Test Artist"),
            Track(position=2, title="Two", artist="Test Artist"),
            Track(position=3, title="Three", artist="Test Artist"),
        ],
    )


def _orchestrator():
    orchestrator = DownloadOrchestrator.__new__(DownloadOrchestrator)
    orchestrator.display_manager = SimpleNamespace(
        console=MagicMock(),
        styling=MagicMock(),
    )
    orchestrator.metadata_service = MagicMock()
    orchestrator.path_manager = MagicMock()
    orchestrator.path_manager.get_release_folder_path.return_value = Path("/tmp/album")
    orchestrator.path_manager.get_existing_tracks.return_value = {}
    orchestrator.full_album_strategy = StrategyStub((1, 2), [2, 3])
    orchestrator.playlist_strategy = StrategyStub((None, None), [1, 2, 3])
    orchestrator.individual_tracks_strategy = FinalRetryStub([3])
    orchestrator.last_failed_track_numbers = []
    return orchestrator


def test_release_retry_only_attempts_tracks_failed_by_album_strategy():
    orchestrator = _orchestrator()

    with patch(
        "odysseus.domain.music.download.orchestrator.Confirm.ask",
        return_value=True,
    ) as confirm:
        downloaded, failed = orchestrator.download_release_tracks(
            _release(), [1, 2, 3], "audio"
        )

    assert (downloaded, failed) == (2, 1)
    assert orchestrator.individual_tracks_strategy.calls == [[2, 3]]
    assert orchestrator.last_failed_track_numbers == [3]
    assert not orchestrator.playlist_strategy.calls
    confirm.assert_called_once()


def test_declining_final_retry_preserves_exact_failed_tracks():
    orchestrator = _orchestrator()

    with patch(
        "odysseus.domain.music.download.orchestrator.Confirm.ask",
        return_value=False,
    ):
        downloaded, failed = orchestrator.download_release_tracks(
            _release(), [1, 2, 3], "audio"
        )

    assert (downloaded, failed) == (1, 2)
    assert orchestrator.individual_tracks_strategy.calls == []
    assert orchestrator.last_failed_track_numbers == [2, 3]


def test_silent_mode_retries_without_prompting():
    orchestrator = _orchestrator()

    with patch(
        "odysseus.domain.music.download.orchestrator.Confirm.ask"
    ) as confirm:
        downloaded, failed = orchestrator.download_release_tracks(
            _release(), [1, 2, 3], "audio", silent=True
        )

    assert (downloaded, failed) == (2, 1)
    assert orchestrator.individual_tracks_strategy.calls == [[2, 3]]
    confirm.assert_not_called()
