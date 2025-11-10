"""
Strategy for downloading individual tracks one by one.
"""

import subprocess
from typing import List, Optional, Dict, Any, Tuple
from .base_strategy import BaseDownloadStrategy
from ...models.releases import ReleaseInfo
from ...services.video_searcher import VideoSearcher
from ...services.playlist_checker import PlaylistChecker


class IndividualTracksStrategy(BaseDownloadStrategy):
    """Strategy for downloading individual tracks one by one."""
    
    def __init__(
        self,
        download_service,
        metadata_service,
        search_service,
        display_manager,
        video_validator,
        title_matcher,
        path_manager
    ):
        """Initialize strategy with helper services."""
        super().__init__(
            download_service,
            metadata_service,
            search_service,
            display_manager,
            video_validator,
            title_matcher,
            path_manager
        )
        # Initialize helper services
        self.video_searcher = VideoSearcher(
            search_service,
            video_validator,
            title_matcher,
            display_manager
        )
        self.playlist_checker = PlaylistChecker(
            download_service,
            search_service,
            video_validator,
            title_matcher,
            display_manager
        )
    
    def download(
        self,
        release_info: ReleaseInfo,
        track_numbers: List[int],
        quality: str,
        silent: bool = False,
        cover_art_data: Optional[bytes] = None
    ) -> Tuple[Optional[int], Optional[int]]:
        """
        Download individual tracks from a release.
        
        Optimized to fetch cover art once per release and reuse it for all tracks.
        Strategy 3: Download individual tracks (fallback).
        
        Args:
            release_info: Release information
            track_numbers: List of track numbers to download
            quality: Download quality
            silent: Whether to suppress output
            cover_art_data: Optional pre-fetched cover art data (to avoid redundant searches)
        """
        console = self.display_manager.console
        
        if not silent:
            console.print("[cyan]🎵 Strategy 3: Downloading individual tracks...[/cyan]")
        
        # Get folder path for cover art extraction from existing tracks
        output_dir = self.path_manager.get_release_folder_path(release_info)
        
        # Fetch cover art only if not provided (optimization to avoid redundant searches)
        if cover_art_data is None:
            if not silent:
                cover_art_data = self.metadata_service.fetch_cover_art_for_release(release_info, console, folder_path=output_dir)
            else:
                # Still fetch cover art in silent mode, just don't print messages
                cover_art_data = self.metadata_service.fetch_cover_art_for_release(release_info, None, folder_path=output_dir)
        
        downloaded_count = 0
        failed_count = 0
        
        # Create progress bar
        progress = self.display_manager.create_progress_bar(
            len(track_numbers),
            "Downloading tracks" if not silent else f"Downloading {release_info.title}"
        )
        
        with progress:
            task = progress.add_task(
                "[cyan]Downloading..." if not silent else "[cyan]Downloading tracks...",
                total=len(track_numbers)
            )
            
            for track_num in track_numbers:
                # Find the track
                track = None
                for t in release_info.tracks:
                    if t.position == track_num:
                        track = t
                        break
                
                if not track:
                    if not silent:
                        console.print(f"[bold red]✗[/bold red] Track [bold]{track_num}[/bold] not found.")
                    failed_count += 1
                    progress.update(task, advance=1)
                    continue
                
                progress.update(task, description=f"[cyan]Downloading: {track.title}")
                
                try:
                    # Search for and match video using VideoSearcher
                    selected_video, playlist_ids_found = self.video_searcher.search_and_match_video(
                        track, release_info, silent
                    )
                    
                    # If no direct match found, try checking playlists from search results
                    if not selected_video and playlist_ids_found:
                        selected_video = self.playlist_checker.check_playlists_from_ids(
                            list(playlist_ids_found),
                            track,
                            release_info,
                            silent
                        )
                    
                    # If still no match, search for playlists containing this track
                    if not selected_video:
                        selected_video = self.playlist_checker.search_and_check_playlists(
                            track,
                            release_info,
                            silent
                        )
                    
                    # If still no valid video found, skip this track
                    if not selected_video:
                        if not silent:
                            console.print(f"[bold red]✗[/bold red] No valid (non-live) video found for: [white]{track.title}[/white]")
                        failed_count += 1
                        progress.update(task, advance=1)
                        continue
                    
                except Exception as e:
                    # Catch any errors in the search/retry process
                    if not silent:
                        console.print(f"[yellow]⚠[/yellow] Error during track search: {e}")
                    failed_count += 1
                    progress.update(task, advance=1)
                    continue
                
                try:
                    # Create metadata for download
                    # Check if this is a Spotify playlist (only Spotify sets release_type to "Playlist")
                    # Also verify URL to ensure it's from Spotify (extra safeguard)
                    is_playlist = (
                        release_info.release_type == "Playlist" and 
                        release_info.url and 
                        "spotify.com" in release_info.url
                    )
                    
                    if is_playlist:
                        # For playlists, use playlist folder structure
                        # Use original_release_date for year if available (prefer original year over re-release year)
                        date_to_use = release_info.original_release_date or release_info.release_date
                        year = int(date_to_use[:4]) if date_to_use and len(date_to_use) >= 4 else None
                        
                        metadata_dict = {
                            'title': track.title,
                            'artist': track.artist,  # Keep actual track artist in metadata
                            'album': release_info.title,
                            'is_playlist': True,
                            'playlist_name': release_info.title,
                            'year': year,
                            'track_number': track_num,  # Use track_num (requested position) not track.position (API position)
                            'total_tracks': len(release_info.tracks)
                        }
                    else:
                        # Use "Various Artists" for folder structure if this is a compilation
                        # but keep the actual track artist in metadata
                        is_compilation = self.path_manager.is_compilation(release_info)
                        folder_artist = "Various Artists" if is_compilation else track.artist
                        
                        # Use original_release_date for year if available (prefer original year over re-release year)
                        date_to_use = release_info.original_release_date or release_info.release_date
                        year = int(date_to_use[:4]) if date_to_use and len(date_to_use) >= 4 else None
                        
                        metadata_dict = {
                            'title': track.title,
                            'artist': folder_artist,  # Use "Various Artists" for folder structure in compilations
                            'album': release_info.title,
                            'year': year,
                            'track_number': track_num,  # Use track_num (requested position) not track.position (API position)
                            'total_tracks': len(release_info.tracks)
                        }
                    
                    # Create nested progress bar for file download
                    file_progress, file_task_id = self.display_manager.create_download_progress_bar(
                        f"Track {track.position}: {track.title[:40]}"
                    )
                    
                    # Progress callback for file download
                    def update_file_progress(progress_info: Dict[str, Any]):
                        """Update file-level progress bar."""
                        # Use percentage for progress (0-100)
                        percent = progress_info.get('percent', 0)
                        file_progress.update(file_task_id, completed=percent)
                        
                        # Update description
                        desc = f"Track {track.position}: {track.title[:35]}"
                        file_progress.update(file_task_id, description=desc)
                    
                    # Download the track with progress
                    youtube_url = selected_video.youtube_url
                    download_error = None
                    
                    try:
                        with file_progress:
                            if quality == 'audio':
                                result = self.download_service.download_high_quality_audio(
                                    youtube_url,
                                    metadata=metadata_dict,
                                    quiet=True,
                                    progress_callback=update_file_progress
                                )
                            else:
                                result = self.download_service.download_video(
                                    youtube_url,
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
                            
                            # Mark as complete
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
                            console.print(f"  [dim]YouTube: {youtube_url}[/dim]")
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
                            # Silent mode - just show brief error
                            console.print(f"[red]✗[/red] Failed: {track.title}")
                        failed_count += 1
                        
                except subprocess.TimeoutExpired:
                    # Timeout occurred during download
                    failed_count += 1
                    if not silent:
                        console.print()
                        from rich.panel import Panel
                        from rich import box
                        error_details = f"[bold red]✗ Download Timeout[/bold red]\n\n"
                        error_details += f"[white]Track:[/white] [yellow]{track.title}[/yellow]\n"
                        error_details += f"[white]Artist:[/white] [yellow]{track.artist}[/yellow]\n"
                        error_details += f"\n[red]Error:[/red] Download timed out after {self.download_service.downloader.timeout} seconds\n"
                        error_details += f"\n[yellow]Tip:[/yellow] The download may be too large or your connection is slow. Try again later.\n"
                        console.print(Panel(
                            error_details,
                            title=f"[bold red]⏱ Track {track.position} Timeout[/bold red]",
                            border_style="red",
                            box=box.ROUNDED,
                            padding=(1, 2)
                        ))
                        console.print()
                    else:
                        console.print(f"[red]✗[/red] Timeout: {track.title}")
                except Exception as e:
                    # Log other exceptions but continue with next track
                    failed_count += 1
                    if not silent:
                        console.print()
                        from rich.panel import Panel
                        from rich import box
                        error_details = f"[bold red]✗ Download Error[/bold red]\n\n"
                        error_details += f"[white]Track:[/white] [yellow]{track.title}[/yellow]\n"
                        error_details += f"[white]Artist:[/white] [yellow]{track.artist}[/yellow]\n"
                        error_details += f"\n[red]Error:[/red] {str(e)[:300]}\n"
                        console.print(Panel(
                            error_details,
                            title=f"[bold red]❌ Track {track.position} Error[/bold red]",
                            border_style="red",
                            box=box.ROUNDED,
                            padding=(1, 2)
                        ))
                        console.print()
                    else:
                        console.print(f"[red]✗[/red] Error: {track.title} - {str(e)[:50]}")
                
                progress.update(task, advance=1)
        
        return downloaded_count, failed_count

