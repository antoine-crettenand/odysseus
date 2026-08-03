"""Optional AcoustID/Chromaprint verification for downloaded audio."""

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable, Dict, Optional

from ..core.config import ACOUSTID_CONFIG


@dataclass(frozen=True)
class AudioVerification:
    """Advisory fingerprint-verification result."""

    status: str
    score: Optional[float] = None
    recording_mbid: Optional[str] = None
    detail: str = ""


class AcoustIDClient:
    """Fingerprint local audio and compare it with an expected recording MBID."""

    def __init__(
        self,
        http_client=None,
        *,
        api_key: Optional[str] = None,
        fpcalc_path: Optional[str] = None,
        runner: Callable[..., Any] = subprocess.run,
    ) -> None:
        if http_client is None:
            from ..core.http import HttpClient

            http_client = HttpClient()
        self.http_client = http_client
        self.base_url = ACOUSTID_CONFIG["BASE_URL"]
        self.api_key = ACOUSTID_CONFIG["API_KEY"] if api_key is None else api_key
        self.fpcalc_path = fpcalc_path or ACOUSTID_CONFIG["FPCALC_PATH"]
        self.min_score = ACOUSTID_CONFIG["MIN_SCORE"]
        self.request_delay = ACOUSTID_CONFIG["REQUEST_DELAY"]
        self.timeout = ACOUSTID_CONFIG["TIMEOUT"]
        self._runner = runner

    def is_available(self) -> bool:
        """Return whether both the service key and Chromaprint are available."""
        return bool(self.api_key and shutil.which(self.fpcalc_path))

    def set_api_key(self, api_key: Optional[str]) -> None:
        """Apply a new AcoustID application key."""
        self.api_key = api_key or ""

    def _fingerprint(self, path: Path) -> Optional[Dict[str, Any]]:
        try:
            result = self._runner(
                [self.fpcalc_path, "-json", str(path)],
                capture_output=True,
                text=True,
                check=True,
                timeout=self.timeout,
            )
            payload = json.loads(result.stdout)
            if payload.get("fingerprint") and payload.get("duration"):
                return payload
        except (OSError, subprocess.SubprocessError, ValueError, TypeError):
            return None
        return None

    def verify(self, path: Path, expected_recording_mbid: Optional[str]) -> AudioVerification:
        """Compare a file fingerprint with an expected MusicBrainz recording."""
        if not expected_recording_mbid:
            return AudioVerification("not_run", detail="No recording MBID is available")
        if not self.is_available():
            return AudioVerification("not_run", detail="AcoustID is not configured")
        fingerprint = self._fingerprint(Path(path))
        if not fingerprint:
            return AudioVerification("inconclusive", detail="Chromaprint could not fingerprint the file")

        data = self.http_client.get_json(
            f"{self.base_url}/lookup",
            params={
                "client": self.api_key,
                "duration": fingerprint["duration"],
                "fingerprint": fingerprint["fingerprint"],
                "meta": "recordingids",
                "format": "json",
            },
            timeout=self.timeout,
            handle_rate_limit=True,
            session_name="acoustid",
            request_delay=self.request_delay,
        )
        candidates = []
        for result in (data or {}).get("results", []):
            score = float(result.get("score") or 0)
            for recording in result.get("recordings", []):
                recording_id = recording.get("id")
                if recording_id:
                    candidates.append((score, recording_id))

        if not candidates:
            return AudioVerification("inconclusive", detail="No AcoustID recording match")
        candidates.sort(reverse=True)
        for score, recording_id in candidates:
            if recording_id == expected_recording_mbid and score >= self.min_score:
                return AudioVerification("verified", score, recording_id)

        score, recording_id = candidates[0]
        if score >= self.min_score:
            return AudioVerification(
                "mismatch",
                score,
                recording_id,
                "The fingerprint resolved to a different MusicBrainz recording",
            )
        return AudioVerification("inconclusive", score, recording_id, "Fingerprint confidence was too low")
