"""
HTTP Client Module
Provides a unified HTTP client with retry logic, rate limiting, and error handling.
"""

import random
import threading
import time
import requests
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, Any, Optional, Callable, Tuple
from .session_manager import SessionManager
from ...clients.network_agent import NetworkAgent
from ..config import RETRY_CONFIG
from ..retry import HttpRetryStrategy


class HttpClient:
    """Unified HTTP client with retry logic and rate limiting."""

    _TRANSIENT_STATUS_CODES = {408, 425, 500, 502, 503, 504}
    _MAX_INLINE_RATE_LIMIT_WAIT = 10.0
    _CIRCUIT_ACCEPTED_FAILURE_CODES = {401, 403}

    def __init__(
        self,
        session_manager: Optional[SessionManager] = None,
        network_agent: Optional[NetworkAgent] = None,
        default_timeout: int = 30,
        default_request_delay: float = 1.0,
        circuit_breaker_threshold: int = 3,
        circuit_breaker_cooldown: float = 30.0,
    ):
        """
        Initialize HTTP client.

        Args:
            session_manager: Optional SessionManager instance
            network_agent: Optional NetworkAgent instance
            default_timeout: Default request timeout in seconds
            default_request_delay: Default delay between requests in seconds
            circuit_breaker_threshold: Terminal failures before provider cooldown
            circuit_breaker_cooldown: Provider cooldown duration in seconds
        """
        self.network_agent = network_agent
        self.session_manager = session_manager or SessionManager(network_agent=network_agent)
        self.default_timeout = default_timeout
        self.default_request_delay = default_request_delay
        self._session_request_delays: Dict[str, float] = {}
        self._last_request_times: Dict[str, float] = {}
        self._request_locks: Dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._cooldown_until: Dict[str, float] = {}
        self._consecutive_failures: Dict[str, int] = {}
        self._last_failures: Dict[str, str] = {}
        self.circuit_breaker_threshold = max(1, circuit_breaker_threshold)
        self.circuit_breaker_cooldown = max(0.0, circuit_breaker_cooldown)

        # Initialize retry strategy from shared retry config
        self.retry_strategy = HttpRetryStrategy(
            max_retries=RETRY_CONFIG["HTTP_MAX_RETRIES"],
            base_delay=RETRY_CONFIG["HTTP_BASE_DELAY"],
            max_delay=RETRY_CONFIG["HTTP_MAX_DELAY"],
        )

    def set_session_request_delay(self, session_name: str, delay: float) -> None:
        """Override the inter-request delay for one named session."""
        self._session_request_delays[session_name] = max(0.0, float(delay))

    def _get_request_lock(self, session_name: str) -> threading.Lock:
        """Return a per-provider lock used for pacing and retry coordination."""
        with self._locks_guard:
            if session_name not in self._request_locks:
                self._request_locks[session_name] = threading.Lock()
            return self._request_locks[session_name]

    def _remaining_cooldown(self, session_name: str) -> float:
        cooldown_until = self._cooldown_until.get(session_name)
        if cooldown_until is None:
            return 0.0
        remaining = cooldown_until - time.monotonic()
        if remaining <= 0:
            self._cooldown_until.pop(session_name, None)
            return 0.0
        return remaining

    def _set_cooldown(self, session_name: str, seconds: float) -> None:
        if seconds > 0:
            self._cooldown_until[session_name] = time.monotonic() + seconds

    def _record_success(self, session_name: str) -> None:
        self._consecutive_failures.pop(session_name, None)
        self._last_failures.pop(session_name, None)
        self._cooldown_until.pop(session_name, None)

    def _record_terminal_failure(self, session_name: str, reason: str) -> None:
        failures = self._consecutive_failures.get(session_name, 0) + 1
        self._consecutive_failures[session_name] = failures
        self._last_failures[session_name] = reason
        if failures >= self.circuit_breaker_threshold:
            self._set_cooldown(session_name, self.circuit_breaker_cooldown)

    def get_provider_health(self, session_name: str) -> Dict[str, Any]:
        """Return lightweight diagnostics without exposing credentials."""
        return {
            "consecutive_failures": self._consecutive_failures.get(session_name, 0),
            "cooldown_remaining": self._remaining_cooldown(session_name),
            "last_failure": self._last_failures.get(session_name),
        }

    @staticmethod
    def _parse_retry_after(value: Optional[str], fallback: float) -> float:
        """Parse Retry-After seconds or an HTTP date."""
        if not value:
            return fallback
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            pass
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(
                0.0,
                (retry_at - datetime.now(timezone.utc)).total_seconds(),
            )
        except (TypeError, ValueError, OverflowError):
            return fallback

    @staticmethod
    def _with_full_jitter(delay: float) -> float:
        """Spread retries to avoid synchronized request bursts."""
        return random.uniform(0.0, max(0.0, delay))

    def _apply_request_delay(
        self,
        session_name: str,
        request_delay: Optional[float] = None,
    ) -> None:
        """Sleep so successive requests on a session respect its pacing delay."""
        delay = (
            request_delay
            if request_delay is not None
            else self._session_request_delays.get(
                session_name,
                self.default_request_delay,
            )
        )
        if delay <= 0:
            return
        last_request = self._last_request_times.get(session_name)
        if last_request is None:
            return
        elapsed = time.monotonic() - last_request
        remaining = delay - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        max_retries: int = 3,
        batch_progress: Optional[Tuple[int, int]] = None,
        log_callback: Optional[Callable[[str, bool], None]] = None,
        handle_rate_limit: bool = False,
        rate_limit_codes: Tuple[int, ...] = (429,),
        rate_limit_wait: int = 60,
        session_name: str = "default",
        accepted_status_codes: Tuple[int, ...] = (),
        headers: Optional[Dict[str, str]] = None,
        request_delay: Optional[float] = None,
    ) -> Optional[requests.Response]:
        """
        Make a GET request with retry logic.

        Args:
            url: Request URL
            params: Request parameters
            timeout: Request timeout (uses default if None)
            max_retries: Maximum retry attempts
            batch_progress: Optional tuple (current, total) for batch operations
            log_callback: Optional callback for logging
            handle_rate_limit: Whether to handle rate limiting
            rate_limit_codes: HTTP status codes that indicate rate limiting
            rate_limit_wait: Seconds to wait when rate limited
            session_name: Session name identifier
            accepted_status_codes: Error status codes to return to the caller
                instead of converting them to a failed request
            headers: Optional per-request headers
            request_delay: Optional per-call pacing override in seconds

        Returns:
            Response object, or None if failed
        """
        timeout = timeout or self.default_timeout
        request_lock = self._get_request_lock(session_name)

        with request_lock:
            cooldown_remaining = self._remaining_cooldown(session_name)
            if cooldown_remaining > 0:
                if log_callback:
                    log_callback(
                        f"{session_name} temporarily paused for "
                        f"{cooldown_remaining:.1f}s after repeated failures",
                        dim=True,
                    )
                return None

            session = self.session_manager.get_session(session_name)

            for attempt in range(max_retries + 1):
                try:
                    # Pace requests across attempts (including the first after prior calls)
                    self._apply_request_delay(session_name, request_delay)

                    response = session.get(
                        url,
                        params=params,
                        headers=headers,
                        timeout=timeout,
                    )
                    self._last_request_times[session_name] = time.monotonic()

                    if handle_rate_limit and response.status_code in rate_limit_codes:
                        wait_seconds = self._parse_retry_after(
                            response.headers.get("Retry-After"),
                            float(rate_limit_wait),
                        )
                        self._last_failures[session_name] = (
                            f"HTTP {response.status_code} rate limit"
                        )
                        self._set_cooldown(session_name, wait_seconds)

                        if attempt == max_retries:
                            if log_callback:
                                log_callback(
                                    f"Rate limit retries exhausted "
                                    f"(HTTP {response.status_code})",
                                    dim=True,
                                )
                            return None

                        # Long provider windows should degrade to cached/alternate
                        # results instead of freezing an interactive search.
                        if wait_seconds > self._MAX_INLINE_RATE_LIMIT_WAIT:
                            if log_callback:
                                log_callback(
                                    f"{session_name} paused for {wait_seconds:g}s; "
                                    "using fallback results",
                                    dim=True,
                                )
                            return None

                        if log_callback:
                            log_callback(
                                f"Rate limited (HTTP {response.status_code}), "
                                f"waiting {wait_seconds:g}s...",
                                dim=True,
                            )
                        time.sleep(wait_seconds)
                        self._cooldown_until.pop(session_name, None)
                        self._last_request_times[session_name] = time.monotonic()
                        continue

                    if response.status_code in accepted_status_codes:
                        # Auth/forbidden denials should open the provider circuit
                        # instead of being treated as quiet successes forever.
                        if response.status_code in self._CIRCUIT_ACCEPTED_FAILURE_CODES:
                            self._record_terminal_failure(
                                session_name,
                                f"HTTP {response.status_code}",
                            )
                        return response

                    response.raise_for_status()
                    self._record_success(session_name)
                    return response

                except requests.exceptions.RequestException as e:
                    self._last_request_times[session_name] = time.monotonic()

                    # A narrow connection strategy change can recover broken
                    # keep-alive/protocol state. Provider identity is restored by
                    # SessionManager.register_headers().
                    if (
                        self.network_agent
                        and self.network_agent.should_switch_strategy(e)
                        and self.network_agent.switch_to_next_strategy(e)
                    ):
                        session = self.session_manager.refresh_session(session_name)

                    from ..retry import RetryContext
                    context = RetryContext(
                        attempt=attempt,
                        max_attempts=max_retries,
                        last_exception=e,
                    )

                    should_retry = self.retry_strategy.should_retry(context, e)
                    if attempt == max_retries or not should_retry:
                        reason = str(e)
                        status = getattr(getattr(e, "response", None), "status_code", None)
                        if status in self._TRANSIENT_STATUS_CODES or isinstance(
                            e,
                            (requests.exceptions.ConnectionError, requests.exceptions.Timeout),
                        ):
                            self._record_terminal_failure(session_name, reason)
                        else:
                            self._last_failures[session_name] = reason
                        if log_callback:
                            log_callback(f"Request failed: {e}", dim=True)
                        return None

                    delay = self._with_full_jitter(
                        self.retry_strategy.calculate_delay(context)
                    )
                    if log_callback:
                        log_callback(
                            f"Retrying request (attempt {attempt + 1}/{max_retries}) "
                            f"after {delay:.1f}s...",
                            dim=True,
                        )
                    time.sleep(delay)

            return None

    def get_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        reduced_retries: bool = False,
        batch_progress: Optional[Tuple[int, int]] = None,
        log_callback: Optional[Callable[[str, bool], None]] = None,
        handle_rate_limit: bool = False,
        rate_limit_codes: Tuple[int, ...] = (429,),
        rate_limit_wait: int = 60,
        session_name: str = "default",
        headers: Optional[Dict[str, str]] = None,
        request_delay: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Make a GET request and return JSON response.

        Args:
            url: Request URL
            params: Request parameters
            timeout: Request timeout (uses default if None)
            reduced_retries: If True, reduce retry attempts
            batch_progress: Optional tuple (current, total) for batch operations
            log_callback: Optional callback for logging
            handle_rate_limit: Whether to handle rate limiting
            rate_limit_codes: HTTP status codes that indicate rate limiting
            rate_limit_wait: Seconds to wait when rate limited
            session_name: Session name identifier
            request_delay: Optional per-call pacing override in seconds

        Returns:
            JSON response as dict, or None if failed
        """
        max_retries = 1 if reduced_retries else RETRY_CONFIG["HTTP_MAX_RETRIES"]

        response = self.get(
            url=url,
            params=params,
            timeout=timeout,
            max_retries=max_retries,
            batch_progress=batch_progress,
            log_callback=log_callback,
            handle_rate_limit=handle_rate_limit,
            rate_limit_codes=rate_limit_codes,
            rate_limit_wait=rate_limit_wait,
            session_name=session_name,
            headers=headers,
            request_delay=request_delay,
        )

        if response is None:
            return None

        try:
            return response.json()
        except ValueError:
            return None
