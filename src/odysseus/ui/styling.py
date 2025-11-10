"""
Enhanced styling utilities for Odysseus CLI.
Provides dimmed text for logs/technical messages, ASCII art, and animations.
"""

from typing import Optional
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.align import Align
from rich import box


class Styling:
    """Enhanced styling utilities for CLI output."""
    
    def __init__(self, console: Console):
        self.console = console
    
    @staticmethod
    def dim(text: str) -> str:
        """Apply dimmed styling to text (for logs, technical messages, paths)."""
        return f"[dim]{text}[/dim]"
    
    @staticmethod
    def dim_cyan(text: str) -> str:
        """Apply dimmed cyan styling (for technical info messages)."""
        return f"[dim cyan]{text}[/dim cyan]"
    
    @staticmethod
    def dim_yellow(text: str) -> str:
        """Apply dimmed yellow styling (for warnings/technical notes)."""
        return f"[dim yellow]{text}[/dim yellow]"
    
    @staticmethod
    def dim_blue(text: str) -> str:
        """Apply dimmed blue styling (for info messages)."""
        return f"[dim blue]{text}[/dim blue]"
    
    @staticmethod
    def dim_red(text: str) -> str:
        """Apply dimmed red styling (for error details)."""
        return f"[dim red]{text}[/dim red]"
    
    def log_info(self, message: str, icon: str = "ℹ"):
        """Print a dimmed info log message."""
        self.console.print(f"{self.dim_blue(icon)} {self.dim(message)}")
    
    def log_warning(self, message: str, icon: str = "⚠"):
        """Print a dimmed warning log message."""
        self.console.print(f"{self.dim_yellow(icon)} {self.dim(message)}")
    
    def log_error(self, message: str, icon: str = "✗"):
        """Print a dimmed error log message."""
        self.console.print(f"{self.dim_red(icon)} {self.dim(message)}")
    
    def log_technical(self, message: str):
        """Print a dimmed technical/log message."""
        self.console.print(self.dim(message))
    
    def log_path(self, path: str):
        """Print a dimmed path message (matching existing style)."""
        self.console.print(f"  {self.dim(f'Path: {path}')}")
    
    def get_ascii_art(self, art_type: str) -> str:
        """Get ASCII art for different contexts."""
        arts = {
            "music_note": """
    ♪ ♫ ♬ ♭ ♮ ♯
            """,
            "vinyl": """
    ╔═══════════╗
    ║   ╱╲╱╲   ║
    ║  ╱  ╲  ╲  ║
    ║ ╱   ╲   ╲ ║
    ║╱     ╲    ║
    ║       ╲   ║
    ╚═══════════╝
            """,
            "wave": """
    ~~~~~ ~~~~~ ~~~~~
            """,
            "download": """
    ⬇  ⬇  ⬇
            """,
            "success": """
    ✨ ✨ ✨
            """,
            "search": """
    🔍  🔍  🔍
            """,
            "sparkles": """
    ✨  ✨  ✨
            """,
            "notes": """
    ♪  ♫  ♬
            """,
            "checkmark": """
    ✓  ✓  ✓
            """,
        }
        return arts.get(art_type, "").strip()
    
    def print_ascii_header(self, title: str, art_type: Optional[str] = None, style: str = "cyan"):
        """Print a header with optional ASCII art."""
        if art_type:
            art = self.get_ascii_art(art_type)
            if art:
                self.console.print(f"[{style}]{art}[/{style}]")
                self.console.print()
        
        # Create a styled panel for the title
        header_text = Text(title, style=f"bold {style}")
        panel = Panel(
            Align.center(header_text),
            border_style=style,
            box=box.ROUNDED,
            padding=(1, 2)
        )
        self.console.print(panel)
        self.console.print()
    
    def print_animated_dots(self, message: str, count: int = 3, style: str = "cyan"):
        """Print message with animated dots (for loading states)."""
        dots = "." * count
        self.console.print(f"[{style}]{message}{dots}[/{style}]", end="")
    
    def get_spinner_frames(self, spinner_type: str = "dots") -> list:
        """Get spinner animation frames."""
        spinners = {
            "dots": ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
            "music": ["♪", "♫", "♬", "♭", "♮", "♯"],
            "arrow": ["←", "↖", "↑", "↗", "→", "↘", "↓", "↙"],
            "wave": ["▁", "▃", "▅", "▇", "█", "▇", "▅", "▃"],
        }
        return spinners.get(spinner_type, spinners["dots"])

