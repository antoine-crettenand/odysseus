"""
User interaction utilities for parsing user input and selections.
"""

from typing import List, Optional
from rich.prompt import Prompt
from rich.table import Table
from rich import box
from ..ui.display import DisplayManager
from .selection import parse_numeric_selection


class UserInteraction:
    """Utilities for user interaction."""

    def __init__(self, display_manager: DisplayManager):
        self.display_manager = display_manager
        self.console = display_manager.console

    def parse_track_selection(
        self,
        tracks_arg: Optional[str],
        total_tracks: int,
        auto: bool = False
    ) -> List[int]:
        """Parse track selection from command line argument or user input."""
        if tracks_arg:
            # Parse comma-separated track numbers
            try:
                track_numbers = parse_numeric_selection(tracks_arg, total_tracks)
                self.console.print(f"[blue]ℹ[/blue] Selected tracks: [cyan]{', '.join(map(str, track_numbers))}[/cyan]")
                return track_numbers
            except ValueError:
                self.console.print("[bold red]✗[/bold red] Invalid track selection format. Use comma-separated numbers (e.g., 1,3,5)")
                return []
        elif auto:
            # Auto mode: select all tracks
            all_tracks = list(range(1, total_tracks + 1))
            if total_tracks <= 10:
                self.console.print(f"[blue]ℹ[/blue] Auto-selected all tracks: [cyan]{', '.join(map(str, all_tracks))}[/cyan]")
            else:
                self.console.print(f"[blue]ℹ[/blue] Auto-selected all [cyan]{total_tracks}[/cyan] tracks")
            return all_tracks
        else:
            # Interactive track selection
            self.console.print("[bold]Select tracks to download:[/bold]")
            options_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
            options_table.add_column("Option", style="cyan")
            options_table.add_row("Enter track numbers separated by commas (e.g., 1,3,5)")
            options_table.add_row("Enter 'all' to download all tracks")
            options_table.add_row("Enter 'q' to cancel")
            self.console.print(options_table)
            self.console.print()

            while True:
                choice = Prompt.ask("[bold]Your selection[/bold]", default="")

                if choice.lower() == 'q':
                    return []

                if choice.lower() == 'all':
                    return list(range(1, total_tracks + 1))

                try:
                    track_numbers = parse_numeric_selection(choice, total_tracks)
                    self.console.print(f"[blue]ℹ[/blue] Selected tracks: [cyan]{', '.join(map(str, track_numbers))}[/cyan]")
                    return track_numbers

                except ValueError:
                    self.console.print("[bold red]✗[/bold red] Invalid format. Use comma-separated numbers (e.g., 1,3,5)")
                    continue
