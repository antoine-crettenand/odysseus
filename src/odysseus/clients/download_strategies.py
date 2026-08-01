"""
Download Strategies Module
Contains different command building strategies for YouTube downloads.
"""

from typing import List, Dict, Any, Callable
from .cookie_manager import CookieManager


# Strategy configurations: client type, user agent, retry params, delays, cookies
STRATEGIES = [
    {
        'client': 'android_music',
        'user_agent': 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
        'retries': None,
        'delays': None,
        'cookies': False
    },
    {
        'client': 'android',
        'user_agent': 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
        'retries': None,
        'delays': None,
        'cookies': False
    },
    {
        'client': 'android_music',
        'user_agent': 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
        'retries': {'--retries': '10', '--fragment-retries': '10', '--extractor-retries': '3'},
        'delays': None,
        'cookies': False
    },
    {
        'client': 'android',
        'user_agent': 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
        'retries': {'--retries': '10', '--fragment-retries': '10'},
        'delays': {'--sleep-requests': '1', '--sleep-interval': '1'},
        'cookies': False
    },
    {
        'client': 'web',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'retries': None,
        'delays': None,
        'cookies': True
    }
]


class DownloadStrategies:
    """Command building strategies for YouTube downloads."""
    
    def __init__(self, cookie_manager: CookieManager, audio_format: str = "mp3"):
        self.cookie_manager = cookie_manager
        self.audio_format = audio_format.lower()
    
    def build_strategy(self, strategy_config: Dict[str, Any], url: str, quality: str, audio_only: bool, output_template: str) -> List[str]:
        """Build download command from strategy configuration."""
        cmd = [
            'yt-dlp',
            '--user-agent', strategy_config['user_agent'],
            '--ignore-errors',
            '--no-warnings',
            '--extractor-args', f'youtube:player_client={strategy_config["client"]}'
        ]
        
        # Add retry parameters if specified
        if strategy_config.get('retries'):
            for key, value in strategy_config['retries'].items():
                cmd.extend([key, value])
        
        # Add delay parameters if specified
        if strategy_config.get('delays'):
            for key, value in strategy_config['delays'].items():
                cmd.extend([key, value])
        
        # Add cookies only for web client if available
        if strategy_config.get('cookies'):
            cookie_browser = self.cookie_manager.get_cookie_browser()
            if cookie_browser:
                cmd.extend(['--cookies-from-browser', cookie_browser])
        
        # Add audio/video format options
        if audio_only:
            cmd.extend([
                '-x',
                '--audio-format', self.audio_format,
                '--audio-quality', '0',
            ])
            if self.audio_format == 'mp3':
                cmd.extend([
                    '--postprocessor-args',
                    'ffmpeg:-b:a 320k',
                ])
        else:
            cmd.extend(['-f', quality])
        
        cmd.extend(['-o', output_template, url])
        return cmd
    
    def get_all_strategies(self) -> List[Callable]:
        """Get all strategy methods in order."""
        return [
            lambda url, quality, audio_only, output_template: self.build_strategy(STRATEGIES[0], url, quality, audio_only, output_template),
            lambda url, quality, audio_only, output_template: self.build_strategy(STRATEGIES[1], url, quality, audio_only, output_template),
            lambda url, quality, audio_only, output_template: self.build_strategy(STRATEGIES[2], url, quality, audio_only, output_template),
            lambda url, quality, audio_only, output_template: self.build_strategy(STRATEGIES[3], url, quality, audio_only, output_template),
            lambda url, quality, audio_only, output_template: self.build_strategy(STRATEGIES[4], url, quality, audio_only, output_template)
        ]
