"""
Retry Handler Module
Handles retry logic for yt-dlp operations with exponential backoff.
"""

import random
import subprocess
import time
from typing import List, Optional, Callable, Tuple
from .yt_dlp_manager import YtDlpManager
from .progress_tracker import ProgressTracker


class RetryHandler:
    """Handles retry logic for yt-dlp operations."""
    
    def __init__(
        self,
        max_retries: int = 5,
        base_retry_delay: float = 2.0,
        max_retry_delay: float = 60.0,
        max_total_time: float = 1800,
        timeout: int = 600,
        yt_dlp_manager: Optional[YtDlpManager] = None
    ):
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay
        self.max_retry_delay = max_retry_delay
        self.max_total_time = max_total_time
        self.timeout = timeout
        self.yt_dlp_manager = yt_dlp_manager or YtDlpManager()
    
    @staticmethod
    def is_retryable_error(error_output: str) -> Tuple[bool, Optional[str]]:
        """
        Determine if an error is retryable and return error type.
        
        Returns:
            Tuple of (is_retryable, error_type)
        """
        error_lower = error_output.lower()
        
        # HTTP 403/401 errors - retryable (often bot detection or access denied)
        if any(keyword in error_lower for keyword in [
            '403', '401', 'forbidden', 'unauthorized', 'access denied',
            'http error 403', 'http error 401', 'http 403', 'http 401',
            'error 403', 'error 401', 'status code 403', 'status code 401'
        ]):
            return True, 'bot_detection'
        
        # Connection errors - definitely retryable
        if any(keyword in error_lower for keyword in [
            'connection', 'network', 'timeout', 'timed out', 
            'unreachable', 'refused', 'reset', 'broken pipe'
        ]):
            return True, 'connection'
        
        # Signature extraction errors - retryable after update
        if any(keyword in error_lower for keyword in [
            'signature extraction', 'signature', 'player', 'extractor',
            'unable to extract', 'could not extract'
        ]):
            return True, 'signature'
        
        # Rate limiting - retryable with backoff
        if any(keyword in error_lower for keyword in [
            'rate limit', '429', 'too many requests', 'quota'
        ]):
            return True, 'rate_limit'
        
        # HTTP 5xx errors - retryable
        if any(keyword in error_lower for keyword in [
            '500', '502', '503', '504', 'internal server error',
            'bad gateway', 'service unavailable', 'gateway timeout'
        ]):
            return True, 'server_error'
        
        # Bot detection - might be retryable with cookies
        if any(keyword in error_lower for keyword in [
            'bot', 'sign in to confirm', 'captcha', 'verify'
        ]):
            return True, 'bot_detection'
        
        # Video unavailable - not retryable
        if any(keyword in error_lower for keyword in [
            'video unavailable', 'private video', 'deleted', 'removed',
            'not available', 'does not exist'
        ]):
            return False, 'unavailable'
        
        # Default: retryable for unknown errors
        return True, 'unknown'
    
    def calculate_retry_delay(self, attempt: int, error_type: str) -> float:
        """
        Calculate retry delay with exponential backoff and jitter.
        
        Args:
            attempt: Current attempt number (0-indexed)
            error_type: Type of error encountered
            
        Returns:
            Delay in seconds
        """
        # Base exponential backoff
        delay = min(
            self.base_retry_delay * (2 ** attempt),
            self.max_retry_delay
        )
        
        # Adjust delay based on error type
        if error_type == 'rate_limit':
            delay = max(delay, 10.0)  # Longer delay for rate limits
        elif error_type == 'signature':
            delay = max(delay, 3.0)  # Shorter delay for signature errors
        elif error_type == 'connection':
            delay = max(delay, 5.0)  # Medium delay for connection errors
        
        # Add jitter (random 0-20% of delay) to prevent thundering herd
        jitter = random.uniform(0, delay * 0.2)
        return delay + jitter
    
    def run_with_retry(
        self,
        cmd: List[str],
        operation_name: str = "yt-dlp operation",
        progress_callback: Optional[Callable] = None,
        quiet: bool = False
    ) -> subprocess.CompletedProcess:
        """
        Run yt-dlp command with comprehensive retry logic and error handling.
        
        This method implements:
        - Exponential backoff with jitter
        - Automatic yt-dlp updates on signature errors
        - Connection error recovery
        - Rate limit handling
        - Timeout protection (per attempt and total time limit)
        
        Args:
            cmd: Command to run
            operation_name: Name of operation for error messages
            progress_callback: Optional callback for progress updates
            quiet: If True, suppress non-critical output
            
        Returns:
            CompletedProcess object
            
        Raises:
            subprocess.CalledProcessError: If all retries fail
            subprocess.TimeoutExpired: If operation times out
        """
        last_error = None
        last_error_type = None
        signature_error_occurred = False
        start_time = time.time()  # Track total elapsed time
        
        for attempt in range(self.max_retries):
            # Check if we've exceeded maximum total time
            elapsed_time = time.time() - start_time
            if elapsed_time > self.max_total_time:
                if not quiet:
                    total_minutes = self.max_total_time / 60
                    print(f"⏱️  Maximum total time ({total_minutes:.0f} minutes) exceeded for {operation_name}")
                    print(f"   Elapsed time: {elapsed_time / 60:.1f} minutes")
                    print(f"   This download is taking too long and may be stuck.")
                raise subprocess.TimeoutExpired(
                    cmd, 
                    self.max_total_time, 
                    f"Total time limit ({self.max_total_time}s) exceeded after {attempt} attempts"
                )
            try:
                # If this is a retry, add a delay
                if attempt > 0:
                    if last_error_type:
                        delay = self.calculate_retry_delay(attempt - 1, last_error_type)
                        if not quiet:
                            error_type_msg = {
                                'connection': 'Connection error',
                                'signature': 'Signature extraction error',
                                'rate_limit': 'Rate limit',
                                'server_error': 'Server error',
                                'timeout': 'Timeout',
                                'bot_detection': 'Bot detection',
                                'unknown': 'Error'
                            }.get(last_error_type, 'Error')
                            print(f"⏳ {error_type_msg} - Retrying {operation_name} in {delay:.1f} seconds... (attempt {attempt + 1}/{self.max_retries})")
                        time.sleep(delay)
                    
                    # If signature error occurred, try updating yt-dlp
                    if signature_error_occurred and not self.yt_dlp_manager.update_attempted:
                        self.yt_dlp_manager.force_update()
                
                # Run the command
                if progress_callback:
                    # Use progress tracking method with timeout tracking
                    result = ProgressTracker.run_download_with_progress(
                        cmd, 
                        progress_callback,
                        start_time=start_time,
                        max_total_time=self.max_total_time,
                        timeout=self.timeout
                    )
                    # Check return code for progress-based downloads
                    if result.returncode != 0:
                        # Download failed - raise exception to trigger retry
                        error_output = result.stderr if result.stderr else (result.stdout if result.stdout else f"yt-dlp exited with code {result.returncode}")
                        raise subprocess.CalledProcessError(result.returncode, cmd, stderr=error_output, output=result.stdout)
                else:
                    # Use standard subprocess
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=self.timeout,
                        check=True
                    )
                
                # Success - reset update flag for future errors
                if signature_error_occurred:
                    self.yt_dlp_manager.update_attempted = False
                
                return result
                
            except subprocess.TimeoutExpired as e:
                last_error = str(e)
                last_error_type = 'timeout'
                elapsed_time = time.time() - start_time
                
                if attempt < self.max_retries - 1:
                    # Check if we have enough time left for another retry
                    if elapsed_time + self.timeout + self.max_retry_delay > self.max_total_time:
                        if not quiet:
                            print(f"⏱️  Timeout on {operation_name} (attempt {attempt + 1})")
                            print(f"   Elapsed time: {elapsed_time / 60:.1f} minutes")
                            print(f"   Not enough time remaining for another retry (max {self.max_total_time / 60:.0f} minutes)")
                        raise
                    
                    if not quiet:
                        remaining_time = (self.max_total_time - elapsed_time) / 60
                        print(f"⏱️  Timeout on {operation_name} (attempt {attempt + 1}/{self.max_retries})")
                        print(f"   Elapsed: {elapsed_time / 60:.1f} min, Remaining: {remaining_time:.1f} min")
                        print(f"   Will retry...")
                    continue
                else:
                    if not quiet:
                        print(f"⏱️  Timeout on {operation_name} after {self.max_retries} attempts")
                        print(f"   Total elapsed time: {elapsed_time / 60:.1f} minutes")
                        print(f"   Maximum allowed time: {self.max_total_time / 60:.0f} minutes")
                        print(f"   This download may be stuck or your connection is too slow.")
                        print(f"   Try again later or check your internet connection.")
                    raise
                    
            except subprocess.CalledProcessError as e:
                error_output = e.stderr if e.stderr else (e.stdout if e.stdout else str(e))
                last_error = error_output
                
                # Check if error is retryable
                is_retryable, error_type = RetryHandler.is_retryable_error(error_output)
                last_error_type = error_type
                
                # Track signature errors for update
                if error_type == 'signature':
                    signature_error_occurred = True
                
                if not is_retryable:
                    # Non-retryable error - fail immediately
                    if not quiet:
                        print(f"❌ {operation_name} failed with non-retryable error: {error_output[:200]}")
                    raise
                
                # Retryable error - continue to next attempt
                if attempt < self.max_retries - 1:
                    if not quiet:
                        error_preview = error_output[:150].replace('\n', ' ')
                        print(f"⚠️  {operation_name} failed ({error_type}): {error_preview}")
                        if error_type == 'signature' and not signature_error_occurred:
                            print("   This usually means yt-dlp needs to be updated. Will try updating...")
                        print(f"   Retrying... (attempt {attempt + 2}/{self.max_retries})")
                    continue
                else:
                    # Last attempt failed
                    if not quiet:
                        print(f"❌ {operation_name} failed after {self.max_retries} attempts")
                        if error_type == 'signature':
                            print("\n💡 Signature extraction errors usually mean yt-dlp needs updating.")
                            print("   Try manually updating: pip3 install --upgrade yt-dlp")
                            print("   Or if that doesn't work, sign in to YouTube in Chrome/Firefox")
                            print("   to use cookies (helps bypass YouTube's bot detection)")
                        elif error_type == 'bot_detection':
                            # Check if it was a 403/401 error
                            if any(keyword in (last_error or '').lower() for keyword in ['403', '401', 'forbidden', 'unauthorized']):
                                print("\n💡 YouTube blocked the request (403/401 Forbidden).")
                                print("   This usually means YouTube detected automated access.")
                                print("   Solutions:")
                                print("   1. Sign in to YouTube in Chrome or Firefox")
                                print("   2. The system will automatically use your browser cookies")
                                print("   3. Or wait a few minutes and try again")
                            else:
                                print("\n💡 YouTube bot detection triggered.")
                                print("   Try signing in to YouTube in Chrome/Firefox to use cookies")
                                print("   (helps bypass YouTube's bot detection)")
                    raise
                    
            except Exception as e:
                # Unexpected error - treat as retryable
                last_error = str(e)
                last_error_type = 'unknown'
                if attempt < self.max_retries - 1:
                    if not quiet:
                        print(f"⚠️  Unexpected error in {operation_name}: {e}")
                        print(f"   Retrying... (attempt {attempt + 2}/{self.max_retries})")
                    time.sleep(self.calculate_retry_delay(attempt, 'unknown'))
                    continue
                else:
                    raise
        
        # Should never reach here, but just in case
        raise subprocess.CalledProcessError(
            1,
            cmd,
            stderr=last_error or "Unknown error",
            output=""
        )

