"""
Strategy for downloading full album videos and splitting them into tracks.
"""

import time
import threading
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from .base_strategy import BaseDownloadStrategy
from .....clients.file_splitter import FileSplitter
from .....models.releases import ReleaseInfo


class FullAlbumStrategy(BaseDownloadStrategy):
    """Strategy for downloading full album videos and splitting into tracks."""

    def _calculate_track_timestamps_from_durations(
        self,
        tracks: List,
        track_numbers: List[int]
    ) -> List[Dict[str, Any]]:
        """Calculate track timestamps from MusicBrainz durations."""
        timestamps = []
        current_time = 0.0

        # Advance through the complete album so a partial selection keeps its
        # real offset in the full-album video.
        sorted_tracks = sorted(tracks, key=lambda track: track.position)
        selected_positions = set(track_numbers)

        for track in sorted_tracks:
            duration_seconds = self.video_validator._parse_duration_to_seconds(track.duration)

            start_time = current_time
            end_time = None

            if duration_seconds:
                end_time = start_time + duration_seconds
                current_time = end_time
            else:
                # If no duration, estimate based on average (3-4 minutes)
                # This is a fallback - better to have chapters
                estimated_duration = 210  # 3.5 minutes
                end_time = start_time + estimated_duration
                current_time = end_time

            if track.position in selected_positions:
                timestamps.append({
                    'start_time': start_time,
                    'end_time': end_time,
                    'track': track
                })

        return timestamps

    def _chapter_title_score(self, chapter_title: str, track_title: str) -> Optional[float]:
        """Return a fuzzy chapter/track title score, or None for generic labels."""
        normalize = self.title_matcher._normalize_for_matching
        chapter = normalize(chapter_title)
        track = normalize(track_title)
        if not chapter or not track:
            return None

        generic_tokens = {
            "chapter",
            "track",
            "side",
            "part",
            "intro",
            "introduction",
            "outro",
            "credits",
        }
        chapter_word_list = [
            word for word in chapter.split()
            if not word.isdigit() and word not in generic_tokens
        ]
        track_word_list = [
            word for word in track.split()
            if not word.isdigit()
        ]
        if not chapter_word_list:
            return None
        chapter_core = " ".join(chapter_word_list)
        track_core = " ".join(track_word_list)
        if chapter_core == track_core:
            return 1.0
        if (
            len(chapter_core) >= 4
            and len(track_core) >= 4
            and (chapter_core in track_core or track_core in chapter_core)
        ):
            return 0.9
        chapter_words = set(chapter_word_list)
        track_words = set(track_word_list)
        if not track_words:
            return 0.0
        return len(chapter_words & track_words) / len(chapter_words | track_words)

    def _chapter_end_time(
        self,
        chapters: List[Dict[str, Any]],
        chapter_index: int,
    ) -> Optional[float]:
        """Return the explicit chapter end, falling back to the next boundary."""
        end_time = chapters[chapter_index].get("end_time")
        if end_time is not None:
            return float(end_time)
        if chapter_index + 1 < len(chapters):
            next_start = chapters[chapter_index + 1].get("start_time")
            return float(next_start) if next_start is not None else None
        return None

    def _chapter_duration_score(
        self,
        chapters: List[Dict[str, Any]],
        chapter_index: int,
        track,
    ) -> Optional[float]:
        """Score how closely one chapter duration matches release metadata."""
        expected = self.video_validator._parse_duration_to_seconds(track.duration)
        start_time = chapters[chapter_index].get("start_time")
        end_time = self._chapter_end_time(chapters, chapter_index)
        if not expected or start_time is None or end_time is None:
            return None
        actual = end_time - float(start_time)
        if actual <= 0:
            return 0.0
        return min(actual, expected) / max(actual, expected)

    def _validate_aligned_timestamps(
        self,
        timestamps: List[Dict[str, Any]],
        silent: bool,
        styling,
    ) -> bool:
        """Reject boundaries that would create implausibly short/long tracks."""
        for timestamp in timestamps:
            track = timestamp["track"]
            expected = self.video_validator._parse_duration_to_seconds(track.duration)
            start_time = timestamp.get("start_time")
            end_time = timestamp.get("end_time")
            if start_time is None or end_time is None:
                continue
            actual = end_time - start_time
            if actual <= 0:
                if not silent:
                    styling.log_warning(
                        f"Invalid chapter boundaries for '{track.title}'"
                    )
                return False
            if expected:
                tolerance = max(12.0, expected * 0.20)
                if abs(actual - expected) > tolerance:
                    if not silent:
                        styling.log_warning(
                            f"Chapter for '{track.title}' is {actual:.0f}s, "
                            f"expected about {expected:.0f}s; rejecting video"
                        )
                    return False
        return True

    def _align_chapters_to_tracks(
        self,
        chapters: List[Dict[str, Any]],
        album_tracks: List,
        selected_tracks: List,
        silent: bool,
        styling,
    ) -> List[Dict[str, Any]]:
        """Align an album tracklist to a chapter subsequence by title/duration."""
        ordered_tracks = sorted(album_tracks, key=lambda track: track.position)
        ordered_chapters = sorted(
            chapters,
            key=lambda chapter: float(chapter.get("start_time", 0)),
        )
        chapter_titles = " ".join(
            str(chapter.get("title") or "")
            for chapter in ordered_chapters
        )
        if self.video_validator.is_vinyl_or_listening_upload(
            "",
            {"description": chapter_titles},
        ):
            if not silent:
                styling.log_warning(
                    "Chapter names indicate vinyl playback or a listening "
                    "session; rejecting video"
                )
            return []

        track_count = len(ordered_tracks)
        chapter_count = len(ordered_chapters)
        if not track_count or chapter_count < track_count:
            if not silent:
                styling.log_warning(
                    f"Chapter count ({chapter_count}) is below album track "
                    f"count ({track_count}); rejecting video"
                )
            return []

        extra_count = chapter_count - track_count
        max_extras = max(2, track_count // 5)
        if extra_count > max_extras:
            if not silent:
                styling.log_warning(
                    f"Too many extra chapters ({chapter_count} chapters for "
                    f"{track_count} tracks); rejecting video"
                )
            return []

        best_indices, best_score = self._best_chapter_alignment(
            ordered_chapters,
            ordered_tracks,
        )

        if best_indices is None or best_score < 0.60:
            if not silent:
                styling.log_warning(
                    f"Chapters do not align confidently with the tracklist "
                    f"(score {max(best_score, 0):.2f}); rejecting video"
                )
            return []

        selected_positions = {track.position for track in selected_tracks}
        timestamps = []
        for chapter_index, track in zip(best_indices, ordered_tracks):
            if track.position not in selected_positions:
                continue
            chapter = ordered_chapters[chapter_index]
            timestamps.append({
                "start_time": float(chapter.get("start_time", 0)),
                "end_time": self._chapter_end_time(
                    ordered_chapters,
                    chapter_index,
                ),
                "chapter_title": chapter.get("title", ""),
                "track": track,
            })

        if not self._validate_aligned_timestamps(timestamps, silent, styling):
            return []

        skipped = [
            ordered_chapters[index].get("title", "")
            for index in set(range(chapter_count)) - set(best_indices)
        ]
        if not silent:
            extra_note = f"; skipped: {', '.join(filter(None, skipped))}" if skipped else ""
            styling.log_info(
                f"Aligned {track_count} tracks to {chapter_count} chapters "
                f"(confidence {best_score:.2f}{extra_note})",
                icon="✓",
            )
        return timestamps

    def _chapter_pair_score(
        self,
        chapters: List[Dict[str, Any]],
        chapter_index: int,
        track,
    ) -> float:
        """Score one ordered chapter/track pairing."""
        title_score = self._chapter_title_score(
            chapters[chapter_index].get("title", ""),
            track.title,
        )
        duration_score = self._chapter_duration_score(
            chapters,
            chapter_index,
            track,
        )
        if title_score is None and duration_score is None:
            return 0.0
        if title_score is None:
            return duration_score
        if duration_score is None:
            return title_score
        return title_score * 0.7 + duration_score * 0.3

    def _best_chapter_alignment(
        self,
        ordered_chapters: List[Dict[str, Any]],
        ordered_tracks: List,
    ) -> Tuple[Optional[Tuple[int, ...]], float]:
        """
        Align tracks to an order-preserving chapter subsequence.

        Uses O(tracks * chapters) dynamic programming instead of enumerating
        combinations, so large albums with a few intro/outro chapters stay safe.
        """
        track_count = len(ordered_tracks)
        chapter_count = len(ordered_chapters)
        if not track_count or chapter_count < track_count:
            return None, -1.0

        neg = float("-inf")
        dp = [[neg] * (chapter_count + 1) for _ in range(track_count + 1)]
        choice = [[None] * (chapter_count + 1) for _ in range(track_count + 1)]
        dp[0][0] = 0.0
        for chapter_used in range(1, chapter_count + 1):
            dp[0][chapter_used] = 0.0
            choice[0][chapter_used] = "skip"

        for track_used in range(1, track_count + 1):
            for chapter_used in range(track_used, chapter_count + 1):
                # Skip this chapter (keep the same number of matched tracks).
                if dp[track_used][chapter_used - 1] > dp[track_used][chapter_used]:
                    dp[track_used][chapter_used] = dp[track_used][chapter_used - 1]
                    choice[track_used][chapter_used] = "skip"

                previous = dp[track_used - 1][chapter_used - 1]
                if previous == neg:
                    continue
                candidate = previous + self._chapter_pair_score(
                    ordered_chapters,
                    chapter_used - 1,
                    ordered_tracks[track_used - 1],
                )
                if candidate > dp[track_used][chapter_used]:
                    dp[track_used][chapter_used] = candidate
                    choice[track_used][chapter_used] = "match"

        best_sum = dp[track_count][chapter_count]
        if best_sum == neg:
            return None, -1.0

        indices: List[int] = []
        track_used = track_count
        chapter_used = chapter_count
        while track_used > 0:
            action = choice[track_used][chapter_used]
            if action == "match":
                indices.append(chapter_used - 1)
                track_used -= 1
                chapter_used -= 1
            elif action == "skip":
                chapter_used -= 1
            else:
                return None, -1.0

        indices.reverse()
        if len(indices) != track_count:
            return None, -1.0
        return tuple(indices), best_sum / track_count

    def download(
        self,
        release_info: ReleaseInfo,
        track_numbers: List[int],
        quality: str,
        silent: bool = False,
        cover_art_data: Optional[bytes] = None
    ) -> Tuple[Optional[int], Optional[int]]:
        """
        Strategy 1: Download full album video and split into tracks.

        Optimized to fetch cover art once per release and reuse it for all tracks.

        Args:
            release_info: Release information
            track_numbers: List of track numbers to download
            quality: Download quality
            silent: Whether to suppress output
            cover_art_data: Optional pre-fetched cover art data (to avoid redundant searches)
        """
        self._start_attempt(track_numbers)

        # Check if strategy should be skipped
        if self._should_skip_strategy(release_info, silent):
            return None, None

        console = self.display_manager.console
        styling = self.display_manager.styling

        if not silent:
            console.print("[cyan]🎵 Strategy 1: Searching for full album video...[/cyan]")

        # Prepare cover art
        output_dir = self.path_manager.get_release_folder_path(release_info)
        cover_art_data = self._prepare_cover_art(release_info, output_dir, cover_art_data, silent, console)

        # Search for full album videos
        full_album_videos = self._search_full_album_videos(release_info, silent)
        if not full_album_videos:
            if not silent:
                styling.log_warning("No full album video found. Trying next strategy...")
            return None, None

        # Try each full album video until one works
        for video in full_album_videos:
            try:
                # Validate video
                if not self._validate_video(video, release_info, track_numbers, silent, styling, console):
                    continue

                youtube_url = video.youtube_url

                # Get selected tracks
                selected_tracks = self._get_selected_tracks(release_info, track_numbers, silent, styling)
                if not selected_tracks:
                    continue

                # Prepare track timestamps
                track_timestamps = self._prepare_track_timestamps(
                    youtube_url, selected_tracks, release_info, track_numbers, silent, styling
                )
                if not track_timestamps or len(track_timestamps) != len(selected_tracks):
                    if not silent:
                        reason = f"Could not prepare track timestamps (got {len(track_timestamps) if track_timestamps else 0}, expected {len(selected_tracks)})"
                        styling.log_warning(reason)
                    continue

                # Download full album video
                album_metadata = self._prepare_album_metadata(release_info)
                full_video_path = self._download_full_album_video(
                    video, youtube_url, album_metadata, silent, styling, console
                )
                if not full_video_path:
                    if not silent:
                        styling.log_warning("Failed to download full album video. Trying next...")
                    continue

                try:
                    # Split video into tracks
                    output_dir = self.download_service.create_organized_path(
                        album_metadata
                    )
                    audio_extensions = ['.mp3', '.m4a', '.ogg', '.opus', '.flac', '.wav', '.aac', '.webm']
                    existing_files_before_split = FileSplitter._get_existing_files_before_split(
                        track_timestamps, output_dir, audio_extensions
                    )
                    metadata_list = self._prepare_metadata_list(track_timestamps, release_info)

                    split_files = self._split_video_into_tracks(
                        full_video_path, track_timestamps, output_dir, metadata_list, silent
                    )

                    successful_splits = [
                        (path, timestamp_info)
                        for path, timestamp_info in zip(split_files, track_timestamps)
                        if path is not None
                    ]
                    if successful_splits:
                        # A split file is a successful download even when applying
                        # tags or cover art subsequently fails.
                        for path, timestamp_info in successful_splits:
                            self._mark_track_downloaded(
                                timestamp_info["track"].position
                            )

                        # Apply metadata to split files (index-aligned; None = failed)
                        return self._apply_metadata_to_split_files(
                            split_files, track_timestamps, release_info, cover_art_data,
                            existing_files_before_split, youtube_url, silent, styling, console
                        )
                finally:
                    self._cleanup_temp_files(full_video_path)

            except Exception as e:
                if not silent:
                    styling.log_warning(f"Error with full album video: {e}. Trying next...")
                continue

        # If we get here, all full album videos failed
        if not silent:
            styling.log_warning("All full album videos failed. Trying next strategy...")
        return None, None

    def _should_skip_strategy(self, release_info: ReleaseInfo, silent: bool) -> bool:
        """Check if strategy should be skipped (e.g., for Spotify playlists)."""
        is_spotify_playlist = (
            release_info.release_type == "Playlist" and
            release_info.url and
            "spotify.com" in release_info.url
        )
        if is_spotify_playlist and not silent:
            styling = self.display_manager.styling
            styling.log_info("Skipping full album strategy for playlist (not applicable)...")
        return is_spotify_playlist

    def _prepare_cover_art(
        self,
        release_info: ReleaseInfo,
        output_dir: Path,
        cover_art_data: Optional[bytes],
        silent: bool,
        console
    ) -> Optional[bytes]:
        """Prepare cover art for the release."""
        if cover_art_data is None:
            cover_art_data = self.metadata_service.fetch_cover_art_for_release(
                release_info, console if not silent else None, folder_path=output_dir
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

        return self.display_manager.show_loading_spinner(
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
        styling,
        console
    ) -> bool:
        """Validate video for album download."""
        is_valid, reason = self.video_validator.validate_video_for_album(
            video, release_info, track_numbers, self.title_matcher, silent
        )

        if not is_valid:
            if not silent:
                styling.log_warning(f"Skipping invalid video: {reason}")
                console.print(f"  [dim]YouTube: {video.youtube_url}[/dim]")
            return False

        if not silent:
            console.print(f"[bold cyan]📥 Found valid full album video:[/bold cyan] [cyan]{video.title}[/cyan]")
            console.print(f"  [dim]YouTube: {video.youtube_url}[/dim]")

        return True

    def _get_selected_tracks(
        self,
        release_info: ReleaseInfo,
        track_numbers: List[int],
        silent: bool,
        styling
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
                styling.log_warning(reason)
            return []

        return selected_tracks

    def _prepare_track_timestamps(
        self,
        youtube_url: str,
        selected_tracks: List,
        release_info: ReleaseInfo,
        track_numbers: List[int],
        silent: bool,
        styling
    ) -> List[Dict[str, Any]]:
        """Prepare track timestamps from YouTube chapters or MusicBrainz durations."""
        chapters = self.download_service.get_video_chapters(youtube_url)
        if chapters:
            track_timestamps = self._align_chapters_to_tracks(
                chapters,
                release_info.tracks,
                selected_tracks,
                silent,
                styling,
            )
            if not track_timestamps:
                return []
            if not silent:
                styling.log_info(
                    f"Using validated YouTube chapters for track splitting "
                    f"({len(chapters)} chapters found)",
                    icon="✓",
                )
        else:
            # Calculate from MusicBrainz durations
            if not silent:
                styling.log_warning("No YouTube chapters found. Using MusicBrainz durations...")
                styling.log_technical("Note: Split track durations may differ from metadata due to video timing differences")

            # Check if we have durations for all tracks
            all_tracks_have_durations = all(t.duration for t in selected_tracks)
            if not all_tracks_have_durations:
                if not silent:
                    reason = f"Missing track durations for some tracks - cannot safely split without chapters"
                    styling.log_warning(reason)
                return []

            track_timestamps = self._calculate_track_timestamps_from_durations(
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
        styling,
        console
    ) -> Optional[Path]:
        """Download full album video with progress tracking."""
        if not silent:
            console.print("[bold cyan]📥 Downloading full album video...[/bold cyan]")

        file_progress, file_task_id = self.display_manager.create_download_progress_bar(
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
                        styling.log_warning(f"Download taking longer than expected at 0% ({int(elapsed_time)}s elapsed)")
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
        silent: bool
    ) -> List[Optional[Path]]:
        """Split video into tracks."""
        if not silent:
            console = self.display_manager.console
            console.print("[bold cyan]✂️  Splitting album into tracks...[/bold cyan]")

        split_progress, split_task_id = self.display_manager.create_download_progress_bar(
            "Splitting tracks"
        )

        def update_split_progress(progress_info: Dict[str, Any]):
            percent = progress_info.get('percent', 0)
            split_progress.update(split_task_id, completed=percent)

        with split_progress:
            split_files = self.download_service.split_video_into_tracks(
                full_video_path,
                track_timestamps,
                output_dir,
                metadata_list,
                progress_callback=update_split_progress
            )
            split_progress.update(split_task_id, completed=100)

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
        styling,
        console
    ) -> Tuple[int, int]:
        """Apply metadata to all successfully split files."""
        downloaded_count = 0
        skipped_count = 0
        failed_count = 0

        if not silent:
            console.print("[bold cyan]📝 Applying metadata and cover art to tracks...[/bold cyan]")

        metadata_progress, metadata_task_id = self.display_manager.create_download_progress_bar(
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
                        styling.log_warning(
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
                            console.print(f"[yellow]⏭[/yellow] Skipped existing track: {track.title}")
                        else:
                            self.display_manager.display_track_download_result(
                                track.title, True, str(split_file), file_existed=False
                            )
                            if downloaded_count == 0:
                                console.print(f"  [dim]YouTube: {youtube_url}[/dim]")

                    self.metadata_service.apply_metadata_with_cover_art(
                        split_file,
                        track,
                        release_info,
                        console if not silent else None,
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
                        styling.log_warning(f"Could not apply metadata to {track.title}: {e}")

                metadata_progress.update(metadata_task_id, advance=1)

        if not silent:
            if downloaded_count > 0:
                styling.log_info(f"Successfully downloaded and split {downloaded_count} track{'s' if downloaded_count != 1 else ''} from full album video", icon="✓")
                console.print(f"[bold green]✓[/bold green] Successfully downloaded and split {downloaded_count} track{'s' if downloaded_count != 1 else ''} from full album video")
            if skipped_count > 0:
                styling.log_info(f"Skipped {skipped_count} existing track{'s' if skipped_count != 1 else ''}", icon="⏭")
            if failed_count > 0:
                styling.log_warning(f"Failed to split or tag {failed_count} track(s)")

        return downloaded_count, failed_count
