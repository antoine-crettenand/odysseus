"""
yt-dlp Manager Module
Handles yt-dlp version checking and updates.
"""

import subprocess
import sys


class YtDlpManager:
    """Performs explicit, user-requested yt-dlp updates."""

    def update(self) -> bool:
        """
        Manually update yt-dlp.

        Call this method only after the user explicitly requests an update.

        Returns:
            True if update was successful, False otherwise
        """
        try:
            print("🔄 Updating yt-dlp...")
            result = subprocess.run(
                [
                    sys.executable,
                    '-m',
                    'pip',
                    'install',
                    '--upgrade',
                    '--no-cache-dir',
                    'yt-dlp',
                ],
                capture_output=True,
                text=True,
                timeout=180,
                check=True
            )
            print("✅ yt-dlp updated successfully")
            print("   You can now retry your download.")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to update yt-dlp: {e}")
            print(f"   Try running manually: {sys.executable} -m pip install --upgrade yt-dlp")
            return False
        except subprocess.TimeoutExpired:
            print(f"❌ Update timed out. Try running manually: {sys.executable} -m pip install --upgrade yt-dlp")
            return False
        except Exception as e:
            print(f"❌ Unexpected error updating yt-dlp: {e}")
            return False
