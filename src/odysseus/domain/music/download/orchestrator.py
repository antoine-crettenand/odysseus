"""
Download orchestrator service for coordinating downloads.
"""

from typing import List, Optional, Dict, Tuple
from pathlib import Path
from ....models.releases import ReleaseInfo
from .download_service import DownloadService
from ..metadata.metadata_service import MetadataService
from ..search.search_service import SearchService
from ..validation.video_validator import VideoValidator
from ..validation.title_matcher import TitleMatcher
from .path_manager import PathManager
from .presenter import NullPresenter
from .progress import (
    ReleaseProgressCallback,
    emit_release_progress,
)
from .strategies.base_strategy import BaseDownloadStrategy
from .strategies.full_album_strategy import FullAlbumStrategy
from .strategies.playlist_strategy import PlaylistStrategy
from .strategies.individual_tracks_strategy import IndividualTracksStrategy


class DownloadOrchestrator:
    """Orchestrates download operations."""

    def __init__(
        self,
        download_service: DownloadService,
        metadata_service: MetadataService,
        search_service: SearchService,
        presenter=None,
    ):
        self.download_service = download_service
        self.metadata_service = metadata_service
        self.search_service = search_service
        self.presenter = presenter if presenter is not None else NullPresenter()

        # Initialize helper services
        self.video_validator = VideoValidator(download_service)
        self.title_matcher = TitleMatcher()
        self.path_manager = PathManager(download_service)

        # Initialize strategies
        self.full_album_strategy = FullAlbumStrategy(
            download_service,
            metadata_service,
            search_service,
            self.presenter,
            self.video_validator,
            self.title_matcher,
            self.path_manager
        )
        self.playlist_strategy = PlaylistStrategy(
            download_service,
            metadata_service,
            search_service,
            self.presenter,
            self.video_validator,
            self.title_matcher,
            self.path_manager
        )
        self.individual_tracks_strategy = IndividualTracksStrategy(
            download_service,
            metadata_service,
            search_service,
            self.presenter,
            self.video_validator,
            self.title_matcher,
            self.path_manager
        )
        self.last_failed_track_numbers: List[int] = []

    def set_presenter(self, presenter) -> None:
        """Swap the presenter used by this orchestrator and its strategies."""
        self.presenter = presenter
        for strategy in (
            self.full_album_strategy,
            self.playlist_strategy,
            self.individual_tracks_strategy,
        ):
            strategy.presenter = presenter
        individual = self.individual_tracks_strategy
        if hasattr(individual, "video_searcher"):
            individual.video_searcher.presenter = presenter
        if hasattr(individual, "playlist_checker"):
            individual.playlist_checker.presenter = presenter

    def _display_summary(self, downloaded: int, failed: int, total: int, title: str = "DOWNLOAD SUMMARY", skipped: int = 0):
        """Display download summary."""
        self.presenter.display_summary(
            downloaded,
            failed,
            total,
            skipped=skipped,
            title=title,
        )

    def _finish_release_attempt(
        self,
        release_info: ReleaseInfo,
        attempted_track_numbers: List[int],
        strategy: BaseDownloadStrategy,
        quality: str,
        silent: bool,
        cover_art_data: Optional[bytes],
        existing_count: int,
        jobs: int,
        progress_callback: Optional[ReleaseProgressCallback] = None,
    ) -> Tuple[int, int]:
        """Offer one final individual retry and return exact final counts."""
        remembered_failures = set(
            getattr(strategy, "failed_track_numbers", attempted_track_numbers)
            or []
        )
        failed_track_numbers = [
            track_number
            for track_number in attempted_track_numbers
            if track_number in remembered_failures
        ]
        self.last_failed_track_numbers = failed_track_numbers

        retry_failed_tracks = bool(failed_track_numbers and silent)
        if failed_track_numbers and not silent:
            failed_tracks = {
                track.position: track.title
                for track in release_info.tracks
                if track.position in failed_track_numbers
            }

            self.presenter.print()
            self.presenter.print(
                "[yellow]The following tracks are still missing:[/yellow]"
            )
            for track_number in failed_track_numbers:
                title = failed_tracks.get(track_number, "Unknown track")
                self.presenter.print(f"  [red]#{track_number}[/red] {title}")
            self.presenter.print()

            retry_failed_tracks = self.presenter.confirm(
                "[bold]Retry these tracks one final time in individual mode?[/bold]",
                default=True
            )

        if retry_failed_tracks:
            if not silent:
                self.presenter.print()
                self.presenter.print(
                    "[cyan]🔁 Final retry: downloading failed tracks individually...[/cyan]"
                )
            retry_arguments = {
                "silent": silent,
                "cover_art_data": cover_art_data,
                "jobs": jobs,
            }
            if progress_callback is not None:
                retry_arguments["progress_callback"] = progress_callback
            self.individual_tracks_strategy.download(
                release_info,
                failed_track_numbers,
                quality,
                **retry_arguments,
            )
            remembered_failures = set(
                self.individual_tracks_strategy.failed_track_numbers
            )
            failed_track_numbers = [
                track_number
                for track_number in failed_track_numbers
                if track_number in remembered_failures
            ]
            self.last_failed_track_numbers = failed_track_numbers

        newly_downloaded = len(attempted_track_numbers) - len(failed_track_numbers)
        return existing_count + newly_downloaded, len(failed_track_numbers)

    def download_release_tracks(
        self,
        release_info: ReleaseInfo,
        track_numbers: List[int],
        quality: str,
        silent: bool = False,
        jobs: int = 1,
        progress_callback: Optional[ReleaseProgressCallback] = None,
    ) -> Tuple[int, int]:
        """Download selected tracks from a release using multi-strategy approach."""
        jobs = DownloadService.validate_worker_count(jobs)
        self.last_failed_track_numbers = []

        emit_release_progress(
            progress_callback,
            stage="preparing",
            status="Preparing",
            message="Checking the local library for existing tracks…",
            percent=0,
        )

        # Check which tracks already exist (partial matches allowed)
        existing_tracks = self.path_manager.get_existing_tracks(release_info, track_numbers)
        missing_track_numbers = [tn for tn in track_numbers if tn not in existing_tracks]

        emit_release_progress(
            progress_callback,
            stage="cover_art",
            status="Artwork",
            message="Fetching release artwork and metadata…",
        )

        # Fetch cover art once for the entire release (before trying any strategies)
        output_dir = self.path_manager.get_release_folder_path(release_info)
        cover_art_data = self.metadata_service.fetch_cover_art_for_release(
            release_info, None, folder_path=output_dir
        )

        # If all tracks exist, only apply metadata
        if not missing_track_numbers:
            emit_release_progress(
                progress_callback,
                stage="metadata",
                status="Tagging",
                message="All tracks already exist; refreshing metadata…",
                percent=0,
            )
            if not silent:
                self.presenter.log_info("All tracks already exist. Applying metadata only...")
                self.presenter.print()

            # Apply metadata to all existing tracks
            processed_count = 0
            failed_count = 0

            # Create progress bar
            progress = self.presenter.create_progress_bar(
                len(track_numbers),
                "Applying metadata" if not silent else f"Applying metadata to {release_info.title}"
            )

            with progress:
                task = progress.add_task(
                    "[cyan]Applying metadata..." if not silent else "[cyan]Applying metadata...",
                    total=len(track_numbers)
                )

                for track_num in track_numbers:
                    # Find the track
                    track = None
                    for t in release_info.tracks:
                        if t.position == track_num:
                            track = t
                            break

                    if not track or track_num not in existing_tracks:
                        failed_count += 1
                        progress.update(task, advance=1)
                        continue

                    file_path = existing_tracks[track_num]
                    progress.update(task, description=f"[cyan]Applying metadata: {track.title}")

                    try:
                        # Display result first (file already exists, so it will show "Use existing file")
                        if not silent:
                            self.presenter.display_track_download_result(
                                track.title, True, str(file_path), file_existed=True
                            )
                        # Apply metadata with cover art
                        self.metadata_service.apply_metadata_with_cover_art(
                            file_path, track, release_info, None, cover_art_data=cover_art_data, path_manager=self.path_manager, file_existed_before=True
                        )
                        processed_count += 1
                    except Exception as e:
                        if not silent:
                            self.presenter.print(f"[yellow]⚠[/yellow] Could not apply metadata to {track.title}: {e}")
                        failed_count += 1

                    progress.update(task, advance=1)
                    emit_release_progress(
                        progress_callback,
                        stage="metadata",
                        status="Tagging",
                        message=f"Applying metadata ({processed_count + failed_count}/{len(track_numbers)})…",
                        percent=(processed_count + failed_count) * 100 / len(track_numbers),
                    )

            # Summary
            if not silent:
                self.presenter.print()
                summary_content = f"[bold green]✓[/bold green] Successfully processed: [green]{processed_count}[/green] track{'s' if processed_count != 1 else ''}\n"
                if failed_count > 0:
                    summary_content += f"[bold red]✗[/bold red] Failed: [red]{failed_count}[/red] track{'s' if failed_count != 1 else ''}\n"
                summary_content += f"[dim blue]ℹ[/dim blue] [dim]Total tracks processed: {len(track_numbers)}[/dim]"

                self.presenter.display_panel(
                    summary_content,
                    title="[bold cyan]📊 METADATA SUMMARY[/bold cyan]",
                    border_style="cyan",
                    padding=(1, 2)
                )
                self.presenter.print()

            return processed_count, failed_count

        # Some tracks are missing - download only missing tracks
        if existing_tracks and not silent:
            # Build list of missing track titles for display
            missing_track_titles = []
            for track_num in missing_track_numbers:
                for t in release_info.tracks:
                    if t.position == track_num:
                        missing_track_titles.append(f"#{track_num}: {t.title}")
                        break

            missing_info = f"{len(missing_track_numbers)} missing track{'s' if len(missing_track_numbers) != 1 else ''}"
            if missing_track_titles:
                missing_info += f" ({', '.join(missing_track_titles)})"

            self.presenter.log_info(f"Found {len(existing_tracks)} existing track{'s' if len(existing_tracks) != 1 else ''}. Downloading {missing_info}...")

            # Display which tracks were found (helpful for debugging ordering issues)
            if len(existing_tracks) > 0:
                rows = []
                wrong_number_count = 0
                for track_num in sorted(existing_tracks.keys()):
                    file_path = existing_tracks[track_num]
                    # Find track title
                    track_title = ""
                    for t in release_info.tracks:
                        if t.position == track_num:
                            track_title = t.title
                            break

                    # Check if track number in filename matches expected
                    filename = file_path.name
                    expected_prefix = f"{track_num:02d} - "
                    has_correct_number = filename.startswith(expected_prefix)

                    # Show file with indicator if number is wrong
                    file_display = filename
                    if not has_correct_number:
                        file_display = f"[yellow]{filename}[/yellow] [dim](wrong track #)[/dim]"
                        wrong_number_count += 1

                    rows.append((str(track_num), track_title, file_display))

                self.presenter.display_existing_tracks(
                    rows, wrong_number_count=wrong_number_count
                )

            self.presenter.print()

        # Strategy 1: Try full album video (only for missing tracks)
        emit_release_progress(
            progress_callback,
            stage="full_album_search",
            status="Full album",
            message="Looking for a complete album video…",
            percent=0,
        )
        full_album_arguments = {"cover_art_data": cover_art_data}
        if progress_callback is not None:
            full_album_arguments["progress_callback"] = progress_callback
        downloaded, failed = self.full_album_strategy.download(
            release_info,
            missing_track_numbers,
            quality,
            silent,
            **full_album_arguments,
        )
        if downloaded is not None:
            total_downloaded, failed = self._finish_release_attempt(
                release_info,
                missing_track_numbers,
                self.full_album_strategy,
                quality,
                silent,
                cover_art_data,
                len(existing_tracks),
                jobs,
                progress_callback,
            )
            # Success with full album - apply metadata to existing tracks too
            if existing_tracks:
                self._apply_metadata_to_existing_tracks(
                    release_info, existing_tracks, cover_art_data, silent
                )
            if not silent:
                self._display_summary(
                    total_downloaded - len(existing_tracks),
                    failed,
                    len(track_numbers),
                    skipped=len(existing_tracks)
                )
            return total_downloaded, failed

        # Strategy 2: Try playlist (only for missing tracks)
        emit_release_progress(
            progress_callback,
            stage="playlist_search",
            status="Playlist fallback",
            message="No usable full-album video; looking for a playlist…",
            percent=0,
        )
        playlist_arguments = {
            "cover_art_data": cover_art_data,
            "jobs": jobs,
        }
        if progress_callback is not None:
            playlist_arguments["progress_callback"] = progress_callback
        downloaded, failed = self.playlist_strategy.download(
            release_info,
            missing_track_numbers,
            quality,
            silent,
            **playlist_arguments,
        )
        if downloaded is not None:
            total_downloaded, failed = self._finish_release_attempt(
                release_info,
                missing_track_numbers,
                self.playlist_strategy,
                quality,
                silent,
                cover_art_data,
                len(existing_tracks),
                jobs,
                progress_callback,
            )
            # Success with playlist - apply metadata to existing tracks too
            if existing_tracks:
                self._apply_metadata_to_existing_tracks(
                    release_info, existing_tracks, cover_art_data, silent
                )
            if not silent:
                self._display_summary(
                    total_downloaded - len(existing_tracks),
                    failed,
                    len(track_numbers),
                    skipped=len(existing_tracks)
                )
            return total_downloaded, failed

        # Strategy 3: Fall back to individual tracks (only for missing tracks)
        emit_release_progress(
            progress_callback,
            stage="individual_search",
            status="Track fallback",
            message="No usable playlist; finding individual track videos…",
            percent=0,
        )
        individual_arguments = {
            "cover_art_data": cover_art_data,
            "jobs": jobs,
        }
        if progress_callback is not None:
            individual_arguments["progress_callback"] = progress_callback
        downloaded, failed = self.individual_tracks_strategy.download(
            release_info,
            missing_track_numbers,
            quality,
            silent,
            **individual_arguments,
        )
        total_downloaded, failed = self._finish_release_attempt(
            release_info,
            missing_track_numbers,
            self.individual_tracks_strategy,
            quality,
            silent,
            cover_art_data,
            len(existing_tracks),
            jobs,
            progress_callback,
        )

        # Apply metadata to existing tracks
        if existing_tracks:
            self._apply_metadata_to_existing_tracks(
                release_info, existing_tracks, cover_art_data, silent
            )

        # Summary (only if not silent)
        if not silent:
            self._display_summary(
                total_downloaded - len(existing_tracks),
                failed,
                len(track_numbers),
                skipped=len(existing_tracks)
            )

        return total_downloaded, failed

    def _apply_metadata_to_existing_tracks(
        self,
        release_info: ReleaseInfo,
        existing_tracks: Dict[int, Path],
        cover_art_data: Optional[bytes],
        silent: bool,
    ) -> None:
        """Apply metadata to existing tracks."""
        if not existing_tracks:
            return

        if not silent:
            self.presenter.log_info(
                f"Applying metadata to {len(existing_tracks)} existing track{'s' if len(existing_tracks) != 1 else ''}...",
                icon="📝",
            )

        for track_num, file_path in existing_tracks.items():
            # Find the track
            track = None
            for t in release_info.tracks:
                if t.position == track_num:
                    track = t
                    break

            if not track:
                continue

            try:
                # Display result first
                if not silent:
                    self.presenter.display_track_download_result(
                        track.title, True, str(file_path), file_existed=True
                    )
                # Apply metadata with cover art
                self.metadata_service.apply_metadata_with_cover_art(
                    file_path, track, release_info, None,
                    cover_art_data=cover_art_data, path_manager=self.path_manager, file_existed_before=True
                )
            except Exception as e:
                if not silent:
                    self.presenter.print(f"[yellow]⚠[/yellow] Could not apply metadata to {track.title}: {e}")
