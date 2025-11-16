"""
Video validation utilities for checking video suitability.
"""

import re
from typing import Optional, Tuple
from ..models.search_results import YouTubeVideo
from ..models.releases import ReleaseInfo, Track
from ..core.config import DURATION_VALIDATION_THRESHOLDS
from .validation_keywords import (
    REMASTER_KEYWORDS,
    LIVE_WORD_BOUNDARY_KEYWORDS,
    LIVE_SIMPLE_KEYWORDS,
    CONCERT_VENUES,
    EXPLICIT_LIVE_PATTERNS,
    REACTION_WORD_BOUNDARY_KEYWORDS,
    TOP_RANKING_PATTERNS,
    REACTION_MULTI_WORD_PHRASES,
    REACTION_SPECIFIC_KEYWORDS,
)


class VideoValidator:
    """Validates YouTube videos for download suitability."""
    
    def __init__(self, download_service):
        """
        Initialize video validator.
        
        Args:
            download_service: DownloadService instance for getting video info
        """
        self.download_service = download_service
    
    def _parse_duration_to_seconds(self, duration_str: Optional[str]) -> Optional[float]:
        """Parse duration string (MM:SS) to seconds."""
        if not duration_str:
            return None
        try:
            parts = duration_str.split(':')
            if len(parts) == 2:
                minutes, seconds = int(parts[0]), int(parts[1])
                return minutes * 60 + seconds
            elif len(parts) == 3:
                hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
                return hours * 3600 + minutes * 60 + seconds
        except (ValueError, AttributeError):
            pass
        return None
    
    def _get_video_duration_seconds(self, video_info: Optional[dict]) -> Optional[float]:
        """Extract video duration in seconds from video info."""
        if not video_info:
            return None
        
        # Try different duration fields
        for field in ['duration', 'lengthSeconds']:
            value = video_info.get(field)
            if value:
                try:
                    return float(value)
                except (ValueError, TypeError):
                    continue
        return None
    
    def _is_remastered_album(self, title_lower: str) -> bool:
        """Check if title indicates a remastered full album (not live)."""
        has_remaster = any(kw in title_lower for kw in REMASTER_KEYWORDS)
        has_full_album = 'full album' in title_lower or 'complete album' in title_lower
        return has_remaster and has_full_album
    
    def _check_patterns(self, title_lower: str, patterns: list) -> bool:
        """Check if any pattern matches the title."""
        return any(re.search(pattern, title_lower) for pattern in patterns)
    
    def _is_live_in_track_title(self, title_lower: str, track_title_lower: str) -> bool:
        """Check if 'live' is part of the track title (false positive prevention)."""
        if not track_title_lower or not re.search(r'\blive\b', track_title_lower):
            return False
        
        track_words = set(re.findall(r'\b\w+\b', track_title_lower))
        video_words = set(re.findall(r'\b\w+\b', title_lower))
        
        if not track_words:
            return False
        
        match_ratio = len(track_words.intersection(video_words)) / len(track_words)
        return match_ratio >= 0.6
    
    def _log_rejection(self, reason: str, video: YouTubeVideo, console, silent: bool):
        """Log rejection message."""
        if not silent and console:
            console.print(f"[yellow]⚠[/yellow] {reason}")
            console.print(f"  [dim]YouTube: {video.youtube_url}[/dim]")
    
    def is_live_version(self, video_title: str, track_title: Optional[str] = None) -> bool:
        """
        Check if video title indicates it's a live version.
        
        Args:
            video_title: The YouTube video title to check
            track_title: Optional track title to check if "live" is part of the song title
        """
        if not video_title:
            return False
        
        title_lower = video_title.lower()
        track_title_lower = track_title.lower() if track_title else ""
        
        # Exclude remastered full albums - these are studio albums, not live
        if self._is_remastered_album(title_lower):
            return False
        
        # Check word-boundary patterns (most specific)
        if self._check_patterns(title_lower, LIVE_WORD_BOUNDARY_KEYWORDS):
            if not self._is_remastered_album(title_lower):
                return True
        
        # Check venue patterns
        venue_pattern = r'\bat\s+[a-z\s]+(?:rocks|garden|hall|theater|theatre|bowl|arena|festival|acoustic)'
        if re.search(venue_pattern, title_lower) and not self._is_remastered_album(title_lower):
            return True
        
        # Check known concert venues
        if any(venue in title_lower for venue in CONCERT_VENUES):
            if not self._is_remastered_album(title_lower):
                return True
        
        # Check standalone "live" word
        if re.search(r'\blive\b', title_lower):
            # Explicit live indicators always flag as live
            if self._check_patterns(title_lower, EXPLICIT_LIVE_PATTERNS):
                return True
            
            # Check if "live" is part of track title (false positive prevention)
            if self._is_live_in_track_title(title_lower, track_title_lower):
                return False
            
            # If remastered album, skip; otherwise likely live
            if not self._is_remastered_album(title_lower):
                return True
        
        # Check simple keywords
        if any(kw in title_lower for kw in LIVE_SIMPLE_KEYWORDS):
            return True
        
        # Check year patterns (e.g., "at Red Rocks 2024")
        if re.search(r'\bat\s+[a-z\s]+\s+\d{4}\b', title_lower):
            if not self._is_remastered_album(title_lower):
                return True
        
        return False
    
    def is_reaction_or_review_video(self, video_title: str) -> bool:
        """Check if video title indicates it's a reaction, review, or similar non-album content."""
        if not video_title:
            return False
        
        title_lower = video_title.lower()
        
        # Check word-boundary patterns
        if self._check_patterns(title_lower, REACTION_WORD_BOUNDARY_KEYWORDS):
            return True
        
        # Special handling for "top" - only flag ranking contexts
        if re.search(r'\btop\b', title_lower) and self._check_patterns(title_lower, TOP_RANKING_PATTERNS):
            return True
        
        # Check multi-word phrases and specific keywords
        return (any(phrase in title_lower for phrase in REACTION_MULTI_WORD_PHRASES) or
                any(keyword in title_lower for keyword in REACTION_SPECIFIC_KEYWORDS))
    
    def validate_video_for_album(
        self,
        video: YouTubeVideo,
        release_info: ReleaseInfo,
        track_numbers: list,
        title_matcher,
        silent: bool = False,
        console=None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate if a video is suitable for the album (not live, duration matches, title matches).
        
        Args:
            video: YouTube video to validate
            release_info: Release information
            track_numbers: List of track numbers
            title_matcher: TitleMatcher instance for title matching
            silent: Whether to suppress output
            console: Optional console for output
            
        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        # Check 1: Title must match album and artist (with year if available)
        release_year = None
        if release_info.release_date and len(release_info.release_date) >= 4:
            release_year = release_info.release_date[:4]
        
        # Check title matches album
        if not title_matcher.title_matches_album(video.title, release_info.title, release_info.artist, release_year):
            reason = f"Video title doesn't match album '{release_info.title}' by '{release_info.artist}' (title: {video.title})"
            self._log_rejection(f"Skipping mismatched video: {video.title}", video, console, silent)
            return False, reason
        
        # Check for live versions
        if self.is_live_version(video.title):
            reason = f"Video appears to be a live version (title: {video.title})"
            self._log_rejection(f"Skipping live version: {video.title}", video, console, silent)
            return False, reason
        
        # Check for reaction/review videos
        if self.is_reaction_or_review_video(video.title):
            reason = f"Video appears to be a reaction/review/non-album content (title: {video.title})"
            self._log_rejection(f"Skipping non-album content: {video.title}", video, console, silent)
            return False, reason
        
        # Check 4: Duration validation
        # Get video info to check duration
        video_info = self.download_service.get_video_info(video.youtube_url)
        if not video_info:
            reason = f"Could not get video info for validation: {video.title}"
            if not silent and console:
                console.print(f"[yellow]⚠[/yellow] {reason}")
            return False, reason
        
        video_duration = self._get_video_duration_seconds(video_info)
        if video_duration:
            all_track_numbers = list(range(1, len(release_info.tracks) + 1))
            expected_duration = self._calculate_expected_album_duration(release_info.tracks, all_track_numbers)
            
            if expected_duration:
                if video_duration > expected_duration * 1.4:
                    reason = f"Video duration ({video_duration/60:.1f} min) is significantly longer than expected ({expected_duration/60:.1f} min) - likely live version"
                    if not silent and console:
                        console.print(f"[yellow]⚠[/yellow] {reason}")
                    return False, reason
                
                if video_duration < expected_duration * 0.7:
                    reason = f"Video duration ({video_duration/60:.1f} min) is significantly shorter than expected ({expected_duration/60:.1f} min) - might be incomplete"
                    if not silent and console:
                        console.print(f"[yellow]⚠[/yellow] {reason}")
                    return False, reason
        
        return True, None
    
    def validate_video_for_track(
        self,
        video: YouTubeVideo,
        track: Track,
        silent: bool = False,
        console=None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate if a video is suitable for a track (not live, duration matches).
        
        Priority: Duration matching is checked first as it's more objective and reliable.
        Title-based checks (live/review) are only used if duration doesn't match or isn't available.
        
        Args:
            video: YouTube video to validate
            track: Track information
            silent: Whether to suppress output
            console: Optional console for output
            
        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        # Duration validation (most reliable - check this first)
        video_info = self.download_service.get_video_info(video.youtube_url)
        duration_matches = False
        
        if video_info:
            video_duration = self._get_video_duration_seconds(video_info)
            if video_duration and track.duration:
                expected_duration = self._parse_duration_to_seconds(track.duration)
                
                if expected_duration:
                    duration_diff = video_duration - expected_duration
                    diff_ratio = abs(duration_diff) / expected_duration
                    
                    threshold_key = "LONGER_THRESHOLD" if duration_diff > 0 else "SHORTER_THRESHOLD"
                    threshold = DURATION_VALIDATION_THRESHOLDS[threshold_key]
                    
                    if diff_ratio > threshold:
                        from ..utils.file_duration_reader import format_duration
                        video_duration_str = format_duration(video_duration)
                        threshold_type = "longer" if duration_diff > 0 else "shorter"
                        reason = f"Video duration ({video_duration_str}) differs by {diff_ratio*100:.1f}% from expected ({track.duration}) - exceeds {threshold*100:.0f}% threshold for {threshold_type} videos"
                        if not silent and console:
                            from ..ui.styling import Styling
                            Styling(console).log_warning(f"Skipping video: {reason}")
                            console.print(f"  [dim]YouTube: {video.youtube_url}[/dim]")
                        return False, reason
                    
                    duration_matches = True
        
        # Title-based validation (only if duration doesn't match)
        if not duration_matches:
            if self.is_live_version(video.title, track.title if track else None):
                reason = f"Video appears to be a live version (title: {video.title})"
                self._log_rejection(f"Skipping live version: {video.title}", video, console, silent)
                return False, reason
            
            if self.is_reaction_or_review_video(video.title):
                reason = f"Video appears to be a reaction/review/non-album content (title: {video.title})"
                self._log_rejection(f"Skipping non-album content: {video.title}", video, console, silent)
                return False, reason
        elif not silent and console:
            # Duration matches - log note if title suggests live/review
            is_live = self.is_live_version(video.title, track.title if track else None)
            is_review = self.is_reaction_or_review_video(video.title)
            if is_live or is_review:
                content_type = "live/review content" if (is_live and is_review) else ("live version" if is_live else "review content")
                from ..ui.styling import Styling
                Styling(console).log_info(f"Duration matches well, accepting despite title suggesting {content_type}")
        
        if not video_info and not silent and console:
            console.print(f"[yellow]⚠[/yellow] Could not get video info for validation: {video.title}")
        
        return True, None
    
    def _calculate_expected_album_duration(self, tracks: list, track_numbers: list) -> Optional[float]:
        """Calculate expected total duration of selected tracks from MusicBrainz."""
        selected_tracks = sorted([t for t in tracks if t.position in track_numbers], key=lambda x: x.position)
        durations = [self._parse_duration_to_seconds(t.duration) for t in selected_tracks]
        durations = [d for d in durations if d is not None]
        return sum(durations) if durations else None

