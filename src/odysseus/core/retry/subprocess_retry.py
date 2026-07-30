"""
Subprocess-specific retry strategy for yt-dlp operations.
"""

import subprocess
import threading
import time
from queue import Empty, Queue
from typing import Optional, Tuple, Callable, Any
from .retry_strategy import RetryStrategy, RetryContext


class SubprocessRetryStrategy(RetryStrategy):
    """
    Retry strategy for subprocess operations (e.g., yt-dlp).

    Handles:
    - Connection errors
    - Signature extraction errors
    - Rate limiting
    - Bot detection
    - Timeout errors
    """

    def __init__(
        self,
        max_retries: int = 5,
        base_delay: float = 2.0,
        max_delay: float = 60.0,
        max_total_time: float = 1800,
        timeout: int = 600,
        progress_parser: Optional[Callable] = None,
        no_activity_timeout: int = 60,
    ):
        """
        Initialize subprocess retry strategy.

        Args:
            max_retries: Maximum retry attempts
            base_delay: Base delay between retries
            max_delay: Maximum delay between retries
            max_total_time: Maximum total time for all attempts
            timeout: Timeout per attempt
            progress_parser: Optional parser called for every output line
            no_activity_timeout: Maximum seconds without subprocess output
        """
        super().__init__(max_retries, base_delay, max_delay)
        self.max_total_time = max_total_time
        self.timeout = timeout
        self.progress_parser = progress_parser
        self.no_activity_timeout = no_activity_timeout
        self._active_processes = set()
        self._active_processes_lock = threading.Lock()
        self._cancel_event = threading.Event()

    def reset_cancellation(self) -> None:
        """Clear a previous cancellation so a new batch can run."""
        self._cancel_event.clear()

    def is_cancelled(self) -> bool:
        """Return whether cancellation was requested."""
        return self._cancel_event.is_set()

    @staticmethod
    def is_retryable_error(error_output: str) -> Tuple[bool, Optional[str]]:
        """
        Check if an error output indicates a retryable error.

        Args:
            error_output: Error output from subprocess

        Returns:
            Tuple of (is_retryable, reason)
        """
        error_lower = error_output.lower()

        # Explicit cancellation - never retry
        if "cancelled" in error_lower:
            return False, "Cancelled"

        # Permanently unavailable media - fail fast
        unavailable_markers = (
            "video unavailable",
            "private video",
            "deleted",
            "removed",
            "not available",
            "does not exist",
        )
        if any(marker in error_lower for marker in unavailable_markers):
            return False, "Unavailable"

        # Connection errors - definitely retryable
        if any(x in error_lower for x in ['connection', 'network', 'timeout', 'timed out']):
            return True, "Connection error"

        # Signature extraction errors - retryable
        signature_errors = (
            "signature extraction",
            "unable to extract signature",
            "nsig extraction",
        )
        if any(message in error_lower for message in signature_errors):
            return True, "Signature extraction error"

        # Rate limiting - retryable
        if any(x in error_lower for x in ['rate limit', '429', 'too many requests']):
            return True, "Rate limiting"

        # Bot detection - retryable
        if any(x in error_lower for x in ['bot', 'captcha', 'blocked']):
            return True, "Bot detection"

        # Default: retryable for unknown errors
        return True, "Unknown error"

    def should_retry(self, context: RetryContext, exception: Exception) -> bool:
        """
        Determine if subprocess operation should be retried.

        Args:
            context: Retry context
            exception: The exception that occurred

        Returns:
            True if retry should be attempted
        """
        if self._cancel_event.is_set():
            return False

        # Check if we've exceeded max retries
        if context.attempt >= self.max_retries:
            return False

        # Check exception type
        if isinstance(exception, subprocess.CalledProcessError):
            error_output = (exception.stderr or exception.stdout or str(exception)).lower()
            is_retryable, _ = self.is_retryable_error(error_output)
            return is_retryable

        # Timeout errors - retry
        if isinstance(exception, subprocess.TimeoutExpired):
            return True

        # FileNotFoundError - don't retry (yt-dlp not installed)
        if isinstance(exception, FileNotFoundError):
            return False

        # Other exceptions - retry
        return True

    def calculate_delay(self, context: RetryContext) -> float:
        """
        Calculate delay with exponential backoff.

        Args:
            context: Retry context

        Returns:
            Delay in seconds
        """
        return super().calculate_delay(context)

    def _run_streaming(
        self,
        cmd: list,
        progress_callback: Callable,
    ) -> subprocess.CompletedProcess:
        """Run one attempt while forwarding real-time output to the parser."""
        effective_cmd = list(cmd)
        if (
            effective_cmd
            and effective_cmd[0].endswith("yt-dlp")
            and "--newline" not in effective_cmd
        ):
            effective_cmd.insert(max(1, len(effective_cmd) - 1), "--newline")

        process = subprocess.Popen(
            effective_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        with self._active_processes_lock:
            self._active_processes.add(process)
        output_queue: Queue = Queue()

        def read_stream(name: str, stream) -> None:
            try:
                for line in iter(stream.readline, ""):
                    output_queue.put((name, line.rstrip("\r\n")))
            finally:
                output_queue.put((name, None))

        threads = [
            threading.Thread(
                target=read_stream,
                args=("stdout", process.stdout),
                daemon=True,
            ),
            threading.Thread(
                target=read_stream,
                args=("stderr", process.stderr),
                daemon=True,
            ),
        ]
        for thread in threads:
            thread.start()

        lines = {"stdout": [], "stderr": []}
        completed_streams = set()
        attempt_started = last_activity = time.monotonic()
        try:
            while len(completed_streams) < 2:
                now = time.monotonic()
                if now - attempt_started > self.timeout:
                    raise subprocess.TimeoutExpired(effective_cmd, self.timeout)
                if now - last_activity > self.no_activity_timeout:
                    raise subprocess.TimeoutExpired(
                        effective_cmd,
                        self.no_activity_timeout,
                        "Subprocess produced no output",
                    )
                try:
                    stream_name, line = output_queue.get(timeout=0.1)
                except Empty:
                    if process.poll() is not None and all(
                        not thread.is_alive() for thread in threads
                    ):
                        break
                    continue
                if line is None:
                    completed_streams.add(stream_name)
                    continue
                last_activity = time.monotonic()
                lines[stream_name].append(line)
                if self.progress_parser:
                    self.progress_parser(line, progress_callback)
        except BaseException:
            if process.poll() is None:
                process.kill()
            process.wait()
            raise
        finally:
            with self._active_processes_lock:
                self._active_processes.discard(process)
            for thread in threads:
                thread.join(timeout=1)

        return_code = process.wait(timeout=10)
        result = subprocess.CompletedProcess(
            effective_cmd,
            return_code,
            stdout="\n".join(lines["stdout"]),
            stderr="\n".join(lines["stderr"]),
        )
        if return_code:
            raise subprocess.CalledProcessError(
                return_code,
                effective_cmd,
                output=result.stdout,
                stderr=result.stderr,
            )
        return result

    def cancel_active(self) -> None:
        """Terminate every subprocess currently owned by this strategy."""
        self._cancel_event.set()
        with self._active_processes_lock:
            processes = list(self._active_processes)

        for process in processes:
            if process.poll() is None:
                try:
                    process.terminate()
                except OSError:
                    pass
        for process in processes:
            if process.poll() is not None:
                continue
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                except OSError:
                    pass

    def _raise_if_cancelled(self, cmd: list) -> None:
        if self._cancel_event.is_set():
            raise subprocess.CalledProcessError(
                -1,
                cmd,
                output="",
                stderr="cancelled",
            )

    def _interruptible_sleep(self, delay: float, cmd: list) -> None:
        """Sleep unless cancellation is requested first."""
        if delay <= 0:
            self._raise_if_cancelled(cmd)
            return
        if self._cancel_event.wait(timeout=delay):
            self._raise_if_cancelled(cmd)

    def _run_attempt(
        self,
        cmd: list,
        progress_callback: Optional[Callable],
    ) -> subprocess.CompletedProcess:
        self._raise_if_cancelled(cmd)
        if progress_callback and self.progress_parser:
            return self._run_streaming(cmd, progress_callback)
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=True,
        )

    def execute_with_progress(
        self,
        cmd: list,
        operation_name: str = "operation",
        quiet: bool = False,
        progress_callback: Optional[Callable] = None
    ) -> subprocess.CompletedProcess:
        """
        Execute subprocess command with retry logic and progress tracking.

        Args:
            cmd: Command to execute as list
            operation_name: Name of operation for logging
            quiet: If True, suppress output
            progress_callback: Optional callback for progress updates

        Returns:
            CompletedProcess result

        Raises:
            subprocess.CalledProcessError: If all retries fail
        """
        # Keep operation timing local so one strategy can serve concurrent jobs.
        operation_started = time.monotonic()

        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                self._raise_if_cancelled(cmd)

                # Update progress callback if provided
                if progress_callback:
                    progress_callback({
                        'percent': (attempt / max(1, self.max_retries)) * 100,
                        'status': 'retrying' if attempt > 0 else 'starting',
                        'speed': None,
                        'eta': None
                    })

                # Execute command
                result = self._run_attempt(cmd, progress_callback)

                # Success - update progress
                if progress_callback:
                    progress_callback({
                        'percent': 100.0,
                        'status': 'completed',
                        'speed': None,
                        'eta': None
                    })

                return result

            except subprocess.CalledProcessError as e:
                last_exception = e
                error_output = (e.stderr or e.stdout or str(e)).lower()

                context = RetryContext(
                    attempt=attempt,
                    max_attempts=self.max_retries,
                    last_exception=e
                )

                # Check if we should retry
                if (
                    attempt == self.max_retries
                    or time.monotonic() - operation_started > self.max_total_time
                    or not self.should_retry(context, e)
                ):
                    raise

                # Calculate delay
                delay = self.calculate_delay(context)

                if not quiet:
                    print(f"Retrying {operation_name} (attempt {attempt + 1}/{self.max_retries}) after {delay:.1f}s...")

                self._interruptible_sleep(delay, cmd)

            except subprocess.TimeoutExpired as e:
                last_exception = e
                context = RetryContext(
                    attempt=attempt,
                    max_attempts=self.max_retries,
                    last_exception=e
                )

                if (
                    attempt == self.max_retries
                    or time.monotonic() - operation_started > self.max_total_time
                    or not self.should_retry(context, e)
                ):
                    raise

                delay = self.calculate_delay(context)
                if not quiet:
                    print(f"Timeout on {operation_name}, retrying (attempt {attempt + 1}/{self.max_retries}) after {delay:.1f}s...")

                self._interruptible_sleep(delay, cmd)

            except Exception as e:
                last_exception = e
                context = RetryContext(
                    attempt=attempt,
                    max_attempts=self.max_retries,
                    last_exception=e
                )

                if (
                    attempt == self.max_retries
                    or time.monotonic() - operation_started > self.max_total_time
                    or not self.should_retry(context, e)
                ):
                    raise

                delay = self.calculate_delay(context)
                if not quiet:
                    print(f"Error on {operation_name}, retrying (attempt {attempt + 1}/{self.max_retries}) after {delay:.1f}s...")

                self._interruptible_sleep(delay, cmd)

        # Should never reach here, but just in case
        if last_exception:
            raise last_exception
        raise subprocess.CalledProcessError(1, cmd, "Retry failed without exception")
