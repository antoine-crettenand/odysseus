"""
Display Formatters Module
Handles formatting and displaying of search results, tables, and UI elements.
"""

from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich import box

from ..models.search_results import SearchResult, MusicBrainzSong, YouTubeVideo
from ..models.releases import ReleaseInfo
from .styling import Styling


class DisplayFormatters:
    """Formatters for displaying search results and UI elements."""
    
    def __init__(self, console: Console):
        self.console = console
        self.styling = Styling(console)
    
    def create_header_panel(self, title: str, subtitle: Optional[str] = None) -> Panel:
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
    
    def format_score(self, score: int) -> Text:
        """Format score with color based on value."""
        if score >= 90:
            return Text(str(score), style="bold green")
        elif score >= 70:
            return Text(str(score), style="bold yellow")
        else:
            return Text(str(score), style="bold red")
    
    def format_track_number(self, number: int) -> str:
        """Format track number with color."""
        return f"[bold white]{number:2d}.[/bold white]"
    
    def display_search_results(self, results: List[SearchResult], search_type: str):
        """Display search results in a beautiful table."""
        if not results:
            self.console.print(f"[bold red]✗[/bold red] No {search_type} results found.")
            return
        
        # Create header
        self.console.print()
        self.console.print(self.create_header_panel(
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
        table.add_column("Artist", style="green", width=30, no_wrap=False)
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
                score = self.format_score(result.score)
            
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
        self.console.print(self.create_header_panel(
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
            if track.artist and track.artist != release_info.artist:
                artist = track.artist
            elif track.artist:
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
        self.console.print(self.create_header_panel(
            "📀 DISCOGRAPHY",
            f"Found {len(releases)} release{'s' if len(releases) != 1 else ''}"
        ))
        self.console.print()
        
        # Define type priority for sorting
        type_priority = {
            'Album': 1, 'EP': 2, 'Single': 3, 'Compilation': 4, 'Live': 5,
            'Soundtrack': 6, 'Spokenword': 7, 'Interview': 8, 'Audiobook': 9, 'Other': 10
        }
        
        def get_type_priority(release: MusicBrainzSong) -> int:
            release_type = release.release_type or "Other"
            return type_priority.get(release_type, 99)
        
        # Group releases by year (use original_release_date if available, otherwise release_date)
        # This ensures re-releases are grouped with their original release year
        releases_by_year = {}
        for release in releases:
            # Prefer original_release_date for grouping (shows when the album was originally released)
            date_to_use = release.original_release_date or release.release_date
            year = date_to_use[:4] if date_to_use and len(date_to_use) >= 4 else "Unknown Year"
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
                if release.release_date and len(release.release_date) >= 4:
                    release_date = release.release_date
                else:
                    release_date = "—"
                release_type = Text(release.release_type, style="bold magenta") if release.release_type else Text("—", style="dim")
                score = self.format_score(release.score) if release.score else Text("—", style="dim")
                
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
    
    def display_download_progress(self, current: int, total: int, release_name: str):
        """Display download progress for releases."""
        self.console.print()
        self.console.print(Panel(
            f"[bold white]Release {current}/{total}[/bold white]\n[yellow]{release_name}[/yellow]",
            border_style="blue",
            box=box.ROUNDED,
            padding=(1, 2)
        ))
    
    def display_track_listing_simple(self, tracks: List, release_name: str):
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
        summary_content += f"[dim blue]ℹ[/dim blue] [dim]Releases processed: {total}[/dim]"
        
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
    
    def display_track_download_result(self, track_title: str, success: bool, path: Optional[str] = None, file_existed: bool = False):
        """Display track download result."""
        if success:
            if file_existed:
                self.console.print(f"[bold yellow]✓[/bold yellow] Use existing file: [green]{track_title}[/green]")
            else:
                self.console.print(f"[bold green]✓[/bold green] Downloaded: [green]{track_title}[/green]")
            if path:
                self.styling.log_path(path)
        else:
            self.console.print(f"[bold red]✗[/bold red] Failed: [red]{track_title}[/red]")
    
    def display_download_strategy_attempt(self, strategy_num: int, total_strategies: int):
        """Display download strategy attempt."""
        self.styling.log_technical(f"Trying strategy {strategy_num}...")
    
    def display_download_strategy_result(self, strategy_num: int, success: bool, error: Optional[str] = None):
        """Display download strategy result."""
        if success:
            self.console.print(f"[bold green]✓[/bold green] Success with strategy {strategy_num}")
        else:
            if error:
                self.styling.log_error(f"Strategy {strategy_num} failed: {error}")
            else:
                self.styling.log_error(f"Strategy {strategy_num} failed")
            if strategy_num < 5:
                self.styling.log_technical("Trying next strategy...")
    
    def display_download_info(self, url: str, quality: str, audio_only: bool, save_location: str, metadata: Optional[dict] = None):
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

