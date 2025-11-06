"""
Color utility module for Odysseus CLI
Provides colored output functions for better user experience.
"""

import sys
from ..core.config import COLORS


class Colors:
    """Color utility class for terminal output."""
    
    @staticmethod
    def colorize(text: str, color: str) -> str:
        """Apply color to text if terminal supports it."""
        if not sys.stdout.isatty():
            return text  # Don't use colors if not in terminal
        
        color_code = COLORS.get(color.upper(), "")
        end_code = COLORS["END"]
        return f"{color_code}{text}{end_code}"
    
    @staticmethod
    def bold(text: str) -> str:
        """Make text bold."""
        return Colors.colorize(text, "BOLD")
    
    @staticmethod
    def red(text: str) -> str:
        """Make text red."""
        return Colors.colorize(text, "RED")
    
    @staticmethod
    def green(text: str) -> str:
        """Make text green."""
        return Colors.colorize(text, "GREEN")
    
    @staticmethod
    def yellow(text: str) -> str:
        """Make text yellow."""
        return Colors.colorize(text, "YELLOW")
    
    @staticmethod
    def blue(text: str) -> str:
        """Make text blue."""
        return Colors.colorize(text, "BLUE")
    
    @staticmethod
    def cyan(text: str) -> str:
        """Make text cyan."""
        return Colors.colorize(text, "CYAN")
    
    @staticmethod
    def magenta(text: str) -> str:
        """Make text magenta."""
        return Colors.colorize(text, "MAGENTA")
    
    @staticmethod
    def white(text: str) -> str:
        """Make text white."""
        return Colors.colorize(text, "WHITE")


def print_header(text: str):
    """Print a colored header."""
    print(Colors.bold(Colors.cyan(f"=== {text} ===")))


def print_success(text: str):
    """Print success message in green."""
    print(Colors.green(f"✓ {text}"))


def print_error(text: str):
    """Print error message in red."""
    print(Colors.red(f"✗ {text}"))


def print_warning(text: str):
    """Print warning message in yellow."""
    print(Colors.yellow(f"⚠ {text}"))


def print_info(text: str):
    """Print info message in blue."""
    print(Colors.blue(f"ℹ {text}"))


def print_separator(length: int = 60):
    """Print a colored separator line."""
    print(Colors.blue("-" * length))


def print_track_number(number: int) -> str:
    """Format track number with color."""
    return Colors.bold(Colors.white(f"{number:2d}."))


def print_score(score: int) -> str:
    """Format score with color based on value."""
    if score >= 90:
        return Colors.green(f"{score}")
    elif score >= 70:
        return Colors.yellow(f"{score}")
    else:
        return Colors.red(f"{score}")


def print_duration(duration: str) -> str:
    """Format duration with color."""
    return Colors.cyan(duration)


def print_views(views: str) -> str:
    """Format views with color."""
    return Colors.magenta(views)


def print_channel(channel: str) -> str:
    """Format channel name with color."""
    return Colors.blue(channel)


def print_artist(artist: str) -> str:
    """Format artist name with color."""
    return Colors.green(artist)


def print_album(album: str) -> str:
    """Format album name with color."""
    return Colors.yellow(album)


def print_title(title: str) -> str:
    """Format title with color."""
    return Colors.white(title)
