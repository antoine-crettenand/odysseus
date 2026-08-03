"""Presentation-neutral release and discography workflow."""

from dataclasses import dataclass
from typing import List, Optional

from ..core.validation import validate_year_range
from ..domain.music.download.download_service import DownloadService
from ..domain.music.download.orchestrator import DownloadOrchestrator
from ..domain.music.download.progress import ReleaseProgressCallback
from ..domain.music.search.search_service import SearchService
from ..models.releases import ReleaseInfo
from ..models.search_results import MusicBrainzSong
from ..models.song import SongData


@dataclass(frozen=True)
class ReleaseDownloadResult:
    """Result of downloading selected tracks from a release."""

    processed: int
    failed: int
    failed_track_numbers: List[int]
    verified: int = 0
    verification_mismatches: int = 0
    verification_inconclusive: int = 0

    @property
    def succeeded(self) -> bool:
        return self.failed == 0


class ReleaseWorkflow:
    """Search, inspect, and download releases without presentation code."""

    def __init__(
        self,
        search_service: SearchService,
        download_service: DownloadService,
        download_orchestrator: DownloadOrchestrator,
        acoustid_client=None,
    ) -> None:
        self.search_service = search_service
        self.download_service = download_service
        self.download_orchestrator = download_orchestrator
        self.acoustid_client = acoustid_client

    def search_releases(
        self,
        album: str,
        artist: str,
        *,
        year: Optional[int] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        release_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[MusicBrainzSong]:
        """Search release candidates by album and artist."""
        validate_year_range(year, year_from, year_to)
        song = SongData(
            title="",
            artist=artist,
            album=album,
            release_year=year,
        )
        return self.search_service.search_releases(
            song,
            limit=max(1, limit),
            release_type=release_type or None,
            year_from=year_from,
            year_to=year_to,
        )

    def search_discography(
        self,
        artist: str,
        *,
        year: Optional[int] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        release_type: Optional[str] = None,
        include_compilations: bool = False,
    ) -> List[MusicBrainzSong]:
        """Browse releases credited to an artist."""
        validate_year_range(year, year_from, year_to)
        return self.search_service.search_artist_releases(
            artist,
            year=year,
            release_type=release_type or None,
            include_compilations=include_compilations,
            year_from=year_from,
            year_to=year_to,
        )

    def get_release_info(self, release: MusicBrainzSong) -> ReleaseInfo:
        """Load a selected release and its track listing."""
        info = self.search_service.get_release_info(
            release.mbid,
            source=release.source or "musicbrainz",
        )
        if info is None:
            raise RuntimeError("Could not load the selected release details")
        if not info.artist:
            info.artist = release.artist
        if not info.title:
            info.title = release.album or release.title
        if not info.release_date:
            info.release_date = release.release_date
        if not info.original_release_date:
            info.original_release_date = release.original_release_date
        return info

    def download(
        self,
        release_info: ReleaseInfo,
        track_numbers: List[int],
        *,
        quality: str = "audio",
        jobs: int = 1,
        progress_callback: Optional[ReleaseProgressCallback] = None,
    ) -> ReleaseDownloadResult:
        """Run the full album/playlist/individual fallback chain."""
        available = {track.position for track in release_info.tracks}
        selected = sorted(set(track_numbers))
        if not selected:
            raise ValueError("Select at least one track")
        if any(number not in available for number in selected):
            raise ValueError("The track selection contains an invalid track number")

        download_arguments = {
            "silent": True,
            "jobs": jobs,
        }
        if progress_callback is not None:
            download_arguments["progress_callback"] = progress_callback
        processed, failed = self.download_orchestrator.download_release_tracks(
            release_info,
            selected,
            quality,
            **download_arguments,
        )
        verified = 0
        mismatches = 0
        inconclusive = 0
        if self.acoustid_client and self.acoustid_client.is_available():
            paths = self.download_orchestrator.path_manager.get_existing_tracks(
                release_info, selected
            )
            tracks = {track.position: track for track in release_info.tracks}
            for position, path in paths.items():
                track = tracks.get(position)
                if track is None or not track.mbid:
                    continue
                try:
                    verification = self.acoustid_client.verify(path, track.mbid)
                except Exception:
                    inconclusive += 1
                    continue
                if verification.status == "verified":
                    verified += 1
                elif verification.status == "mismatch":
                    mismatches += 1
                elif verification.status == "inconclusive":
                    inconclusive += 1
        return ReleaseDownloadResult(
            processed=processed,
            failed=failed,
            failed_track_numbers=list(
                self.download_orchestrator.last_failed_track_numbers
            ),
            verified=verified,
            verification_mismatches=mismatches,
            verification_inconclusive=inconclusive,
        )

    def cancel(self) -> None:
        """Cancel active release downloads."""
        self.download_service.cancel_active_downloads()
