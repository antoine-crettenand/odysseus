"""
Progress Displays Module
Handles progress bars, spinners, and download progress tracking.
"""

from typing import Optional, Any, Callable
from rich.console import Console
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn, 
    TaskProgressColumn, TimeElapsedColumn
)


class ProgressDisplays:
    """Handles progress bars and loading spinners."""
    
    def __init__(self, console: Console):
        self.console = console
    
    def show_loading_spinner(self, message: str, task_func: Callable, *args, **kwargs) -> Any:
        """Show a loading spinner while executing a task."""
        with self.console.status(f"[bold cyan]{message}[/bold cyan]", spinner="dots"):
            return task_func(*args, **kwargs)
    
    def create_progress_bar(self, total: int, description: str = "Processing") -> Progress:
        """Create a progress bar for tracking downloads."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console,
            expand=True
        )
    
    def create_download_progress_bar(self, description: str = "Downloading", total: Optional[float] = None) -> tuple[Progress, Any]:
        """
        Create a progress bar specifically for file downloads.
        Returns (Progress instance, task_id).
        
        Args:
            description: Description text for the progress bar
            total: Total size in bytes (if known, otherwise will be updated dynamically)
        """
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
            expand=True
        )
        # Start with None total, will be updated when we know the file size
        task_id = progress.add_task(description, total=total or 100)
        return progress, task_id

