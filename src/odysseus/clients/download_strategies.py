"""
Download Strategies Module
Contains different command building strategies for YouTube downloads.
"""

from typing import List, Optional, Callable
from .cookie_manager import CookieManager


class DownloadStrategies:
    """Command building strategies for YouTube downloads."""
    
    def __init__(self, cookie_manager: CookieManager):
        self.cookie_manager = cookie_manager
    
    def build_strategy_1(self, url: str, quality: str, audio_only: bool, output_template: str) -> List[str]:
        """Strategy 1: android_music client (fastest, ~9.74s, 0.69 MB/s) - NO COOKIES"""
        # Analysis shows android_music is fastest and most reliable
        # Cookies with mobile clients actually cause failures, so we skip them
        cmd = [
            'yt-dlp',
            '--user-agent', 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            '--no-check-certificate',
            '--ignore-errors',
            '--no-warnings',
            '--extractor-args', 'youtube:player_client=android_music'  # Fastest player client
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
    
    def build_strategy_2(self, url: str, quality: str, audio_only: bool, output_template: str) -> List[str]:
        """Strategy 2: android client (reliable, ~10.69s, 0.57 MB/s) - NO COOKIES"""
        # Analysis shows android client is reliable fallback
        # Cookies with mobile clients cause failures, so we skip them
        cmd = [
            'yt-dlp',
            '--user-agent', 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            '--no-check-certificate',
            '--ignore-errors',
            '--no-warnings',
            '--extractor-args', 'youtube:player_client=android'  # Reliable mobile client
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
    
    def build_strategy_3(self, url: str, quality: str, audio_only: bool, output_template: str) -> List[str]:
        """Strategy 3: android_music with increased retries (fallback for unstable connections)"""
        # Use android_music with retries for better reliability
        cmd = [
            'yt-dlp',
            '--user-agent', 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            '--no-check-certificate',
            '--ignore-errors',
            '--no-warnings',
            '--extractor-args', 'youtube:player_client=android_music',
            '--retries', '10',
            '--fragment-retries', '10',
            '--extractor-retries', '3'
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
    
    def build_strategy_4(self, url: str, quality: str, audio_only: bool, output_template: str) -> List[str]:
        """Strategy 4: android client with retries and request delays (fallback)"""
        # Use android with retries and delays for rate-limited scenarios
        cmd = [
            'yt-dlp',
            '--user-agent', 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            '--no-check-certificate',
            '--ignore-errors',
            '--no-warnings',
            '--extractor-args', 'youtube:player_client=android',
            '--retries', '10',
            '--fragment-retries', '10',
            '--sleep-requests', '1',  # Add delay between requests to avoid rate limiting
            '--sleep-interval', '1'
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
    
    def build_strategy_5(self, url: str, quality: str, audio_only: bool, output_template: str) -> List[str]:
        """Strategy 5: Web client with cookies (last resort - web client has low success rate)"""
        # Web client is last resort as it has lower success rate
        # Only use cookies with web client (cookies break mobile clients)
        cmd = [
            'yt-dlp',
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            '--no-check-certificate',
            '--ignore-errors',
            '--no-warnings',
            '--extractor-args', 'youtube:player_client=web'
        ]
        
        # Only add cookies if available (cookies work with web client, not mobile)
        cookie_browser = self.cookie_manager.get_cookie_browser()
        if cookie_browser:
            cmd.extend(['--cookies-from-browser', cookie_browser])
        
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
    
    def get_all_strategies(self) -> List[Callable]:
        """Get all strategy methods in order."""
        return [
            self.build_strategy_1,
            self.build_strategy_2,
            self.build_strategy_3,
            self.build_strategy_4,
            self.build_strategy_5
        ]

