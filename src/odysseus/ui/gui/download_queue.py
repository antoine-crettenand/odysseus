"""Background download queue for the desktop controller."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, List, Optional

from PySide6.QtCore import QTimer

from ...application.recording_workflow import RecordingDownloadResult
from ...application.release_workflow import ReleaseDownloadResult
from .workers import _Worker

if TYPE_CHECKING:
    from .controller import OdysseusController


@dataclass
class _DownloadJob:
    """One immutable request managed by the background download queue."""

    label: str
    function: Callable
    workflow: object
    with_progress: bool
    row: dict


class DownloadQueue:
    """Owns queued download jobs and drives worker lifecycle via host callbacks."""

    def __init__(self, host: OdysseusController) -> None:
        self._host = host
        self.jobs: List[_DownloadJob] = []
        self.current: Optional[_DownloadJob] = None

    @property
    def rows(self) -> List[dict]:
        return [job.row for job in self.jobs]

    @property
    def active_count(self) -> int:
        return sum(
            job.row["status"] in {"Queued", "Downloading", "Cancelling"}
            for job in self.jobs
        )

    def enqueue(
        self,
        label: str,
        function: Callable,
        workflow: object,
        *,
        with_progress: bool = False,
    ) -> None:
        host = self._host
        job = _DownloadJob(
            label=label,
            function=function,
            workflow=workflow,
            with_progress=with_progress,
            row={
                "label": label,
                "status": "Queued",
                "stage": "Queued",
                "detail": "Waiting to start",
                "progress": 0.0,
            },
        )
        self.jobs.append(job)
        host.queueChanged.emit()
        host._set_status(f"Added to download queue: {label}", "#7ce7b2")
        self.start_next()

    def start_next(self) -> None:
        host = self._host
        if self.current is not None:
            return
        job = next(
            (item for item in self.jobs if item.row["status"] == "Queued"),
            None,
        )
        if job is None:
            return

        self.current = job
        host._active_workflow = job.workflow
        host._cancel_requested = False
        host._downloading = True
        host._progress = 0.0
        host._progress_detail = job.label
        job.row.update(
            status="Downloading",
            stage="Starting",
            detail="Preparing download…",
            progress=0.0,
        )
        host.busyChanged.emit()
        host.progressChanged.emit()
        host.queueChanged.emit()

        worker = _Worker(job.function, with_progress=job.with_progress)
        host._workers.add(worker)
        worker.signals.result.connect(
            lambda result, current=job: self.job_succeeded(current, result)
        )
        worker.signals.error.connect(
            lambda message, current=job: self.job_failed(current, message)
        )
        if job.with_progress:
            worker.signals.progress.connect(
                lambda progress, current=job: self.queued_progressed(
                    current, progress
                )
            )
        worker.signals.finished.connect(
            lambda current_worker=worker, current_job=job: (
                self.job_finished(current_worker, current_job)
            )
        )
        host.thread_pool.start(worker)

    def cancel(self) -> None:
        host = self._host
        if not host._downloading:
            return
        host._cancel_requested = True
        if self.current is not None:
            self.current.row.update(
                status="Cancelling",
                detail="Cancellation requested",
            )
            host.queueChanged.emit()
        host._set_status("Cancelling download…", "#ffc66d")
        host._active_workflow.cancel()

    def clear_finished(self) -> None:
        self.jobs = [
            job
            for job in self.jobs
            if job.row["status"] in {"Queued", "Downloading", "Cancelling"}
        ]
        self._host.queueChanged.emit()

    def job_succeeded(self, job: _DownloadJob, result: object) -> None:
        host = self._host
        if isinstance(result, RecordingDownloadResult):
            host._download_finished(result)
            detail = result.warning or str(result.path)
            status = "Completed with warning" if result.warning else "Completed"
        elif isinstance(result, ReleaseDownloadResult):
            host._release_download_finished(result)
            detail = f"Processed {result.processed}; failed {result.failed}"
            if result.verified or result.verification_mismatches:
                detail += (
                    f"; verified {result.verified}; fingerprint warnings "
                    f"{result.verification_mismatches}"
                )
            status = "Completed with errors" if result.failed else "Completed"
            if result.verification_mismatches:
                status = "Completed with warning"
        else:
            detail = "Completed"
            status = "Completed"
        job.row.update(status=status, detail=detail, progress=100.0)
        host.queueChanged.emit()

    def job_failed(self, job: _DownloadJob, message: str) -> None:
        host = self._host
        if host._cancel_requested:
            job.row.update(status="Cancelled", detail="Cancelled by user")
            host._set_status("Download cancelled.", "#ffc66d")
            host._progress_detail = "Cancelled"
        else:
            detail = message or "Download failed without an error message"
            job.row.update(status="Failed", detail=detail)
            host._set_status(f"Download failed: {detail}", "#ff8797")
            host._progress_detail = detail
        host.progressChanged.emit()
        host.queueChanged.emit()

    def job_finished(self, worker: _Worker, job: _DownloadJob) -> None:
        host = self._host
        host._workers.discard(worker)
        if job.row["status"] in {"Downloading", "Cancelling"}:
            job.row.update(
                status="Cancelled" if host._cancel_requested else "Failed",
                detail=(
                    "Cancelled by user"
                    if host._cancel_requested
                    else "The worker ended without returning a result"
                ),
            )
        self.current = None
        host._downloading = False
        host._cancel_requested = False
        host.busyChanged.emit()
        host.queueChanged.emit()
        QTimer.singleShot(0, self.start_next)

    def queued_progressed(self, job: _DownloadJob, progress: dict) -> None:
        host = self._host
        host._download_progressed(progress)
        job.row.update(
            progress=host._progress,
            detail=host._progress_detail,
            stage=str(progress.get("status") or job.row.get("stage", "Downloading")),
        )
        host.queueChanged.emit()
