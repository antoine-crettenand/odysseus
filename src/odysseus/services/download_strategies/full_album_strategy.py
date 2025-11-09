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
        silent: bool = False
    ) -> Tuple[Optional[int], Optional[int]]:
        """
        Strategy 1: Download full album video and split into tracks.
        
        Optimized to fetch cover art once per release and reuse it for all tracks.
        """
        # Skip this strategy for Spotify playlists - playlists are not albums
        # Verify it's a Spotify playlist (extra safeguard)
        if (
            release_info.release_type == "Playlist" and 
            release_info.url and 
            "spotify.com" in release_info.url
        ):
            if not silent:
                console = self.display_manager.console
                console.print("[cyan]ℹ[/cyan] Skipping full album strategy for playlist (not applicable)...")
            return None, None
        
        console = self.display_manager.console
        
        if not silent:
            console.print("[cyan]🎵 Strategy 1: Searching for full album video...[/cyan]")
        
        # Get folder path for cover art extraction from existing tracks
        output_dir = self.path_manager.get_release_folder_path(release_info)
        
        # Fetch cover art once for the entire release (optimization)
        # Pass folder_path so it can extract from existing tracks if available
        cover_art_data = None
        if not silent:
            cover_art_data = self.metadata_service.fetch_cover_art_for_release(release_info, console, folder_path=output_dir)
        else:
            # Still fetch cover art in silent mode, just don't print messages
            cover_art_data = self.metadata_service.fetch_cover_art_for_release(release_info, None, folder_path=output_dir)
        
        # Extract release year if available
        release_year = None
        if release_info.release_date and len(release_info.release_date) >= 4:
            release_year = release_info.release_date[:4]
        
        # Search for full album video (with year for better accuracy)
        full_album_videos = self.display_manager.show_loading_spinner(
            f"Searching for full album: {release_info.title}",
            self.search_service.search_full_album,
            release_info.artist,
            release_info.title,
            3,
            release_year
        )
        
        if not full_album_videos:
            if not silent:
                console.print("[yellow]⚠[/yellow] No full album video found. Trying next strategy...")
            return None, None  # Signal to try next strategy
        
        # Try each full album video until one works
        for video in full_album_videos:
            try:
                # Validate video (check for live versions, duration, etc.)
                is_valid, reason = self.video_validator.validate_video_for_album(
                    video, release_info, track_numbers, self.title_matcher, silent
                )
                
                if not is_valid:
                    if not silent:
                        console.print(f"[yellow]⚠[/yellow] Skipping invalid video: {reason}")
                    continue
                
                if not silent:
                    console.print(f"[cyan]📥 Found valid full album video: {video.title}[/cyan]")
                
                youtube_url = video.youtube_url
                
                # Get video chapters (if available)
                chapters = self.download_service.get_video_chapters(youtube_url)
                
                # Filter tracks to selected ones
                selected_tracks = [
                    t for t in release_info.tracks
                    if t.position in track_numbers
                ]
                selected_tracks.sort(key=lambda x: x.position)
                
                # Prepare track timestamps
                track_timestamps = []
                if chapters and len(chapters) >= len(selected_tracks):
                    # Use YouTube chapters
                    if not silent:
                        console.print(f"[green]✓[/green] Using YouTube chapters for track splitting ({len(chapters)} chapters found)")
                    
                    # Additional validation: check if number of chapters roughly matches number of tracks
                    # Allow some flexibility (chapters might include intro/outro)
                    if len(chapters) < len(selected_tracks) * 0.8:
                        reason = f"Number of chapters ({len(chapters)}) doesn't match number of tracks ({len(selected_tracks)}) - likely wrong video"
                        if not silent:
                            console.print(f"[yellow]⚠[/yellow] {reason}")
                        continue
                    
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
                        console.print("[yellow]⚠[/yellow] No YouTube chapters found. Using MusicBrainz durations...")
                    
                    # For full album downloads without chapters, we need to be more careful
                    # Check if we have durations for all tracks
                    all_tracks_have_durations = all(t.duration for t in selected_tracks)
                    if not all_tracks_have_durations:
                        reason = f"Missing track durations for some tracks - cannot safely split without chapters"
                        if not silent:
                            console.print(f"[yellow]⚠[/yellow] {reason}")
                        continue
                    
                    track_timestamps = self._calculate_track_timestamps_from_durations(
                        release_info.tracks, track_numbers
                    )
                
                if not track_timestamps or len(track_timestamps) != len(selected_tracks):
                    reason = f"Could not prepare track timestamps (got {len(track_timestamps) if track_timestamps else 0}, expected {len(selected_tracks)})"
                    if not silent:
                        console.print(f"[yellow]⚠[/yellow] {reason}")
                    continue
                
                # Download the full album video to a temporary location
                temp_dir = self.download_service.downloads_dir / ".temp_album"
                temp_dir.mkdir(exist_ok=True)
                
                # Create metadata for the full album download
                # Check if this is a Spotify playlist (only Spotify sets release_type to "Playlist")
                # Verify it's a Spotify playlist (extra safeguard)
                is_playlist = (
                    release_info.release_type == "Playlist" and 
                    release_info.url and 
                    "spotify.com" in release_info.url
                )
                
                if is_playlist:
                    # For playlists, use playlist folder structure
                    album_metadata = {
                        'title': release_info.title,
                        'artist': release_info.artist,  # Keep actual artist in metadata
                        'album': release_info.title,
                        'is_playlist': True,
                        'playlist_name': release_info.title,
                        'year': int(release_info.release_date[:4]) if release_info.release_date and len(release_info.release_date) >= 4 else None,
                    }
                else:
                    # Use "Various Artists" for folder structure if this is a compilation
                    is_compilation = self.path_manager.is_compilation(release_info)
                    folder_artist = "Various Artists" if is_compilation else release_info.artist
                    
                    album_metadata = {
                        'title': release_info.title,
                        'artist': folder_artist,  # Use "Various Artists" for folder structure in compilations
                        'album': release_info.title,
                        'year': int(release_info.release_date[:4]) if release_info.release_date and len(release_info.release_date) >= 4 else None,
                    }
                
                # Download full album video
                if not silent:
                    console.print("[cyan]📥 Downloading full album video...[/cyan]")
                
                file_progress, file_task_id = self.display_manager.create_download_progress_bar(
                    f"Initializing download: {video.title[:40]}"
                )
                
                # Track when download started and last update for stuck detection
                download_start_time = time.time()
                last_update_time = time.time()
                stuck_warning_shown = False
                current_percent = 0
                current_status = 'downloading'
                current_speed = ''
                current_eta = ''
                download_complete = False
                
                def update_progress(progress_info: Dict[str, Any]):
                    """Update progress bar with download info and dynamic status."""
                    nonlocal last_update_time, stuck_warning_shown, current_percent, current_status, current_speed, current_eta
                    
                    # Use percentage for progress (0-100)
                    current_percent = progress_info.get('percent', 0)
                    current_status = progress_info.get('status', 'downloading')
                    current_speed = progress_info.get('speed', '')
                    current_eta = progress_info.get('eta', '')
                    
                    # Update last activity time
                    current_time = time.time()
                    last_update_time = current_time
                    
                    _update_progress_display()
                
                def _update_progress_display():
                    """Update the progress bar display with current state."""
                    nonlocal stuck_warning_shown
                    elapsed_time = time.time() - download_start_time
                    base_title = video.title[:35]
                    
                    # Determine status message based on progress_info status and percentage
                    if current_status == 'extracting':
                        status_msg = "Extracting audio..."
                    elif current_status == 'merging':
                        status_msg = "Merging formats..."
                    elif current_percent == 0:
                        # Show elapsed time if stuck at 0% for a while
                        if elapsed_time > 10:  # After 10 seconds, show elapsed time
                            status_msg = f"Connecting to YouTube... ({int(elapsed_time)}s)"
                            if not stuck_warning_shown and elapsed_time > 60:
                                # Show warning in console (not progress bar)
                                if not silent:
                                    console.print(f"[yellow]⚠[/yellow] Download taking longer than expected at 0% ({int(elapsed_time)}s elapsed)")
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
                    
                    # Add speed and ETA if available
                    speed_info = f" @ {current_speed}" if current_speed else ""
                    eta_info = f" (ETA: {current_eta})" if current_eta else ""
                    
                    # Build full description
                    desc = f"{status_msg}: {base_title}{speed_info}{eta_info}"
                    
                    file_progress.update(file_task_id, completed=current_percent, description=desc)
                
                # Start background thread to periodically update progress bar
                def periodic_update():
                    """Periodically update progress bar even when no progress is received."""
                    while not download_complete:
                        time.sleep(2)  # Update every 2 seconds
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
                        # Mark as complete
                        download_complete = True
                        file_progress.update(file_task_id, completed=100, description=f"Complete: {video.title[:35]}")
                finally:
                    # Ensure thread stops
                    download_complete = True
                
                if not full_video_path:
                    if not silent:
                        console.print("[yellow]⚠[/yellow] Failed to download full album video. Trying next...")
                    continue
                
                # Create output directory for split tracks
                output_dir = self.download_service.downloader._create_organized_path(album_metadata)
                
                # Prepare metadata list for splitting
                metadata_list = []
                for timestamp_info in track_timestamps:
                    track = timestamp_info['track']
                    metadata_list.append({
                        'title': track.title,
                        'artist': track.artist,
                        'album': release_info.title,
                        'year': int(release_info.release_date[:4]) if release_info.release_date and len(release_info.release_date) >= 4 else None,
                        'track_number': track.position,
                        'total_tracks': len(release_info.tracks)
                    })
                
                # Split video into tracks
                if not silent:
                    console.print("[cyan]✂️  Splitting album into tracks...[/cyan]")
                
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
                
                # Clean up temporary video file
                try:
                    if full_video_path.exists():
                        full_video_path.unlink()
                    if temp_dir.exists():
                        temp_dir.rmdir()
                except Exception:
                    pass  # Ignore cleanup errors
                
                if split_files:
                    # Apply metadata only to files that already existed (to minimize API calls)
                    # Note: For split files, we check if they existed before the split operation
                    downloaded_count = 0
                    for split_file, timestamp_info in zip(split_files, track_timestamps):
                        track = timestamp_info['track']
                        # Check if file existed before split (it would have been in existing_files set)
                        # Since split always creates new files, we skip metadata for newly split files
                        # to minimize API calls. Metadata can be applied later if needed.
                        downloaded_count += 1
                    
                    if not silent:
                        console.print(f"[bold green]✓[/bold green] Successfully downloaded and split {downloaded_count} tracks from full album video")
                    
                    return downloaded_count, len(track_numbers) - downloaded_count
                
            except Exception as e:
                if not silent:
                    console.print(f"[yellow]⚠[/yellow] Error with full album video: {e}. Trying next...")
                continue
        
        # If we get here, all full album videos failed
        if not silent:
            console.print("[yellow]⚠[/yellow] All full album videos failed. Trying next strategy...")
        return None, None

