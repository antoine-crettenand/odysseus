"""Regression tests for subprocess retry behavior."""

import subprocess
from unittest.mock import MagicMock, patch

from odysseus.core.retry import SubprocessRetryStrategy


def test_signature_failure_retries_without_mutating_dependencies():
    strategy = SubprocessRetryStrategy(
        max_retries=1,
        base_delay=0,
    )
    failure = subprocess.CalledProcessError(
        1,
        ["yt-dlp"],
        stderr="signature extraction failed",
    )
    success = subprocess.CompletedProcess(["yt-dlp"], 0, stdout="ok", stderr="")

    with patch(
        "odysseus.core.retry.subprocess_retry.subprocess.run",
        side_effect=[failure, success],
    ), patch("odysseus.core.retry.subprocess_retry.time.sleep"):
        result = strategy.execute_with_progress(["yt-dlp"])

    assert result is success


def test_generic_extraction_error_is_not_misclassified_as_signature_error():
    retryable, reason = SubprocessRetryStrategy.is_retryable_error(
        "ffmpeg failed while extracting audio"
    )

    assert retryable is True
    assert reason == "Unknown error"


def test_deleted_and_removed_videos_are_not_retryable():
    for message in (
        "ERROR: video unavailable",
        "This video has been deleted",
        "Content has been removed",
        "The video does not exist",
    ):
        retryable, reason = SubprocessRetryStrategy.is_retryable_error(message)
        assert retryable is False
        assert reason == "Unavailable"


def test_total_time_budget_is_reset_for_each_operation():
    strategy = SubprocessRetryStrategy(max_retries=0)
    success = subprocess.CompletedProcess(["yt-dlp"], 0, stdout="ok", stderr="")
    progress_callback = MagicMock()

    with patch(
        "odysseus.core.retry.subprocess_retry.subprocess.run",
        return_value=success,
    ), patch(
        "odysseus.core.retry.subprocess_retry.time.monotonic",
        side_effect=[10.0, 20.0],
    ) as monotonic:
        strategy.execute_with_progress(
            ["yt-dlp"],
            progress_callback=progress_callback,
        )
        strategy.execute_with_progress(["yt-dlp"])

    assert monotonic.call_count == 2
    assert not hasattr(strategy, "start_time")
    progress_callback.assert_any_call(
        {
            "percent": 0.0,
            "status": "starting",
            "speed": None,
            "eta": None,
        }
    )
