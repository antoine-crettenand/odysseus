"""
Strategy for downloading tracks from YouTube playlists.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .base_strategy import BaseDownloadStrategy
from ..download_service import DownloadRequest, DownloadResult
from .....models.releases import ReleaseInfo, Track
from .....models.search_results import YouTubeVideo


@dataclass(frozen=True)
class _PreparedPlaylistTrack:
    track: Track
    youtube_url: str
    request: DownloadRequest


class PlaylistStrategy(BaseDownloadStrategy):
    """Strategy for downloading tracks from YouTube playlists."""

    def download(
        self,
        release_info: ReleaseInfo,
        track_numbers: List[int],
        quality: str,
        silent: bool = False,
        cover_art_data: Optional[bytes] = None,
        jobs: int = 1,
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
            jobs: Maximum number of simultaneous independent track downloads
        """
        self._start_attempt(track_numbers)

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

                prepared, failed_count = self._prepare_downloads(
                    release_info,
                    track_to_video,
                    quality,
                    silent,
                )
                results = self._download_prepared(
                    prepared,
                    len(track_to_video),
                    failed_count,
                    jobs,
                    release_info,
                    silent,
                )
                downloaded_count, result_failures = self._apply_results(
                    prepared,
                    results,
                    release_info,
                    cover_art_data,
                    silent,
                )
                failed_count += result_failures

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

    def _prepare_downloads(
        self,
        release_info: ReleaseInfo,
        track_to_video: Dict[Track, Dict],
        quality: str,
        silent: bool,
    ) -> Tuple[List[_PreparedPlaylistTrack], int]:
        """Validate matches and build immutable worker requests."""
        prepared = []
        failed = 0
        console = self.display_manager.console
        date = release_info.original_release_date or release_info.release_date
        year = int(date[:4]) if date and len(date) >= 4 else None

        for track, video_info in track_to_video.items():
            video = YouTubeVideo(
                title=video_info["title"],
                video_id=video_info["id"],
                url_suffix=f"watch?v={video_info['id']}",
            )
            is_valid, reason = self.video_validator.validate_video_for_track(
                video,
                track,
                silent,
            )
            if not is_valid:
                if not silent:
                    self.display_manager.styling.log_warning(
                        f"Skipping invalid video for {track.title}: {reason}"
                    )
                    console.print(f"  [dim]YouTube: {video.youtube_url}[/dim]")
                failed += 1
                continue

            video_url = video_info.get("webpage_url")
            if not video_url:
                video_id = video_info.get("id") or video_info.get("url")
                if not video_id:
                    if not silent:
                        console.print(
                            "[yellow]⚠[/yellow] Could not determine video "
                            f"URL for {track.title}"
                        )
                    failed += 1
                    continue
                video_url = f"https://www.youtube.com/watch?v={video_id}"

            track_artist = (
                track.artist
                if track.artist and track.artist != release_info.artist
                else release_info.artist or "Unknown Artist"
            )
            metadata = {
                "title": track.title,
                "artist": track_artist,
                "album": release_info.title,
                "year": year,
                "track_number": track.position,
                "total_tracks": len(release_info.tracks),
            }
            if (
                release_info.release_type == "Playlist"
                and release_info.url
                and "spotify.com" in release_info.url
            ):
                metadata.update(
                    {
                        "is_playlist": True,
                        "playlist_name": release_info.title,
                    }
                )

            prepared.append(
                _PreparedPlaylistTrack(
                    track=track,
                    youtube_url=video_url,
                    request=DownloadRequest(
                        key=track.position,
                        url=video_url,
                        quality=quality,
                        metadata=metadata,
                    ),
                )
            )

        return prepared, failed

    def _download_prepared(
        self,
        prepared: List[_PreparedPlaylistTrack],
        total_matches: int,
        failed_count: int,
        jobs: int,
        release_info: ReleaseInfo,
        silent: bool,
    ) -> List[DownloadResult]:
        """Download validated playlist tracks with caller-thread progress."""
        if not prepared:
            return []

        progress = self.display_manager.create_progress_bar(
            total_matches,
            "Downloading from playlist"
            if not silent
            else f"Downloading {release_info.title}",
        )
        percentages = {
            item.track.position: 0.0
            for item in prepared
        }
        tracks = {
            item.track.position: item.track
            for item in prepared
        }
        with progress:
            task = progress.add_task(
                "[cyan]Downloading from playlist..."
                if not silent
                else "[cyan]Downloading tracks...",
                total=100 * total_matches,
                completed=100 * failed_count,
            )

            def update_progress(track_number: int, info: Dict) -> None:
                percentages[track_number] = max(
                    percentages.get(track_number, 0.0),
                    float(info.get("percent", 0.0) or 0.0),
                )
                track = tracks[track_number]
                progress.update(
                    task,
                    completed=100 * failed_count + sum(percentages.values()),
                    description=f"[cyan]Downloading: {track.title[:40]}",
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
        return results

    def _apply_results(
        self,
        prepared: List[_PreparedPlaylistTrack],
        results: List[DownloadResult],
        release_info: ReleaseInfo,
        cover_art_data: Optional[bytes],
        silent: bool,
    ) -> Tuple[int, int]:
        """Apply metadata serially and report ordered worker outcomes."""
        results_by_key = {result.key: result for result in results}
        downloaded = 0
        failed = 0
        console = self.display_manager.console

        for item in prepared:
            result = results_by_key.get(item.track.position)
            if result is None:
                result = DownloadResult(
                    item.track.position,
                    error="Download worker returned no result",
                )
            if not result.succeeded:
                self._display_failure(item.track, result, silent)
                failed += 1
                continue

            self._mark_track_downloaded(item.track.position)
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
            downloaded += 1

        return downloaded, failed

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
