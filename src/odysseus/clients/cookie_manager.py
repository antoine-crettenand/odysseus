"""
Cookie Manager Module
Handles browser cookie detection for YouTube downloads.
"""

from pathlib import Path
from typing import Optional


class CookieManager:
    """Manages browser cookies for YouTube downloads."""
    
    @staticmethod
    def has_chrome_cookies() -> bool:
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
    
    @staticmethod
    def has_firefox_cookies() -> bool:
        """Check if Firefox cookies database exists."""
        firefox_cookie_paths = [
            Path.home() / "Library/Application Support/Firefox/Profiles",
            Path.home() / ".mozilla/firefox",
            Path.home() / "AppData/Roaming/Mozilla/Firefox/Profiles",
        ]
        
        for path in firefox_cookie_paths:
            if path.exists() and path.is_dir():
                # Check if there are any profile directories
                profiles = [p for p in path.iterdir() if p.is_dir()]
                if profiles:
                    return True
        return False
    
    @staticmethod
    def get_cookie_browser() -> Optional[str]:
        """Get the first available browser for cookies (Chrome preferred, then Firefox)."""
        if CookieManager.has_chrome_cookies():
            return 'chrome'
        elif CookieManager.has_firefox_cookies():
            return 'firefox'
        return None

