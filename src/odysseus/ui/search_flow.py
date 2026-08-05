"""
Unified search flow manager for consistent search behavior across handlers.
"""

from typing import List, Optional, Callable
from ..models.search_results import SearchResult
from .display import DisplayManager
from ..core.config import ERROR_MESSAGES


class SearchFlowManager:
    """
    Unified manager for search flows with pagination, result display, and user selection.

    This class handles the common pattern of:
    1. Searching with pagination support
    2. Displaying results
    3. Getting user selection (with RESHUFFLE support)
    4. Handling auto-selection mode
    """

    def __init__(self, display_manager: DisplayManager):
        self.display_manager = display_manager
        self.console = display_manager.console

    def search_with_pagination(
        self,
        search_func: Callable[..., List[SearchResult]],
        search_message: str,
        result_type: str,
        auto_select_func: Optional[Callable[[List[SearchResult], ...], Optional[SearchResult]]] = None,
        auto_select_args: Optional[dict] = None,
        *search_args,
        **search_kwargs
    ) -> Optional[SearchResult]:
        """
        Execute a search with pagination support and user selection.

        Args:
            search_func: Function to call for searching (should accept offset parameter)
            search_message: Message to display during search
            result_type: Type of results (e.g., "RECORDINGS", "RELEASES")
            auto_select_func: Optional function to auto-select result (for auto mode)
            auto_select_args: Optional arguments to pass to auto_select_func
            *search_args: Positional arguments to pass to search_func
            **search_kwargs: Keyword arguments to pass to search_func (offset will be added/modified)

        Returns:
            Selected result or None if cancelled, or 'RESHUFFLE' if user wants to reshuffle
        """
        offset = search_kwargs.pop('offset', 0)
        auto = search_kwargs.pop('auto', False)

        while True:
            if offset > 0:
                self.console.print(f"[blue]ℹ[/blue] Showing results starting from position {offset + 1}")

            # Execute search with current offset
            results = self.display_manager.show_loading_spinner(
                search_message,
                search_func,
                *search_args,
                offset=offset,
                **search_kwargs
            )

            if not results:
                if offset == 0:
                    self.console.print(f"[bold red]✗[/bold red] {ERROR_MESSAGES['NO_RESULTS']}")
                    return None
                else:
                    self.console.print("[yellow]⚠[/yellow] No more results available. Starting from beginning...")
                    offset = 0
                    continue

            # Display results
            self.display_manager.display_search_results(results, result_type)

            # Handle selection
            if auto and auto_select_func:
                # Auto-select the best match
                auto_args = auto_select_args or {}
                selected = auto_select_func(results, **auto_args)
                if selected:
                    self.console.print(f"[bold green]✓[/bold green] Auto-selected: [white]{selected.get_display_name()}[/white] by [green]{selected.artist}[/green]")
                    return selected
                else:
                    self.console.print(
                        "[yellow]⚠[/yellow] No result met the automatic matching threshold."
                    )
                    return None
            else:
                # Get user selection
                selected = self.display_manager.get_user_selection(results)

                if selected == 'RESHUFFLE':
                    offset += len(results)
                    self.console.print()
                    continue
                elif not selected:
                    self.console.print("[yellow]⚠[/yellow] No selection made. Exiting.")
                    return None

                return selected

    def search_without_pagination(
        self,
        search_func: Callable[..., List[SearchResult]],
        search_message: str,
        result_type: str,
        *search_args,
        **search_kwargs
    ) -> List[SearchResult]:
        """
        Execute a search without pagination support.

        Args:
            search_func: Function to call for searching
            search_message: Message to display during search
            result_type: Type of results (for display)
            *search_args: Positional arguments to pass to search_func
            **search_kwargs: Keyword arguments to pass to search_func

        Returns:
            List of search results
        """
        results = self.display_manager.show_loading_spinner(
            search_message,
            search_func,
            *search_args,
            **search_kwargs
        )

        if not results:
            self.console.print(f"[bold red]✗[/bold red] {ERROR_MESSAGES['NO_RESULTS']}")
            return []

        return results
