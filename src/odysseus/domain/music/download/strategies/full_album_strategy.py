"""
Strategy for downloading full album videos and splitting them into tracks.
"""

from typing import List, Optional, Tuple
from .base_strategy import BaseDownloadStrategy
from .full_album import ChapterAligner, FullAlbumDownloadPipeline
from ..progress import ReleaseProgressCallback, emit_release_progress
from .....clients.file_splitter import FileSplitter
from .....models.releases import ReleaseInfo


class FullAlbumStrategy(BaseDownloadStrategy):
    """Strategy for downloading full album videos and splitting into tracks."""

    def __init__(
        self,
        download_service,
        metadata_service,
        search_service,
        presenter,
        video_validator,
        title_matcher,
        path_manager,
    ):
        super().__init__(
            download_service,
            metadata_service,
            search_service,
            presenter,
            video_validator,
            title_matcher,
            path_manager,
        )
        self.chapter_aligner = ChapterAligner(
            video_validator=video_validator,
            title_matcher=title_matcher,
            presenter=presenter,
        )
        self.pipeline = FullAlbumDownloadPipeline(
            download_service=download_service,
            metadata_service=metadata_service,
            search_service=search_service,
            presenter=presenter,
            video_validator=video_validator,
            title_matcher=title_matcher,
            path_manager=path_manager,
            chapter_aligner=self.chapter_aligner,
        )

    def download(
        self,
        release_info: ReleaseInfo,
        track_numbers: List[int],
        quality: str,
        silent: bool = False,
        cover_art_data: Optional[bytes] = None,
        progress_callback: Optional[ReleaseProgressCallback] = None,
    ) -> Tuple[Optional[int], Optional[int]]:
        """
        Strategy 1: Download full album video and split into tracks.

        Optimized to fetch cover art once per release and reuse it for all tracks.
        """
        self._start_attempt(track_numbers)

        if self._should_skip_strategy(release_info, silent):
            emit_release_progress(
                progress_callback,
                stage="full_album_skipped",
                status="Full album skipped",
                message="A full-album video does not apply to this playlist source.",
            )
            return None, None

        if not silent:
            self.presenter.print("[cyan]🎵 Strategy 1: Searching for full album video...[/cyan]")

        output_dir = self.path_manager.get_release_folder_path(release_info)
        cover_art_data = self._prepare_cover_art(release_info, output_dir, cover_art_data, silent)

        full_album_videos = self._search_full_album_videos(release_info, silent)
        if not full_album_videos:
            emit_release_progress(
                progress_callback,
                stage="full_album_not_found",
                status="No full album",
                message="No full-album video was found.",
            )
            if not silent:
                self.presenter.log_warning("No full album video found. Trying next strategy...")
            return None, None

        emit_release_progress(
            progress_callback,
            stage="full_album_found",
            status="Full album found",
            message=(
                f"Found {len(full_album_videos)} full-album candidate"
                f"{'s' if len(full_album_videos) != 1 else ''}; validating…"
            ),
        )

        for candidate_number, video in enumerate(full_album_videos, start=1):
            try:
                emit_release_progress(
                    progress_callback,
                    stage="full_album_validating",
                    status="Validating",
                    message=(
                        f"Validating full-album candidate {candidate_number}/"
                        f"{len(full_album_videos)}: {video.title}"
                    ),
                )
                if not self._validate_video(video, release_info, track_numbers, silent):
                    continue

                youtube_url = video.youtube_url

                selected_tracks = self._get_selected_tracks(release_info, track_numbers, silent)
                if not selected_tracks:
                    continue

                emit_release_progress(
                    progress_callback,
                    stage="full_album_timestamps",
                    status="Track timing",
                    message="Full-album video accepted; locating track boundaries…",
                )
                track_timestamps = self._prepare_track_timestamps(
                    youtube_url, selected_tracks, release_info, track_numbers, silent
                )
                if not track_timestamps or len(track_timestamps) != len(selected_tracks):
                    if not silent:
                        reason = f"Could not prepare track timestamps (got {len(track_timestamps) if track_timestamps else 0}, expected {len(selected_tracks)})"
                        self.presenter.log_warning(reason)
                    continue

                album_metadata = self._prepare_album_metadata(release_info)
                full_video_path = self._download_full_album_video(
                    video,
                    youtube_url,
                    album_metadata,
                    silent,
                    progress_callback,
                )
                if not full_video_path:
                    if not silent:
                        self.presenter.log_warning("Failed to download full album video. Trying next...")
                    continue

                try:
                    output_dir = self.download_service.create_organized_path(
                        album_metadata
                    )
                    audio_extensions = ['.mp3', '.m4a', '.ogg', '.opus', '.flac', '.wav', '.aac', '.webm']
                    existing_files_before_split = FileSplitter._get_existing_files_before_split(
                        track_timestamps, output_dir, audio_extensions
                    )
                    metadata_list = self._prepare_metadata_list(track_timestamps, release_info)

                    split_files = self._split_video_into_tracks(
                        full_video_path,
                        track_timestamps,
                        output_dir,
                        metadata_list,
                        silent,
                        progress_callback,
                    )

                    successful_splits = [
                        (path, timestamp_info)
                        for path, timestamp_info in zip(split_files, track_timestamps)
                        if path is not None
                    ]
                    if successful_splits:
                        for path, timestamp_info in successful_splits:
                            self._mark_track_downloaded(
                                timestamp_info["track"].position
                            )

                        emit_release_progress(
                            progress_callback,
                            stage="metadata",
                            status="Tagging",
                            message="Split complete; applying track metadata and artwork…",
                            percent=0,
                        )
                        return self._apply_metadata_to_split_files(
                            split_files, track_timestamps, release_info, cover_art_data,
                            existing_files_before_split, youtube_url, silent
                        )
                finally:
                    self._cleanup_temp_files(full_video_path)

            except Exception as e:
                if not silent:
                    self.presenter.log_warning(f"Error with full album video: {e}. Trying next...")
                continue

        if not silent:
            self.presenter.log_warning("All full album videos failed. Trying next strategy...")
        emit_release_progress(
            progress_callback,
            stage="full_album_rejected",
            status="Full album unusable",
            message="Full-album candidates were found, but none could be used.",
        )
        return None, None

    # Chapter-aligner delegates (kept for callers that still use strategy methods).
    def _calculate_track_timestamps_from_durations(self, *args, **kwargs):
        return self.chapter_aligner._calculate_track_timestamps_from_durations(*args, **kwargs)

    def _chapter_title_score(self, *args, **kwargs):
        return self.chapter_aligner._chapter_title_score(*args, **kwargs)

    def _chapter_end_time(self, *args, **kwargs):
        return self.chapter_aligner._chapter_end_time(*args, **kwargs)

    def _chapter_duration_score(self, *args, **kwargs):
        return self.chapter_aligner._chapter_duration_score(*args, **kwargs)

    def _validate_aligned_timestamps(self, *args, **kwargs):
        return self.chapter_aligner._validate_aligned_timestamps(*args, **kwargs)

    def _align_chapters_to_tracks(self, *args, **kwargs):
        return self.chapter_aligner._align_chapters_to_tracks(*args, **kwargs)

    def _chapter_pair_score(self, *args, **kwargs):
        return self.chapter_aligner._chapter_pair_score(*args, **kwargs)

    def _best_chapter_alignment(self, *args, **kwargs):
        return self.chapter_aligner._best_chapter_alignment(*args, **kwargs)

    # Pipeline delegates (kept so tests can monkeypatch strategy methods).
    def _should_skip_strategy(self, *args, **kwargs):
        return self.pipeline._should_skip_strategy(*args, **kwargs)

    def _prepare_cover_art(self, *args, **kwargs):
        return self.pipeline._prepare_cover_art(*args, **kwargs)

    def _search_full_album_videos(self, *args, **kwargs):
        return self.pipeline._search_full_album_videos(*args, **kwargs)

    def _validate_video(self, *args, **kwargs):
        return self.pipeline._validate_video(*args, **kwargs)

    def _get_selected_tracks(self, *args, **kwargs):
        return self.pipeline._get_selected_tracks(*args, **kwargs)

    def _prepare_track_timestamps(self, *args, **kwargs):
        return self.pipeline._prepare_track_timestamps(*args, **kwargs)

    def _prepare_album_metadata(self, *args, **kwargs):
        return self.pipeline._prepare_album_metadata(*args, **kwargs)

    def _download_full_album_video(self, *args, **kwargs):
        return self.pipeline._download_full_album_video(*args, **kwargs)

    def _prepare_metadata_list(self, *args, **kwargs):
        return self.pipeline._prepare_metadata_list(*args, **kwargs)

    def _split_video_into_tracks(self, *args, **kwargs):
        return self.pipeline._split_video_into_tracks(*args, **kwargs)

    def _cleanup_temp_files(self, *args, **kwargs):
        return self.pipeline._cleanup_temp_files(*args, **kwargs)

    def _apply_metadata_to_split_files(self, *args, **kwargs):
        return self.pipeline._apply_metadata_to_split_files(*args, **kwargs)
