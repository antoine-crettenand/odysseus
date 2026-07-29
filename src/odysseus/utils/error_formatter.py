"""
Error formatting utility for consistent error message formatting.
Consolidates error formatting logic from various modules.
"""

from typing import Optional, Callable, Any
from ..utils.colors import Colors


class ErrorFormatter:
    """Utility class for formatting error messages consistently."""

    @staticmethod
    def format_command_error(error: Exception, quiet: bool = False,
                           progress_callback: Optional[Callable] = None,
                           has_next: bool = False) -> str:
        if isinstance(error, FileNotFoundError):
            cmd_name = str(error).split("'")[1] if "'" in str(error) else "command"
            if "yt-dlp" in cmd_name:
                install_cmd = "pip install yt-dlp"
            elif "youtube-dl" in cmd_name:
                install_cmd = "pip install youtube-dl"
            else:
                install_cmd = f"pip install {cmd_name}"
            error_msg = f"{cmd_name} not found. Please install it with: {install_cmd}"
        else:
            error_msg = (
                error.stderr[:200] if hasattr(error, 'stderr') and error.stderr
                else error.stdout[:200] if hasattr(error, 'stdout') and error.stdout
                else str(error)[:200]
            )

        if not quiet and not progress_callback:
            msg = f"Strategy failed: {error_msg}"
            try:
                from rich.console import Console
                Console().print(f"[bold red]✗[/bold red] {msg}")
                if has_next:
                    Console().print("[blue]ℹ[/blue] Trying next strategy...")
            except ImportError:
                print(f"{Colors.red('❌')} {msg}")
                if has_next:
                    print(f"{Colors.blue('ℹ')} Trying next strategy...")

        return error_msg

    @staticmethod
    def format_strategy_error(error: Exception, strategy_num: int, quiet: bool = False,
                            progress_callback: Optional[Callable] = None,
                            has_next: bool = False) -> str:
        return f"Strategy {strategy_num} failed: {ErrorFormatter.format_command_error(error, quiet, progress_callback, has_next)}"

    @staticmethod
    def format_network_error(error: Exception, url: Optional[str] = None) -> str:
        error_str = str(error)[:200]
        return f"Network error fetching {url}: {error_str}" if url else f"Network error: {error_str}"

    @staticmethod
    def format_download_error(error: Exception, url: Optional[str] = None) -> str:
        error_str = str(error)
        if "No such file or directory" in error_str:
            if "youtube-dl" in error_str:
                return "youtube-dl not found. Please install yt-dlp with: pip install yt-dlp"
            elif "yt-dlp" in error_str:
                return "yt-dlp not found. Please install it with: pip install yt-dlp"

        if url:
            return f"Error downloading video from {url}: {error_str[:200]}"
        return f"Error downloading video: {error_str[:200]}"
