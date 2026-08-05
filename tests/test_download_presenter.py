"""Unit tests for DownloadPresenter implementations."""

from unittest.mock import MagicMock

import pytest

from odysseus.domain.music.download.presenter import NullPresenter, _NullProgress
from odysseus.ui.download_presenter import RichDownloadPresenter
from odysseus.ui.display import DisplayManager


@pytest.mark.unit
def test_null_presenter_confirm_defaults_true():
    presenter = NullPresenter()
    assert presenter.confirm("Retry?") is True
    assert presenter.confirm("Retry?", default=False) is True


@pytest.mark.unit
def test_null_presenter_spinner_runs_callable():
    presenter = NullPresenter()
    assert presenter.show_loading_spinner("x", lambda a, b: a + b, 2, 3) == 5


@pytest.mark.unit
def test_null_presenter_progress_bars_are_noop_context_managers():
    presenter = NullPresenter()
    progress = presenter.create_progress_bar(3, "work")
    assert isinstance(progress, _NullProgress)
    with progress:
        task = progress.add_task("item", total=3)
        progress.update(task, advance=1)

    file_progress, task_id = presenter.create_download_progress_bar("dl")
    with file_progress:
        file_progress.update(task_id, completed=50)


@pytest.mark.unit
def test_null_presenter_display_methods_are_noop():
    presenter = NullPresenter()
    presenter.print("hello")
    presenter.display_download_info("http://x", "audio", True, "/tmp")
    presenter.display_track_download_result("Track", True, "/tmp/a.mp3")
    presenter.display_summary(1, 0, 1, skipped=0)
    presenter.display_panel("body", title="t")
    presenter.display_existing_tracks([("1", "A", "01 - A.mp3")], wrong_number_count=1)
    presenter.log_info("info")
    presenter.log_warning("warn")


@pytest.mark.unit
def test_rich_presenter_delegates_to_display_manager():
    display = MagicMock(spec=DisplayManager)
    display.console = MagicMock()
    display.styling = MagicMock()
    display.create_progress_bar.return_value = MagicMock()
    display.create_download_progress_bar.return_value = (MagicMock(), 1)
    presenter = RichDownloadPresenter(display)

    presenter.print("hi")
    display.console.print.assert_called_once_with("hi")

    presenter.show_loading_spinner("msg", lambda: 9)
    display.show_loading_spinner.assert_called_once()

    presenter.display_download_info("u", "audio", True, "/d", {"title": "T"})
    display.display_download_info.assert_called_once()

    presenter.display_track_download_result("T", True, "/f", file_existed=True)
    display.display_track_download_result.assert_called_once()

    presenter.log_info("i", icon="x")
    display.styling.log_info.assert_called_once_with("i", icon="x")
    presenter.log_warning("w")
    display.styling.log_warning.assert_called_once_with("w")

    presenter.create_progress_bar(2, "p")
    display.create_progress_bar.assert_called_once_with(2, "p")
    presenter.create_download_progress_bar("d")
    display.create_download_progress_bar.assert_called_once()


@pytest.mark.unit
def test_rich_presenter_display_summary_and_panel():
    display = MagicMock(spec=DisplayManager)
    display.console = MagicMock()
    presenter = RichDownloadPresenter(display)
    presenter.display_summary(2, 1, 4, skipped=1, title="SUMMARY")
    assert display.console.print.call_count >= 2
    presenter.display_panel("content", title="Title", border_style="red")
    assert display.console.print.call_count >= 3


@pytest.mark.unit
def test_rich_presenter_existing_tracks_table():
    display = MagicMock(spec=DisplayManager)
    display.console = MagicMock()
    presenter = RichDownloadPresenter(display)
    presenter.display_existing_tracks(
        [("1", "One", "01 - One.mp3"), ("2", "Two", "[yellow]bad[/yellow]")],
        wrong_number_count=1,
    )
    assert display.console.print.call_count >= 3
