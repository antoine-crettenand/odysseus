"""
Input Handlers Module
Handles user input, selection, and confirmation dialogs.
"""

from typing import List, Optional, Tuple, Union
from rich.console import Console
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.table import Table
from rich import box

from ..models.search_results import SearchResult, MusicBrainzSong, YouTubeVideo
from ..utils.string_utils import normalize_string


class InputHandlers:
    """Handlers for user input and selection."""
    
    def __init__(self, console: Console, formatters):
        self.console = console
        self.formatters = formatters
    
    def get_user_selection(self, results: List[SearchResult], prompt: str = "Select a result", allow_reshuffle: bool = True) -> Union[Optional[SearchResult], str]:
        """Get user selection from search results."""
        if not results:
            return None
        
        options_text = f"[cyan]1-{len(results)}[/cyan]"
        if allow_reshuffle:
            options_text += ", [yellow]'r'[/yellow] to reshuffle/search again"
        options_text += ", or [red]'q'[/red] to quit"
        
        self.console.print(f"[bold blue]ℹ[/bold blue] {prompt} ({options_text}):")
        
        while True:
            try:
                choice = Prompt.ask("[bold]Your choice[/bold]", default="")
                
                if choice.lower() in ['q', 'quit', 'exit']:
                    self.console.print("[yellow]⚠[/yellow] Selection cancelled.")
                    return None
                
                if allow_reshuffle and choice.lower() == 'r':
                    self.console.print("[blue]ℹ[/blue] Reshuffling search...")
                    return 'RESHUFFLE'
                
                choice_num = int(choice)
                if 1 <= choice_num <= len(results):
                    selected = results[choice_num - 1]
                    self.console.print(f"[bold green]✓[/bold green] Selected: [white]{selected.get_display_name()}[/white] by [green]{selected.artist}[/green]")
                    return selected
                else:
                    self.console.print(f"[bold red]✗[/bold red] Please enter a number between 1 and {len(results)}")
                    
            except ValueError:
                if allow_reshuffle:
                    self.console.print("[bold red]✗[/bold red] Please enter a valid number, 'r' to reshuffle, or 'q' to quit")
                else:
                    self.console.print("[bold red]✗[/bold red] Please enter a valid number or 'q' to quit")
    
    def get_video_selection(self, videos: List[YouTubeVideo], allow_reshuffle: bool = True) -> Union[Optional[YouTubeVideo], str]:
        """Get user selection from YouTube video results."""
        if not videos:
            return None
        
        options_text = f"[cyan]1-{len(videos)}[/cyan]"
        if allow_reshuffle:
            options_text += ", [yellow]'r'[/yellow] to search again"
        options_text += ", or [red]'q'[/red] to skip"
        
        self.console.print(f"[bold blue]ℹ[/bold blue] Select a video to download ({options_text}):")
        
        while True:
            try:
                choice = Prompt.ask("[bold]Your choice[/bold]", default="")
                
                if choice.lower() in ['q', 'quit', 'skip', 'exit']:
                    self.console.print("[yellow]⚠[/yellow] Video selection skipped.")
                    return None
                
                if allow_reshuffle and choice.lower() == 'r':
                    self.console.print("[blue]ℹ[/blue] Reshuffling YouTube search...")
                    return 'RESHUFFLE'
                
                choice_num = int(choice)
                if 1 <= choice_num <= len(videos):
                    selected = videos[choice_num - 1]
                    self.console.print(f"[bold green]✓[/bold green] Selected: [white]{selected.title or 'No title'}[/white] from [blue]{selected.channel or 'Unknown'}[/blue]")
                    return selected
                else:
                    self.console.print(f"[bold red]✗[/bold red] Please enter a number between 1 and {len(videos)}")
                    
            except ValueError:
                if allow_reshuffle:
                    self.console.print("[bold red]✗[/bold red] Please enter a valid number, 'r' to search again, or 'q' to skip")
                else:
                    self.console.print("[bold red]✗[/bold red] Please enter a valid number or 'q' to skip")
    
    def get_release_selection(self, releases: List[MusicBrainzSong], quality: str = "audio", search_service=None) -> Tuple[List[MusicBrainzSong], bool]:
        """
        Get user selection for releases to download.
        Returns: (list of releases, auto_download_all_tracks flag)
        """
        self.console.print()
        self.console.print(self.formatters.create_header_panel(
            "📦 RELEASE SELECTION",
            f"Found {len(releases)} release{'s' if len(releases) != 1 else ''}. Choose how to select:"
        ))
        self.console.print()
        
        # Show selection options in a table
        options_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        options_table.add_column("Option", style="bold white", width=3)
        options_table.add_column("Description", style="cyan")
        
        options_table.add_row("1", "Single release - Enter one number")
        options_table.add_row("2", "Multiple releases - Enter numbers separated by commas (e.g., 1,3,5)")
        options_table.add_row("3", "Range of releases - Enter range (e.g., 1-5)")
        options_table.add_row("4", "All releases - Download everything")
        options_table.add_row("5", "[red]Cancel[/red] - Exit without downloading")
        
        self.console.print(options_table)
        self.console.print()
        
        while True:
            choice = Prompt.ask("[bold]Choose selection mode[/bold]", choices=["1", "2", "3", "4", "5"], default="5")
            
            if choice == '1':
                selected = self._select_single_release(releases)
                if selected:  # Only return if something was selected
                    return (selected, False)
                # If empty list returned, continue loop to show menu again
                self.console.print()
                self.console.print(self.formatters.create_header_panel(
                    "📦 RELEASE SELECTION",
                    f"Found {len(releases)} release{'s' if len(releases) != 1 else ''}. Choose how to select:"
                ))
                self.console.print()
                self.console.print(options_table)
                self.console.print()
            elif choice == '2':
                result = self._select_multiple_releases(releases)
                if result is None or (result and not result[0]):
                    # User cancelled or no selection, show menu again
                    if result is None:
                        # Already printed cancellation message
                        pass
                    self.console.print()
                    self.console.print(self.formatters.create_header_panel(
                        "📦 RELEASE SELECTION",
                        f"Found {len(releases)} release{'s' if len(releases) != 1 else ''}. Choose how to select:"
                    ))
                    self.console.print()
                    self.console.print(options_table)
                    self.console.print()
                elif result and result[0]:  # Only return if something was selected
                    return result
            elif choice == '3':
                result = self._select_range_releases(releases)
                if result is None or (result and not result[0]):
                    # User cancelled or no selection, show menu again
                    if result is None:
                        # Already printed cancellation message
                        pass
                    self.console.print()
                    self.console.print(self.formatters.create_header_panel(
                        "📦 RELEASE SELECTION",
                        f"Found {len(releases)} release{'s' if len(releases) != 1 else ''}. Choose how to select:"
                    ))
                    self.console.print()
                    self.console.print(options_table)
                    self.console.print()
                elif result and result[0]:  # Only return if something was selected
                    return result
            elif choice == '4':
                result = self._confirm_all_releases(releases, quality, search_service)
                if result is None or (result and not result[0]):
                    # User cancelled or no selection, show menu again
                    if result is None:
                        # Already printed cancellation message
                        pass
                    self.console.print()
                    self.console.print(self.formatters.create_header_panel(
                        "📦 RELEASE SELECTION",
                        f"Found {len(releases)} release{'s' if len(releases) != 1 else ''}. Choose how to select:"
                    ))
                    self.console.print()
                    self.console.print(options_table)
                    self.console.print()
                elif result and result[0]:  # Only return if something was selected
                    return result
            elif choice == '5':
                self.console.print("[yellow]⚠[/yellow] Selection cancelled.")
                return ([], False)
    
    def _select_single_release(self, releases: List[MusicBrainzSong]) -> List[MusicBrainzSong]:
        """Select a single release."""
        while True:
            try:
                choice = IntPrompt.ask(f"[bold]Enter release number[/bold] (1-{len(releases)})", default=None)
                
                if choice is None:
                    return []
                
                if 1 <= choice <= len(releases):
                    selected = releases[choice - 1]
                    self.console.print(f"[bold green]✓[/bold green] Selected: [yellow]{selected.album}[/yellow] by [green]{selected.artist}[/green]")
                    return [selected]
                else:
                    self.console.print(f"[bold red]✗[/bold red] Please enter a number between 1 and {len(releases)}")
                    
            except (ValueError, KeyboardInterrupt):
                return []
    
    def _select_multiple_releases(self, releases: List[MusicBrainzSong]) -> Optional[Tuple[List[MusicBrainzSong], bool]]:
        """
        Select multiple releases by comma-separated numbers.
        Returns: (list of selected releases, auto_download_all_tracks flag)
        """
        while True:
            try:
                choice = Prompt.ask("[bold]Enter release numbers[/bold] (e.g., 1,3,5 or 1-3,5)", default="")
                
                if choice.lower() in ['q', 'quit', 'cancel']:
                    self.console.print("[yellow]⚠[/yellow] Selection cancelled. Returning to selection menu...")
                    self.console.print()
                    return None
                
                # Parse both individual numbers and ranges
                numbers = set()
                parts = choice.split(',')
                
                for part in parts:
                    part = part.strip()
                    if '-' in part:
                        start, end = map(int, part.split('-'))
                        numbers.update(range(start, end + 1))
                    else:
                        numbers.add(int(part))
                
                # Validate all numbers
                valid_numbers = [n for n in numbers if 1 <= n <= len(releases)]
                
                if len(valid_numbers) == len(numbers):
                    selected_releases = [releases[n - 1] for n in sorted(valid_numbers)]
                    
                    # Show confirmation
                    self.console.print(f"\n[blue]ℹ[/blue] Selected {len(selected_releases)} release{'s' if len(selected_releases) != 1 else ''}:")
                    for i, release in enumerate(selected_releases, 1):
                        self.console.print(f"  {i}. [yellow]{release.album}[/yellow] by [green]{release.artist}[/green]")
                    
                    if Confirm.ask("\n[bold]Proceed with download?[/bold]", default=True):
                        self.console.print()
                        auto_download_all = Confirm.ask(
                            "[bold cyan]Automatically download ALL tracks from ALL selected releases?[/bold cyan]\n"
                            "[dim]If yes, will skip manual track selection for each release.[/dim]",
                            default=True
                        )
                        
                        if auto_download_all:
                            self.console.print("[bold green]✓[/bold green] Will automatically download all tracks from all selected releases.")
                            return (selected_releases, True)
                        else:
                            self.console.print("[blue]ℹ[/blue] Will prompt for track selection for each release.")
                            return (selected_releases, False)
                    else:
                        self.console.print("[yellow]⚠[/yellow] Selection cancelled. Returning to selection menu...")
                        self.console.print()
                        # Return None to signal we should go back to the main selection menu
                        return None
                else:
                    invalid = numbers - set(valid_numbers)
                    self.console.print(f"[bold red]✗[/bold red] Invalid numbers: {', '.join(map(str, invalid))}. Available: 1-{len(releases)}")
                    
            except (ValueError, KeyboardInterrupt):
                self.console.print("[bold red]✗[/bold red] Invalid format. Use numbers separated by commas (e.g., 1,3,5) or ranges (e.g., 1-3,5)")
    
    def _select_range_releases(self, releases: List[MusicBrainzSong]) -> Optional[Tuple[List[MusicBrainzSong], bool]]:
        """
        Select a range of releases.
        Returns: (list of selected releases, auto_download_all_tracks flag)
        """
        while True:
            try:
                choice = Prompt.ask("[bold]Enter range[/bold] (e.g., 1-5)", default="")
                
                if choice.lower() in ['q', 'quit', 'cancel']:
                    self.console.print("[yellow]⚠[/yellow] Selection cancelled. Returning to selection menu...")
                    self.console.print()
                    return None
                
                if '-' not in choice:
                    self.console.print("[bold red]✗[/bold red] Please enter a range in format 'start-end' (e.g., 1-5)")
                    continue
                
                start, end = map(int, choice.split('-'))
                
                if start < 1 or end > len(releases) or start > end:
                    self.console.print(f"[bold red]✗[/bold red] Invalid range. Please enter numbers between 1 and {len(releases)}")
                    continue
                
                selected_releases = releases[start - 1:end]
                
                # Show confirmation
                self.console.print(f"\n[blue]ℹ[/blue] Selected releases {start}-{end} ({len(selected_releases)} release{'s' if len(selected_releases) != 1 else ''}):")
                for i, release in enumerate(selected_releases, start):
                    self.console.print(f"  {i}. [yellow]{release.album}[/yellow] by [green]{release.artist}[/green]")
                
                if Confirm.ask("\n[bold]Proceed with download?[/bold]", default=True):
                    self.console.print()
                    auto_download_all = Confirm.ask(
                        "[bold cyan]Automatically download ALL tracks from ALL selected releases?[/bold cyan]\n"
                        "[dim]If yes, will skip manual track selection for each release.[/dim]",
                        default=True
                    )
                    
                    if auto_download_all:
                        self.console.print("[bold green]✓[/bold green] Will automatically download all tracks from all selected releases.")
                        return (selected_releases, True)
                    else:
                        self.console.print("[blue]ℹ[/blue] Will prompt for track selection for each release.")
                        return (selected_releases, False)
                else:
                    self.console.print("[yellow]⚠[/yellow] Selection cancelled. Returning to selection menu...")
                    self.console.print()
                    # Return None to signal we should go back to the main selection menu
                    return None
                    
            except (ValueError, KeyboardInterrupt):
                self.console.print("[bold red]✗[/bold red] Invalid format. Please enter range as 'start-end' (e.g., 1-5)")
    
    def _parse_duration_to_minutes(self, duration_str: Optional[str]) -> float:
        """Parse duration string (MM:SS or HH:MM:SS) to minutes."""
        if not duration_str or duration_str == "—":
            return 0.0
        
        try:
            parts = duration_str.split(':')
            if len(parts) == 2:  # MM:SS
                minutes, seconds = map(int, parts)
                return minutes + seconds / 60.0
            elif len(parts) == 3:  # HH:MM:SS
                hours, minutes, seconds = map(int, parts)
                return hours * 60 + minutes + seconds / 60.0
        except (ValueError, AttributeError):
            pass
        return 0.0
    
    def _estimate_disk_space(self, releases: List[MusicBrainzSong], quality: str, search_service=None) -> Tuple[str, int, float]:
        """
        Estimate disk space needed for downloading releases.
        Returns: (formatted_size, total_tracks, total_minutes)
        """
        # Bitrate estimates (MB per minute of audio)
        bitrate_estimates = {
            'audio': 1.4,      # ~192 kbps MP3
            'best': 2.4,       # ~320 kbps MP3
            'worst': 0.7,      # ~96 kbps MP3
        }
        
        mb_per_minute = bitrate_estimates.get(quality, 1.4)
        
        total_minutes = 0.0
        total_tracks = 0
        
        # Try to get actual track info for better estimates
        if search_service:
            sample_size = min(3, len(releases))
            sample_releases = releases[:sample_size]
            
            sample_tracks = 0
            sample_minutes = 0.0
            
            for release in sample_releases:
                try:
                    source = getattr(release, 'source', 'musicbrainz')
                    release_info = search_service.get_release_info(release.mbid, source=source)
                    if release_info and release_info.tracks:
                        sample_tracks += len(release_info.tracks)
                        for track in release_info.tracks:
                            track_minutes = self._parse_duration_to_minutes(track.duration)
                            sample_minutes += track_minutes
                except Exception:
                    pass
            
            if sample_tracks > 0:
                avg_tracks_per_release = sample_tracks / sample_size
                avg_minutes_per_track = sample_minutes / sample_tracks if sample_tracks > 0 else 4.0
                
                total_tracks = int(avg_tracks_per_release * len(releases))
                total_minutes = avg_minutes_per_track * total_tracks
            else:
                avg_tracks_per_release = 10
                avg_minutes_per_track = 4.0
                total_tracks = int(avg_tracks_per_release * len(releases))
                total_minutes = avg_minutes_per_track * total_tracks
        else:
            avg_tracks_per_release = 10
            avg_minutes_per_track = 4.0
            total_tracks = int(avg_tracks_per_release * len(releases))
            total_minutes = avg_minutes_per_track * total_tracks
        
        # Calculate total size in MB
        total_size_mb = total_minutes * mb_per_minute
        
        # Format size
        if total_size_mb < 1024:
            formatted_size = f"{total_size_mb:.1f} MB"
        else:
            formatted_size = f"{total_size_mb / 1024:.2f} GB"
        
        return formatted_size, total_tracks, total_minutes
    
    def _filter_unknown_year_duplicates(self, releases: List[MusicBrainzSong]) -> List[MusicBrainzSong]:
        """Filter out releases in 'Unknown Year' that are duplicates of releases with dates."""
        # Build a set of (normalized_album, normalized_artist) tuples for releases with dates
        releases_with_dates = set()
        for release in releases:
            if release.release_date and len(release.release_date) >= 4:
                album = normalize_string(release.album)
                artist = normalize_string(release.artist)
                if album and artist:
                    releases_with_dates.add((album, artist))
        
        # Filter out releases without dates that match releases with dates
        filtered = []
        filtered_count = 0
        for release in releases:
            has_date = release.release_date and len(release.release_date) >= 4
            if has_date:
                filtered.append(release)
            else:
                album = normalize_string(release.album)
                artist = normalize_string(release.artist)
                if album and artist and (album, artist) in releases_with_dates:
                    filtered_count += 1
                else:
                    filtered.append(release)
        
        if filtered_count > 0:
            self.console.print(f"[blue]ℹ[/blue] Filtered out {filtered_count} duplicate release{'s' if filtered_count != 1 else ''} from 'Unknown Year' category.")
        
        return filtered
    
    def _confirm_all_releases(self, releases: List[MusicBrainzSong], quality: str = "audio", search_service=None) -> Optional[Tuple[List[MusicBrainzSong], bool]]:
        """Confirm downloading all releases with disk space estimate."""
        # Filter out "Unknown Year" duplicates before processing
        filtered_releases = self._filter_unknown_year_duplicates(releases)
        
        if len(filtered_releases) < len(releases):
            self.console.print(f"[blue]ℹ[/blue] Filtered releases: {len(releases)} → {len(filtered_releases)} (removed duplicates from 'Unknown Year')")
        
        # Ask if user wants to exclude "Unknown Year" releases
        unknown_year_count = sum(1 for r in filtered_releases if not r.release_date or len(r.release_date) < 4)
        if unknown_year_count > 0:
            self.console.print(f"\n[blue]ℹ[/blue] Found {unknown_year_count} release{'s' if unknown_year_count != 1 else ''} in 'Unknown Year' category.")
            exclude_unknown = Confirm.ask(
                "[bold]Exclude 'Unknown Year' releases from download?[/bold]",
                default=True
            )
            
            if exclude_unknown:
                releases_with_dates = [r for r in filtered_releases if r.release_date and len(r.release_date) >= 4]
                self.console.print(f"[blue]ℹ[/blue] Excluding {unknown_year_count} release{'s' if unknown_year_count != 1 else ''} from 'Unknown Year' category.")
                filtered_releases = releases_with_dates
        
        if not filtered_releases:
            self.console.print("[yellow]⚠[/yellow] No releases to download after filtering.")
            return ([], False)
        
        self.console.print(f"[bold yellow]⚠[/bold yellow] This will download ALL {len(filtered_releases)} release{'s' if len(filtered_releases) != 1 else ''}!")
        
        # Estimate disk space (will be wrapped with spinner by caller if needed)
        estimated_size, total_tracks, total_minutes = self._estimate_disk_space(filtered_releases, quality, search_service)
        
        # Format time estimate
        estimated_time_minutes = total_tracks
        if estimated_time_minutes < 60:
            time_estimate = f"~{estimated_time_minutes} minutes"
        else:
            hours = estimated_time_minutes // 60
            minutes = estimated_time_minutes % 60
            time_estimate = f"~{hours}h {minutes}m" if minutes > 0 else f"~{hours} hours"
        
        self.console.print(f"[blue]ℹ[/blue] Estimated disk space: [bold cyan]{estimated_size}[/bold cyan]")
        self.console.print(f"[blue]ℹ[/blue] Estimated tracks: [cyan]{total_tracks}[/cyan] (~{total_minutes:.0f} minutes of music)")
        self.console.print(f"[blue]ℹ[/blue] Estimated time: [cyan]{time_estimate}[/cyan]")
        self.console.print("[blue]ℹ[/blue] This may take a very long time and use significant disk space.")
        
        # Show a preview
        self.console.print("\n[bold]Preview of releases to download:[/bold]")
        for i, release in enumerate(filtered_releases[:5], 1):
            self.console.print(f"  {i}. [yellow]{release.album}[/yellow] by [green]{release.artist}[/green]")
        
        if len(filtered_releases) > 5:
            self.console.print(f"  ... and {len(filtered_releases) - 5} more release{'s' if len(filtered_releases) - 5 != 1 else ''}")
        
        if Confirm.ask("\n[bold red]Are you sure you want to download ALL releases?[/bold red]", default=False):
            self.console.print(f"[bold green]✓[/bold green] Confirmed! Will download all {len(filtered_releases)} release{'s' if len(filtered_releases) != 1 else ''}.")
            
            self.console.print()
            auto_download_all = Confirm.ask(
                "[bold cyan]Automatically download ALL tracks from ALL releases?[/bold cyan]\n"
                "[dim]If yes, will skip manual track selection for each release.[/dim]",
                default=True
            )
            
            if auto_download_all:
                self.console.print("[bold green]✓[/bold green] Will automatically download all tracks from all releases.")
                return (filtered_releases, True)
            else:
                self.console.print("[blue]ℹ[/blue] Will prompt for track selection for each release.")
                return (filtered_releases, False)
        else:
            self.console.print("[yellow]⚠[/yellow] Download cancelled. Returning to selection menu...")
            self.console.print()
            # Return None to signal we should go back to the main selection menu
            return None

