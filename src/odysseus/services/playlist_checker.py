"""
Playlist checker module for finding tracks in YouTube playlists.
"""

from typing import List, Optional, Dict, Any
from ..models.releases import ReleaseInfo
from ..models.search_results import YouTubeVideo


class PlaylistChecker:
    """Handles checking YouTube playlists for tracks."""
    
    def __init__(
        self,
        download_service,
        search_service,
        video_validator,
        title_matcher,
        display_manager
    ):
        """
        Initialize playlist checker.
        
        Args:
            download_service: DownloadService instance
            search_service: SearchService instance
            video_validator: VideoValidator instance
            title_matcher: TitleMatcher instance
            display_manager: DisplayManager instance
        """
        self.download_service = download_service
        self.search_service = search_service
        self.video_validator = video_validator
        self.title_matcher = title_matcher
        self.display_manager = display_manager
    
    def _match_track_in_playlist(
        self,
        playlist_videos: List[Dict[str, Any]],
        track,
        release_info: ReleaseInfo,
        silent: bool,
        min_score: float = 0.25
    ) -> Optional[YouTubeVideo]:
        """
        Match a track in a playlist's videos.
        
        Args:
            playlist_videos: List of video info dicts from playlist
            track: Track to match
            release_info: Release information
            silent: Whether to suppress output
            min_score: Minimum matching score threshold
            
        Returns:
            Matched YouTubeVideo or None
        """
        best_match = None
        best_score = min_score
        
        for video_info in playlist_videos:
            score = self.title_matcher.match_playlist_video_to_track(
                video_info['title'],
                track.title,
                release_info.artist,
                self.video_validator
            )
            
            if score > best_score:
                # Validate the video
                video = YouTubeVideo(
                    title=video_info['title'],
                    video_id=video_info['id'],
                    url_suffix=f"watch?v={video_info['id']}"
                )
                
                is_valid, _ = self.video_validator.validate_video_for_track(
                    video, track, silent
                )
                
                if is_valid:
                    best_score = score
                    best_match = video
        
        return best_match
    
    def check_playlists_from_ids(
        self,
        playlist_ids: List[str],
        track,
        release_info: ReleaseInfo,
        silent: bool = False,
        max_playlists: int = 3
    ) -> Optional[YouTubeVideo]:
        """
        Check playlists from a list of playlist IDs.
        
        Args:
            playlist_ids: List of playlist IDs to check
            track: Track to find
            release_info: Release information
            silent: Whether to suppress output
            max_playlists: Maximum number of playlists to check
            
        Returns:
            Matched YouTubeVideo or None
        """
        console = self.display_manager.console
        
        if not playlist_ids:
            return None
        
        if not silent:
            console.print(f"[blue]ℹ[/blue] No direct match found. Checking {len(playlist_ids)} playlist(s) from search results...")
        
        for playlist_id in list(playlist_ids)[:max_playlists]:
            try:
                playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
                playlist_videos = self.download_service.get_playlist_info(playlist_url)
                
                if not playlist_videos:
                    continue
                
                best_match = self._match_track_in_playlist(
                    playlist_videos, track, release_info, silent
                )
                
                if best_match:
                    if not silent:
                        console.print(f"[green]✓[/green] Found track in playlist: {track.title}")
                    return best_match
            
            except Exception as e:
                if not silent:
                    console.print(f"[yellow]⚠[/yellow] Error checking playlist: {e}")
                continue
        
        return None
    
    def search_and_check_playlists(
        self,
        track,
        release_info: ReleaseInfo,
        silent: bool = False,
        max_results: int = 5
    ) -> Optional[YouTubeVideo]:
        """
        Search for playlists containing the track and check them.
        
        Args:
            track: Track to find
            release_info: Release information
            silent: Whether to suppress output
            max_results: Maximum number of playlists to search for
            
        Returns:
            Matched YouTubeVideo or None
        """
        console = self.display_manager.console
        
        if not silent:
            console.print(f"[blue]ℹ[/blue] Searching for playlists containing: {track.title}...")
        
        try:
            # Search for playlists that might contain this track
            track_playlists = self.search_service.search_playlist(
                release_info.artist,
                release_info.title,
                max_results=max_results,
                track_titles=[track.title]
            )
            
            if not track_playlists:
                if not silent:
                    console.print(f"[yellow]⚠[/yellow] No playlists found containing: {track.title}")
                return None
            
            if not silent:
                console.print(f"[blue]ℹ[/blue] Found {len(track_playlists)} playlist(s). Checking for track...")
            
            for idx, playlist_info in enumerate(track_playlists, 1):
                try:
                    playlist_url = playlist_info['url']
                    playlist_title = playlist_info.get('title', 'Unknown')
                    
                    if not silent:
                        console.print(f"[blue]ℹ[/blue] Checking playlist {idx}/{len(track_playlists)}: {playlist_title[:60]}...")
                    
                    playlist_videos = self.download_service.get_playlist_info(playlist_url)
                    
                    if not playlist_videos:
                        if not silent:
                            console.print(f"[yellow]⚠[/yellow] Could not fetch videos from playlist")
                        continue
                    
                    if not silent:
                        console.print(f"[blue]ℹ[/blue] Checking {len(playlist_videos)} videos in playlist...")
                    
                    best_match = self._match_track_in_playlist(
                        playlist_videos, track, release_info, silent
                    )
                    
                    if best_match:
                        if not silent:
                            console.print(f"[green]✓[/green] Found track in playlist: {track.title}")
                        return best_match
                    elif not silent:
                        console.print(f"[yellow]⚠[/yellow] Track not found in this playlist")
                
                except Exception as e:
                    if not silent:
                        console.print(f"[yellow]⚠[/yellow] Error checking playlist: {e}")
                    continue
        
        except Exception as e:
            if not silent:
                console.print(f"[yellow]⚠[/yellow] Error searching for playlists: {e}")
        
        return None

