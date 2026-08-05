"""
Presentation port for download orchestration.

Domain code talks to DownloadPresenter instead of Rich / DisplayManager.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, TypeVar

T = TypeVar("T")


class _NullProgress:
    """Progress bar stand-in that records nothing."""

    def __enter__(self) -> "_NullProgress":
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def add_task(self, description: str = "", total: Optional[float] = None, **kwargs: Any) -> int:
        return 0

    def update(self, task_id: Any, **kwargs: Any) -> None:
        return None


class DownloadPresenter(Protocol):
    """Human-facing I/O during downloads. Machine progress uses ReleaseProgressCallback."""

    def print(self, *args: Any, **kwargs: Any) -> None:
        ...

    def confirm(self, prompt: str, *, default: bool = True) -> bool:
        ...

    def show_loading_spinner(self, message: str, task_func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        ...

    def create_progress_bar(self, total: int, description: str = "Processing") -> Any:
        ...

    def create_download_progress_bar(
        self, description: str = "Downloading", total: Optional[float] = None
    ) -> Tuple[Any, Any]:
        ...

    def display_download_info(
        self,
        url: str,
        quality: str,
        audio_only: bool,
        save_location: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        ...

    def display_track_download_result(
        self,
        track_title: str,
        success: bool,
        path: Optional[str] = None,
        file_existed: bool = False,
    ) -> None:
        ...

    def display_summary(
        self,
        downloaded: int,
        failed: int,
        total: int,
        *,
        skipped: int = 0,
        title: str = "DOWNLOAD SUMMARY",
    ) -> None:
        ...

    def display_panel(
        self,
        content: str,
        *,
        title: str,
        border_style: str = "cyan",
        padding: Tuple[int, int] = (1, 2),
    ) -> None:
        ...

    def display_existing_tracks(
        self,
        rows: List[Tuple[str, str, str]],
        wrong_number_count: int = 0,
    ) -> None:
        ...

    def log_info(self, message: str, **kwargs: Any) -> None:
        ...

    def log_warning(self, message: str, **kwargs: Any) -> None:
        ...


@dataclass
class NullPresenter:
    """No-op presenter for GUI / silent / headless paths."""

    auto_confirm: bool = True

    def print(self, *args: Any, **kwargs: Any) -> None:
        return None

    def confirm(self, prompt: str, *, default: bool = True) -> bool:
        return self.auto_confirm if self.auto_confirm is not None else default

    def show_loading_spinner(self, message: str, task_func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        return task_func(*args, **kwargs)

    def create_progress_bar(self, total: int, description: str = "Processing") -> Any:
        return _NullProgress()

    def create_download_progress_bar(
        self, description: str = "Downloading", total: Optional[float] = None
    ) -> Tuple[Any, Any]:
        progress = _NullProgress()
        return progress, progress.add_task(description, total=total or 100)

    def display_download_info(
        self,
        url: str,
        quality: str,
        audio_only: bool,
        save_location: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        return None

    def display_track_download_result(
        self,
        track_title: str,
        success: bool,
        path: Optional[str] = None,
        file_existed: bool = False,
    ) -> None:
        return None

    def display_summary(
        self,
        downloaded: int,
        failed: int,
        total: int,
        *,
        skipped: int = 0,
        title: str = "DOWNLOAD SUMMARY",
    ) -> None:
        return None

    def display_panel(
        self,
        content: str,
        *,
        title: str,
        border_style: str = "cyan",
        padding: Tuple[int, int] = (1, 2),
    ) -> None:
        return None

    def display_existing_tracks(
        self,
        rows: List[Tuple[str, str, str]],
        wrong_number_count: int = 0,
    ) -> None:
        return None

    def log_info(self, message: str, **kwargs: Any) -> None:
        return None

    def log_warning(self, message: str, **kwargs: Any) -> None:
        return None
