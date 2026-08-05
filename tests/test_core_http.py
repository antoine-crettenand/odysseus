"""Tests for shared HTTP client behavior."""

import threading
from unittest.mock import MagicMock, patch

import pytest
import requests

from odysseus.clients.base_api_client import BaseAPIClient
from odysseus.core.http import HttpClient, SessionManager
from odysseus.core.http.network_agent import NetworkAgent


def _response(status_code, headers=None):
    response = MagicMock(spec=requests.Response)
    response.status_code = status_code
    response.headers = headers or {}
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(
            response=response
        )
    return response


def _client_with_session(*responses):
    session = MagicMock()
    session.get.side_effect = responses
    session_manager = MagicMock()
    session_manager.get_session.return_value = session
    client = HttpClient(
        session_manager=session_manager,
        default_request_delay=0,
    )
    return client, session


def test_accepted_error_response_is_returned_to_caller():
    forbidden = _response(403)
    client, session = _client_with_session(forbidden)

    result = client.get(
        "https://example.test",
        max_retries=0,
        accepted_status_codes=(403,),
    )

    assert result is forbidden
    forbidden.raise_for_status.assert_not_called()
    session.get.assert_called_once()


def test_unaccepted_server_error_is_retried():
    first = _response(503)
    second = _response(200)
    client, session = _client_with_session(first, second)

    with patch("odysseus.core.http.http_client.time.sleep"):
        result = client.get("https://example.test", max_retries=1)

    assert result is second
    assert session.get.call_count == 2


def test_rate_limit_uses_retry_after_header():
    limited = _response(429, {"Retry-After": "2.5"})
    success = _response(200)
    client, _ = _client_with_session(limited, success)

    with patch("odysseus.core.http.http_client.time.sleep") as sleep:
        result = client.get(
            "https://example.test",
            max_retries=1,
            handle_rate_limit=True,
        )

    assert result is success
    sleep.assert_called_once_with(2.5)


def test_final_rate_limit_response_does_not_sleep():
    limited = _response(429)
    client, _ = _client_with_session(limited)

    with patch("odysseus.core.http.http_client.time.sleep") as sleep:
        result = client.get(
            "https://example.test",
            max_retries=0,
            handle_rate_limit=True,
        )

    assert result is None
    sleep.assert_not_called()


def test_long_rate_limit_window_fails_fast_and_opens_cooldown():
    limited = _response(429, {"Retry-After": "120"})
    client, session = _client_with_session(limited)

    with patch("odysseus.core.http.http_client.time.sleep") as sleep:
        result = client.get(
            "https://example.test",
            max_retries=1,
            handle_rate_limit=True,
        )

    assert result is None
    assert client.get_provider_health("default")["cooldown_remaining"] > 0
    sleep.assert_not_called()
    session.get.assert_called_once()


def test_base_api_json_request_uses_requested_session():
    http_client = MagicMock()
    client = BaseAPIClient(
        {
            "BASE_URL": "https://example.test",
            "USER_AGENT": "test",
            "REQUEST_DELAY": 0,
            "MAX_RESULTS": 10,
            "TIMEOUT": 5,
        },
        cache_manager=MagicMock(),
        http_client=http_client,
    )

    client._make_request_json(
        "https://example.test/data",
        {},
        session_name="musicbrainz",
    )

    assert http_client.get_json.call_args.kwargs["session_name"] == "musicbrainz"


def test_request_timeout_status_is_retried():
    first = _response(408)
    second = _response(200)
    client, session = _client_with_session(first, second)

    with patch(
        "odysseus.core.http.http_client.random.uniform",
        return_value=0,
    ):
        result = client.get("https://example.test", max_retries=1)

    assert result is second
    assert session.get.call_count == 2


def test_circuit_breaker_pauses_provider_after_terminal_failure():
    failed = _response(503)
    client, session = _client_with_session(failed)
    client.circuit_breaker_threshold = 1
    client.circuit_breaker_cooldown = 30

    assert client.get("https://example.test", max_retries=0) is None
    assert client.get("https://example.test", max_retries=0) is None

    session.get.assert_called_once()


