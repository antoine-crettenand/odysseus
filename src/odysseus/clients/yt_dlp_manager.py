"""
yt-dlp Manager Module
Handles yt-dlp version checking and updates.
"""

import subprocess
from typing import Optional


class YtDlpManager:
    """Manages yt-dlp installation and updates."""
    
    def __init__(self):
        self.update_attempted = False
    
    def ensure_updated(self) -> None:
        """Ensure yt-dlp is up to date to avoid 403 errors."""
        try:
            print("Checking yt-dlp version...")
            result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                current_version = result.stdout.strip()
                print(f"Current yt-dlp version: {current_version}")
                
                # Try to update yt-dlp
                print("Updating yt-dlp to latest version...")
                update_result = subprocess.run(['pip3', 'install', '--upgrade', 'yt-dlp'], 
                                             capture_output=True, text=True, timeout=120)
                if update_result.returncode == 0:
                    print("✅ yt-dlp updated successfully")
                else:
                    print("⚠️  Could not update yt-dlp, continuing with current version")
            else:
                print("❌ yt-dlp not found, please install it with: pip install yt-dlp")
        except subprocess.TimeoutExpired:
            print("⚠️  yt-dlp version check timed out, continuing...")
        except Exception as e:
            print(f"⚠️  Could not check yt-dlp version: {e}")
    
    def force_update(self) -> bool:
        """Force update yt-dlp (used when signature extraction fails)."""
        if self.update_attempted:
            return False  # Already tried updating
        
        self.update_attempted = True
        try:
            print("🔄 Signature extraction failed - updating yt-dlp...")
            print("   This usually happens when YouTube changes their API. Updating yt-dlp should fix it.")
            print("   Note: Known issue as of 2025 - yt-dlp team is working on fixes.")
            result = subprocess.run(
                ['pip3', 'install', '--upgrade', '--no-cache-dir', 'yt-dlp'], 
                capture_output=True, 
                text=True, 
                timeout=180,
                check=True
            )
            print("✅ yt-dlp updated successfully")
            
            # Check if update was successful and get version
            try:
                version_result = subprocess.run(
                    ['yt-dlp', '--version'], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                if version_result.returncode == 0:
                    version = version_result.stdout.strip()
                    print(f"   Updated to version: {version}")
                    # Warn about future Deno requirement if version is recent
                    if version >= "2025.10.22":
                        print("   ⚠️  Note: Future versions may require Deno (JavaScript runtime) for YouTube downloads")
            except:
                pass
            
            print("   Retrying download with updated version...")
            # Reset flag after successful update to allow future updates
            import time
            time.sleep(2)  # Give yt-dlp a moment to be ready
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, Exception) as e:
            print(f"⚠️  Could not automatically update yt-dlp: {e}")
            print("   You may need to manually update yt-dlp:")
            print("   Run: pip3 install --upgrade yt-dlp")
            print("   Or: pip install --upgrade yt-dlp")
            print("   Or use: yt-dlp -U (if installed via standalone)")
            print("   Known issues: Check https://github.com/yt-dlp/yt-dlp/issues for updates")
            return False
    
    def update(self) -> bool:
        """
        Manually update yt-dlp.
        
        Call this method if you're experiencing signature extraction errors
        and the automatic update didn't work.
        
        Returns:
            True if update was successful, False otherwise
        """
        try:
            print("🔄 Updating yt-dlp...")
            # Reset the update flag to allow manual updates
            self.update_attempted = False
            result = subprocess.run(
                ['pip3', 'install', '--upgrade', '--no-cache-dir', 'yt-dlp'], 
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
            print("   Try running manually: pip3 install --upgrade yt-dlp")
            return False
        except subprocess.TimeoutExpired:
            print("❌ Update timed out. Try running manually: pip3 install --upgrade yt-dlp")
            return False
        except Exception as e:
            print(f"❌ Unexpected error updating yt-dlp: {e}")
            return False

