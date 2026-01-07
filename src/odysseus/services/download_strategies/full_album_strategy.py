"""
Strategy for downloading full album videos and splitting them into tracks.
"""

import time
import threading
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from .base_strategy import BaseDownloadStrategy
from ...models.releases import ReleaseInfo


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
        
        # Filter tracks to only selected ones, sorted by position
        selected_tracks = [
            t for t in tracks
            if t.position in track_numbers
        ]
        selected_tracks.sort(key=lambda x: x.position)
        
        for i, track in enumerate(selected_tracks):
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
            
            timestamps.append({
                'start_time': start_time,
                'end_time': end_time,
                'track': track
            })
        
        return timestamps
    
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
                
                # Split video into tracks
                output_dir = self.download_service.downloader._create_organized_path(album_metadata)
                existing_files_before_split = self._get_existing_files_before_split(
                    track_timestamps, output_dir
                )
                metadata_list = self._prepare_metadata_list(track_timestamps, release_info)
                
                split_files = self._split_video_into_tracks(
                    full_video_path, track_timestamps, output_dir, metadata_list, silent
                )
                
                # Clean up temporary video file
                self._cleanup_temp_files(full_video_path)
                
                if split_files:
                    # Apply metadata to split files
                    return self._apply_metadata_to_split_files(
                        split_files, track_timestamps, release_info, cover_art_data,
                        existing_files_before_split, youtube_url, silent, styling, console
                    )
                
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
            if not silent:
                cover_art_data = self.metadata_service.fetch_cover_art_for_release(
                    release_info, console, folder_path=output_dir
                )
            else:
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
        track_timestamps = []
        
        if chapters and len(chapters) >= len(selected_tracks):
            # Use YouTube chapters
            if not silent:
                styling.log_info(f"Using YouTube chapters for track splitting ({len(chapters)} chapters found)", icon="✓")
            
            # Validate chapter count
            if len(chapters) < len(selected_tracks) * 0.8:
                if not silent:
                    reason = f"Number of chapters ({len(chapters)}) doesn't match number of tracks ({len(selected_tracks)}) - likely wrong video"
                    styling.log_warning(reason)
                return []
            
            for i, track in enumerate(selected_tracks):
                if i < len(chapters):
                    chapter = chapters[i]
                    start_time = chapter.get('start_time', 0)
                    end_time = chapters[i + 1].get('start_time') if i + 1 < len(chapters) else None
                    track_timestamps.append({
                        'start_time': start_time,
                        'end_time': end_time,
                        'track': track
                    })
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
        is_playlist = (
            release_info.release_type == "Playlist" and 
            release_info.url and 
            "spotify.com" in release_info.url
        )
        
        date_to_use = release_info.original_release_date or release_info.release_date
        year = int(date_to_use[:4]) if date_to_use and len(date_to_use) >= 4 else None
        
        if is_playlist:
            return {
                'title': release_info.title,
                'artist': release_info.artist,
                'album': release_info.title,
                'is_playlist': True,
                'playlist_name': release_info.title,
                'year': year,
            }
        else:
            is_compilation = self.path_manager.is_compilation(release_info)
            folder_artist = "Various Artists" if is_compilation else release_info.artist
            
            return {
                'title': release_info.title,
                'artist': folder_artist,
                'album': release_info.title,
                'year': year,
            }
    
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
    
    def _get_existing_files_before_split(
        self,
        track_timestamps: List[Dict[str, Any]],
        output_dir: Path
    ) -> set:
        """Get set of files that exist before splitting."""
        existing_files_before_split = set()
        audio_extensions = ['.mp3', '.m4a', '.ogg', '.opus', '.flac', '.wav', '.aac', '.webm']
        
        for timestamp_info in track_timestamps:
            track = timestamp_info['track']
            title = self.download_service.downloader._sanitize_filename(track.title)
            track_prefix = f"{track.position:02d} - "
            expected_base = f"{track_prefix}{title}"
            
            found_existing = False
            for ext in audio_extensions:
                potential_file = output_dir / f"{expected_base}{ext}"
                if potential_file.exists() and potential_file.is_file():
                    existing_files_before_split.add(potential_file)
                    found_existing = True
                    break
            
            if not found_existing:
                existing_files = [
                    f for f in output_dir.glob(f"{expected_base}*")
                    if f.is_file() and f.suffix.lower() in audio_extensions
                ]
                if existing_files:
                    existing_files_before_split.add(existing_files[0])
        
        return existing_files_before_split
    
    def _prepare_metadata_list(
        self,
        track_timestamps: List[Dict[str, Any]],
        release_info: ReleaseInfo
    ) -> List[Dict[str, Any]]:
        """Prepare metadata list for track splitting."""
        date_to_use = release_info.original_release_date or release_info.release_date
        year = int(date_to_use[:4]) if date_to_use and len(date_to_use) >= 4 else None
        
        metadata_list = []
        for timestamp_info in track_timestamps:
            track = timestamp_info['track']
            track_artist = track.artist if (track.artist and track.artist != release_info.artist) else (release_info.artist or "Unknown Artist")
            metadata_list.append({
                'title': track.title,
                'artist': track_artist,
                'album': release_info.title,
                'year': year,
                'track_number': track.position,
                'total_tracks': len(release_info.tracks)
            })
        
        return metadata_list
    
    def _split_video_into_tracks(
        self,
        full_video_path: Path,
        track_timestamps: List[Dict[str, Any]],
        output_dir: Path,
        metadata_list: List[Dict[str, Any]],
        silent: bool
    ) -> List[Path]:
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
        """Clean up temporary video file."""
        try:
            temp_dir = self.download_service.downloads_dir / ".temp_album"
            if full_video_path.exists():
                full_video_path.unlink()
            if temp_dir.exists():
                temp_dir.rmdir()
        except Exception:
            pass  # Ignore cleanup errors
    
    def _apply_metadata_to_split_files(
        self,
        split_files: List[Path],
        track_timestamps: List[Dict[str, Any]],
        release_info: ReleaseInfo,
        cover_art_data: Optional[bytes],
        existing_files_before_split: set,
        youtube_url: str,
        silent: bool,
        styling,
        console
    ) -> Tuple[int, int]:
        """Apply metadata to all split files."""
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
                styling.log_warning(f"Failed to apply metadata to {failed_count} track(s)")
        
        return downloaded_count, failed_count

