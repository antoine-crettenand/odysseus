"""
Video validation utilities for checking video suitability.
"""

import re
from typing import Optional, Tuple
from ..models.search_results import YouTubeVideo
from ..models.releases import ReleaseInfo, Track


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
        duration = video_info.get('duration')
        if duration:
            if isinstance(duration, (int, float)):
                return float(duration)
            elif isinstance(duration, str):
                # Try parsing as seconds
                try:
                    return float(duration)
                except ValueError:
                    pass
        
        # Try lengthSeconds field
        length_seconds = video_info.get('lengthSeconds')
        if length_seconds:
            try:
                return float(length_seconds)
            except (ValueError, TypeError):
                pass
        
        return None
    
    def is_live_version(self, video_title: str) -> bool:
        """Check if video title indicates it's a live version."""
        if not video_title:
            return False
        
        title_lower = video_title.lower()
        
        # Exclude remastered/reissue versions - these are studio albums, not live
        # Check for remaster keywords first - if present, it's likely a studio remaster, not live
        remaster_keywords = ['remaster', 'remastered', 'reissue', 're-release', 'deluxe edition', 'anniversary edition']
        has_remaster_keyword = any(keyword in title_lower for keyword in remaster_keywords)
        
        # If it has remaster keywords and "full album" or similar, it's definitely not live
        if has_remaster_keyword and ('full album' in title_lower or 'complete album' in title_lower):
            return False
        
        # Keywords that need word boundary matching (to avoid false positives)
        # Use word boundaries to avoid matching "live" in words like "lives", "alive", "deliver", etc.
        word_boundary_keywords = [
            r'\blive\s+concert\b',  # "live concert"
            r'\blive\s+performance\b',  # "live performance"
            r'\blive\s+on\s+stage\b',  # "live on stage"
            r'\brecorded\s+live\b',  # "recorded live"
            r'\blive\s+session\b',  # "live session"
            r'\blive\s+recording\b',  # "live recording"
            r'\blive\s+from\b',  # "live from"
            r'\blive\s+@\b',  # "live @"
            r'\blive\s+in\b',  # "live in" (but not "live in" as part of song title)
            r'\blive\s+at\b',  # "live at" (e.g., "Live at Red Rocks")
            r'\blive\s+version\b',  # "live version"
            r'\blive\s+take\b',  # "live take"
            r'\blive\s+acoustic\b',  # "live acoustic"
            r'\blive\s+bootleg\b',  # "live bootleg"
            r'\blive\s+broadcast\b',  # "live broadcast"
        ]
        
        # Keywords that don't need word boundaries (they're specific enough)
        simple_keywords = [
            'unplugged',
            'mtv unplugged',
            'kexp',
            'npr tiny desk',
            'audience',
            'applause',
            'encore'
        ]
        
        # Check for word-boundary keywords first (more specific, avoids false positives)
        for pattern in word_boundary_keywords:
            if re.search(pattern, title_lower):
                # Additional check: if it's a remaster with "live" in context, be more careful
                if has_remaster_keyword:
                    # "live" in remaster context might be false positive - check if it's actually about live performance
                    # If it says "remaster" and "full album", it's not live
                    if 'full album' in title_lower or 'complete album' in title_lower:
                        continue  # Skip this match, it's a remastered studio album
                return True
        
        # Check for simple keywords (substring match is fine for these)
        for keyword in simple_keywords:
            if keyword in title_lower:
                return True
        
        return False
    
    def is_reaction_or_review_video(self, video_title: str) -> bool:
        """Check if video title indicates it's a reaction, review, or similar non-album content."""
        if not video_title:
            return False
        
        title_lower = video_title.lower()
        non_album_keywords = [
            'reaction',
            'react',
            'reacting',
            'reacts',
            'first reaction',
            'first time listening',
            'first listen',
            'review',
            'album review',
            'music review',
            'unboxing',
            'unbox',
            'reaction to',
            'reacting to',
            'reacts to',
            'my reaction',
            'honest reaction',
            'genuine reaction',
            'blind reaction',
            'album reaction',
            'song reaction',
            'listening to',
            'listening session',
            'first time hearing',
            'first time hearing',
            'rate',
            'rating',
            'ranking',
            'rank',
            'top',
            'worst',
            'best',
            'vs',
            'versus',
            'comparison',
            'breakdown',
            'analysis',
            'explained',
            'meaning',
            'lyrics explained',
            'album explained',
            'discussion',
            'podcast',
            'interview',
            'behind the scenes',
            'making of',
            'studio tour',
            'documentary',
            'trailer',
            'teaser',
            'preview',
            'snippet',
            'clip',
            'excerpt',
            'highlights',
            'best moments',
            'compilation',
            'mashup',
            'remix',
            'cover',
            'covers',
            'tribute',
            'parody',
            'meme',
            'funny',
            'comedy',
            'prank',
            'challenge',
            'tier list',
            'ranking',
            'top 10',
            'top 5',
            'worst to best',
            'best to worst'
        ]
        
        # Check for non-album keywords
        for keyword in non_album_keywords:
            if keyword in title_lower:
                return True
        
        return False
    
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
        
        if not title_matcher.title_matches_album(video.title, release_info.title, release_info.artist, release_year):
            reason = f"Video title doesn't match album '{release_info.title}' by '{release_info.artist}' (title: {video.title})"
            if not silent and console:
                console.print(f"[yellow]⚠[/yellow] Skipping mismatched video: {video.title}")
            return False, reason
        
        # Check 2: Title validation - filter out live versions
        if self.is_live_version(video.title):
            reason = f"Video appears to be a live version (title: {video.title})"
            if not silent and console:
                console.print(f"[yellow]⚠[/yellow] Skipping live version: {video.title}")
            return False, reason
        
        # Check 3: Filter out reaction videos, reviews, and other non-album content
        if self.is_reaction_or_review_video(video.title):
            reason = f"Video appears to be a reaction/review/non-album content (title: {video.title})"
            if not silent and console:
                console.print(f"[yellow]⚠[/yellow] Skipping non-album content: {video.title}")
            return False, reason
        
        # Check 4: Duration validation
        # Get video info to check duration
        video_info = self.download_service.get_video_info(video.youtube_url)
        if not video_info:
            # If we can't get video info, reject it for full album downloads (too risky)
            reason = f"Could not get video info for validation: {video.title}"
            if not silent and console:
                console.print(f"[yellow]⚠[/yellow] {reason}")
            return False, reason
        
        video_duration = self._get_video_duration_seconds(video_info)
        if video_duration:
            # Calculate expected album duration
            # For full album videos, validate against ALL tracks (not just selected ones)
            # since we're downloading the entire video
            all_track_numbers = list(range(1, len(release_info.tracks) + 1))
            expected_duration = self._calculate_expected_album_duration(
                release_info.tracks, all_track_numbers
            )
            
            if expected_duration:
                # If video is significantly longer, it might be a live version
                # Live versions are often 1.5x to 2x longer due to extended solos, audience interaction, etc.
                if video_duration > expected_duration * 1.4:
                    reason = f"Video duration ({video_duration/60:.1f} min) is significantly longer than expected ({expected_duration/60:.1f} min) - likely live version"
                    if not silent and console:
                        console.print(f"[yellow]⚠[/yellow] {reason}")
                    return False, reason
                
                # If video is significantly shorter, it might be incomplete
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
        
        Args:
            video: YouTube video to validate
            track: Track information
            silent: Whether to suppress output
            console: Optional console for output
            
        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        # Check 1: Title validation - filter out live versions
        if self.is_live_version(video.title):
            reason = f"Video appears to be a live version (title: {video.title})"
            if not silent and console:
                console.print(f"[yellow]⚠[/yellow] Skipping live version: {video.title}")
            return False, reason
        
        # Check 2: Filter out reaction videos, reviews, and other non-album content
        if self.is_reaction_or_review_video(video.title):
            reason = f"Video appears to be a reaction/review/non-album content (title: {video.title})"
            if not silent and console:
                console.print(f"[yellow]⚠[/yellow] Skipping non-album content: {video.title}")
            return False, reason
        
        # Check 3: Duration validation
        # Get video info to check duration
        video_info = self.download_service.get_video_info(video.youtube_url)
        if not video_info:
            # If we can't get video info, we'll still try it but warn
            if not silent and console:
                console.print(f"[yellow]⚠[/yellow] Could not get video info for validation: {video.title}")
            return True, None  # Allow it, but with warning
        
        video_duration = self._get_video_duration_seconds(video_info)
        if video_duration and track.duration:
            # Calculate expected track duration
            expected_duration = self._parse_duration_to_seconds(track.duration)
            
            if expected_duration:
                # If video is significantly longer, it might be a live version
                # Live versions are often 1.5x to 2x longer due to extended solos, audience interaction, etc.
                if video_duration > expected_duration * 1.4:
                    reason = f"Video duration ({video_duration/60:.1f} min) is significantly longer than expected ({expected_duration/60:.1f} min) - likely live version"
                    if not silent and console:
                        console.print(f"[yellow]⚠[/yellow] {reason}")
                    return False, reason
                
                # If video is significantly shorter, it might be incomplete or wrong track
                if video_duration < expected_duration * 0.7:
                    reason = f"Video duration ({video_duration/60:.1f} min) is significantly shorter than expected ({expected_duration/60:.1f} min) - might be incomplete or wrong track"
                    if not silent and console:
                        console.print(f"[yellow]⚠[/yellow] {reason}")
                    return False, reason
        
        return True, None
    
    def _calculate_expected_album_duration(self, tracks: list, track_numbers: list) -> Optional[float]:
        """Calculate expected total duration of selected tracks from MusicBrainz."""
        total_seconds = 0.0
        has_durations = False
        
        selected_tracks = [t for t in tracks if t.position in track_numbers]
        selected_tracks.sort(key=lambda x: x.position)
        
        for track in selected_tracks:
            duration_seconds = self._parse_duration_to_seconds(track.duration)
            if duration_seconds:
                total_seconds += duration_seconds
                has_durations = True
        
        return total_seconds if has_durations else None

