"""
Download service for handling file downloads.
"""

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from queue import Empty, Queue
import threading
import weakref
from typing import Optional, Dict, Any, List, Callable, Tuple
from pathlib import Path
from ....clients.path_utils import PathUtils
from ....clients.youtube_downloader import YouTubeDownloader


MAX_PARALLEL_DOWNLOADS = 4


@dataclass(frozen=True)
class DownloadRequest:
    """One independently downloadable media item."""

    key: Any
    url: str
    quality: str
    metadata: Dict[str, Any]


@dataclass(frozen=True)
class DownloadResult:
    """Outcome for one batch download request."""

    key: Any
    path: Optional[Path] = None
    file_existed: bool = False
    error: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        return self.path is not None


class DownloadService:
    """Service for handling downloads."""

    def __init__(self, download_dir: Optional[str] = None, downloader=None):
        """
        Initialize download service with dependencies.

        Args:
            download_dir: Optional download directory path
            downloader: Optional YouTubeDownloader instance
        """
        self.downloader = downloader or YouTubeDownloader(download_dir)
        self.downloads_dir = self.downloader.download_dir
        self._target_locks = weakref.WeakValueDictionary()
        self._target_locks_guard = threading.Lock()

    @staticmethod
    def validate_worker_count(workers: int) -> int:
        """Validate the bounded parallel-download worker count."""
        if not isinstance(workers, int) or isinstance(workers, bool):
            raise ValueError("jobs must be an integer")
        if workers < 1 or workers > MAX_PARALLEL_DOWNLOADS:
            raise ValueError(
                f"jobs must be between 1 and {MAX_PARALLEL_DOWNLOADS}"
            )
        return workers

    @staticmethod
    def _reservation_key(request: DownloadRequest) -> str:
        """Mirror downloader path rules to reserve the actual output target."""
        metadata = request.metadata or {}
        if not metadata or not metadata.get("title"):
            return "__unresolved_output__"

        sanitize = PathUtils.sanitize_filename
        title = sanitize(metadata["title"])
        track_number = metadata.get("track_number")
        filename = (
            f"{track_number:02d} - {title}"
            if track_number
            else title
        )

        if metadata.get("is_playlist"):
            playlist_name = metadata.get(
                "playlist_name",
                metadata.get("album", "Unknown Playlist"),
            )
            parts = (
                "Playlists",
                sanitize(playlist_name),
                filename,
            )
        else:
            artist = sanitize(metadata.get("artist") or "Unknown Artist")
            album = sanitize(metadata.get("album") or "Unknown Album")
            year = metadata.get("year")
            folder = sanitize(f"{album} ({year})" if year else album)
            parts = (artist, folder, filename)

        return "\x1f".join(str(part).casefold().strip() for part in parts)

    def _get_target_lock(self, request: DownloadRequest) -> threading.Lock:
        key = self._reservation_key(request)
        with self._target_locks_guard:
            lock = self._target_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._target_locks[key] = lock
            return lock

    def _download_request(
        self,
        request: DownloadRequest,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> DownloadResult:
        """Execute one request while reserving its target path."""
        try:
            with self._get_target_lock(request):
                if request.quality == "audio":
                    result = self.download_high_quality_audio(
                        request.url,
                        metadata=request.metadata,
                        quiet=True,
                        progress_callback=progress_callback,
                    )
                else:
                    result = self.download_video(
                        request.url,
                        quality=request.quality,
                        audio_only=False,
                        metadata=request.metadata,
                        quiet=True,
                        progress_callback=progress_callback,
                    )

            if result is None:
                return DownloadResult(
                    request.key,
                    error="Download service returned no result",
                )
            path, file_existed = result
            if path is None:
                return DownloadResult(
                    request.key,
                    error="Download completed without creating a file",
                )
            return DownloadResult(request.key, path, file_existed)
        except Exception as error:
            return DownloadResult(request.key, error=str(error))

    def download_many(
        self,
        requests: List[DownloadRequest],
        workers: int = 1,
        progress_callback: Optional[
            Callable[[Any, Dict[str, Any]], None]
        ] = None,
    ) -> List[DownloadResult]:
        """
        Download independent requests with bounded concurrency.

        Results preserve request order. Progress callbacks always execute on
        the calling thread, never on worker threads.
        """
        workers = self.validate_worker_count(workers)
        if not requests:
            return []

        reset_cancellation = getattr(self.downloader, "reset_cancellation", None)
        if reset_cancellation:
            reset_cancellation()

        if workers == 1 or len(requests) == 1:
            return [
                self._download_request(
                    request,
                    (
                        lambda info, key=request.key: progress_callback(key, info)
                    )
                    if progress_callback
                    else None,
                )
                for request in requests
            ]

        event_queue: Queue = Queue()
        results: List[Optional[DownloadResult]] = [None] * len(requests)

        def run(index: int, request: DownloadRequest) -> Tuple[int, DownloadResult]:
            callback = lambda info: event_queue.put((request.key, info))
            return index, self._download_request(request, callback)

        executor = ThreadPoolExecutor(
            max_workers=min(workers, len(requests)),
            thread_name_prefix="odysseus-download",
        )
        futures = {
            executor.submit(run, index, request)
            for index, request in enumerate(requests)
        }
        pending = set(futures)
        try:
            while pending:
                completed, pending = wait(
                    pending,
                    timeout=0.1,
                    return_when=FIRST_COMPLETED,
                )
                self._drain_progress_events(event_queue, progress_callback)
                for future in completed:
                    index, result = future.result()
                    results[index] = result
            self._drain_progress_events(event_queue, progress_callback)
        except BaseException:
            for future in pending:
                future.cancel()
            self.cancel_active_downloads()
            executor.shutdown(wait=False)
            raise
        else:
            executor.shutdown(wait=True)

        return [result for result in results if result is not None]

    @staticmethod
    def _drain_progress_events(
        event_queue: Queue,
        progress_callback: Optional[Callable[[Any, Dict[str, Any]], None]],
    ) -> None:
        """Forward queued worker progress from the calling thread."""
        while True:
            try:
                key, info = event_queue.get_nowait()
            except Empty:
                return
            if progress_callback:
                progress_callback(key, info)

    def cancel_active_downloads(self) -> None:
        """Cancel active downloader subprocesses when supported."""
        cancel = getattr(self.downloader, "cancel_active_downloads", None)
        if cancel:
            cancel()

    def download_video(self, url: str, quality: str = "best",
                      audio_only: bool = True, metadata: Optional[Dict[str, Any]] = None,
                      quiet: bool = True, progress_callback: Optional[Callable] = None) -> Tuple[Optional[Path], bool]:
        """Download a video from URL."""
        return self.downloader.download(url, quality, audio_only, metadata, quiet=quiet, progress_callback=progress_callback)

    def download_high_quality_audio(self, url: str, metadata: Optional[Dict[str, Any]] = None,
                                     quiet: bool = True, progress_callback: Optional[Callable] = None) -> Tuple[Optional[Path], bool]:
        """Download high-quality audio from video."""
        return self.downloader.download_high_quality_audio(url, metadata, quiet=quiet, progress_callback=progress_callback)

    def download_playlist(self, url: str, quality: str = "bestaudio") -> List[str]:
        """Download a YouTube playlist."""
        return self.downloader.download_playlist(url, quality)

    def get_available_formats(self, url: str) -> List[Dict[str, Any]]:
        """Get available formats for a video."""
        return self.downloader.get_available_formats(url)

    def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Get video information."""
        return self.downloader.get_video_info(url)

    def get_video_chapters(self, url: str) -> Optional[List[Dict[str, Any]]]:
        """Get video chapters/timestamps."""
        return self.downloader.get_video_chapters(url)

    def get_playlist_info(self, url: str) -> Optional[List[Dict[str, Any]]]:
        """Get information about videos in a YouTube playlist."""
        return self.downloader.get_playlist_info(url)

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize a title for use at the filesystem boundary."""
        return self.downloader.path_utils.sanitize_filename(filename)

    def create_organized_path(
        self,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Create the configured output directory for metadata."""
        return self.downloader.path_utils.create_organized_path(
            self.downloads_dir,
            metadata,
        )

    def split_video_into_tracks(
        self,
        video_path: Path,
        track_timestamps: List[Dict[str, Any]],
        output_dir: Path,
        metadata_list: List[Dict[str, Any]],
        progress_callback: Optional[Callable] = None
    ) -> List[Optional[Path]]:
        """Split a full album video into individual tracks."""
        return self.downloader.split_video_into_tracks(
            video_path, track_timestamps, output_dir, metadata_list, progress_callback
        )
