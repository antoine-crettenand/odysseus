"""
Strategy for downloading tracks from YouTube playlists.
"""

from typing import List, Optional, Dict, Any, Tuple
from .base_strategy import BaseDownloadStrategy
from ...models.releases import ReleaseInfo
from ...models.search_results import YouTubeVideo


class PlaylistStrategy(BaseDownloadStrategy):
    """Strategy for downloading tracks from YouTube playlists."""
    
    def download(
        self,
        release_info: ReleaseInfo,
        track_numbers: List[int],
        quality: str,
        silent: bool = False,
        cover_art_data: Optional[bytes] = None
    ) -> Tuple[Optional[int], Optional[int]]:
        """
        Strategy 2: Download from YouTube playlist.
        
        Optimized to fetch cover art once per release and reuse it for all tracks.
        
        Args:
            release_info: Release information
            track_numbers: List of track numbers to download
            quality: Download quality
            silent: Whether to suppress output
            cover_art_data: Optional pre-fetched cover art data (to avoid redundant searches)
        """
        # Skip this strategy for Spotify playlists - searching by playlist name/owner doesn't make sense
        # This strategy is for finding YouTube playlists that match an album, not for Spotify playlists
        # Verify it's a Spotify playlist (extra safeguard)
        if (
            release_info.release_type == "Playlist" and 
            release_info.url and 
            "spotify.com" in release_info.url
        ):
            if not silent:
                console = self.display_manager.console
                console.print("[cyan]ℹ[/cyan] Skipping YouTube playlist strategy for Spotify playlist (not applicable)...")
            return None, None
        
        console = self.display_manager.console
        
        if not silent:
            console.print("[cyan]🎵 Strategy 2: Searching for playlist...[/cyan]")
        
        # Get folder path for cover art extraction from existing tracks
        output_dir = self.path_manager.get_release_folder_path(release_info)
        
        # Fetch cover art only if not provided (optimization to avoid redundant searches)
        if cover_art_data is None:
            if not silent:
                cover_art_data = self.metadata_service.fetch_cover_art_for_release(release_info, console, folder_path=output_dir)
            else:
                # Still fetch cover art in silent mode, just don't print messages
                cover_art_data = self.metadata_service.fetch_cover_art_for_release(release_info, None, folder_path=output_dir)
        
        # Extract track titles for more thorough playlist search
        track_titles = [track.title for track in release_info.tracks[:5]]  # Use first 5 tracks
        
        # Search for playlists
        playlists = self.display_manager.show_loading_spinner(
            f"Searching for playlist: {release_info.title}",
            self.search_service.search_playlist,
            release_info.artist,
            release_info.title,
            3,
            track_titles
        )
        
        if not playlists:
            if not silent:
                styling = self.display_manager.styling
                styling.log_warning("No playlist found. Trying next strategy...")
            return None, None
        
        # Try downloading from playlist
        for playlist_info in playlists:
            try:
                playlist_url = playlist_info['url']
                if not silent:
                    console.print(f"[cyan]📥 Found playlist: {playlist_info['title']}[/cyan]")
                
                # Get playlist video information
                if not silent:
                    console.print("[cyan]📋 Fetching playlist information...[/cyan]")
                
                try:
                    playlist_videos = self.display_manager.show_loading_spinner(
                        "Fetching playlist videos",
                        self.download_service.get_playlist_info,
                        playlist_url
                    )
                except Exception as e:
                    if not silent:
                        console.print(f"[yellow]⚠[/yellow] Error fetching playlist: {e}. Trying next playlist...")
                    continue
                
                if not playlist_videos:
                    if not silent:
                        console.print(f"[yellow]⚠[/yellow] Could not fetch playlist videos from: {playlist_url}")
                        console.print("[yellow]⚠[/yellow] This might be due to:")
                        console.print("  - Playlist is private or unavailable")
                        console.print("  - Playlist is empty")
                        console.print("  - Network/API issues")
                        console.print("[yellow]⚠[/yellow] Trying next playlist...")
                    continue
                
                if not silent:
                    console.print(f"[green]✓[/green] Found {len(playlist_videos)} videos in playlist")
                
                # Check if this is a Side 1 or Side 2 playlist
                playlist_title = playlist_info.get('title', '').lower()
                is_side_1 = any(keyword in playlist_title for keyword in ['side 1', 'side a', 'side one'])
                is_side_2 = any(keyword in playlist_title for keyword in ['side 2', 'side b', 'side two'])
                
                # Filter tracks to selected ones
                selected_tracks = [
                    t for t in release_info.tracks
                    if t.position in track_numbers
                ]
                selected_tracks.sort(key=lambda x: x.position)
                
                # If this is a Side 1 or Side 2 playlist, we might need to adjust track matching
                # Side 1 typically contains first half of tracks, Side 2 contains second half
                if is_side_1 or is_side_2:
                    total_tracks = len(release_info.tracks)
                    if is_side_1:
                        # Side 1: typically tracks 1 to approximately total_tracks/2
                        # Filter to only tracks that are likely on Side 1
                        side_1_tracks = [t for t in selected_tracks if t.position <= (total_tracks + 1) // 2]
                        if side_1_tracks:
                            if not silent:
                                console.print(f"[blue]ℹ[/blue] Detected Side 1 playlist - focusing on tracks 1-{(total_tracks + 1) // 2}")
                            # Use side 1 tracks if we have them, otherwise use all selected tracks
                            if len(side_1_tracks) >= len(selected_tracks) * 0.5:
                                selected_tracks = side_1_tracks
                    elif is_side_2:
                        # Side 2: typically tracks from approximately total_tracks/2 + 1 to end
                        # Filter to only tracks that are likely on Side 2
                        side_2_start = (total_tracks + 1) // 2 + 1
                        side_2_tracks = [t for t in selected_tracks if t.position >= side_2_start]
                        if side_2_tracks:
                            if not silent:
                                console.print(f"[blue]ℹ[/blue] Detected Side 2 playlist - focusing on tracks {side_2_start}-{total_tracks}")
                            # Use side 2 tracks if we have them, otherwise use all selected tracks
                            if len(side_2_tracks) >= len(selected_tracks) * 0.5:
                                selected_tracks = side_2_tracks
                
                # Match playlist videos to tracks
                if not silent:
                    console.print("[cyan]🔍 Matching videos to tracks...[/cyan]")
                
                # Create a mapping: track -> best matching video
                track_to_video = {}
                used_videos = set()
                
                # First pass: try to find exact/very good matches (lower threshold for better coverage)
                for track in selected_tracks:
                    best_match = None
                    best_score = 0.4  # Lowered threshold from 0.5 to 0.4 for better coverage
                    
                    for video in playlist_videos:
                        if video['id'] in used_videos:
                            continue
                        
                        score = self.title_matcher.match_playlist_video_to_track(
                            video['title'],
                            track.title,
                            release_info.artist,
                            self.video_validator
                        )
                        
                        if score > best_score:
                            best_score = score
                            best_match = video
                    
                    if best_match:
                        track_to_video[track] = best_match
                        used_videos.add(best_match['id'])
                
                # Second pass: try to match remaining tracks with a lower threshold
                unmatched_tracks = [t for t in selected_tracks if t not in track_to_video]
                if unmatched_tracks:
                    if not silent:
                        console.print(f"[blue]ℹ[/blue] First pass matched {len(track_to_video)}/{len(selected_tracks)} tracks. Trying second pass with lower threshold...")
                    
                    for track in unmatched_tracks:
                        best_match = None
                        best_score = 0.25  # Lower threshold for second pass
                        
                        for video in playlist_videos:
                            if video['id'] in used_videos:
                                continue
                            
                            score = self.title_matcher.match_playlist_video_to_track(
                                video['title'],
                                track.title,
                                release_info.artist,
                                self.video_validator
                            )
                            
                            if score > best_score:
                                best_score = score
                                best_match = video
                        
                        if best_match:
                            track_to_video[track] = best_match
                            used_videos.add(best_match['id'])
                            if not silent:
                                console.print(f"[blue]ℹ[/blue] Second pass matched: {track.title} (score: {best_score:.2f})")
                
                # Check how many tracks we matched
                matched_count = len(track_to_video)
                # Lower threshold: require at least 30% match OR at least 1 match (for single track downloads)
                min_required = max(1, int(len(selected_tracks) * 0.3))
                if matched_count < min_required:
                    if not silent:
                        console.print(f"[yellow]⚠[/yellow] Only matched {matched_count}/{len(selected_tracks)} tracks (minimum: {min_required}). Trying next playlist...")
                    continue
                
                if not silent:
                    console.print(f"[green]✓[/green] Matched {matched_count}/{len(selected_tracks)} tracks")
                
                # Download matched videos
                downloaded_count = 0
                failed_count = 0
                
                # Create progress bar
                progress = self.display_manager.create_progress_bar(
                    len(track_to_video),
                    "Downloading from playlist" if not silent else f"Downloading {release_info.title}"
                )
                
                with progress:
                    task = progress.add_task(
                        "[cyan]Downloading from playlist..." if not silent else "[cyan]Downloading tracks...",
                        total=len(track_to_video)
                    )
                    
                    for track, video_info in track_to_video.items():
                        progress.update(task, description=f"[cyan]Downloading: {track.title}")
                        
                        try:
                            # Validate video (check for live versions, duration, etc.)
                            # Create a YouTubeVideo object for validation
                            video = YouTubeVideo(
                                title=video_info['title'],
                                video_id=video_info['id'],
                                url_suffix=f"watch?v={video_info['id']}"
                            )
                            
                            is_valid, reason = self.video_validator.validate_video_for_track(
                                video, track, silent
                            )
                            
                            if not is_valid:
                                if not silent:
                                    styling = self.display_manager.styling
                                    styling.log_warning(f"Skipping invalid video for {track.title}: {reason}")
                                    console.print(f"  [dim]YouTube: {video.youtube_url}[/dim]")
                                failed_count += 1
                                progress.update(task, advance=1)
                                continue
                            
                            # Get video URL
                            # With --flat-playlist, we might not get webpage_url, so construct from ID
                            video_url = video_info.get('webpage_url')
                            if not video_url:
                                # Construct URL from ID (most reliable with --flat-playlist)
                                video_id = video_info.get('id') or video_info.get('url')
                                if video_id:
                                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                                else:
                                    if not silent:
                                        console.print(f"[yellow]⚠[/yellow] Could not determine video URL for {track.title}")
                                    failed_count += 1
                                    progress.update(task, advance=1)
                                    continue
                            
                            # Create metadata for download
                            # Check if this is a Spotify playlist (only Spotify sets release_type to "Playlist")
                            # Verify it's a Spotify playlist (extra safeguard)
                            is_playlist = (
                                release_info.release_type == "Playlist" and 
                                release_info.url and 
                                "spotify.com" in release_info.url
                            )
                            
                            # Use original_release_date for year if available (prefer original year over re-release year)
                            date_to_use = release_info.original_release_date or release_info.release_date
                            year = int(date_to_use[:4]) if date_to_use and len(date_to_use) >= 4 else None
                            
                            if is_playlist:
                                # For playlists, use playlist folder structure
                                metadata_dict = {
                                    'title': track.title,
                                    'artist': track.artist,  # Keep actual track artist in metadata
                                    'album': release_info.title,
                                    'is_playlist': True,
                                    'playlist_name': release_info.title,
                                    'year': year,
                                    'track_number': track.position,
                                    'total_tracks': len(release_info.tracks)
                                }
                            else:
                                metadata_dict = {
                                    'title': track.title,
                                    'artist': track.artist,
                                    'album': release_info.title,
                                    'year': year,
                                    'track_number': track.position,
                                    'total_tracks': len(release_info.tracks)
                                }
                            
                            # Create nested progress bar for file download
                            file_progress, file_task_id = self.display_manager.create_download_progress_bar(
                                f"Track {track.position}: {track.title[:40]}"
                            )
                            
                            # Progress callback for file download
                            def update_file_progress(progress_info: Dict[str, Any]):
                                """Update file-level progress bar."""
                                percent = progress_info.get('percent', 0)
                                file_progress.update(file_task_id, completed=percent)
                                desc = f"Track {track.position}: {track.title[:35]}"
                                file_progress.update(file_task_id, description=desc)
                            
                            # Download the track with progress
                            download_error = None
                            try:
                                with file_progress:
                                    if quality == 'audio':
                                        result = self.download_service.download_high_quality_audio(
                                            video_url,
                                            metadata=metadata_dict,
                                            quiet=True,
                                            progress_callback=update_file_progress
                                        )
                                    else:
                                        result = self.download_service.download_video(
                                            video_url,
                                            quality=quality,
                                            audio_only=(quality == 'audio'),
                                            metadata=metadata_dict,
                                            quiet=True,
                                            progress_callback=update_file_progress
                                        )
                                    
                                    # Ensure result is a tuple
                                    if result is None:
                                        downloaded_path, file_existed = None, False
                                        download_error = "Download service returned None (no file was downloaded)"
                                    else:
                                        downloaded_path, file_existed = result
                                    
                                    file_progress.update(file_task_id, completed=100)
                            except Exception as e:
                                downloaded_path, file_existed = None, False
                                download_error = str(e)
                                try:
                                    file_progress.update(file_task_id, completed=100, description=f"[red]Failed: {track.title[:30]}[/red]")
                                except:
                                    pass
                            
                            if downloaded_path:
                                # Display download confirmation first
                                if not silent:
                                    self.display_manager.display_track_download_result(
                                        track.title, True, str(downloaded_path), file_existed=file_existed
                                    )
                                    console.print(f"  [dim]YouTube: {video_url}[/dim]")
                                # Apply metadata (including cover art) to all downloaded files
                                # Cover art was already fetched earlier, so we can apply it to all tracks
                                try:
                                    self.metadata_service.apply_metadata_with_cover_art(
                                        downloaded_path, track, release_info, console if not silent else None, cover_art_data=cover_art_data, path_manager=self.path_manager, file_existed_before=file_existed
                                    )
                                    downloaded_count += 1
                                except Exception as e:
                                    # If metadata application fails, still count as downloaded but log the error
                                    if not silent and console:
                                        console.print(f"[yellow]⚠[/yellow] Could not apply metadata to {track.title}: {e}")
                                    downloaded_count += 1
                            else:
                                if not silent:
                                    # Display concise error for failed track
                                    console.print()
                                    from rich.panel import Panel
                                    from rich import box
                                    
                                    # Extract actual error message (remove "All download strategies failed. " prefix if present)
                                    actual_error = download_error or "Download service returned no file"
                                    if actual_error.startswith("All download strategies failed. "):
                                        actual_error = actual_error.replace("All download strategies failed. ", "", 1)
                                    # Truncate long errors
                                    if len(actual_error) > 150:
                                        actual_error = actual_error[:147] + "..."
                                    
                                    error_details = f"[yellow]{track.title}[/yellow] — [red]{actual_error}[/red]"
                                    
                                    # Add tip only for specific errors
                                    if download_error and ("bot" in download_error.lower() or "sign in" in download_error.lower()):
                                        error_details += f"\n[yellow]Tip:[/yellow] YouTube may be blocking requests. Try signing in to YouTube."
                                    
                                    console.print(Panel(
                                        error_details,
                                        title=f"[bold red]✗ Track {track.position}[/bold red]",
                                        border_style="red",
                                        box=box.ROUNDED,
                                        padding=(0, 1)
                                    ))
                                else:
                                    console.print(f"[red]✗[/red] Failed: {track.title}")
                                failed_count += 1
                        
                        except Exception as e:
                            failed_count += 1
                            if not silent:
                                console.print()
                                from rich.panel import Panel
                                from rich import box
                                error_msg = str(e)
                                if len(error_msg) > 150:
                                    error_msg = error_msg[:147] + "..."
                                error_details = f"[yellow]{track.title}[/yellow] — [red]{error_msg}[/red]"
                                console.print(Panel(
                                    error_details,
                                    title=f"[bold red]✗ Track {track.position}[/bold red]",
                                    border_style="red",
                                    box=box.ROUNDED,
                                    padding=(0, 1)
                                ))
                            else:
                                console.print(f"[red]✗[/red] Error: {track.title} - {str(e)[:50]}")
                        
                        progress.update(task, advance=1)
                
                # Return results if we downloaded at least some tracks
                if downloaded_count > 0:
                    return downloaded_count, failed_count
                else:
                    if not silent:
                        console.print("[yellow]⚠[/yellow] No tracks downloaded from playlist. Trying next playlist...")
                    continue
                
            except Exception as e:
                if not silent:
                    console.print(f"[yellow]⚠[/yellow] Error with playlist: {e}. Trying next...")
                continue
        
        # If we get here, all playlists failed
        if not silent:
            styling = self.display_manager.styling
            styling.log_warning("All playlists failed. Trying next strategy...")
        return None, None

