"""Qt bridge between QML and presentation-neutral workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional, Set

from PySide6.QtCore import (
    Property,
    QObject,
    QThreadPool,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QDesktopServices

from ...application.recording_workflow import (
    RecordingDownloadResult,
    RecordingWorkflow,
)
from ...application.release_workflow import ReleaseDownloadResult, ReleaseWorkflow
from .catalog_controller import CatalogController
from .download_queue import DownloadQueue
from .recording_controller import RecordingController
from .settings_bridge import SettingsBridge
from .workers import _Worker


class OdysseusController(QObject):
    """Expose recording workflow state and actions to QML."""

    recordingResultsChanged = Signal()
    videoResultsChanged = Signal()
    selectionChanged = Signal()
    busyChanged = Signal()
    statusChanged = Signal()
    progressChanged = Signal()
    lastDownloadChanged = Signal()
    catalogResultsChanged = Signal()
    tracksChanged = Signal()
    queueChanged = Signal()
    settingsChanged = Signal()

    def __init__(
        self,
        workflow: RecordingWorkflow,
        release_workflow: Optional[ReleaseWorkflow] = None,
        *,
        settings_service=None,
        thread_pool: Optional[QThreadPool] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.workflow = workflow
        self.release_workflow = release_workflow
        self.settings_service = settings_service
        self.thread_pool = thread_pool or QThreadPool.globalInstance()
        self._workers: Set[_Worker] = set()
        self._busy = False
        self._downloading = False
        self._cancel_requested = False
        self._status_text = "Search for a recording to begin."
        self._status_color = "#9aa8c7"
        self._progress = 0.0
        self._progress_detail = ""
        self._last_download: Optional[Path] = None
        self._active_workflow = workflow
        self._recordings = RecordingController(self)
        self._catalog = CatalogController(self)
        self._queue = DownloadQueue(self)
        self._settings = SettingsBridge(self)

    # Compatibility aliases used by tests / collaborators
    @property
    def _catalog_releases(self) -> List:
        return self._catalog.releases

    @property
    def _current_download_job(self):
        return self._queue.current

    # --- Properties (QML bindings) -----------------------------------------

    @Property("QVariantList", notify=recordingResultsChanged)
    def recordingResults(self) -> List[dict]:
        return self._recordings.recording_rows

    @Property("QVariantList", notify=videoResultsChanged)
    def videoResults(self) -> List[dict]:
        return self._recordings.video_rows

    @Property("QVariantList", notify=catalogResultsChanged)
    def catalogResults(self) -> List[dict]:
        return self._catalog.rows

    @Property(int, notify=catalogResultsChanged)
    def catalogTotalCount(self) -> int:
        return len(self._catalog.all_rows)

    @Property("QVariantList", notify=tracksChanged)
    def releaseTracks(self) -> List[dict]:
        return self._catalog.track_rows

    @Property(int, notify=tracksChanged)
    def selectedTrackCount(self) -> int:
        return self._catalog.selected_track_count

    @Property(int, notify=selectionChanged)
    def selectedCatalogIndex(self) -> int:
        return self._catalog.selected_index

    @Property(bool, notify=tracksChanged)
    def canDownloadRelease(self) -> bool:
        return self._catalog.can_download_release

    @Property(int, notify=selectionChanged)
    def selectedRecordingIndex(self) -> int:
        return self._recordings.selected_recording

    @Property(int, notify=selectionChanged)
    def selectedVideoIndex(self) -> int:
        return self._recordings.selected_video

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Property(bool, notify=busyChanged)
    def downloading(self) -> bool:
        return self._downloading

    @Property(bool, notify=selectionChanged)
    def canDownload(self) -> bool:
        return self._recordings.can_download

    @Property(str, notify=statusChanged)
    def statusText(self) -> str:
        return self._status_text

    @Property(str, notify=statusChanged)
    def statusColor(self) -> str:
        return self._status_color

    @Property(float, notify=progressChanged)
    def downloadProgress(self) -> float:
        return self._progress

    @Property(str, notify=progressChanged)
    def progressDetail(self) -> str:
        return self._progress_detail

    @Property(bool, notify=lastDownloadChanged)
    def hasLastDownload(self) -> bool:
        return self._last_download is not None

    @Property("QVariantList", notify=queueChanged)
    def queueRows(self) -> List[dict]:
        return self._queue.rows

    @Property(int, notify=queueChanged)
    def queueCount(self) -> int:
        return self._queue.active_count

    @Property("QVariantMap", notify=settingsChanged)
    def apiSettings(self) -> dict:
        return self._settings.summary()

    @Property(str, notify=settingsChanged)
    def settingsMessage(self) -> str:
        return self._settings.message

    @Property(int, constant=True)
    def minYear(self) -> int:
        return self._settings.min_year

    @Property(int, constant=True)
    def maxYear(self) -> int:
        return self._settings.max_year

    # --- Slots (thin QML wrappers) ----------------------------------------

    @Slot("QVariantMap", result=bool)
    def saveApiSettings(self, updates: dict) -> bool:
        return self._settings.save(updates)

    @Slot(str, result=bool)
    def clearApiCredentials(self, provider: str) -> bool:
        return self._settings.clear_provider(provider)

    @Slot(str, str, str, str)
    def searchRecordings(
        self,
        title: str,
        artist: str,
        album: str,
        year_text: str,
    ) -> None:
        self._recordings.search_recordings(title, artist, album, year_text)

    @Slot(int)
    def selectRecording(self, index: int) -> None:
        self._recordings.select_recording(index)

    @Slot(int)
    def selectVideo(self, index: int) -> None:
        self._recordings.select_video(index)

    @Slot(str)
    def filterCatalogResults(self, query: str) -> None:
        self._catalog.filter_results(query)

    @Slot(str, str, str, str, str, str)
    def searchAlbums(
        self,
        album: str,
        artist: str,
        year_text: str,
        release_type: str,
        year_from_text: str = "",
        year_to_text: str = "",
    ) -> None:
        self._catalog.search_albums(
            album,
            artist,
            year_text,
            release_type,
            year_from_text,
            year_to_text,
        )

    @Slot(str, str, str, bool, str, str)
    def searchDiscography(
        self,
        artist: str,
        year_text: str,
        release_type: str,
        include_compilations: bool,
        year_from_text: str = "",
        year_to_text: str = "",
    ) -> None:
        self._catalog.search_discography(
            artist,
            year_text,
            release_type,
            include_compilations,
            year_from_text,
            year_to_text,
        )

    @Slot(int)
    def selectCatalogRelease(self, index: int) -> None:
        self._catalog.select_release(index)

    @Slot(int)
    def toggleTrack(self, index: int) -> None:
        self._catalog.toggle_track(index)

    @Slot(bool)
    def selectAllTracks(self, selected: bool) -> None:
        self._catalog.select_all_tracks(selected)

    @Slot(str, int)
    def downloadSelectedRelease(self, quality: str, jobs: int) -> None:
        if not self.canDownloadRelease or self.release_workflow is None:
            return
        release_info = self._catalog.release_info
        numbers = [
            row["position"] for row in self._catalog.track_rows if row["selected"]
        ]
        label = f"{release_info.artist} — {release_info.title}"
        self._queue.enqueue(
            label,
            lambda progress: self.release_workflow.download(
                release_info,
                numbers,
                quality=quality or "audio",
                jobs=jobs,
                progress_callback=progress,
            ),
            self.release_workflow,
            with_progress=True,
        )

    @Slot(str)
    def downloadSelected(self, quality: str) -> None:
        if not self.canDownload:
            return
        recording = self._recordings.recordings[self._recordings.selected_recording]
        video = self._recordings.videos[self._recordings.selected_video]
        label = f"{recording.artist} — {recording.title}"
        self._queue.enqueue(
            label,
            lambda progress: self.workflow.download(
                recording,
                video,
                quality=quality or "audio",
                progress_callback=progress,
            ),
            self.workflow,
            with_progress=True,
        )

    @Slot()
    def cancelDownload(self) -> None:
        self._queue.cancel()

    @Slot()
    def clearFinishedQueueItems(self) -> None:
        self._queue.clear_finished()

    @Slot()
    def openDownloadsFolder(self) -> None:
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self.workflow.downloads_dir.resolve()))
        )

    @Slot()
    def revealLastDownload(self) -> None:
        if self._last_download is not None:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self._last_download.parent.resolve()))
            )

    # --- Shared host helpers used by collaborators ------------------------

    @Slot(object)
    def _catalog_found(self, releases) -> None:
        self._catalog.on_catalog_found(releases)

    def _queued_download_progressed(self, job, progress: dict) -> None:
        self._queue.queued_progressed(job, progress)

    def _set_busy(self, busy: bool) -> None:
        changed = self._busy != busy
        self._busy = busy
        if changed:
            self.busyChanged.emit()
            self.selectionChanged.emit()
            self.tracksChanged.emit()

    def _set_status(self, text: str, color: str = "#9aa8c7") -> None:
        self._status_text = text
        self._status_color = color
        self.statusChanged.emit()

    def _start_worker(
        self,
        function: Callable,
        result_handler: Callable,
        *,
        with_progress: bool = False,
    ) -> None:
        worker = _Worker(function, with_progress=with_progress)
        self._workers.add(worker)
        worker.signals.result.connect(result_handler)
        worker.signals.error.connect(self._operation_failed)
        if with_progress:
            worker.signals.progress.connect(self._download_progressed)
        worker.signals.finished.connect(
            lambda current=worker: self._worker_finished(current)
        )
        self._set_busy(True)
        self.thread_pool.start(worker)

    @Slot(object)
    def _download_progressed(self, progress: dict) -> None:
        try:
            percent = float(progress.get("percent", self._progress) or 0.0)
        except (TypeError, ValueError):
            percent = self._progress
        self._progress = max(0.0, min(100.0, percent))
        details = []
        if progress.get("message"):
            details.append(str(progress["message"]))
        if progress.get("speed"):
            details.append(str(progress["speed"]))
        if progress.get("eta"):
            raw_eta = progress["eta"]
            eta = str(raw_eta)
            if eta.upper().startswith("ETA"):
                details.append(eta)
            elif isinstance(raw_eta, (int, float)):
                details.append(f"ETA {eta}s")
            else:
                details.append(f"ETA {eta}")
        self._progress_detail = " · ".join(details) or str(
            progress.get("status", "Downloading…")
        )
        self.progressChanged.emit()

    @Slot(object)
    def _download_finished(self, result: RecordingDownloadResult) -> None:
        self._progress = 100.0
        self._progress_detail = str(result.path)
        self._last_download = result.path
        self.progressChanged.emit()
        self.lastDownloadChanged.emit()
        if result.warning:
            self._set_status(result.warning, "#ffc66d")
        elif result.file_existed:
            self._set_status("File already existed; metadata was refreshed.", "#7ce7b2")
        else:
            self._set_status("Download completed successfully.", "#7ce7b2")

    @Slot(object)
    def _release_download_finished(self, result: ReleaseDownloadResult) -> None:
        self._progress = 100.0
        self._progress_detail = (
            f"Processed {result.processed} · Failed {result.failed}"
        )
        self.progressChanged.emit()
        if result.failed:
            failed = ", ".join(str(number) for number in result.failed_track_numbers)
            self._set_status(f"Release finished with failed tracks: {failed}", "#ffc66d")
        elif result.verification_mismatches:
            self._set_status(
                "Release downloaded, but AcoustID flagged "
                f"{result.verification_mismatches} possible mismatch(es).",
                "#ffc66d",
            )
        elif result.verified:
            self._set_status(
                f"Release download completed · {result.verified} track(s) verified.",
                "#7ce7b2",
            )
        else:
            self._set_status("Release download completed successfully.", "#7ce7b2")

    @Slot(str)
    def _operation_failed(self, message: str) -> None:
        if self._cancel_requested:
            self._set_status("Download cancelled.", "#ffc66d")
            self._progress_detail = "Cancelled"
            self.progressChanged.emit()
        else:
            self._set_status(message or "Operation failed.", "#ff8797")

    def _worker_finished(self, worker: _Worker) -> None:
        self._workers.discard(worker)
        self._set_busy(False)
        self._cancel_requested = False
