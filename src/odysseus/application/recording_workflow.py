"""Application workflow for recording search and download."""

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ..domain.music.common.date_utils import extract_year
from ..domain.music.download.download_service import DownloadService
from ..domain.music.metadata.metadata_service import MetadataService
from ..domain.music.search.search_service import SearchService
from ..models.search_results import MusicBrainzSong, YouTubeVideo
from ..models.song import AudioMetadata, SongData


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecordingDownloadResult:
    """Machine-readable result of a recording download."""

    path: Path
    file_existed: bool = False
    metadata_applied: bool = False
    warning: Optional[str] = None
    verification_status: str = "not_run"
    verification_score: Optional[float] = None


class RecordingWorkflow:
    """Coordinate recording operations without terminal or GUI dependencies."""

    def __init__(
        self,
        search_service: SearchService,
        download_service: DownloadService,
        metadata_service: MetadataService,
        acoustid_client=None,
    ) -> None:
        self.search_service = search_service
        self.download_service = download_service
        self.metadata_service = metadata_service
        self.acoustid_client = acoustid_client

    @property
    def downloads_dir(self) -> Path:
        """Return the configured download directory."""
        return Path(self.download_service.downloads_dir)

    def search_recordings(
        self,
        title: str,
        artist: str,
        album: Optional[str] = None,
        year: Optional[int] = None,
        *,
        offset: int = 0,
        limit: int = 10,
    ) -> List[MusicBrainzSong]:
        """Search metadata providers for matching recordings."""
        song = SongData(
            title=title,
            artist=artist,
            album=album or None,
            release_year=year,
        )
        return self.search_service.search_recordings(
            song,
            offset=max(0, offset),
            limit=max(1, limit),
        )

    def search_videos(
        self,
        recording: MusicBrainzSong,
        *,
        offset: int = 0,
        limit: int = 6,
    ) -> List[YouTubeVideo]:
        """Find downloadable video candidates for a metadata recording."""
        query = f"{recording.artist} {recording.title}".strip()
        return self.search_service.search_youtube(
            query,
            max_results=max(1, limit),
            offset=max(0, offset),
        )

    def download(
        self,
        recording: MusicBrainzSong,
        video: YouTubeVideo,
        *,
        quality: str = "audio",
        progress_callback: Optional[Callable[[Dict], None]] = None,
    ) -> RecordingDownloadResult:
        """Download one selected recording and apply its metadata."""
        youtube_url = video.youtube_url
        if not youtube_url:
            raise ValueError("The selected video has no downloadable URL")

        year_text = extract_year(
            recording.original_release_date or recording.release_date
        )
        year = int(year_text) if year_text is not None else None
        metadata = {
            "title": recording.title,
            "artist": recording.artist,
            "album": recording.album,
            "year": year,
        }

        if quality == "audio":
            downloaded_path, file_existed = (
                self.download_service.download_high_quality_audio(
                    youtube_url,
                    metadata=metadata,
                    quiet=True,
                    progress_callback=progress_callback,
                )
            )
        else:
            downloaded_path, file_existed = self.download_service.download_video(
                youtube_url,
                quality=quality,
                audio_only=False,
                metadata=metadata,
                quiet=True,
                progress_callback=progress_callback,
            )

        if downloaded_path is None:
            raise RuntimeError("Download completed without creating a file")

        warnings = []
        metadata_applied = False
        audio_metadata = AudioMetadata(
            title=recording.title,
            artist=recording.artist,
            album=recording.album,
            year=year,
            genre=recording.genre,
        )
        if recording.mbid:
            try:
                audio_metadata.cover_art_data = self.metadata_service.fetch_cover_art(
                    recording.mbid,
                    console=None,
                )
            except Exception as error:
                logger.warning("Could not fetch recording cover art: %s", error)
                warnings.append(f"Cover art could not be fetched: {error}")

        try:
            self.metadata_service.set_final_metadata(audio_metadata)
            metadata_applied = self.metadata_service.apply_metadata_to_file(
                str(downloaded_path),
                quiet=True,
            )
            if not metadata_applied:
                warnings.append(
                    "The audio downloaded, but its metadata could not be applied."
                )
        except Exception as error:
            logger.warning("Could not apply recording metadata: %s", error)
            warnings.append(f"The audio downloaded, but metadata failed: {error}")

        verification_status = "not_run"
        verification_score = None
        if self.acoustid_client and self.acoustid_client.is_available():
            try:
                verification = self.acoustid_client.verify(
                    Path(downloaded_path), recording.mbid
                )
                verification_status = verification.status
                verification_score = verification.score
                if verification.status == "mismatch":
                    warnings.append(
                        "AcoustID indicates that the downloaded audio may be a "
                        "different recording."
                    )
            except Exception as error:
                logger.warning("AcoustID verification failed: %s", error)
                verification_status = "inconclusive"

        return RecordingDownloadResult(
            path=Path(downloaded_path),
            file_existed=file_existed,
            metadata_applied=metadata_applied,
            warning=" ".join(warnings) or None,
            verification_status=verification_status,
            verification_score=verification_score,
        )

    def cancel(self) -> None:
        """Request cancellation of active downloads."""
        self.download_service.cancel_active_downloads()
