"""
Display management for Odysseus CLI with Rich components.
Modern, beautiful terminal interface with animations and colors.
"""

from typing import List, Optional, Any, Dict, Union, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn, DownloadColumn, TransferSpeedColumn
from rich.text import Text
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.align import Align
from rich import box

from ..models.search_results import SearchResult, MusicBrainzSong, YouTubeVideo
from ..models.releases import ReleaseInfo, Track
from ..utils.string_utils import normalize_string


class DisplayManager:
    """Manages display formatting for search results and other UI elements using Rich."""
    
    def __init__(self):
        self.console = Console()
        self.separator_length = 60
    
    def _create_header_panel(self, title: str, subtitle: str = None) -> Panel:
        """Create a styled header panel."""
        header_text = Text(title, style="bold cyan")
        if subtitle:
            header_text.append(f"\n{subtitle}", style="dim")
        return Panel(
            Align.center(header_text),
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2)
        )
    
    def _format_score(self, score: int) -> Text:
        """Format score with color based on value."""
        if score >= 90:
            return Text(str(score), style="bold green")
        elif score >= 70:
            return Text(str(score), style="bold yellow")
        else:
            return Text(str(score), style="bold red")
    
    def display_search_results(self, results: List[SearchResult], search_type: str):
        """Display search results in a beautiful table."""
        if not results:
            self.console.print(f"[bold red]✗[/bold red] No {search_type} results found.")
            return
        
        # Create header
        self.console.print()
        self.console.print(self._create_header_panel(
            f"🎵 {search_type.upper()} SEARCH RESULTS",
            f"Found {len(results)} result{'s' if len(results) != 1 else ''}"
        ))
        self.console.print()
        
        # Create table
        table = Table(
            show_header=True,
            header_style="bold magenta",
            box=box.ROUNDED,
            border_style="blue",
            show_lines=True
        )
        
        table.add_column("#", style="bold white", width=4, justify="center")
        table.add_column("Title", style="white", width=30)
        table.add_column("Artist", style="green", width=30, no_wrap=False)  # Increased width for collaborative artists
        table.add_column("Album", style="yellow", width=25, no_wrap=False)
        table.add_column("Type", style="magenta", width=12, justify="center")
        table.add_column("Release Date", style="cyan", width=12, justify="center")
        table.add_column("Score", style="bold", width=8, justify="center")
        
        for i, result in enumerate(results, 1):
            title = result.get_display_name()
            artist = result.artist or "Unknown"
            album = ""
            release_date = ""
            release_type = Text("—", style="dim")
            score = Text("—", style="dim")
            
            if hasattr(result, 'album') and result.album:
                album = result.album
            if hasattr(result, 'release_date') and result.release_date:
                release_date = result.release_date
            if hasattr(result, 'release_type') and result.release_type:
                release_type = Text(result.release_type, style="bold magenta")
            if hasattr(result, 'score') and result.score:
                score = self._format_score(result.score)
            
            table.add_row(
                str(i),
                title,
                artist,
                album,
                release_type,
                release_date,
                score
            )
        
        self.console.print(table)
        self.console.print()
    
    def display_youtube_results(self, videos: List[YouTubeVideo]):
        """Display YouTube search results in a beautiful table."""
        if not videos:
            self.console.print("[bold red]✗[/bold red] No YouTube results found.")
            return
        
        # Create header
        self.console.print()
        self.console.print(self._create_header_panel(
            "📺 YOUTUBE SEARCH RESULTS",
            f"Found {len(videos)} video{'s' if len(videos) != 1 else ''}"
        ))
        self.console.print()
        
        # Create table
        table = Table(
            show_header=True,
            header_style="bold magenta",
            box=box.ROUNDED,
            border_style="red",
            show_lines=True
        )
        
        table.add_column("#", style="bold white", width=4, justify="center")
        table.add_column("Title", style="white", width=40, no_wrap=False)
        table.add_column("Channel", style="blue", width=20)
        table.add_column("Duration", style="cyan", width=10, justify="center")
        table.add_column("Views", style="magenta", width=12, justify="right")
        table.add_column("Published", style="dim", width=12)
        
        for i, video in enumerate(videos, 1):
            title = video.title or "No title"
            channel = video.channel or "Unknown"
            duration = video.duration or "—"
            views = video.views or "—"
            publish_time = video.publish_time or "—"
            
            table.add_row(
                str(i),
                title,
                channel,
                duration,
                views,
                publish_time
            )
        
        self.console.print(table)
        self.console.print()
    
    def display_track_listing(self, release_info: ReleaseInfo):
        """Display the track listing for a release in a beautiful format."""
        # Create header panel
        header_content = f"[bold yellow]{release_info.title}[/bold yellow]"
        header_content += f"\n[green]by {release_info.artist}[/green]"
        if release_info.release_type:
            header_content += f"\n[bold magenta]Type: {release_info.release_type}[/bold magenta]"
        if release_info.release_date:
            header_content += f"\n[cyan]Released: {release_info.release_date}[/cyan]"
        if release_info.genre:
            header_content += f"\n[magenta]Genre: {release_info.genre}[/magenta]"
        
        self.console.print()
        self.console.print(Panel(
            header_content,
            title="[bold cyan]🎼 TRACK LISTING[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2)
        ))
        self.console.print()
        
        # Create track table
        table = Table(
            show_header=True,
            header_style="bold magenta",
            box=box.SIMPLE,
            border_style="blue",
            show_lines=False
        )
        
        table.add_column("#", style="bold white", width=4, justify="right")
        table.add_column("Track Title", style="white", width=50)
        table.add_column("Duration", style="cyan", width=10, justify="center")
        table.add_column("Artist", style="green", width=25)
        
        for track in release_info.tracks:
            duration = track.duration or "—"
            # Show track artist if it's different from release artist, or if track artist exists
            # This handles cases where tracks have collaborative artists that match the release artist
            if track.artist and track.artist != release_info.artist:
                artist = track.artist
            elif track.artist:
                # Track artist matches release artist - show it anyway for clarity
                artist = track.artist
            else:
                artist = ""
            
            table.add_row(
                str(track.position),
                track.title,
                duration,
                artist
            )
        
        self.console.print(table)
        self.console.print()
    
    def display_discography(self, releases: List[MusicBrainzSong]):
        """Display discography grouped by year with global numbering, sorted by type within each year."""
        # Create header
        self.console.print()
        self.console.print(self._create_header_panel(
            "📀 DISCOGRAPHY",
            f"Found {len(releases)} release{'s' if len(releases) != 1 else ''}"
        ))
        self.console.print()
        
        # Define type priority for sorting (lower number = higher priority)
        type_priority = {
            'Album': 1,
            'EP': 2,
            'Single': 3,
            'Compilation': 4,
            'Live': 5,
            'Soundtrack': 6,
            'Spokenword': 7,
            'Interview': 8,
            'Audiobook': 9,
            'Other': 10
        }
        
        def get_type_priority(release: MusicBrainzSong) -> int:
            """Get priority for sorting releases by type."""
            release_type = release.release_type or "Other"
            return type_priority.get(release_type, 99)
        
        # Group releases by year
        releases_by_year = {}
        for release in releases:
            year = release.release_date[:4] if release.release_date and len(release.release_date) >= 4 else "Unknown Year"
            if year not in releases_by_year:
                releases_by_year[year] = []
            releases_by_year[year].append(release)
        
        # Sort years in descending order
        sorted_years = sorted(releases_by_year.keys(), reverse=True)
        
        # Create ordered list that matches the display order
        ordered_releases = []
        global_counter = 1
        
        for year in sorted_years:
            year_releases = releases_by_year[year]
            
            # Sort releases within year by type priority, then by release date
            year_releases.sort(key=lambda r: (
                get_type_priority(r),
                r.release_date or ""
            ))
            
            # Year header
            self.console.print(Panel(
                f"[bold cyan]{year}[/bold cyan]",
                border_style="cyan",
                box=box.SIMPLE,
                padding=(0, 1)
            ))
            
            # Create table for this year's releases
            table = Table(
                show_header=False,
                box=box.SIMPLE,
                border_style="dim",
                show_lines=False,
                padding=(0, 1)
            )
            
            table.add_column("#", style="bold white", width=4, justify="right")
            table.add_column("Album", style="yellow", width=40)
            table.add_column("Artist", style="green", width=25)
            table.add_column("Type", style="magenta", width=12, justify="center")
            table.add_column("Release Date", style="cyan", width=15)
            table.add_column("Score", style="bold", width=8, justify="center")
            
            for release in year_releases:
                # Show release date if available (even if just a year like "2015")
                if release.release_date and len(release.release_date) >= 4:
                    release_date = release.release_date
                else:
                    release_date = "—"
                release_type = Text(release.release_type, style="bold magenta") if release.release_type else Text("—", style="dim")
                score = self._format_score(release.score) if release.score else Text("—", style="dim")
                
                table.add_row(
                    str(global_counter),
                    release.album,
                    release.artist,
                    release_type,
                    release_date,
                    score
                )
                
                ordered_releases.append(release)
                global_counter += 1
            
            self.console.print(table)
            self.console.print()
        
        return ordered_releases
    
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
        self.console.print(self._create_header_panel(
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
                return (selected, False)  # Manual track selection for single release
            elif choice == '2':
                selected = self._select_multiple_releases(releases)
                return (selected, False)  # Manual track selection for multiple releases
            elif choice == '3':
                selected = self._select_range_releases(releases)
                return (selected, False)  # Manual track selection for range
            elif choice == '4':
                return self._confirm_all_releases(releases, quality, search_service)
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
    
    def _select_multiple_releases(self, releases: List[MusicBrainzSong]) -> List[MusicBrainzSong]:
        """Select multiple releases by comma-separated numbers."""
        while True:
            try:
                choice = Prompt.ask("[bold]Enter release numbers[/bold] (e.g., 1,3,5 or 1-3,5)", default="")
                
                if choice.lower() in ['q', 'quit', 'cancel']:
                    return []
                
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
                        return selected_releases
                    else:
                        self.console.print("[yellow]⚠[/yellow] Selection cancelled.")
                        return []
                else:
                    invalid = numbers - set(valid_numbers)
                    self.console.print(f"[bold red]✗[/bold red] Invalid numbers: {', '.join(map(str, invalid))}. Available: 1-{len(releases)}")
                    
            except (ValueError, KeyboardInterrupt):
                self.console.print("[bold red]✗[/bold red] Invalid format. Use numbers separated by commas (e.g., 1,3,5) or ranges (e.g., 1-3,5)")
    
    def _select_range_releases(self, releases: List[MusicBrainzSong]) -> List[MusicBrainzSong]:
        """Select a range of releases."""
        while True:
            try:
                choice = Prompt.ask("[bold]Enter range[/bold] (e.g., 1-5)", default="")
                
                if choice.lower() in ['q', 'quit', 'cancel']:
                    return []
                
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
                    return selected_releases
                else:
                    self.console.print("[yellow]⚠[/yellow] Selection cancelled.")
                    return []
                    
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
    
    def _estimate_disk_space(self, releases: List[MusicBrainzSong], quality: str, search_service=None) -> tuple[str, int, float]:
        """
        Estimate disk space needed for downloading releases.
        Returns: (formatted_size, total_tracks, total_minutes)
        """
        # Bitrate estimates (MB per minute of audio)
        # These are approximate values for MP3 encoding
        bitrate_estimates = {
            'audio': 1.4,      # ~192 kbps MP3
            'best': 2.4,       # ~320 kbps MP3 (best audio quality)
            'worst': 0.7,      # ~96 kbps MP3 (worst quality)
        }
        
        mb_per_minute = bitrate_estimates.get(quality, 1.4)  # Default to audio quality
        
        total_minutes = 0.0
        total_tracks = 0
        
        # Try to get actual track info for better estimates
        if search_service:
            # Sample a few releases to get average track count and duration
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
                    # If we can't get info, use defaults
                    pass
            
            if sample_tracks > 0:
                # Calculate averages from sample
                avg_tracks_per_release = sample_tracks / sample_size
                avg_minutes_per_track = sample_minutes / sample_tracks if sample_tracks > 0 else 4.0
                
                total_tracks = int(avg_tracks_per_release * len(releases))
                total_minutes = avg_minutes_per_track * total_tracks
            else:
                # Fallback to defaults
                avg_tracks_per_release = 10  # Average tracks per album
                avg_minutes_per_track = 4.0  # Average 4 minutes per track
                total_tracks = int(avg_tracks_per_release * len(releases))
                total_minutes = avg_minutes_per_track * total_tracks
        else:
            # Use default estimates
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
                # Always keep releases with dates
                filtered.append(release)
            else:
                # Check if this release without a date matches a release with a date
                album = normalize_string(release.album)
                artist = normalize_string(release.artist)
                if album and artist and (album, artist) in releases_with_dates:
                    # This is a duplicate - skip it
                    filtered_count += 1
                else:
                    # Unique release without a date - keep it
                    filtered.append(release)
        
        if filtered_count > 0:
            self.console.print(f"[blue]ℹ[/blue] Filtered out {filtered_count} duplicate release{'s' if filtered_count != 1 else ''} from 'Unknown Year' category.")
        
        return filtered
    
    def _confirm_all_releases(self, releases: List[MusicBrainzSong], quality: str = "audio", search_service=None) -> List[MusicBrainzSong]:
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
            return []
        
        self.console.print(f"[bold yellow]⚠[/bold yellow] This will download ALL {len(filtered_releases)} release{'s' if len(filtered_releases) != 1 else ''}!")
        
        # Estimate disk space (with loading indicator if we need to fetch release info)
        if search_service:
            estimated_size, total_tracks, total_minutes = self.show_loading_spinner(
                "Calculating disk space estimate...",
                self._estimate_disk_space,
                filtered_releases,
                quality,
                search_service
            )
        else:
            estimated_size, total_tracks, total_minutes = self._estimate_disk_space(filtered_releases, quality, search_service)
        
        # Format time estimate (rough estimate: 1 minute per track for download + processing)
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
            
            # Ask if user wants to automatically download all tracks from all releases
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
            self.console.print("[yellow]⚠[/yellow] Download cancelled.")
            return ([], False)
    
    def display_download_progress(self, current: int, total: int, release_name: str):
        """Display download progress for releases."""
        self.console.print()
        self.console.print(Panel(
            f"[bold white]Release {current}/{total}[/bold white]\n[yellow]{release_name}[/yellow]",
            border_style="blue",
            box=box.ROUNDED,
            padding=(1, 2)
        ))
    
    def display_track_listing_simple(self, tracks: List[Any], release_name: str):
        """Display a simple track listing for download progress."""
        self.console.print(f"\n[cyan]Tracks in [yellow]{release_name}[/yellow]:[/cyan]")
        for track in tracks:
            duration_str = f" [dim]({track.duration})[/dim]" if track.duration else ""
            self.console.print(f"  [bold white]{track.position:2d}.[/bold white] [white]{track.title}[/white]{duration_str}")
    
    def display_download_options(self):
        """Display download options."""
        self.console.print("\n[bold]Download options:[/bold]")
        options_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        options_table.add_column("Option", style="bold white", width=3)
        options_table.add_column("Description", style="cyan")
        
        options_table.add_row("1", "Download all tracks")
        options_table.add_row("2", "Select specific tracks")
        options_table.add_row("3", "[red]Skip this release[/red]")
        
        self.console.print(options_table)
    
    def display_download_summary(self, downloaded: int, failed: int, total: int):
        """Display final download summary."""
        self.console.print()
        summary_content = f"[bold green]✓[/bold green] Total tracks downloaded: [green]{downloaded}[/green]\n"
        if failed > 0:
            summary_content += f"[bold red]✗[/bold red] Total tracks failed: [red]{failed}[/red]\n"
        summary_content += f"[blue]ℹ[/blue] Releases processed: [cyan]{total}[/cyan]"
        
        self.console.print(Panel(
            summary_content,
            title="[bold cyan]📊 FINAL DOWNLOAD SUMMARY[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2)
        ))
        self.console.print()
    
    def display_track_download_progress(self, track_num: int, track_title: str):
        """Display individual track download progress."""
        self.console.print(f"[cyan]Downloading track [bold white]{track_num}[/bold white]: [white]{track_title}[/white][/cyan]")
    
    def display_track_download_result(self, track_title: str, success: bool, path: str = None):
        """Display track download result."""
        if success:
            self.console.print(f"[bold green]✓[/bold green] Downloaded: [green]{track_title}[/green]")
            if path:
                self.console.print(f"  [dim]Path: {path}[/dim]")
        else:
            self.console.print(f"[bold red]✗[/bold red] Failed: [red]{track_title}[/red]")
    
    def display_download_strategy_attempt(self, strategy_num: int, total_strategies: int):
        """Display download strategy attempt."""
        self.console.print(f"[blue]Trying strategy [bold white]{strategy_num}[/bold white]...[/blue]")
    
    def display_download_strategy_result(self, strategy_num: int, success: bool, error: str = None):
        """Display download strategy result."""
        if success:
            self.console.print(f"[bold green]✓[/bold green] Success with strategy {strategy_num}")
        else:
            self.console.print(f"[bold red]✗[/bold red] Strategy {strategy_num} failed: {error}")
            if strategy_num < 5:
                self.console.print("[blue]ℹ[/blue] Trying next strategy...")
    
    def display_download_info(self, url: str, quality: str, audio_only: bool, save_location: str, metadata: Dict[str, Any] = None):
        """Display download information."""
        info_content = f"[cyan]Downloading:[/cyan] [blue]{url}[/blue]\n"
        info_content += f"[cyan]Quality:[/cyan] [yellow]{quality}[/yellow]\n"
        info_content += f"[cyan]Audio only:[/cyan] [yellow]{audio_only}[/yellow]\n"
        info_content += f"[cyan]Save location:[/cyan] [blue]{save_location}[/blue]"
        
        if metadata:
            artist = metadata.get('artist', 'Unknown')
            album = metadata.get('album', 'Unknown')
            year = metadata.get('year', 'Unknown Year')
            title = metadata.get('title', 'Unknown Title')
            info_content += f"\n[cyan]Organized as:[/cyan] [green]{artist}[/green]/[yellow]{album}[/yellow] ([cyan]{year}[/cyan])/[white]{title}[/white]"
        
        self.console.print()
        self.console.print(Panel(
            info_content,
            title="[bold cyan]📥 DOWNLOAD INFO[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2)
        ))
        self.console.print()
    
    def show_loading_spinner(self, message: str, task_func, *args, **kwargs):
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
    
    def _format_track_number(self, number: int) -> str:
        """Format track number with color."""
        return f"[bold white]{number:2d}.[/bold white]"
