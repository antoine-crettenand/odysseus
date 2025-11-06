"""
YouTube Downloader Module
A module to download YouTube videos using yt-dlp.
"""

import os
import subprocess
import sys
import re
from typing import Dict, Any, Optional, List
from pathlib import Path
from ..core.config import (
    DOWNLOAD_CONFIG, ERROR_MESSAGES, SUCCESS_MESSAGES, 
    QUALITY_PRESETS, FILE_EXTENSIONS, DEFAULTS
)
from ..utils.colors import Colors


class YouTubeDownloader:
    """YouTube video downloader using yt-dlp."""
    
    def __init__(self, download_dir: Optional[str] = None):
        self.download_dir = Path(download_dir or DOWNLOAD_CONFIG["DEFAULT_DIR"])
        self.download_dir.mkdir(exist_ok=True)
        
        self.default_quality = DOWNLOAD_CONFIG["DEFAULT_QUALITY"]
        self.audio_format = DOWNLOAD_CONFIG["AUDIO_FORMAT"]
        self.timeout = DOWNLOAD_CONFIG["TIMEOUT"]
        
        # Check and update yt-dlp if needed
        self._ensure_yt_dlp_updated()
    
    def _ensure_yt_dlp_updated(self):
        """Ensure yt-dlp is up to date to avoid 403 errors."""
        try:
            print("Checking yt-dlp version...")
            result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                current_version = result.stdout.strip()
                print(f"Current yt-dlp version: {current_version}")
                
                # Try to update yt-dlp
                print("Updating yt-dlp to latest version...")
                update_result = subprocess.run(['pip3', 'install', '--upgrade', 'yt-dlp'], 
                                             capture_output=True, text=True)
                if update_result.returncode == 0:
                    print("✅ yt-dlp updated successfully")
                else:
                    print("⚠️  Could not update yt-dlp, continuing with current version")
            else:
                print("❌ yt-dlp not found, please install it with: pip install yt-dlp")
        except Exception as e:
            print(f"⚠️  Could not check yt-dlp version: {e}")
    
    def update_yt_dlp(self) -> bool:
        """Manually update yt-dlp."""
        try:
            print("Updating yt-dlp...")
            result = subprocess.run(['pip3', 'install', '--upgrade', 'yt-dlp'], 
                                  capture_output=True, text=True, check=True)
            print("✅ yt-dlp updated successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to update yt-dlp: {e}")
            return False
    
    def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        try:
            cmd = [
                'yt-dlp',
                '--dump-json',
                '--no-download',
                url
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return eval(result.stdout)  # Parse JSON output
            
        except subprocess.CalledProcessError as e:
            print(f"Error getting video info: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None
    
    def _sanitize_filename(self, filename: str) -> str:
        # Remove or replace invalid characters for filesystem
        invalid_chars = r'[<>:"/\\|?*]'
        sanitized = re.sub(invalid_chars, '_', filename)
        # Remove multiple consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        # Remove leading/trailing underscores and dots
        sanitized = sanitized.strip('_.')
        return sanitized
    
    def _create_organized_path(self, metadata: Optional[Dict[str, Any]] = None) -> Path:
        if not metadata:
            return self.download_dir
        
        # Extract metadata fields
        artist = metadata.get('artist', 'Unknown Artist')
        album = metadata.get('album', 'Unknown Album')
        year = metadata.get('year')
        title = metadata.get('title', 'Unknown Title')
        
        # Sanitize all components
        artist = self._sanitize_filename(artist)
        album = self._sanitize_filename(album)
        title = self._sanitize_filename(title)
        
        # Create folder structure: Artist/LP (release year)/
        artist_dir = self.download_dir / artist
        
        if year:
            lp_folder_name = f"{album} ({year})"
        else:
            lp_folder_name = album
        
        # Create the organized directory structure
        organized_dir = artist_dir / lp_folder_name
        organized_dir.mkdir(parents=True, exist_ok=True)
        
        return organized_dir
    
    def download(self, url: str, quality: str = "bestaudio", 
                      audio_only: bool = True, metadata: Optional[Dict[str, Any]] = None) -> Optional[Path]:
        try:
            # Determine download directory based on metadata
            download_dir = self._create_organized_path(metadata)
            
            # Create filename template based on metadata
            if metadata and metadata.get('title'):
                title = self._sanitize_filename(metadata['title'])
                if audio_only:
                    filename_template = f"{title}.%(ext)s"
                else:
                    filename_template = f"{title}.%(ext)s"
            else:
                filename_template = "%(title)s.%(ext)s"
            
            # Set output template
            output_template = str(download_dir / filename_template)
            
            # Import colors here to avoid circular imports
            from ..utils.colors import Colors
            
            print(f"Downloading: {Colors.blue(url)}")
            print(f"Quality: {Colors.cyan(quality)}")
            print(f"Audio only: {Colors.cyan(str(audio_only))}")
            print(f"Save location: {Colors.blue(str(download_dir))}")
            if metadata:
                artist = metadata.get('artist', 'Unknown')
                album = metadata.get('album', 'Unknown')
                year = metadata.get('year', 'Unknown Year')
                title = metadata.get('title', 'Unknown Title')
                print(f"Organized as: {Colors.green(artist)}/{Colors.yellow(album)} ({Colors.cyan(str(year))})/{Colors.white(title)}")
            print()
            
            # Try multiple strategies to bypass 403 errors
            strategies = [
                self._build_command_strategy_1,
                self._build_command_strategy_2,
                self._build_command_strategy_3,
                self._build_command_strategy_4,
                self._build_command_strategy_5
            ]
            
            for i, strategy in enumerate(strategies, 1):
                try:
                    # Use Rich console if available, otherwise fall back to print
                    try:
                        from rich.console import Console
                        console = Console()
                        console.print(f"[blue]Trying strategy [bold white]{i}[/bold white]...[/blue]")
                    except ImportError:
                        print(f"Trying strategy {Colors.bold(Colors.white(str(i)))}...")
                    
                    cmd = strategy(url, quality, audio_only, output_template)
                    
                    # Run download
                    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                    
                    # Find the downloaded file
                    downloaded_files = list(download_dir.glob("*"))
                    if downloaded_files:
                        # Get the most recently created file
                        latest_file = max(downloaded_files, key=os.path.getctime)
                        try:
                            from rich.console import Console
                            console = Console()
                            console.print(f"[bold green]✓[/bold green] Success with strategy {i}")
                        except ImportError:
                            print(f"{Colors.green('✅')} Success with strategy {i}")
                        return latest_file
                        
                except subprocess.CalledProcessError as e:
                    error_msg = e.stderr if e.stderr else str(e)
                    try:
                        from rich.console import Console
                        console = Console()
                        console.print(f"[bold red]✗[/bold red] Strategy {i} failed: {error_msg}")
                        if i < len(strategies):
                            console.print("[blue]ℹ[/blue] Trying next strategy...")
                    except ImportError:
                        print(f"{Colors.red('❌')} Strategy {i} failed: {error_msg}")
                        if i < len(strategies):
                            print(f"{Colors.blue('ℹ')} Trying next strategy...")
                    
                    if i < len(strategies):
                        continue
                    else:
                        raise Exception(f"All download strategies failed. Last error: {e}")
                
        except Exception as e:
            raise Exception(f"Error downloading video: {e}") from e
    
    def _has_chrome_cookies(self) -> bool:
        """Check if Chrome cookies database exists."""
        chrome_cookie_paths = [
            Path.home() / "Library/Application Support/Google/Chrome/Default/Cookies",
            Path.home() / "Library/Application Support/Google/Chrome/Profile 1/Cookies",
            Path.home() / ".config/google-chrome/Default/Cookies",
            Path.home() / ".config/google-chrome/Profile 1/Cookies",
            Path.home() / "AppData/Local/Google/Chrome/User Data/Default/Cookies",
            Path.home() / "AppData/Local/Google/Chrome/User Data/Profile 1/Cookies",
        ]
        
        for path in chrome_cookie_paths:
            if path.exists():
                return True
        return False
    
    def _build_command_strategy_1(self, url: str, quality: str, audio_only: bool, output_template: str) -> List[str]:
        """Strategy 1: Basic yt-dlp with user agent, optionally with cookies if available"""
        cmd = [
            'yt-dlp',
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            '--no-check-certificate',
            '--ignore-errors',
            '--no-warnings',
            '--extractor-args', 'youtube:player_client=web'
        ]
        
        # Only add cookies if Chrome is available
        if self._has_chrome_cookies():
            cmd.extend(['--cookies-from-browser', 'chrome'])
        
        if audio_only:
            cmd.extend([
                '-x',  # Extract audio
                '--audio-format', 'mp3',
                '--audio-quality', '0',
                '--postprocessor-args', 'ffmpeg:-b:a 320k'
            ])
        else:
            cmd.extend(['-f', quality])
        
        cmd.extend(['-o', output_template, url])
        return cmd
    
    def _build_command_strategy_2(self, url: str, quality: str, audio_only: bool, output_template: str) -> List[str]:
        """Strategy 2: Use different extractor and bypass age restriction"""
        cmd = [
            'yt-dlp',
            '--user-agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            '--age-limit', '0',  # Bypass age restriction
            '--no-check-certificate',
            '--ignore-errors',
            '--extractor-args', 'youtube:player_client=android,web',
            '--no-warnings'
        ]
        
        if audio_only:
            cmd.extend([
                '-x',
                '--audio-format', 'mp3',
                '--audio-quality', '0',
                '--postprocessor-args', 'ffmpeg:-b:a 320k'
            ])
        else:
            cmd.extend(['-f', quality])
        
        cmd.extend(['-o', output_template, url])
        return cmd
    
    def _build_command_strategy_3(self, url: str, quality: str, audio_only: bool, output_template: str) -> List[str]:
        """Strategy 3: Use different player client and referer"""
        cmd = [
            'yt-dlp',
            '--user-agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            '--referer', 'https://www.youtube.com/',
            '--no-check-certificate',
            '--ignore-errors',
            '--extractor-args', 'youtube:player_client=ios',
            '--no-warnings'
        ]
        
        if audio_only:
            cmd.extend([
                '-x',
                '--audio-format', 'mp3',
                '--audio-quality', '0',
                '--postprocessor-args', 'ffmpeg:-b:a 320k'
            ])
        else:
            cmd.extend(['-f', quality])
        
        cmd.extend(['-o', output_template, url])
        return cmd
    
    def _build_command_strategy_4(self, url: str, quality: str, audio_only: bool, output_template: str) -> List[str]:
        """Strategy 4: Use yt-dlp with all bypass options"""
        cmd = [
            'yt-dlp',
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0',
            '--cookies-from-browser', 'firefox',
            '--no-check-certificate',
            '--ignore-errors',
            '--extractor-args', 'youtube:player_client=android_music,web',
            '--sleep-requests', '1',  # Add delay between requests
            '--sleep-interval', '1',
            '--max-sleep-interval', '5',
            '--no-warnings',
            '--retries', '3'
        ]
        
        if audio_only:
            cmd.extend([
                '-x',
                '--audio-format', 'mp3',
                '--audio-quality', '0',
                '--postprocessor-args', 'ffmpeg:-b:a 320k'
            ])
        else:
            cmd.extend(['-f', quality])
        
        cmd.extend(['-o', output_template, url])
        return cmd
    
    def _build_command_strategy_5(self, url: str, quality: str, audio_only: bool, output_template: str) -> List[str]:
        """Strategy 5: Use youtube-dl as fallback with different options"""
        cmd = [
            'youtube-dl',  # Try youtube-dl instead of yt-dlp
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            '--no-check-certificate',
            '--ignore-errors',
            '--no-warnings',
            '--extractor-args', 'youtube:player_client=android,web'
        ]
        
        if audio_only:
            cmd.extend([
                '-x',  # Extract audio
                '--audio-format', 'mp3',
                '--audio-quality', '0',
                '--postprocessor-args', 'ffmpeg:-b:a 320k'
            ])
        else:
            cmd.extend(['-f', quality])
        
        cmd.extend(['-o', output_template, url])
        return cmd
    
    def download_high_quality_audio(self, url: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[Path]:
        """
        Download high-quality audio from YouTube video.
        
        Args:
            url: YouTube video URL
            metadata: Optional metadata for organized file structure
            
        Returns:
            Path to downloaded audio file or None if failed
        """
        return self.download(url, quality="bestaudio", audio_only=True, metadata=metadata)
    
    def download_playlist(self, url: str, quality: str = "bestaudio") -> List[str]:
        """
        Download a YouTube playlist.
        
        Args:
            url: YouTube playlist URL
            quality: Video quality preference
            
        Returns:
            List of paths to downloaded files
        """
        try:
            cmd = [
                'yt-dlp',
                '-o', str(self.download_dir / "%(playlist_index)s - %(title)s.%(ext)s"),
                '-f', quality,
                url
            ]
            
            # Import colors here to avoid circular imports
            from ..utils.colors import Colors
            
            print(f"Downloading playlist: {Colors.blue(url)}")
            print(f"Quality: {Colors.cyan(quality)}")
            print(f"Save location: {Colors.blue(str(self.download_dir))}")
            print()
            
            subprocess.run(cmd, check=True)
            
            # Return list of downloaded files
            downloaded_files = list(self.download_dir.glob("*"))
            return [str(f) for f in downloaded_files]
            
        except subprocess.CalledProcessError as e:
            print(f"Playlist download failed: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error during playlist download: {e}")
            return []
    
    def get_available_formats(self, url: str) -> List[Dict[str, Any]]:
        """
        Get available formats for a video.
        
        Args:
            url: YouTube video URL
            
        Returns:
            List of available formats
        """
        try:
            cmd = [
                'yt-dlp',
                '--list-formats',
                url
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Parse the output to extract format information
            formats = []
            lines = result.stdout.split('\n')
            
            for line in lines:
                if 'format code' in line.lower() or 'extension' in line.lower():
                    continue
                if line.strip() and ' ' in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        formats.append({
                            'format_code': parts[0],
                            'extension': parts[1],
                            'resolution': parts[2] if len(parts) > 2 else 'unknown',
                            'note': ' '.join(parts[3:]) if len(parts) > 3 else ''
                        })
            
            return formats
            
        except subprocess.CalledProcessError as e:
            print(f"Error getting formats: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error: {e}")
            return []
