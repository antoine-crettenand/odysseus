"""Recording/video search and selection helpers for the desktop controller."""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from ...core.validation import validate_year
from ...domain.music.common.date_utils import format_release_date_label
from ...models.search_results import MusicBrainzSong, YouTubeVideo

if TYPE_CHECKING:
    from .controller import OdysseusController


class RecordingController:
    """Plain helper owning recording/video row state and search flows."""

    def __init__(self, host: OdysseusController) -> None:
        self._host = host
        self.recordings: List[MusicBrainzSong] = []
        self.videos: List[YouTubeVideo] = []
        self.recording_rows: List[dict] = []
        self.video_rows: List[dict] = []
        self.selected_recording = -1
        self.selected_video = -1

    @property
    def can_download(self) -> bool:
        return (
            not self._host._busy
            and 0 <= self.selected_recording < len(self.recordings)
            and 0 <= self.selected_video < len(self.videos)
        )

    def search_recordings(
        self,
        title: str,
        artist: str,
        album: str,
        year_text: str,
    ) -> None:
        host = self._host
        if host._busy:
            return
        title = title.strip()
        artist = artist.strip()
        album = album.strip()
        if not title or not artist:
            host._set_status("Title and artist are required.", "#ff8797")
            return

        try:
            year = int(year_text.strip()) if year_text.strip() else None
            if year is not None:
                validate_year(year)
        except (TypeError, ValueError) as error:
            host._set_status(str(error), "#ff8797")
            return

        self.recordings = []
        self.videos = []
        self.recording_rows = []
        self.video_rows = []
        self.selected_recording = -1
        self.selected_video = -1
        host.recordingResultsChanged.emit()
        host.videoResultsChanged.emit()
        host.selectionChanged.emit()
        host._set_status("Searching metadata providers…", "#71d7ff")
        host._start_worker(
            lambda: host.workflow.search_recordings(
                title,
                artist,
                album or None,
                year,
            ),
            self.on_recordings_found,
        )

    def select_recording(self, index: int) -> None:
        host = self._host
        if host._busy or not 0 <= index < len(self.recordings):
            return
        self.selected_recording = index
        self.selected_video = -1
        self.videos = []
        self.video_rows = []
        host.videoResultsChanged.emit()
        host.selectionChanged.emit()
        recording = self.recordings[index]
        host._set_status("Searching YouTube candidates…", "#71d7ff")
        host._start_worker(
            lambda: host.workflow.search_videos(recording),
            self.on_videos_found,
        )

    def select_video(self, index: int) -> None:
        host = self._host
        if host._busy or not 0 <= index < len(self.videos):
            return
        self.selected_video = index
        host.selectionChanged.emit()
        host._set_status("Ready to download.", "#7ce7b2")

    def on_recordings_found(self, recordings: List[MusicBrainzSong]) -> None:
        host = self._host
        self.recordings = list(recordings)
        self.recording_rows = [
            {
                "title": item.title or "Unknown title",
                "artist": item.artist or "Unknown artist",
                "album": item.album or "Unknown album",
                "date": format_release_date_label(item),
                "source": item.source.title(),
                "score": item.score,
            }
            for item in self.recordings
        ]
        host.recordingResultsChanged.emit()
        if self.recordings:
            host._set_status(
                f"Found {len(self.recordings)} metadata candidate(s). Select one.",
                "#7ce7b2",
            )
        else:
            host._set_status("No matching recordings found.", "#ffc66d")

    def on_videos_found(self, videos: List[YouTubeVideo]) -> None:
        host = self._host
        self.videos = list(videos)
        self.video_rows = [
            {
                "title": item.title or "Untitled video",
                "channel": item.channel or "Unknown channel",
                "duration": item.duration or "—",
                "views": item.views or "—",
            }
            for item in self.videos
        ]
        host.videoResultsChanged.emit()
        if self.videos:
            host._set_status(
                f"Found {len(self.videos)} video candidate(s). Select one.",
                "#7ce7b2",
            )
        else:
            host._set_status("No downloadable videos found.", "#ffc66d")
