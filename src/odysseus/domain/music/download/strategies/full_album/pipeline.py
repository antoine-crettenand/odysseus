"""Download pipeline helpers for full-album strategy."""

import time
import threading
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path

from ...progress import ReleaseProgressCallback, emit_release_progress
from ......models.releases import ReleaseInfo


class FullAlbumDownloadPipeline:
    """Search, validate, download, split, and tag a full-album video."""

    def __init__(
        self,
        download_service,
        metadata_service,
        search_service,
        presenter,
        video_validator,
        title_matcher,
        path_manager,
        chapter_aligner,
    ):
        self.download_service = download_service
        self.metadata_service = metadata_service
        self.search_service = search_service
        self.presenter = presenter
        self.video_validator = video_validator
        self.title_matcher = title_matcher
        self.path_manager = path_manager
        self.chapter_aligner = chapter_aligner

    def _should_skip_strategy(self, release_info: ReleaseInfo, silent: bool) -> bool:
        """Check if strategy should be skipped (e.g., for Spotify playlists)."""
        is_spotify_playlist = (
            release_info.release_type == "Playlist" and
            release_info.url and
            "spotify.com" in release_info.url
        )
        if is_spotify_playlist and not silent:
            self.presenter.log_info("Skipping full album strategy for playlist (not applicable)...")
        return is_spotify_playlist

    def _prepare_cover_art(
        self,
        release_info: ReleaseInfo,
        output_dir: Path,
        cover_art_data: Optional[bytes],
        silent: bool,
    ) -> Optional[bytes]:
        """Prepare cover art for the release."""
        if cover_art_data is None:
            cover_art_data = self.metadata_service.fetch_cover_art_for_release(
                release_info, None, folder_path=output_dir
            )
        return cover_art_data

    def _search_full_album_videos(
        self,
        release_info: ReleaseInfo,
        silent: bool
    ) -> List:
        """Search for full album videos."""
        # Extract release year if available
        release_year = None
        date_to_use = release_info.original_release_date or release_info.release_date
        if date_to_use and len(date_to_use) >= 4:
            release_year = date_to_use[:4]

        return self.presenter.show_loading_spinner(
            f"Searching for full album: {release_info.title}",
            self.search_service.search_full_album,
            release_info.artist,
            release_info.title,
            3,
            release_year
        )

    def _validate_video(
        self,
        video,
        release_info: ReleaseInfo,
        track_numbers: List[int],
        silent: bool,
    ) -> bool:
        """Validate video for album download."""
        is_valid, _reason = self.video_validator.validate_video_for_album(
            video,
            release_info,
            track_numbers,
            self.title_matcher,
            silent,
            console=None,
        )

        if not is_valid:
            return False

        if not silent:
            self.presenter.print(f"[bold cyan]📥 Found valid full album video:[/bold cyan] [cyan]{video.title}[/cyan]")
            self.presenter.print(f"  [dim]YouTube: {video.youtube_url}[/dim]")

        return True

    def _get_selected_tracks(
        self,
        release_info: ReleaseInfo,
        track_numbers: List[int],
        silent: bool,
    ) -> List:
        """Get selected tracks from release info."""
        selected_tracks = [
            t for t in release_info.tracks
            if t.position in track_numbers
        ]
        selected_tracks.sort(key=lambda x: x.position)

        if not selected_tracks:
            available_positions = [t.position for t in release_info.tracks] if release_info.tracks else []
            reason = f"No tracks found matching requested positions. Requested: {track_numbers}, Available: {available_positions}, Total tracks: {len(release_info.tracks)}"
            if not silent:
                self.presenter.log_warning(reason)
            return []

        return selected_tracks

    def _prepare_track_timestamps(
        self,
        youtube_url: str,
        selected_tracks: List,
        release_info: ReleaseInfo,
        track_numbers: List[int],
        silent: bool,
    ) -> List[Dict[str, Any]]:
        """Prepare track timestamps from YouTube chapters or MusicBrainz durations."""
        chapters = self.download_service.get_video_chapters(youtube_url)
        if chapters:
            track_timestamps = self.chapter_aligner._align_chapters_to_tracks(
                chapters,
                release_info.tracks,
                selected_tracks,
                silent,
            )
            if not track_timestamps:
                return []
            if not silent:
                self.presenter.log_info(
                    f"Using validated YouTube chapters for track splitting "
                    f"({len(chapters)} chapters found)",
                    icon="✓",
                )
        else:
            # Calculate from MusicBrainz durations
            if not silent:
                self.presenter.log_warning("No YouTube chapters found. Using MusicBrainz durations...")
                self.presenter.log_info("Note: Split track durations may differ from metadata due to video timing differences")

            # Every track through the last selection contributes to its offset.
            # Missing durations after the last selected track are irrelevant.
            last_selected_position = max(t.position for t in selected_tracks)
            offset_tracks = [
                track
                for track in release_info.tracks
                if track.position <= last_selected_position
            ]
            all_offsets_are_known = all(t.duration for t in offset_tracks)
            if not all_offsets_are_known:
                if not silent:
                    reason = (
                        "Missing duration before or within the selected tracks - "
                        "cannot safely split without chapters"
                    )
                    self.presenter.log_warning(reason)
                return []

            track_timestamps = self.chapter_aligner._calculate_track_timestamps_from_durations(
                release_info.tracks, track_numbers
            )

        return track_timestamps

    def _prepare_album_metadata(self, release_info: ReleaseInfo) -> Dict[str, Any]:
        """Prepare metadata for album download."""
        date_to_use = release_info.original_release_date or release_info.release_date
        year = int(date_to_use[:4]) if date_to_use and len(date_to_use) >= 4 else None

        is_playlist = (
            release_info.release_type == "Playlist" and
            release_info.url and
            "spotify.com" in release_info.url
        )

        if is_playlist:
            return {'title': release_info.title, 'artist': release_info.artist, 'album': release_info.title, 'is_playlist': True, 'playlist_name': release_info.title, 'year': year}

        is_compilation = self.path_manager.is_compilation(release_info)
        return {'title': release_info.title, 'artist': "Various Artists" if is_compilation else release_info.artist, 'album': release_info.title, 'year': year}

    def _download_full_album_video(
        self,
        video,
        youtube_url: str,
        album_metadata: Dict[str, Any],
        silent: bool,
        progress_callback: Optional[ReleaseProgressCallback] = None,
    ) -> Optional[Path]:
        """Download full album video with progress tracking."""
        if not silent:
            self.presenter.print("[bold cyan]📥 Downloading full album video...[/bold cyan]")

        file_progress, file_task_id = self.presenter.create_download_progress_bar(
            f"Initializing download: {video.title[:40]}"
        )

        # Track download progress
        download_start_time = time.time()
        stuck_warning_shown = False
        current_percent = 0
        current_status = 'downloading'
        current_speed = ''
        current_eta = ''
        download_complete = False

        def update_progress(progress_info: Dict[str, Any]):
            """Update progress bar with download info."""
            nonlocal stuck_warning_shown, current_percent, current_status, current_speed, current_eta

            current_percent = progress_info.get('percent', 0)
            current_status = progress_info.get('status', 'downloading')
            current_speed = progress_info.get('speed', '')
            current_eta = progress_info.get('eta', '')

            raw_status = str(current_status or "downloading")
            status_message = {
                "extracting": "Extracting audio from the full-album video…",
                "merging": "Merging the full-album audio stream…",
                "finished": "Finalizing the full-album download…",
            }.get(raw_status, f"Downloading full-album video: {video.title}")
            emit_release_progress(
                progress_callback,
                stage="full_album_download",
                status="Downloading album",
                message=status_message,
                percent=current_percent,
                speed=current_speed,
                eta=current_eta,
                download_status=raw_status,
            )

            _update_progress_display()

        def _update_progress_display():
            """Update the progress bar display."""
            nonlocal stuck_warning_shown
            elapsed_time = time.time() - download_start_time
            base_title = video.title[:35]

            # Determine status message
            if current_status == 'extracting':
                status_msg = "Extracting audio..."
            elif current_status == 'merging':
                status_msg = "Merging formats..."
            elif current_percent == 0:
                if elapsed_time > 10:
                    status_msg = f"Connecting to YouTube... ({int(elapsed_time)}s)"
                    if not stuck_warning_shown and elapsed_time > 60 and not silent:
                        self.presenter.log_warning(f"Download taking longer than expected at 0% ({int(elapsed_time)}s elapsed)")
                        stuck_warning_shown = True
                else:
                    status_msg = "Connecting to YouTube..."
            elif current_percent < 5:
                status_msg = "Initializing download..."
            elif current_percent < 20:
                status_msg = "Downloading metadata..."
            elif current_percent < 50:
                status_msg = "Downloading audio stream..."
            elif current_percent < 90:
                status_msg = "Downloading..."
            elif current_percent < 100:
                status_msg = "Finalizing..."
            else:
                status_msg = "Complete"

            speed_info = f" @ {current_speed}" if current_speed else ""
            eta_info = f" (ETA: {current_eta})" if current_eta else ""
            desc = f"{status_msg}: {base_title}{speed_info}{eta_info}"

            file_progress.update(file_task_id, completed=current_percent, description=desc)

        def periodic_update():
            """Periodically update progress bar."""
            while not download_complete:
                time.sleep(2)
                if not download_complete:
                    _update_progress_display()

        update_thread = threading.Thread(target=periodic_update, daemon=True)
        update_thread.start()

        try:
            with file_progress:
                full_video_path, _ = self.download_service.download_high_quality_audio(
                    youtube_url,
                    metadata=album_metadata,
                    quiet=True,
                    progress_callback=update_progress
                )
                download_complete = True
                file_progress.update(file_task_id, completed=100, description=f"Complete: {video.title[:35]}")
                emit_release_progress(
                    progress_callback,
                    stage="full_album_download",
                    status="Album downloaded",
                    message="Full-album video downloaded; preparing to split tracks…",
                    percent=100,
                )
        finally:
            download_complete = True

        return full_video_path

    def _prepare_metadata_list(
        self,
        track_timestamps: List[Dict[str, Any]],
        release_info: ReleaseInfo
    ) -> List[Dict[str, Any]]:
        """Prepare metadata list for track splitting."""
        return self.metadata_service.prepare_track_metadata_list(track_timestamps, release_info)

    def _split_video_into_tracks(
        self,
        full_video_path: Path,
        track_timestamps: List[Dict[str, Any]],
        output_dir: Path,
        metadata_list: List[Dict[str, Any]],
        silent: bool,
        progress_callback: Optional[ReleaseProgressCallback] = None,
    ) -> List[Optional[Path]]:
        """Split video into tracks."""
        if not silent:
            self.presenter.print("[bold cyan]✂️  Splitting album into tracks...[/bold cyan]")

        split_progress, split_task_id = self.presenter.create_download_progress_bar(
            "Splitting tracks"
        )

        def update_split_progress(progress_info: Dict[str, Any]):
            percent = progress_info.get('percent', 0)
            split_progress.update(split_task_id, completed=percent)
            emit_release_progress(
                progress_callback,
                stage="splitting",
                status="Splitting tracks",
                message=str(
                    progress_info.get("message")
                    or progress_info.get("status")
                    or "Splitting the full-album audio into tracks…"
                ),
                percent=percent,
            )

        with split_progress:
            split_files = self.download_service.split_video_into_tracks(
                full_video_path,
                track_timestamps,
                output_dir,
                metadata_list,
                progress_callback=update_split_progress
            )
            split_progress.update(split_task_id, completed=100)
            emit_release_progress(
                progress_callback,
                stage="splitting",
                status="Split complete",
                message=f"Created {len([path for path in split_files if path])} track files.",
                percent=100,
            )

        return split_files

    def _cleanup_temp_files(self, full_video_path: Path) -> None:
        """Clean up the downloaded full-album source file after splitting."""
        if not full_video_path:
            return
        try:
            if full_video_path.exists():
                full_video_path.unlink()
        except OSError as error:
            print(
                f"Warning: could not remove temporary album file "
                f"{full_video_path}: {error}"
            )

    def _apply_metadata_to_split_files(
        self,
        split_files: List[Optional[Path]],
        track_timestamps: List[Dict[str, Any]],
        release_info: ReleaseInfo,
        cover_art_data: Optional[bytes],
        existing_files_before_split: set,
        youtube_url: str,
        silent: bool,
    ) -> Tuple[int, int]:
        """Apply metadata to all successfully split files."""
        downloaded_count = 0
        skipped_count = 0
        failed_count = 0

        if not silent:
            self.presenter.print("[bold cyan]📝 Applying metadata and cover art to tracks...[/bold cyan]")

        metadata_progress, metadata_task_id = self.presenter.create_download_progress_bar(
            "Applying metadata"
        )

        with metadata_progress:
            for split_file, timestamp_info in zip(split_files, track_timestamps):
                track = timestamp_info['track']
                metadata_progress.update(
                    metadata_task_id,
                    description=f"Applying metadata: {track.title[:40]}"
                )

                if split_file is None:
                    failed_count += 1
                    if not silent:
                        self.presenter.log_warning(
                            f"Could not split track: {track.title}"
                        )
                    metadata_progress.update(metadata_task_id, advance=1)
                    continue

                # Check if file already existed
                file_existed = any(
                    split_file.resolve() == existing_file.resolve()
                    for existing_file in existing_files_before_split
                )

                try:
                    if not silent:
                        if file_existed:
                            self.presenter.print(f"[yellow]⏭[/yellow] Skipped existing track: {track.title}")
                        else:
                            self.presenter.display_track_download_result(
                                track.title, True, str(split_file), file_existed=False
                            )
                            if downloaded_count == 0:
                                self.presenter.print(f"  [dim]YouTube: {youtube_url}[/dim]")

                    self.metadata_service.apply_metadata_with_cover_art(
                        split_file,
                        track,
                        release_info,
                        None,
                        cover_art_data=cover_art_data,
                        path_manager=self.path_manager,
                        file_existed_before=file_existed
                    )

                    if file_existed:
                        skipped_count += 1
                    else:
                        downloaded_count += 1
                except Exception as e:
                    failed_count += 1
                    if not silent:
                        self.presenter.log_warning(f"Could not apply metadata to {track.title}: {e}")

                metadata_progress.update(metadata_task_id, advance=1)

        if not silent:
            if downloaded_count > 0:
                self.presenter.log_info(f"Successfully downloaded and split {downloaded_count} track{'s' if downloaded_count != 1 else ''} from full album video", icon="✓")
                self.presenter.print(f"[bold green]✓[/bold green] Successfully downloaded and split {downloaded_count} track{'s' if downloaded_count != 1 else ''} from full album video")
            if skipped_count > 0:
                self.presenter.log_info(f"Skipped {skipped_count} existing track{'s' if skipped_count != 1 else ''}", icon="⏭")
            if failed_count > 0:
                self.presenter.log_warning(f"Failed to split or tag {failed_count} track(s)")

        return downloaded_count, failed_count
