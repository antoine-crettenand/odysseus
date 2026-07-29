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


def test_total_time_budget_is_reset_for_each_operation():
    strategy = SubprocessRetryStrategy(max_retries=0)
    success = subprocess.CompletedProcess(["yt-dlp"], 0, stdout="ok", stderr="")
    progress_callback = MagicMock()

    with patch(
        "odysseus.core.retry.subprocess_retry.subprocess.run",
        return_value=success,
    ), patch(
        "odysseus.core.retry.subprocess_retry.time.time",
        side_effect=[10.0, 20.0],
    ):
        strategy.execute_with_progress(
            ["yt-dlp"],
            progress_callback=progress_callback,
        )
        first_start = strategy.start_time
        strategy.execute_with_progress(["yt-dlp"])

    assert first_start == 10.0
    assert strategy.start_time == 20.0
    progress_callback.assert_any_call(
        {
            "percent": 0.0,
            "status": "starting",
            "speed": None,
            "eta": None,
        }
    )
