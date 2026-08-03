"""Strategy for downloading independent tracks."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .base_strategy import BaseDownloadStrategy
from ..download_service import DownloadRequest, DownloadResult
from ..progress import ReleaseProgressCallback, emit_release_progress
from .....models.releases import ReleaseInfo, Track
from ...search.video_searcher import VideoSearcher
from ...search.playlist_checker import PlaylistChecker


@dataclass(frozen=True)
class _PreparedTrack:
    track_number: int
    track: Track
    youtube_url: str
    request: DownloadRequest


class IndividualTracksStrategy(BaseDownloadStrategy):
    """Search tracks sequentially, then download independent files in parallel."""

    def __init__(
        self,
        download_service,
        metadata_service,
        search_service,
        display_manager,
        video_validator,
        title_matcher,
        path_manager,
    ):
        super().__init__(
            download_service,
            metadata_service,
            search_service,
            display_manager,
            video_validator,
            title_matcher,
            path_manager,
        )
        self.video_searcher = VideoSearcher(
            search_service,
            video_validator,
            title_matcher,
            display_manager,
        )
        self.playlist_checker = PlaylistChecker(
            download_service,
            search_service,
            video_validator,
            title_matcher,
            display_manager,
        )

    def download(
        self,
        release_info: ReleaseInfo,
        track_numbers: List[int],
        quality: str,
        silent: bool = False,
        cover_art_data: Optional[bytes] = None,
        jobs: int = 1,
        progress_callback: Optional[ReleaseProgressCallback] = None,
    ) -> Tuple[Optional[int], Optional[int]]:
        """
        Download individual tracks with bounded worker concurrency.

        Provider search and video matching remain sequential. Only independent
        file downloads run in the worker pool.
        """
        self._start_attempt(track_numbers)
        console = self.display_manager.console

        if not silent:
            suffix = f" with {jobs} workers" if jobs > 1 else ""
            console.print(
                f"[cyan]🎵 Strategy 3: Downloading individual tracks{suffix}...[/cyan]"
            )

        output_dir = self.path_manager.get_release_folder_path(release_info)
        if cover_art_data is None:
            cover_art_data = self.metadata_service.fetch_cover_art_for_release(
                release_info,
                console if not silent else None,
                folder_path=output_dir,
            )

        emit_release_progress(
            progress_callback,
            stage="individual_search",
            status="Finding tracks",
            message=f"Finding videos for {len(track_numbers)} individual tracks…",
            percent=0,
        )
        prepared, failed_count = self._prepare_tracks(
            release_info,
            track_numbers,
            quality,
            silent,
            progress_callback,
        )
        if not prepared:
            return 0, failed_count

        progress = self.display_manager.create_progress_bar(
            len(track_numbers),
            "Downloading tracks"
            if not silent
            else f"Downloading {release_info.title}",
        )
        percentages = {item.track_number: 0.0 for item in prepared}

        with progress:
            task = progress.add_task(
                "[cyan]Downloading tracks...",
                total=100 * len(track_numbers),
                completed=100 * failed_count,
            )

            def update_progress(track_number: int, info: Dict) -> None:
                percentages[track_number] = max(
                    percentages.get(track_number, 0.0),
                    float(info.get("percent", 0.0) or 0.0),
                )
                track = next(
                    item.track
                    for item in prepared
                    if item.track_number == track_number
                )
                progress.update(
                    task,
                    completed=100 * failed_count + sum(percentages.values()),
                    description=(
                        f"[cyan]Downloading #{track_number}: "
                        f"{track.title[:40]}"
                    ),
                )
                completed = 100 * failed_count + sum(percentages.values())
                emit_release_progress(
                    progress_callback,
                    stage="individual_download",
                    status="Downloading tracks",
                    message=f"Downloading #{track_number}: {track.title}",
                    percent=completed / len(track_numbers),
                    speed=info.get("speed", ""),
                    eta=info.get("eta", ""),
                    download_status=info.get("status", "downloading"),
                )

            results = self.download_service.download_many(
                [item.request for item in prepared],
                workers=jobs,
                progress_callback=update_progress,
            )
            for result in results:
                percentages[result.key] = 100.0
            progress.update(
                task,
                completed=100 * failed_count + sum(percentages.values()),
            )

        results_by_key = {result.key: result for result in results}
        downloaded_count = 0
        emit_release_progress(
            progress_callback,
            stage="metadata",
            status="Tagging",
            message="Downloads finished; applying track metadata and artwork…",
            percent=0,
        )
        for item in prepared:
            result = results_by_key[item.track_number]
            if not result.succeeded:
                failed_count += 1
                self._display_failure(item.track, result, silent)
                continue

            self._mark_track_downloaded(item.track_number)
            if not silent:
                self.display_manager.display_track_download_result(
                    item.track.title,
                    True,
                    str(result.path),
                    file_existed=result.file_existed,
                )
                console.print(f"  [dim]YouTube: {item.youtube_url}[/dim]")

            try:
                self.metadata_service.apply_metadata_with_cover_art(
                    result.path,
                    item.track,
                    release_info,
                    console if not silent else None,
                    cover_art_data=cover_art_data,
                    path_manager=self.path_manager,
                    file_existed_before=result.file_existed,
                )
            except Exception as error:
                if not silent:
                    console.print(
                        f"[yellow]⚠[/yellow] Could not apply metadata to "
                        f"{item.track.title}: {error}"
                    )
            downloaded_count += 1

        return downloaded_count, failed_count

    def _prepare_tracks(
        self,
        release_info: ReleaseInfo,
        track_numbers: List[int],
        quality: str,
        silent: bool,
        progress_callback: Optional[ReleaseProgressCallback] = None,
    ) -> Tuple[List[_PreparedTrack], int]:
        """Resolve videos and metadata sequentially before starting workers."""
        prepared = []
        failed = 0
        console = self.display_manager.console
        tracks_by_number = {
            track.position: track for track in release_info.tracks
        }

        for search_number, track_number in enumerate(track_numbers, start=1):
            track = tracks_by_number.get(track_number)
            if track is None:
                if not silent:
                    console.print(
                        f"[bold red]✗[/bold red] Track "
                        f"[bold]{track_number}[/bold] not found."
                    )
                failed += 1
                continue

            emit_release_progress(
                progress_callback,
                stage="individual_search",
                status="Finding tracks",
                message=(
                    f"Finding video {search_number}/{len(track_numbers)}: "
                    f"{track.title}"
                ),
                percent=(search_number - 1) * 100 / len(track_numbers),
            )

            try:
                selected_video = self._find_video(track, release_info, silent)
            except Exception as error:
                if not silent:
                    console.print(
                        f"[yellow]⚠[/yellow] Error searching for "
                        f"{track.title}: {error}"
                    )
                failed += 1
                continue

            if selected_video is None:
                if not silent:
                    console.print(
                        "[bold red]✗[/bold red] No valid (non-live) video "
                        f"found for: [white]{track.title}[/white]"
                    )
                failed += 1
                continue

            metadata = self._build_metadata(
                release_info,
                track,
                track_number,
            )
            prepared.append(
                _PreparedTrack(
                    track_number=track_number,
                    track=track,
                    youtube_url=selected_video.youtube_url,
                    request=DownloadRequest(
                        key=track_number,
                        url=selected_video.youtube_url,
                        quality=quality,
                        metadata=metadata,
                    ),
                )
            )

        return prepared, failed

    def _find_video(
        self,
        track: Track,
        release_info: ReleaseInfo,
        silent: bool,
    ):
        selected_video, playlist_ids = (
            self.video_searcher.search_and_match_video(
                track,
                release_info,
                silent,
            )
        )
        if not selected_video and playlist_ids:
            selected_video = self.playlist_checker.check_playlists_from_ids(
                list(playlist_ids),
                track,
                release_info,
                silent,
            )
        if not selected_video:
            selected_video = self.playlist_checker.search_and_check_playlists(
                track,
                release_info,
                silent,
            )
        return selected_video

    def _build_metadata(
        self,
        release_info: ReleaseInfo,
        track: Track,
        track_number: int,
    ) -> Dict:
        date = release_info.original_release_date or release_info.release_date
        year = int(date[:4]) if date and len(date) >= 4 else None
        track_artist = (
            track.artist
            if track.artist and track.artist != release_info.artist
            else release_info.artist or "Unknown Artist"
        )
        is_playlist = bool(
            release_info.release_type == "Playlist"
            and release_info.url
            and "spotify.com" in release_info.url
        )
        metadata = {
            "title": track.title,
            "artist": track_artist,
            "album": release_info.title,
            "year": year,
            "track_number": track_number,
            "total_tracks": len(release_info.tracks),
        }
        if is_playlist:
            metadata.update(
                {
                    "is_playlist": True,
                    "playlist_name": release_info.title,
                }
            )
        elif self.path_manager.is_compilation(release_info):
            metadata["artist"] = "Various Artists"
        return metadata

    def _display_failure(
        self,
        track: Track,
        result: DownloadResult,
        silent: bool,
    ) -> None:
        console = self.display_manager.console
        if silent:
            console.print(f"[red]✗[/red] Failed: {track.title}")
            return

        from rich import box
        from rich.panel import Panel

        error = result.error or "Download service returned no file"
        if error.startswith("All download strategies failed. "):
            error = error.replace("All download strategies failed. ", "", 1)
        if len(error) > 150:
            error = error[:147] + "..."
        details = f"[yellow]{track.title}[/yellow] — [red]{error}[/red]"
        if "bot" in error.lower() or "sign in" in error.lower():
            details += (
                "\n[yellow]Tip:[/yellow] YouTube may be blocking requests. "
                "Try signing in to YouTube."
            )
        console.print(
            Panel(
                details,
                title=f"[bold red]✗ Track {track.position}[/bold red]",
                border_style="red",
                box=box.ROUNDED,
                padding=(0, 1),
            )
        )
