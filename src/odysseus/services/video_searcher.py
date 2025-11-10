"""
Video searcher module for finding and matching YouTube videos to tracks.
"""

import re
from typing import List, Optional, Tuple, Set
from ..models.releases import ReleaseInfo
from ..models.search_results import YouTubeVideo


class VideoSearcher:
    """Handles searching and matching YouTube videos for tracks."""
    
    def __init__(
        self,
        search_service,
        video_validator,
        title_matcher,
        display_manager
    ):
        """
        Initialize video searcher.
        
        Args:
            search_service: SearchService instance
            video_validator: VideoValidator instance
            title_matcher: TitleMatcher instance
            display_manager: DisplayManager instance
        """
        self.search_service = search_service
        self.video_validator = video_validator
        self.title_matcher = title_matcher
        self.display_manager = display_manager
    
    def build_track_search_query(self, track, release_info: ReleaseInfo) -> str:
        """
        Build an optimized YouTube search query for a track.
        
        When track title matches or is similar to album name, adds disambiguating terms
        to improve search results and avoid interviews, live versions, etc.
        """
        # For Spotify playlists, don't compare track title to playlist name
        is_playlist = (
            release_info.release_type == "Playlist" and 
            release_info.url and 
            "spotify.com" in release_info.url
        )
        titles_similar = False
        
        if not is_playlist:
            titles_similar = self.title_matcher.are_titles_similar(track.title, release_info.title)
        
        # Build base query
        query_parts = [track.artist, track.title]
        
        # If titles are similar, add disambiguating terms
        if titles_similar:
            query_parts.append("album")
            if release_info.release_date:
                year = release_info.release_date[:4] if len(release_info.release_date) >= 4 else None
                if year and year.isdigit():
                    query_parts.append(year)
        
        return " ".join(query_parts)
    
    def _extract_playlist_ids(self, videos: List[YouTubeVideo]) -> Set[str]:
        """Extract playlist IDs from video URLs."""
        playlist_ids = set()
        for video in videos:
            if video.url_suffix and 'list=' in video.url_suffix:
                match = re.search(r'list=([^&]+)', video.url_suffix)
                if match:
                    playlist_id = match.group(1)
                    # Skip Radio playlists (RD prefix) - these are auto-generated
                    if not playlist_id.startswith('RD'):
                        playlist_ids.add(playlist_id)
        return playlist_ids
    
    def _find_fuzzy_match(
        self,
        videos: List[YouTubeVideo],
        track,
        release_info: ReleaseInfo,
        min_score: float = 0.3
    ) -> Optional[Tuple[YouTubeVideo, float]]:
        """
        Find best fuzzy match from videos.
        
        Returns:
            Tuple of (video, score) or None if no match found
        """
        best_match = None
        best_score = 0.0
        
        for video in videos:
            # Skip if it's clearly a live version
            if self.video_validator.is_live_version(video.title):
                continue
            
            # Calculate fuzzy match score
            video_normalized = self.title_matcher._normalize_for_matching(video.title)
            track_normalized = self.title_matcher._normalize_for_matching(track.title)
            artist_normalized = self.title_matcher._normalize_for_matching(release_info.artist)
            
            score = 0.0
            
            # Check if track title words appear in video title
            track_words = [w for w in track_normalized.split() if len(w) > 2]
            if track_words:
                matching_words = sum(1 for word in track_words if word in video_normalized)
                score += 0.5 * (matching_words / len(track_words))
            
            # Check if artist appears
            if artist_normalized in video_normalized:
                score += 0.3
            else:
                artist_words = [w for w in artist_normalized.split() if len(w) > 2]
                if artist_words:
                    matching_words = sum(1 for word in artist_words if word in video_normalized)
                    score += 0.2 * (matching_words / len(artist_words))
            
            # Penalize reaction/review videos
            if self.video_validator.is_reaction_or_review_video(video.title):
                score *= 0.2
            
            if score > best_score and score >= min_score:
                # Validate the fuzzy match
                is_valid, _ = self.video_validator.validate_video_for_track(
                    video, track, True  # Silent validation for fuzzy matches
                )
                
                if is_valid:
                    best_score = score
                    best_match = video
        
        return (best_match, best_score) if best_match else None
    
    def search_and_match_video(
        self,
        track,
        release_info: ReleaseInfo,
        silent: bool = False
    ) -> Tuple[Optional[YouTubeVideo], Set[str]]:
        """
        Search for and match a video for a track with progressive retry logic.
        
        Args:
            track: Track to find video for
            release_info: Release information
            silent: Whether to suppress output
            
        Returns:
            Tuple of (matched YouTubeVideo or None, set of playlist IDs found)
        """
        console = self.display_manager.console
        
        # Build search query
        search_query = self.build_track_search_query(track, release_info)
        
        # Check if we need more results (when track title is similar to album name)
        is_playlist = (
            release_info.release_type == "Playlist" and 
            release_info.url and 
            "spotify.com" in release_info.url
        )
        titles_similar = False if is_playlist else self.title_matcher.are_titles_similar(
            track.title, release_info.title
        )
        
        # Progressive retry system: start with fewer results, expand if needed
        max_attempts = 3
        initial_results = 10 if titles_similar else 5
        results_increment = 10
        max_total_results = 50
        
        selected_video = None
        playlist_ids_found = set()
        all_videos_checked = []
        
        search_display = f"{track.artist} - {track.title}" if track.artist else track.title
        
        for attempt in range(max_attempts):
            current_max_results = min(initial_results + (attempt * results_increment), max_total_results)
            
            if attempt > 0:
                if not silent:
                    console.print(f"[blue]ℹ[/blue] Retry {attempt + 1}/{max_attempts}: Expanding search to {current_max_results} results...")
            
            try:
                # Search YouTube
                videos = self.display_manager.show_loading_spinner(
                    f"Searching YouTube for: {search_display}" if attempt == 0 else f"Searching (attempt {attempt + 1}): {search_display}",
                    self.search_service.search_youtube,
                    search_query,
                    current_max_results
                )
                
                if not videos:
                    if attempt == 0:
                        if not silent:
                            console.print(f"[bold red]✗[/bold red] No YouTube results found for: [white]{track.title}[/white]")
                        return None, playlist_ids_found
                    continue
                
                # Filter out videos we've already checked
                new_videos = [v for v in videos if v.video_id not in [v2.video_id for v2 in all_videos_checked]]
                
                if not new_videos:
                    if not silent:
                        console.print(f"[blue]ℹ[/blue] All {len(videos)} results already checked. Expanding search...")
                    continue
                
                all_videos_checked.extend(new_videos)
                
                # Extract playlist IDs
                playlist_ids_found.update(self._extract_playlist_ids(new_videos))
                
                # First pass: strict validation (exact matches, no live versions)
                for video in new_videos:
                    is_valid, reason = self.video_validator.validate_video_for_track(
                        video, track, silent
                    )
                    
                    if is_valid:
                        selected_video = video
                        break
                    elif not silent and attempt == 0:
                        console.print(f"[yellow]⚠[/yellow] Skipping invalid video: {reason}")
                
                # If found valid video, break retry loop
                if selected_video:
                    break
                
                # Second pass: fuzzy matching for close matches
                if not selected_video and attempt < max_attempts - 1:
                    if not silent:
                        console.print(f"[blue]ℹ[/blue] No exact match found. Trying fuzzy matching on {len(new_videos)} videos...")
                    
                    fuzzy_result = self._find_fuzzy_match(new_videos, track, release_info)
                    if fuzzy_result:
                        selected_video, best_fuzzy_score = fuzzy_result
                        if not silent:
                            console.print(f"[green]✓[/green] Found fuzzy match (score: {best_fuzzy_score:.2f}): {selected_video.title}")
                        break
            
            except Exception as e:
                if not silent:
                    console.print(f"[yellow]⚠[/yellow] Error during search attempt {attempt + 1}: {e}")
                if attempt == max_attempts - 1:
                    break
                continue
        
        return selected_video, playlist_ids_found

