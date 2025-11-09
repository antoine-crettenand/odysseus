"""
Download orchestrator service for coordinating downloads.
"""

from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from ..models.song import SongData, AudioMetadata
from ..models.search_results import MusicBrainzSong, YouTubeVideo
from ..models.releases import ReleaseInfo
from ..services.download_service import DownloadService
from ..services.metadata_service import MetadataService
from ..services.search_service import SearchService
from ..ui.display import DisplayManager
from .video_validator import VideoValidator
from .title_matcher import TitleMatcher
from .path_manager import PathManager
from .download_strategies import (
    FullAlbumStrategy,
    PlaylistStrategy,
    IndividualTracksStrategy
)


class DownloadOrchestrator:
    """Orchestrates download operations."""
    
    def __init__(
        self,
        download_service: DownloadService,
        metadata_service: MetadataService,
        search_service: SearchService,
        display_manager: DisplayManager
    ):
        self.download_service = download_service
        self.metadata_service = metadata_service
        self.search_service = search_service
        self.display_manager = display_manager
        
        # Initialize helper services
        self.video_validator = VideoValidator(download_service)
        self.title_matcher = TitleMatcher()
        self.path_manager = PathManager(download_service)
        
        # Initialize strategies
        self.full_album_strategy = FullAlbumStrategy(
            download_service,
            metadata_service,
            search_service,
            display_manager,
            self.video_validator,
            self.title_matcher,
            self.path_manager
        )
        self.playlist_strategy = PlaylistStrategy(
            download_service,
            metadata_service,
            search_service,
            display_manager,
            self.video_validator,
            self.title_matcher,
            self.path_manager
        )
        self.individual_tracks_strategy = IndividualTracksStrategy(
            download_service,
            metadata_service,
            search_service,
            display_manager,
            self.video_validator,
            self.title_matcher,
            self.path_manager
        )
    
    def download_recording(
        self,
        song_data: SongData,
        selected_video: YouTubeVideo,
        metadata: MusicBrainzSong,
        quality: str
    ) -> Optional[Path]:
        """Download a single recording."""
        console = self.display_manager.console
        video_id = selected_video.video_id
        if not video_id:
            console.print("[bold red]✗[/bold red] No video ID found.")
            return None
        
        youtube_url = selected_video.youtube_url
        video_title = selected_video.title or 'Unknown'
        
        # Warn if this appears to be a live version
        if self.video_validator.is_live_version(video_title):
            console.print(f"[yellow]⚠[/yellow] Warning: This video appears to be a live version: {video_title}")
            console.print("[yellow]⚠[/yellow] If you want a studio version, consider selecting a different video.")
            console.print()
        
        # Warn if this appears to be a reaction/review video
        if self.video_validator.is_reaction_or_review_video(video_title):
            console.print(f"[yellow]⚠[/yellow] Warning: This video appears to be a reaction/review/non-album content: {video_title}")
            console.print("[yellow]⚠[/yellow] This is not the actual album content. Consider selecting a different video.")
            console.print()
        
        # Validate duration if we have track duration info
        if hasattr(metadata, 'duration') and metadata.duration:
            video_info = self.download_service.get_video_info(youtube_url)
            if video_info:
                video_duration = self.video_validator._get_video_duration_seconds(video_info)
                expected_duration = self.video_validator._parse_duration_to_seconds(metadata.duration)
                
                if video_duration and expected_duration:
                    if video_duration > expected_duration * 1.4:
                        console.print(f"[yellow]⚠[/yellow] Warning: Video duration ({video_duration/60:.1f} min) is significantly longer than expected ({expected_duration/60:.1f} min)")
                        console.print("[yellow]⚠[/yellow] This might be a live version with extended sections.")
                        console.print()
                    elif video_duration < expected_duration * 0.7:
                        console.print(f"[yellow]⚠[/yellow] Warning: Video duration ({video_duration/60:.1f} min) is significantly shorter than expected ({expected_duration/60:.1f} min)")
                        console.print("[yellow]⚠[/yellow] This might be incomplete or a different version.")
                        console.print()
        
        # Display download info
        self.display_manager.display_download_info(
            youtube_url,
            quality,
            quality == 'audio',
            str(self.download_service.downloads_dir),
            {
                'title': song_data.title,
                'artist': song_data.artist,
                'album': song_data.album,
                'year': song_data.release_year
            }
        )
        
        # Create metadata for download
        metadata_dict = {
            'title': song_data.title,
            'artist': song_data.artist,
            'album': song_data.album,
            'year': song_data.release_year
        }
        
        # Download with progress bar
        console.print("[cyan]Starting download...[/cyan]")
        
        # Create progress bar for file download
        progress, task_id = self.display_manager.create_download_progress_bar(
            f"Downloading: {video_title[:50]}"
        )
        
        # Progress callback to update the progress bar
        def update_progress(progress_info: Dict[str, Any]):
            """Update progress bar with download info."""
            # Use percentage for progress (0-100)
            percent = progress_info.get('percent', 0)
            progress.update(task_id, completed=percent)
            
            # Update description
            desc = f"Downloading: {video_title[:40]}"
            progress.update(task_id, description=desc)
        
        # Download with progress tracking
        download_error = None
        try:
            with progress:
                if quality == 'audio':
                    result = self.download_service.download_high_quality_audio(
                        youtube_url,
                        metadata=metadata_dict,
                        quiet=True,
                        progress_callback=update_progress
                    )
                else:
                    result = self.download_service.download_video(
                        youtube_url,
                        quality=quality,
                        audio_only=(quality == 'audio'),
                        metadata=metadata_dict,
                        quiet=True,
                        progress_callback=update_progress
                    )
                
                # Ensure result is a tuple (handle case where download method might return None)
                if result is None:
                    downloaded_path, file_existed = None, False
                    download_error = "Download service returned None (no file was downloaded)"
                else:
                    downloaded_path, file_existed = result
                
                # Mark as complete
                progress.update(task_id, completed=100, description=f"Completed: {video_title[:40]}")
        except Exception as e:
            # If download fails, ensure we have valid values
            downloaded_path, file_existed = None, False
            download_error = str(e)
            # Update progress to show error
            try:
                progress.update(task_id, completed=100, description=f"[red]Failed: {video_title[:35]}[/red]")
            except:
                pass
        
        if downloaded_path:
            # Apply metadata (including cover art) to all downloaded files
            # For newly downloaded files, we should apply metadata so they have proper tags
            audio_metadata = AudioMetadata(
                title=song_data.title,
                artist=song_data.artist,
                album=song_data.album,
                year=song_data.release_year
            )
            # Try to get cover art from MusicBrainz if we have MBID
            if hasattr(metadata, 'mbid') and metadata.mbid:
                cover_art_data = self.metadata_service.fetch_cover_art(metadata.mbid, console)
                if cover_art_data:
                    audio_metadata.cover_art_data = cover_art_data
            
            self.metadata_service.merger.set_final_metadata(audio_metadata)
            self.metadata_service.apply_metadata_to_file(str(downloaded_path), quiet=True)
            console.print(f"[bold green]✓[/bold green] Download completed: [green]{downloaded_path}[/green]")
            return downloaded_path
        else:
            # Display concise error message
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
            
            error_details = f"[yellow]{song_data.title}[/yellow] — [red]{actual_error}[/red]"
            
            # Add tip only for specific errors
            if download_error and ("bot" in download_error.lower() or "sign in" in download_error.lower()):
                error_details += f"\n[yellow]Tip:[/yellow] YouTube may be blocking requests. Try signing in to YouTube."
            
            console.print(Panel(
                error_details,
                title="[bold red]✗ Download Failed[/bold red]",
                border_style="red",
                box=box.ROUNDED,
                padding=(0, 1)
            ))
            return None
    
    def _display_summary(self, downloaded: int, failed: int, total: int, title: str = "DOWNLOAD SUMMARY", skipped: int = 0):
        """Display download summary."""
        console = self.display_manager.console
        console.print()
        summary_content = f"[bold green]✓[/bold green] Successfully downloaded: [green]{downloaded}[/green] track{'s' if downloaded != 1 else ''}\n"
        if skipped > 0:
            summary_content += f"[yellow]⏭[/yellow] Skipped existing: [yellow]{skipped}[/yellow] track{'s' if skipped != 1 else ''}\n"
        if failed > 0:
            summary_content += f"[bold red]✗[/bold red] Failed downloads: [red]{failed}[/red] track{'s' if failed != 1 else ''}\n"
        summary_content += f"[blue]ℹ[/blue] Total tracks processed: [cyan]{total}[/cyan]"
        
        from rich.panel import Panel
        from rich import box
        console.print(Panel(
            summary_content,
            title=f"[bold cyan]📊 {title}[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2)
        ))
        console.print()
    
    def download_release_tracks(
        self,
        release_info: ReleaseInfo,
        track_numbers: List[int],
        quality: str,
        silent: bool = False
    ) -> Tuple[int, int]:
        """Download selected tracks from a release using multi-strategy approach."""
        console = self.display_manager.console
        
        # Check which tracks already exist (partial matches allowed)
        existing_tracks = self.path_manager.get_existing_tracks(release_info, track_numbers)
        missing_track_numbers = [tn for tn in track_numbers if tn not in existing_tracks]
        
        # Fetch cover art once for the entire release (before trying any strategies)
        output_dir = self.path_manager.get_release_folder_path(release_info)
        cover_art_data = None
        if not silent:
            cover_art_data = self.metadata_service.fetch_cover_art_for_release(release_info, console, folder_path=output_dir)
        else:
            cover_art_data = self.metadata_service.fetch_cover_art_for_release(release_info, None, folder_path=output_dir)
        
        # If all tracks exist, only apply metadata
        if not missing_track_numbers:
            if not silent:
                console.print("[cyan]ℹ[/cyan] All tracks already exist. Applying metadata only...")
                console.print()
            
            # Apply metadata to all existing tracks
            processed_count = 0
            failed_count = 0
            
            # Create progress bar
            progress = self.display_manager.create_progress_bar(
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
                            self.display_manager.display_track_download_result(
                                track.title, True, str(file_path), file_existed=True
                            )
                        # Apply metadata with cover art
                        self.metadata_service.apply_metadata_with_cover_art(
                            file_path, track, release_info, console, cover_art_data=cover_art_data, path_manager=self.path_manager
                        )
                        processed_count += 1
                    except Exception as e:
                        if not silent:
                            console.print(f"[yellow]⚠[/yellow] Could not apply metadata to {track.title}: {e}")
                        failed_count += 1
                    
                    progress.update(task, advance=1)
            
            # Summary
            if not silent:
                console.print()
                summary_content = f"[bold green]✓[/bold green] Successfully processed: [green]{processed_count}[/green] track{'s' if processed_count != 1 else ''}\n"
                if failed_count > 0:
                    summary_content += f"[bold red]✗[/bold red] Failed: [red]{failed_count}[/red] track{'s' if failed_count != 1 else ''}\n"
                summary_content += f"[blue]ℹ[/blue] Total tracks processed: [cyan]{len(track_numbers)}[/cyan]"
                
                from rich.panel import Panel
                from rich import box
                console.print(Panel(
                    summary_content,
                    title="[bold cyan]📊 METADATA SUMMARY[/bold cyan]",
                    border_style="cyan",
                    box=box.ROUNDED,
                    padding=(1, 2)
                ))
                console.print()
            
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
            
            console.print(f"[cyan]ℹ[/cyan] Found {len(existing_tracks)} existing track{'s' if len(existing_tracks) != 1 else ''}. Downloading {missing_info}...")
            
            # Display which tracks were found (helpful for debugging ordering issues)
            tracks_with_wrong_numbers = []
            if len(existing_tracks) > 0:
                from rich.table import Table
                table = Table(title="[cyan]Existing Tracks Found[/cyan]", show_header=True, header_style="bold cyan")
                table.add_column("Expected #", style="cyan", justify="right")
                table.add_column("Track Title", style="green")
                table.add_column("File", style="yellow")
                
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
                        tracks_with_wrong_numbers.append((track_num, file_path, track_title))
                    
                    table.add_row(str(track_num), track_title, file_display)
                
                console.print()
                console.print(table)
                console.print()
                
                # Offer to reorder tracks with wrong numbers
                if tracks_with_wrong_numbers and not silent:
                    console.print(f"[yellow]⚠[/yellow] Found {len(tracks_with_wrong_numbers)} track{'s' if len(tracks_with_wrong_numbers) != 1 else ''} with incorrect track numbers.")
                    console.print("[dim]These tracks will still be used, but you may want to rename them to match the correct order.[/dim]")
                    console.print()
            
            console.print()
        
        # Strategy 1: Try full album video (only for missing tracks)
        downloaded, failed = self.full_album_strategy.download(
            release_info, missing_track_numbers, quality, silent, cover_art_data=cover_art_data
        )
        if downloaded is not None:
            # Success with full album - apply metadata to existing tracks too
            if existing_tracks:
                self._apply_metadata_to_existing_tracks(
                    release_info, existing_tracks, cover_art_data, silent, console
                )
            if not silent:
                self._display_summary(downloaded, failed, len(track_numbers), skipped=len(existing_tracks))
            return downloaded + len(existing_tracks), failed
        
        # Strategy 2: Try playlist (only for missing tracks)
        downloaded, failed = self.playlist_strategy.download(
            release_info, missing_track_numbers, quality, silent, cover_art_data=cover_art_data
        )
        if downloaded is not None:
            # Success with playlist - apply metadata to existing tracks too
            if existing_tracks:
                self._apply_metadata_to_existing_tracks(
                    release_info, existing_tracks, cover_art_data, silent, console
                )
            if not silent:
                self._display_summary(downloaded, failed, len(track_numbers), skipped=len(existing_tracks))
            return downloaded + len(existing_tracks), failed
        
        # Strategy 3: Fall back to individual tracks (only for missing tracks)
        downloaded, failed = self.individual_tracks_strategy.download(
            release_info, missing_track_numbers, quality, silent, cover_art_data=cover_art_data
        )
        
        # Apply metadata to existing tracks
        if existing_tracks:
            self._apply_metadata_to_existing_tracks(
                release_info, existing_tracks, cover_art_data, silent, console
            )
        
        # Summary (only if not silent)
        if not silent:
            total_downloaded = downloaded + len(existing_tracks) if downloaded is not None else len(existing_tracks)
            self._display_summary(total_downloaded, failed, len(track_numbers), skipped=len(existing_tracks))
        
        return (downloaded + len(existing_tracks) if downloaded is not None else len(existing_tracks)), failed
    
    def _apply_metadata_to_existing_tracks(
        self,
        release_info: ReleaseInfo,
        existing_tracks: Dict[int, Path],
        cover_art_data: Optional[bytes],
        silent: bool,
        console
    ) -> None:
        """Apply metadata to existing tracks."""
        if not existing_tracks:
            return
        
        if not silent:
            console.print(f"[cyan]📝 Applying metadata to {len(existing_tracks)} existing track{'s' if len(existing_tracks) != 1 else ''}...[/cyan]")
        
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
                # Apply metadata with cover art
                self.metadata_service.apply_metadata_with_cover_art(
                    file_path, track, release_info, console if not silent else None,
                    cover_art_data=cover_art_data, path_manager=self.path_manager
                )
                if not silent:
                    self.display_manager.display_track_download_result(
                        track.title, True, str(file_path), file_existed=True
                    )
            except Exception as e:
                if not silent:
                    console.print(f"[yellow]⚠[/yellow] Could not apply metadata to {track.title}: {e}")
