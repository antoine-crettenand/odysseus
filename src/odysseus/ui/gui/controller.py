"""Qt bridge between QML and presentation-neutral workflows."""

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Callable, List, Optional, Set

from PySide6.QtCore import (
    QObject,
    Property,
    QRunnable,
    QThreadPool,
    QTimer,
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
from ...core.config import VALIDATION_RULES
from ...core.validation import validate_year, validate_year_range
from ...domain.music.common.date_utils import (
    extract_year,
    format_release_date_label,
    get_original_release_year,
)
from ...models.search_results import MusicBrainzSong, YouTubeVideo


logger = logging.getLogger(__name__)


class _WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    progress = Signal(object)
    finished = Signal()


class _Worker(QRunnable):
    """Run a blocking workflow operation outside the Qt UI thread."""

    def __init__(self, function: Callable, *, with_progress: bool = False) -> None:
        super().__init__()
        self.function = function
        self.with_progress = with_progress
        self.signals = _WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            if self.with_progress:
                result = self.function(self.signals.progress.emit)
            else:
                result = self.function()
        except Exception as error:
            logger.exception("Desktop workflow operation failed")
            self.signals.error.emit(str(error) or error.__class__.__name__)
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()


@dataclass
class _DownloadJob:
    """One immutable request managed by the background download queue."""

    label: str
    function: Callable
    workflow: object
    with_progress: bool
    row: dict


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
        self._recordings: List[MusicBrainzSong] = []
        self._videos: List[YouTubeVideo] = []
        self._recording_rows: List[dict] = []
        self._video_rows: List[dict] = []
        self._selected_recording = -1
        self._selected_video = -1
        self._busy = False
        self._downloading = False
        self._cancel_requested = False
        self._status_text = "Search for a recording to begin."
        self._status_color = "#9aa8c7"
        self._progress = 0.0
        self._progress_detail = ""
        self._last_download: Optional[Path] = None
        self._catalog_releases: List[MusicBrainzSong] = []
        self._catalog_rows: List[dict] = []
        self._all_catalog_releases: List[MusicBrainzSong] = []
        self._all_catalog_rows: List[dict] = []
        self._selected_catalog_release = -1
        self._release_info = None
        self._track_rows: List[dict] = []
        self._active_workflow = workflow
        self._download_jobs: List[_DownloadJob] = []
        self._current_download_job: Optional[_DownloadJob] = None
        self._settings_message = ""

    @Property("QVariantList", notify=recordingResultsChanged)
    def recordingResults(self) -> List[dict]:
        return self._recording_rows

    @Property("QVariantList", notify=videoResultsChanged)
    def videoResults(self) -> List[dict]:
        return self._video_rows

    @Property("QVariantList", notify=catalogResultsChanged)
    def catalogResults(self) -> List[dict]:
        return self._catalog_rows

    @Property(int, notify=catalogResultsChanged)
    def catalogTotalCount(self) -> int:
        return len(self._all_catalog_rows)

    @Property("QVariantList", notify=tracksChanged)
    def releaseTracks(self) -> List[dict]:
        return self._track_rows

    @Property(int, notify=tracksChanged)
    def selectedTrackCount(self) -> int:
        return sum(bool(row["selected"]) for row in self._track_rows)

    @Property(int, notify=selectionChanged)
    def selectedCatalogIndex(self) -> int:
        return self._selected_catalog_release

    @Property(bool, notify=tracksChanged)
    def canDownloadRelease(self) -> bool:
        return not self._busy and any(row["selected"] for row in self._track_rows)

    @Property(int, notify=selectionChanged)
    def selectedRecordingIndex(self) -> int:
        return self._selected_recording

    @Property(int, notify=selectionChanged)
    def selectedVideoIndex(self) -> int:
        return self._selected_video

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Property(bool, notify=busyChanged)
    def downloading(self) -> bool:
        return self._downloading

    @Property(bool, notify=selectionChanged)
    def canDownload(self) -> bool:
        return (
            not self._busy
            and 0 <= self._selected_recording < len(self._recordings)
            and 0 <= self._selected_video < len(self._videos)
        )

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
        return [job.row for job in self._download_jobs]

    @Property(int, notify=queueChanged)
    def queueCount(self) -> int:
        return sum(
            job.row["status"] in {"Queued", "Downloading", "Cancelling"}
            for job in self._download_jobs
        )

    @Property("QVariantMap", notify=settingsChanged)
    def apiSettings(self) -> dict:
        if self.settings_service is None:
            return {
                "youtubeConfigured": False,
                "discogsConfigured": False,
                "spotifyConfigured": False,
                "appleMusicConfigured": False,
                "acoustidConfigured": False,
                "storefront": "us",
                "storageLabel": "Unavailable",
                "persistentStorage": False,
            }
        return self.settings_service.summary()

    @Property(str, notify=settingsChanged)
    def settingsMessage(self) -> str:
        return self._settings_message

    @Property(int, constant=True)
    def minYear(self) -> int:
        return int(VALIDATION_RULES["MIN_YEAR"])

    @Property(int, constant=True)
    def maxYear(self) -> int:
        return int(VALIDATION_RULES["MAX_YEAR"])

    @Slot("QVariantMap", result=bool)
    def saveApiSettings(self, updates: dict) -> bool:
        if self.settings_service is None:
            self._settings_message = "API settings are unavailable."
            self.settingsChanged.emit()
            return False
        try:
            self.settings_service.save(dict(updates))
        except Exception as error:
            self._settings_message = str(error) or "Could not save API settings."
            self.settingsChanged.emit()
            return False
        self._settings_message = "Provider settings saved and applied."
        self.settingsChanged.emit()
        return True

    @Slot(str, result=bool)
    def clearApiCredentials(self, provider: str) -> bool:
        if self.settings_service is None:
            self._settings_message = "API settings are unavailable."
            self.settingsChanged.emit()
            return False
        try:
            self.settings_service.clear_provider(provider)
        except Exception as error:
            self._settings_message = str(error) or "Could not clear credentials."
            self.settingsChanged.emit()
            return False
        self._settings_message = f"Cleared saved {provider} settings."
        self.settingsChanged.emit()
        return True

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

    def _enqueue_download(
        self,
        label: str,
        function: Callable,
        workflow: object,
        *,
        with_progress: bool = False,
    ) -> None:
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
        self._download_jobs.append(job)
        self.queueChanged.emit()
        self._set_status(f"Added to download queue: {label}", "#7ce7b2")
        self._start_next_download()

    def _start_next_download(self) -> None:
        if self._current_download_job is not None:
            return
        job = next(
            (item for item in self._download_jobs if item.row["status"] == "Queued"),
            None,
        )
        if job is None:
            return

        self._current_download_job = job
        self._active_workflow = job.workflow
        self._cancel_requested = False
        self._downloading = True
        self._progress = 0.0
        self._progress_detail = job.label
        job.row.update(
            status="Downloading",
            stage="Starting",
            detail="Preparing download…",
            progress=0.0,
        )
        self.busyChanged.emit()
        self.progressChanged.emit()
        self.queueChanged.emit()

        worker = _Worker(job.function, with_progress=job.with_progress)
        self._workers.add(worker)
        worker.signals.result.connect(
            lambda result, current=job: self._download_job_succeeded(current, result)
        )
        worker.signals.error.connect(
            lambda message, current=job: self._download_job_failed(current, message)
        )
        if job.with_progress:
            worker.signals.progress.connect(
                lambda progress, current=job: self._queued_download_progressed(
                    current, progress
                )
            )
        worker.signals.finished.connect(
            lambda current_worker=worker, current_job=job: (
                self._download_job_finished(current_worker, current_job)
            )
        )
        self.thread_pool.start(worker)

    @Slot(str, str, str, str)
    def searchRecordings(
        self,
        title: str,
        artist: str,
        album: str,
        year_text: str,
    ) -> None:
        if self._busy:
            return
        title = title.strip()
        artist = artist.strip()
        album = album.strip()
        if not title or not artist:
            self._set_status("Title and artist are required.", "#ff8797")
            return

        try:
            year = int(year_text.strip()) if year_text.strip() else None
            if year is not None:
                validate_year(year)
        except (TypeError, ValueError) as error:
            self._set_status(str(error), "#ff8797")
            return

        self._recordings = []
        self._videos = []
        self._recording_rows = []
        self._video_rows = []
        self._selected_recording = -1
        self._selected_video = -1
        self.recordingResultsChanged.emit()
        self.videoResultsChanged.emit()
        self.selectionChanged.emit()
        self._set_status("Searching metadata providers…", "#71d7ff")
        self._start_worker(
            lambda: self.workflow.search_recordings(
                title,
                artist,
                album or None,
                year,
            ),
            self._recordings_found,
        )

    @Slot(int)
    def selectRecording(self, index: int) -> None:
        if self._busy or not 0 <= index < len(self._recordings):
            return
        self._selected_recording = index
        self._selected_video = -1
        self._videos = []
        self._video_rows = []
        self.videoResultsChanged.emit()
        self.selectionChanged.emit()
        recording = self._recordings[index]
        self._set_status("Searching YouTube candidates…", "#71d7ff")
        self._start_worker(
            lambda: self.workflow.search_videos(recording),
            self._videos_found,
        )

    @Slot(int)
    def selectVideo(self, index: int) -> None:
        if self._busy or not 0 <= index < len(self._videos):
            return
        self._selected_video = index
        self.selectionChanged.emit()
        self._set_status("Ready to download.", "#7ce7b2")

    def _parse_year_filters(
        self,
        year_text: str,
        year_from_text: str,
        year_to_text: str,
    ):
        year = int(year_text.strip()) if year_text.strip() else None
        year_from = int(year_from_text.strip()) if year_from_text.strip() else None
        year_to = int(year_to_text.strip()) if year_to_text.strip() else None
        validate_year_range(year, year_from, year_to)
        return year, year_from, year_to

    def _clear_catalog(self) -> None:
        self._catalog_releases = []
        self._catalog_rows = []
        self._all_catalog_releases = []
        self._all_catalog_rows = []
        self._selected_catalog_release = -1
        self._release_info = None
        self._track_rows = []
        self.catalogResultsChanged.emit()
        self.tracksChanged.emit()
        self.selectionChanged.emit()

    @Slot(str)
    def filterCatalogResults(self, query: str) -> None:
        """Filter loaded releases locally while keeping row/release indexes aligned."""
        terms = query.casefold().split()
        if not terms:
            self._catalog_releases = list(self._all_catalog_releases)
            self._catalog_rows = list(self._all_catalog_rows)
        else:
            matches = []
            for release, row in zip(
                self._all_catalog_releases,
                self._all_catalog_rows,
            ):
                searchable = " ".join(
                    str(value)
                    for value in (
                        row.get("title", ""),
                        row.get("artist", ""),
                        row.get("date", ""),
                        row.get("year", ""),
                        row.get("editionYear", ""),
                        row.get("type", ""),
                        row.get("source", ""),
                        row.get("editionDetail", ""),
                        row.get("identifierDetail", ""),
                    )
                ).casefold()
                if all(term in searchable for term in terms):
                    matches.append((release, row))
            self._catalog_releases = [release for release, _ in matches]
            self._catalog_rows = [row for _, row in matches]

        # A visible index may refer to a different release after filtering.
        self._selected_catalog_release = -1
        self._release_info = None
        self._track_rows = []
        self.catalogResultsChanged.emit()
        self.tracksChanged.emit()
        self.selectionChanged.emit()

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
        if self._busy or self.release_workflow is None:
            return
        album = album.strip()
        artist = artist.strip()
        if not album or not artist:
            self._set_status("Album and artist are required.", "#ff8797")
            return
        try:
            year, year_from, year_to = self._parse_year_filters(
                year_text,
                year_from_text,
                year_to_text,
            )
        except ValueError as error:
            self._set_status(str(error), "#ff8797")
            return
        self._clear_catalog()
        self._set_status("Searching release providers…", "#71d7ff")
        self._start_worker(
            lambda: self.release_workflow.search_releases(
                album,
                artist,
                year=year,
                year_from=year_from,
                year_to=year_to,
                release_type=release_type or None,
            ),
            self._catalog_found,
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
        if self._busy or self.release_workflow is None:
            return
        artist = artist.strip()
        if not artist:
            self._set_status("Artist is required.", "#ff8797")
            return
        try:
            year, year_from, year_to = self._parse_year_filters(
                year_text,
                year_from_text,
                year_to_text,
            )
        except ValueError as error:
            self._set_status(str(error), "#ff8797")
            return
        self._clear_catalog()
        self._set_status("Loading artist discography…", "#71d7ff")
        self._start_worker(
            lambda: self.release_workflow.search_discography(
                artist,
                year=year,
                year_from=year_from,
                year_to=year_to,
                release_type=release_type or None,
                include_compilations=include_compilations,
            ),
            self._catalog_found,
        )

    @Slot(int)
    def selectCatalogRelease(self, index: int) -> None:
        if (
            self._busy
            or self.release_workflow is None
            or not 0 <= index < len(self._catalog_releases)
        ):
            return
        self._selected_catalog_release = index
        self._release_info = None
        self._track_rows = []
        self.tracksChanged.emit()
        self.selectionChanged.emit()
        release = self._catalog_releases[index]
        self._set_status("Loading track listing…", "#71d7ff")
        self._start_worker(
            lambda: self.release_workflow.get_release_info(release),
            self._release_loaded,
        )

    @Slot(int)
    def toggleTrack(self, index: int) -> None:
        if self._busy or not 0 <= index < len(self._track_rows):
            return
        self._track_rows[index]["selected"] = not self._track_rows[index]["selected"]
        self.tracksChanged.emit()

    @Slot(bool)
    def selectAllTracks(self, selected: bool) -> None:
        if self._busy:
            return
        for row in self._track_rows:
            row["selected"] = selected
        self.tracksChanged.emit()

    @Slot(str, int)
    def downloadSelectedRelease(self, quality: str, jobs: int) -> None:
        if not self.canDownloadRelease or self.release_workflow is None:
            return
        release_info = self._release_info
        numbers = [
            row["position"] for row in self._track_rows if row["selected"]
        ]
        label = f"{release_info.artist} — {release_info.title}"
        self._enqueue_download(
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
        recording = self._recordings[self._selected_recording]
        video = self._videos[self._selected_video]
        label = f"{recording.artist} — {recording.title}"
        self._enqueue_download(
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
        if not self._downloading:
            return
        self._cancel_requested = True
        if self._current_download_job is not None:
            self._current_download_job.row.update(
                status="Cancelling",
                detail="Cancellation requested",
            )
            self.queueChanged.emit()
        self._set_status("Cancelling download…", "#ffc66d")
        self._active_workflow.cancel()

    @Slot()
    def clearFinishedQueueItems(self) -> None:
        self._download_jobs = [
            job
            for job in self._download_jobs
            if job.row["status"] in {"Queued", "Downloading", "Cancelling"}
        ]
        self.queueChanged.emit()

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

    @Slot(object)
    def _recordings_found(self, recordings: List[MusicBrainzSong]) -> None:
        self._recordings = list(recordings)
        self._recording_rows = [
            {
                "title": item.title or "Unknown title",
                "artist": item.artist or "Unknown artist",
                "album": item.album or "Unknown album",
                "date": format_release_date_label(item),
                "source": item.source.title(),
                "score": item.score,
            }
            for item in self._recordings
        ]
        self.recordingResultsChanged.emit()
        if self._recordings:
            self._set_status(
                f"Found {len(self._recordings)} metadata candidate(s). Select one.",
                "#7ce7b2",
            )
        else:
            self._set_status("No matching recordings found.", "#ffc66d")

    @Slot(object)
    def _videos_found(self, videos: List[YouTubeVideo]) -> None:
        self._videos = list(videos)
        self._video_rows = [
            {
                "title": item.title or "Untitled video",
                "channel": item.channel or "Unknown channel",
                "duration": item.duration or "—",
                "views": item.views or "—",
            }
            for item in self._videos
        ]
        self.videoResultsChanged.emit()
        if self._videos:
            self._set_status(
                f"Found {len(self._videos)} video candidate(s). Select one.",
                "#7ce7b2",
            )
        else:
            self._set_status("No downloadable videos found.", "#ffc66d")

    @Slot(object)
    def _catalog_found(self, releases: List[MusicBrainzSong]) -> None:
        self._all_catalog_releases = sorted(
            releases,
            key=lambda release: (
                get_original_release_year(release) is None,
                get_original_release_year(release) or 0,
            ),
        )
        self._all_catalog_rows = []
        for item in self._all_catalog_releases:
            original_year = extract_year(item.original_release_date)
            edition_year = extract_year(item.release_date)
            cover_art_url = item.cover_art_url or ""
            if (
                not cover_art_url
                and item.source.casefold() == "musicbrainz"
                and item.mbid
            ):
                cover_art_url = (
                    "https://coverartarchive.org/release/"
                    f"{item.mbid}/front-250"
                )
            has_distinct_edition = bool(
                original_year
                and edition_year
                and original_year != edition_year
            )
            source_key = item.source.casefold()
            source_name = {
                "applemusic": "Apple Music",
                "musicbrainz": "MusicBrainz",
            }.get(source_key, item.source.title())
            edition_parts = []
            if item.country:
                edition_parts.append(item.country)
            if item.media_format:
                edition_parts.append(item.media_format)
            if item.label:
                edition_parts.append(item.label)
            if item.catalog_number:
                edition_parts.append(item.catalog_number)
            if item.track_count:
                edition_parts.append(f"{item.track_count} tracks")
            identifier_parts = []
            if item.barcode:
                identifier_parts.append(f"UPC/EAN {item.barcode}")
            if item.release_status:
                identifier_parts.append(item.release_status.title())
            self._all_catalog_rows.append(
                {
                    "title": item.album or item.title or "Unknown release",
                    "artist": item.artist or "Unknown artist",
                    "date": format_release_date_label(item),
                    "year": original_year or edition_year or "—",
                    "yearKind": "Original" if original_year else "Release",
                    "editionYear": edition_year if has_distinct_edition else "",
                    "isReissue": has_distinct_edition,
                    "coverArtUrl": cover_art_url,
                    "editionDetail": " · ".join(edition_parts),
                    "identifierDetail": " · ".join(identifier_parts),
                    "type": item.release_type or "Release",
                    "source": source_name,
                }
            )
        self._catalog_releases = list(self._all_catalog_releases)
        self._catalog_rows = list(self._all_catalog_rows)
        self.catalogResultsChanged.emit()
        if releases:
            self._set_status(
                f"Found {len(releases)} release(s). Select one to view tracks.",
                "#7ce7b2",
            )
        else:
            self._set_status("No matching releases found.", "#ffc66d")

    @Slot(object)
    def _release_loaded(self, release_info) -> None:
        self._release_info = release_info
        self._track_rows = [
            {
                "position": track.position,
                "title": track.title,
                "artist": track.artist or release_info.artist,
                "duration": track.duration or "—",
                "selected": True,
            }
            for track in release_info.tracks
        ]
        self.tracksChanged.emit()
        self._set_status(
            f"Loaded {len(self._track_rows)} tracks from {release_info.title}.",
            "#7ce7b2",
        )

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

    def _download_job_succeeded(self, job: _DownloadJob, result: object) -> None:
        if isinstance(result, RecordingDownloadResult):
            self._download_finished(result)
            detail = result.warning or str(result.path)
            status = "Completed with warning" if result.warning else "Completed"
        elif isinstance(result, ReleaseDownloadResult):
            self._release_download_finished(result)
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
        self.queueChanged.emit()

    def _download_job_failed(self, job: _DownloadJob, message: str) -> None:
        if self._cancel_requested:
            job.row.update(status="Cancelled", detail="Cancelled by user")
            self._set_status("Download cancelled.", "#ffc66d")
            self._progress_detail = "Cancelled"
        else:
            detail = message or "Download failed without an error message"
            job.row.update(status="Failed", detail=detail)
            self._set_status(f"Download failed: {detail}", "#ff8797")
            self._progress_detail = detail
        self.progressChanged.emit()
        self.queueChanged.emit()

    def _download_job_finished(self, worker: _Worker, job: _DownloadJob) -> None:
        self._workers.discard(worker)
        if job.row["status"] in {"Downloading", "Cancelling"}:
            job.row.update(
                status="Cancelled" if self._cancel_requested else "Failed",
                detail=(
                    "Cancelled by user"
                    if self._cancel_requested
                    else "The worker ended without returning a result"
                ),
            )
        self._current_download_job = None
        self._downloading = False
        self._cancel_requested = False
        self.busyChanged.emit()
        self.queueChanged.emit()
        QTimer.singleShot(0, self._start_next_download)

    def _queued_download_progressed(
        self,
        job: _DownloadJob,
        progress: dict,
    ) -> None:
        self._download_progressed(progress)
        job.row.update(
            progress=self._progress,
            detail=self._progress_detail,
            stage=str(progress.get("status") or job.row.get("stage", "Downloading")),
        )
        self.queueChanged.emit()

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
