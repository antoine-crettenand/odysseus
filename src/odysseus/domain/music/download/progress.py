"""Presentation-neutral progress events for release downloads."""

from typing import Any, Callable, Dict, Optional


ReleaseProgressCallback = Callable[[Dict[str, Any]], None]


def emit_release_progress(
    callback: Optional[ReleaseProgressCallback],
    *,
    stage: str,
    status: str,
    message: str,
    percent: Optional[float] = None,
    **details: Any,
) -> None:
    """Send one structured progress event when a listener is present."""
    if callback is None:
        return
    event: Dict[str, Any] = {
        "stage": stage,
        "status": status,
        "message": message,
    }
    if percent is not None:
        event["percent"] = max(0.0, min(100.0, float(percent)))
    event.update(details)
    callback(event)
