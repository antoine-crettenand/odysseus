"""
Rich-backed DownloadPresenter for the CLI.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

from rich import box
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from .display import DisplayManager

T = TypeVar("T")


class RichDownloadPresenter:
    """Adapts DisplayManager to the domain DownloadPresenter port."""

    def __init__(self, display_manager: DisplayManager):
        self._display = display_manager

    def print(self, *args: Any, **kwargs: Any) -> None:
        self._display.console.print(*args, **kwargs)

    def confirm(self, prompt: str, *, default: bool = True) -> bool:
        return Confirm.ask(prompt, default=default)

    def show_loading_spinner(self, message: str, task_func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        return self._display.show_loading_spinner(message, task_func, *args, **kwargs)

    def create_progress_bar(self, total: int, description: str = "Processing") -> Any:
        return self._display.create_progress_bar(total, description)

    def create_download_progress_bar(
        self, description: str = "Downloading", total: Optional[float] = None
    ) -> Tuple[Any, Any]:
        return self._display.create_download_progress_bar(description, total)

    def display_download_info(
        self,
        url: str,
        quality: str,
        audio_only: bool,
        save_location: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._display.display_download_info(url, quality, audio_only, save_location, metadata)

    def display_track_download_result(
        self,
        track_title: str,
        success: bool,
        path: Optional[str] = None,
        file_existed: bool = False,
    ) -> None:
        self._display.display_track_download_result(track_title, success, path, file_existed)

    def display_summary(
        self,
        downloaded: int,
        failed: int,
        total: int,
        *,
        skipped: int = 0,
        title: str = "DOWNLOAD SUMMARY",
    ) -> None:
        self.print()
        summary_content = (
            f"[bold green]✓[/bold green] Successfully downloaded: "
            f"[green]{downloaded}[/green] track{'s' if downloaded != 1 else ''}\n"
        )
        if skipped > 0:
            summary_content += (
                f"[yellow]⏭[/yellow] Skipped existing: "
                f"[yellow]{skipped}[/yellow] track{'s' if skipped != 1 else ''}\n"
            )
        if failed > 0:
            summary_content += (
                f"[bold red]✗[/bold red] Failed downloads: "
                f"[red]{failed}[/red] track{'s' if failed != 1 else ''}\n"
            )
        summary_content += f"[dim blue]ℹ[/dim blue] [dim]Total tracks processed: {total}[/dim]"
        self.display_panel(
            summary_content,
            title=f"[bold cyan]📊 {title}[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
        self.print()

    def display_panel(
        self,
        content: str,
        *,
        title: str,
        border_style: str = "cyan",
        padding: Tuple[int, int] = (1, 2),
    ) -> None:
        self.print(
            Panel(
                content,
                title=title,
                border_style=border_style,
                box=box.ROUNDED,
                padding=padding,
            )
        )

    def display_existing_tracks(
        self,
        rows: List[Tuple[str, str, str]],
        wrong_number_count: int = 0,
    ) -> None:
        table = Table(
            title="[cyan]Existing Tracks Found[/cyan]",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Expected #", style="cyan", justify="right")
        table.add_column("Track Title", style="green")
        table.add_column("File", style="yellow")
        for expected, title, file_display in rows:
            table.add_row(expected, title, file_display)
        self.print()
        self.print(table)
        self.print()
        if wrong_number_count:
            self.print(
                f"[yellow]⚠[/yellow] Found {wrong_number_count} "
                f"track{'s' if wrong_number_count != 1 else ''} with incorrect track numbers."
            )
            self.print(
                "[dim]These tracks will still be used, but you may want to rename them "
                "to match the correct order.[/dim]"
            )
            self.print()

    def log_info(self, message: str, **kwargs: Any) -> None:
        self._display.styling.log_info(message, **kwargs)

    def log_warning(self, message: str, **kwargs: Any) -> None:
        self._display.styling.log_warning(message, **kwargs)