def test_retry_after_http_date_is_supported():
    from datetime import datetime, timedelta, timezone
    from email.utils import format_datetime

    retry_at = datetime.now(timezone.utc) + timedelta(seconds=5)
    delay = HttpClient._parse_retry_after(format_datetime(retry_at), 60)

    assert 0 < delay <= 5


def test_session_refresh_preserves_registered_provider_headers():
    manager = SessionManager()
    manager.register_headers(
        "discogs",
        {
            "User-Agent": "Odysseus/1.0",
            "Authorization": "Discogs token=secret",
        },
    )

    first = manager.get_session("discogs")
    refreshed = manager.refresh_session("discogs")

    assert refreshed is not first
    assert refreshed.headers["User-Agent"] == "Odysseus/1.0"
    assert refreshed.headers["Authorization"] == "Discogs token=secret"


def test_replacing_provider_headers_removes_cleared_authorization():
    manager = SessionManager()
    manager.register_headers(
        "discogs",
        {
            "User-Agent": "Odysseus/1.0",
            "Authorization": "Discogs token=secret",
        },
    )
    session = manager.get_session("discogs")

    manager.register_headers("discogs", {"User-Agent": "Odysseus/1.0"})

    assert "Authorization" not in session.headers
    assert session.headers["User-Agent"] == "Odysseus/1.0"

def test_http_client_paces_successful_requests_between_calls():
    first = MagicMock()
    first.status_code = 200
    first.raise_for_status = MagicMock()
    second = MagicMock()
    second.status_code = 200
    second.raise_for_status = MagicMock()

    session = MagicMock()
    session.get.side_effect = [first, second]
    session_manager = MagicMock()
    session_manager.get_session.return_value = session
    client = HttpClient(
        session_manager=session_manager,
        default_request_delay=0.5,
    )

    with patch(
        "odysseus.core.http.http_client.time.monotonic",
        side_effect=[
            10.0,  # stamp after first request
            10.1,  # pacing check before second request
            10.6,  # stamp after second request
        ],
    ):
        with patch("odysseus.core.http.http_client.time.sleep") as sleep:
            client.get("https://example.test/a", max_retries=0)
            client.get("https://example.test/b", max_retries=0)

    sleep.assert_called_once()
    assert sleep.call_args.args[0] == pytest.approx(0.4)

def test_accepted_403_counts_toward_circuit_breaker():
    response = MagicMock(spec=requests.Response)
    response.status_code = 403
    response.headers = {}
    session = MagicMock()
    session.get.return_value = response
    session_manager = MagicMock()
    session_manager.get_session.return_value = session
    client = HttpClient(
        session_manager=session_manager,
        default_request_delay=0,
        circuit_breaker_threshold=2,
        circuit_breaker_cooldown=30,
    )

    first = client.get(
        "https://example.test",
        max_retries=0,
        accepted_status_codes=(403,),
        session_name="discogs",
    )
    second = client.get(
        "https://example.test",
        max_retries=0,
        accepted_status_codes=(403,),
        session_name="discogs",
    )
    third = client.get(
        "https://example.test",
        max_retries=0,
        accepted_status_codes=(403,),
        session_name="discogs",
    )

    assert first is response
    assert second is response
    assert third is None
    assert client.get_provider_health("discogs")["cooldown_remaining"] > 0

def test_session_request_delay_override_is_honored():
    client = HttpClient(default_request_delay=1.0)
    client.set_session_request_delay("spotify", 0.1)
    client._last_request_times["spotify"] = 0.0

    with patch("odysseus.core.http.http_client.time.monotonic", return_value=0.05), patch(
        "odysseus.core.http.http_client.time.sleep"
    ) as sleep:
        client._apply_request_delay("spotify")

    sleep.assert_called_once()
    assert sleep.call_args.args[0] == pytest.approx(0.05)

def test_network_agent_strategy_switch_is_thread_safe():
    agent = NetworkAgent("TestAgent/1.0")

    def switch_many():
        for _ in range(50):
            agent.switch_to_next_strategy(RuntimeError("boom"))

    threads = [threading.Thread(target=switch_many) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert 0 <= agent.current_strategy_index < len(agent.strategies)
    # Locking preserves one history entry per switch with no lost updates.
    assert len(agent.error_history) == 200
