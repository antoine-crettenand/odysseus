"""
Download orchestrator service for coordinating downloads.
"""

import re
import subprocess
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from ..models.song import SongData, AudioMetadata
from ..models.search_results import MusicBrainzSong, YouTubeVideo
from ..models.releases import ReleaseInfo, Track
from ..services.download_service import DownloadService
from ..services.metadata_service import MetadataService
from ..services.search_service import SearchService
from ..ui.display import DisplayManager


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
    
    def _is_compilation(self, release_info: ReleaseInfo) -> bool:
        """
        Check if a release is a compilation (has multiple different artists).
        
        A compilation has different artists on different tracks.
        A collaboration album has the same collaborating artists on all tracks.
        
        Returns True if there are at least 2 tracks with different artists.
        """
        if not release_info.tracks or len(release_info.tracks) < 2:
            return False
        
        # Normalize artist names for comparison (case-insensitive, strip whitespace)
        from ..utils.string_utils import normalize_string
        artists = set()
        for track in release_info.tracks:
            artist = normalize_string(track.artist) if track.artist else ""
            if artist:  # Only count non-empty artists
                artists.add(artist)
        
        # If all tracks have the same artist (even if it's "Artist A & Artist B"),
        # it's a collaboration album, not a compilation
        if len(artists) == 1:
            return False
        
        # If we have 2 or more different artists across tracks, it's a compilation
        # This means different tracks have different artists (not just different artist names)
        return len(artists) >= 2
    
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
        if self._is_live_version(video_title):
            console.print(f"[yellow]⚠[/yellow] Warning: This video appears to be a live version: {video_title}")
            console.print("[yellow]⚠[/yellow] If you want a studio version, consider selecting a different video.")
            console.print()
        
        # Warn if this appears to be a reaction/review video
        if self._is_reaction_or_review_video(video_title):
            console.print(f"[yellow]⚠[/yellow] Warning: This video appears to be a reaction/review/non-album content: {video_title}")
            console.print("[yellow]⚠[/yellow] This is not the actual album content. Consider selecting a different video.")
            console.print()
        
        # Validate duration if we have track duration info
        if hasattr(metadata, 'duration') and metadata.duration:
            video_info = self.download_service.get_video_info(youtube_url)
            if video_info:
                video_duration = self._get_video_duration_seconds(video_info)
                expected_duration = self._parse_duration_to_seconds(metadata.duration)
                
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
        with progress:
            if quality == 'audio':
                downloaded_path = self.download_service.download_high_quality_audio(
                    youtube_url,
                    metadata=metadata_dict,
                    quiet=True,
                    progress_callback=update_progress
                )
            else:
                downloaded_path = self.download_service.download_video(
                    youtube_url,
                    quality=quality,
                    audio_only=(quality == 'audio'),
                    metadata=metadata_dict,
                    quiet=True,
                    progress_callback=update_progress
                )
            
            # Mark as complete
            progress.update(task_id, completed=100, description=f"Completed: {video_title[:40]}")
        
        if downloaded_path:
            # Apply metadata with cover art
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
            console.print("[bold red]✗[/bold red] Download failed")
            return None
    
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
    
    def _is_live_version(self, video_title: str) -> bool:
        """Check if video title indicates it's a live version."""
        if not video_title:
            return False
        
        title_lower = video_title.lower()
        live_keywords = [
            'live',
            'concert',
            'performance',
            'on stage',
            'recorded live',
            'live session',
            'live recording',
            'live from',
            'live @',
            'live in',
            'live at',
            'live version',
            'live take',
            'live studio',
            'live acoustic',
            'unplugged',
            'mtv unplugged',
            'kexp',
            'npr tiny desk',
            'audience',
            'applause',
            'encore'
        ]
        
        # Keywords that need word boundary matching (to avoid false positives)
        word_boundary_keywords = [
            r'\bat\b',  # "at" as a standalone word (e.g., "Live at Red Rocks")
        ]
        
        # Check for live keywords (simple substring match)
        for keyword in live_keywords:
            if keyword in title_lower:
                return True
        
        # Check for word-boundary keywords (to avoid matching "at" in "heat", "cat", etc.)
        for pattern in word_boundary_keywords:
            if re.search(pattern, title_lower):
                return True
        
        return False
    
    def _is_reaction_or_review_video(self, video_title: str) -> bool:
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
    
    def _calculate_expected_album_duration(self, tracks: List[Track], track_numbers: List[int]) -> Optional[float]:
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
    
    def _get_video_duration_seconds(self, video_info: Optional[Dict[str, Any]]) -> Optional[float]:
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
    
    def _normalize_for_matching(self, text: str) -> str:
        """Normalize text for matching (lowercase, remove special chars, etc.)."""
        if not text:
            return ""
        # Convert to lowercase and remove common special characters
        normalized = text.lower()
        # Remove common punctuation and special characters
        normalized = normalized.replace("'", "").replace("'", "").replace('"', '').replace('"', '')
        normalized = normalized.replace("&", "and").replace("+", "and")
        # Remove extra spaces
        normalized = ' '.join(normalized.split())
        return normalized
    
    def _extract_version_suffix(self, album_title: str) -> Optional[str]:
        """
        Extract version suffix from album title (e.g., "ii", "2", "part 2", "vol. 2").
        
        Returns:
            Version suffix if found, None otherwise
        """
        if not album_title:
            return None
        
        album_lower = album_title.lower().strip()
        
        # Remove year in parentheses at the end (e.g., "album ii (2025)" -> "album ii")
        # This helps match version suffixes even when year is present
        album_lower = re.sub(r'\s*\(\d{4}\)\s*$', '', album_lower).strip()
        
        # Common version patterns at the end of album titles
        # Order matters - check longer patterns first
        version_patterns = [
            r'\bpart\s+ii\b$',    # "part ii" at the end
            r'\bpart\s+2\b$',     # "part 2" at the end
            r'\bvol\.?\s*2\b$',   # "vol. 2" or "vol 2" at the end
            r'\bvolume\s+2\b$',   # "volume 2" at the end
            r'\bversion\s+2\b$',  # "version 2" at the end
            r'\biii\b$',          # "iii" as a word at the end
            r'\biv\b$',           # "iv" as a word at the end
            r'\bii\b$',           # "ii" as a word at the end
            r'\b3\b$',            # "3" as a word at the end
            r'\b2\b$',            # "2" as a word at the end
        ]
        
        for pattern in version_patterns:
            match = re.search(pattern, album_lower)
            if match:
                # Return the matched suffix (normalized)
                suffix = match.group(0).strip()
                return suffix
        
        return None
    
    def _has_version_suffix_in_title(self, title: str, version_suffix: str) -> bool:
        """
        Check if a title contains the version suffix.
        
        Args:
            title: Title to check
            version_suffix: Version suffix to look for (e.g., "ii", "2", "part 2")
        """
        if not title or not version_suffix:
            return False
        
        title_lower = title.lower()
        suffix_lower = version_suffix.lower()
        
        # Direct match
        if suffix_lower in title_lower:
            return True
        
        # For numeric suffixes, also check for roman numerals
        if suffix_lower == "2":
            # Check for "ii" as well
            if " ii " in title_lower or title_lower.endswith(" ii"):
                return True
        elif suffix_lower == "ii":
            # Check for "2" as well
            if re.search(r'\b2\b', title_lower):
                return True
        
        return False
    
    def _artist_matches(self, video_title: str, artist: str) -> bool:
        """Check if video title contains artist name (with flexible matching)."""
        if not video_title or not artist:
            return False
        
        video_normalized = self._normalize_for_matching(video_title)
        artist_normalized = self._normalize_for_matching(artist)
        
        # Direct match
        if artist_normalized in video_normalized:
            return True
        
        # Flexible matching: remove common prefixes like "the", "a", "an"
        artist_words = artist_normalized.split()
        if len(artist_words) > 1 and artist_words[0] in ['the', 'a', 'an']:
            # Try without the prefix
            artist_without_prefix = ' '.join(artist_words[1:])
            if artist_without_prefix in video_normalized:
                return True
        
        # Check if significant words from artist name are in video title
        # For example: "The Jimi Hendrix Experience" should match "Jimi Hendrix"
        significant_words = [w for w in artist_words if len(w) > 2 and w not in ['the', 'a', 'an']]
        if len(significant_words) >= 2:
            # If at least 2 significant words match, consider it a match
            matching_words = sum(1 for word in significant_words if word in video_normalized)
            if matching_words >= min(2, len(significant_words)):
                return True
        
        return False
    
    def _title_matches_album(self, video_title: str, album_title: str, artist: str, release_year: Optional[str] = None) -> bool:
        """
        Check if video title contains album title and artist (with strict matching).
        
        Args:
            video_title: YouTube video title
            album_title: Album title to match
            artist: Artist name
            release_year: Optional release year for additional validation
            
        Returns:
            True if video title matches the album
        """
        if not video_title or not album_title or not artist:
            return False
        
        video_normalized = self._normalize_for_matching(video_title)
        album_normalized = self._normalize_for_matching(album_title)
        
        # Check if artist matches (with flexible matching)
        artist_matches = self._artist_matches(video_title, artist)
        if not artist_matches:
            return False
        
        # Extract version suffix from album title (e.g., "ii", "2", "part 2")
        version_suffix = self._extract_version_suffix(album_title)
        
        # If album has a version suffix, require it to be present in video title
        # This prevents matching "The Universe Smiles Upon You" when looking for "The Universe Smiles Upon You ii"
        if version_suffix:
            if not self._has_version_suffix_in_title(video_title, version_suffix):
                return False  # Version suffix is required - reject if not found
        
        # First, try exact phrase match (most reliable)
        # Check if the full normalized album title appears as a phrase in the video title
        if album_normalized in video_normalized:
            # If year is provided, require it to match (strict check for versioned albums)
            if release_year:
                year_in_title = release_year in video_title
                if version_suffix:
                    # For versioned albums, year match is required to distinguish versions
                    if not year_in_title:
                        return False
                # For non-versioned albums, year is preferred but not strictly required
                # (some videos don't include year in title)
            return True
        
        # If exact phrase not found, check word-by-word with stricter requirements
        album_words = [w for w in album_normalized.split() if len(w) > 1]  # Include 2+ char words
        if not album_words:
            # If album title is very short, require exact match
            return album_normalized in video_normalized
        
        # For word-by-word matching, require at least 90% of words (stricter than before)
        # This helps avoid matching similar album names
        matching_words = sum(1 for word in album_words if word in video_normalized)
        word_match_ratio = matching_words / len(album_words) if album_words else 0
        
        # Require at least 90% word match (was 70%)
        if word_match_ratio < 0.9:
            return False
        
        # Additional check: ensure all "important" words (3+ chars) are present
        important_words = [w for w in album_words if len(w) >= 3]
        if important_words:
            important_matches = sum(1 for word in important_words if word in video_normalized)
            if important_matches < len(important_words):
                return False  # Missing important words
        
        # If year is provided, make it required for versioned albums
        if release_year:
            year_in_title = release_year in video_title
            if version_suffix:
                # For versioned albums, year match is required
                if not year_in_title:
                    return False
            # For non-versioned albums, year is preferred but not strictly required
            # (some videos don't include year in title)
        
        return True
    
    def _validate_video_for_album(
        self,
        video: YouTubeVideo,
        release_info: ReleaseInfo,
        track_numbers: List[int],
        silent: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate if a video is suitable for the album (not live, duration matches, title matches).
        
        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        console = self.display_manager.console
        
        # Check 1: Title must match album and artist (with year if available)
        release_year = None
        if release_info.release_date and len(release_info.release_date) >= 4:
            release_year = release_info.release_date[:4]
        
        if not self._title_matches_album(video.title, release_info.title, release_info.artist, release_year):
            reason = f"Video title doesn't match album '{release_info.title}' by '{release_info.artist}' (title: {video.title})"
            if not silent:
                console.print(f"[yellow]⚠[/yellow] Skipping mismatched video: {video.title}")
            return False, reason
        
        # Check 2: Title validation - filter out live versions
        if self._is_live_version(video.title):
            reason = f"Video appears to be a live version (title: {video.title})"
            if not silent:
                console.print(f"[yellow]⚠[/yellow] Skipping live version: {video.title}")
            return False, reason
        
        # Check 3: Filter out reaction videos, reviews, and other non-album content
        if self._is_reaction_or_review_video(video.title):
            reason = f"Video appears to be a reaction/review/non-album content (title: {video.title})"
            if not silent:
                console.print(f"[yellow]⚠[/yellow] Skipping non-album content: {video.title}")
            return False, reason
        
        # Check 4: Duration validation
        # Get video info to check duration
        video_info = self.download_service.get_video_info(video.youtube_url)
        if not video_info:
            # If we can't get video info, reject it for full album downloads (too risky)
            reason = f"Could not get video info for validation: {video.title}"
            if not silent:
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
                    if not silent:
                        console.print(f"[yellow]⚠[/yellow] {reason}")
                    return False, reason
                
                # If video is significantly shorter, it might be incomplete
                if video_duration < expected_duration * 0.7:
                    reason = f"Video duration ({video_duration/60:.1f} min) is significantly shorter than expected ({expected_duration/60:.1f} min) - might be incomplete"
                    if not silent:
                        console.print(f"[yellow]⚠[/yellow] {reason}")
                    return False, reason
        
        return True, None
    
    def _validate_video_for_track(
        self,
        video: YouTubeVideo,
        track: Track,
        silent: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate if a video is suitable for a track (not live, duration matches).
        
        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        console = self.display_manager.console
        
        # Check 1: Title validation - filter out live versions
        if self._is_live_version(video.title):
            reason = f"Video appears to be a live version (title: {video.title})"
            if not silent:
                console.print(f"[yellow]⚠[/yellow] Skipping live version: {video.title}")
            return False, reason
        
        # Check 2: Filter out reaction videos, reviews, and other non-album content
        if self._is_reaction_or_review_video(video.title):
            reason = f"Video appears to be a reaction/review/non-album content (title: {video.title})"
            if not silent:
                console.print(f"[yellow]⚠[/yellow] Skipping non-album content: {video.title}")
            return False, reason
        
        # Check 3: Duration validation
        # Get video info to check duration
        video_info = self.download_service.get_video_info(video.youtube_url)
        if not video_info:
            # If we can't get video info, we'll still try it but warn
            if not silent:
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
                    if not silent:
                        console.print(f"[yellow]⚠[/yellow] {reason}")
                    return False, reason
                
                # If video is significantly shorter, it might be incomplete or wrong track
                if video_duration < expected_duration * 0.7:
                    reason = f"Video duration ({video_duration/60:.1f} min) is significantly shorter than expected ({expected_duration/60:.1f} min) - might be incomplete or wrong track"
                    if not silent:
                        console.print(f"[yellow]⚠[/yellow] {reason}")
                    return False, reason
        
        return True, None
    
    def _calculate_track_timestamps_from_durations(
        self,
        tracks: List[Track],
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
            duration_seconds = self._parse_duration_to_seconds(track.duration)
            
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
    
    def _download_full_album_and_split(
        self,
        release_info: ReleaseInfo,
        track_numbers: List[int],
        quality: str,
        silent: bool = False
    ) -> Tuple[int, int]:
        """
        Strategy 1: Download full album video and split into tracks.
        
        Optimized to fetch cover art once per release and reuse it for all tracks.
        """
        console = self.display_manager.console
        
        if not silent:
            console.print("[cyan]🎵 Strategy 1: Searching for full album video...[/cyan]")
        
        # Fetch cover art once for the entire release (optimization)
        cover_art_data = None
        if not silent:
            cover_art_data = self.metadata_service.fetch_cover_art_for_release(release_info, console)
        else:
            # Still fetch cover art in silent mode, just don't print messages
            cover_art_data = self.metadata_service.fetch_cover_art_for_release(release_info, None)
        
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
                is_valid, reason = self._validate_video_for_album(
                    video, release_info, track_numbers, silent
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
                # Use "Various Artists" for folder structure if this is a compilation
                is_compilation = self._is_compilation(release_info)
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
                    f"Downloading: {video.title[:40]}"
                )
                
                def update_progress(progress_info: Dict[str, Any]):
                    """Update progress bar with download info."""
                    # Use percentage for progress (0-100)
                    percent = progress_info.get('percent', 0)
                    file_progress.update(file_task_id, completed=percent)
                
                with file_progress:
                    full_video_path = self.download_service.download_high_quality_audio(
                        youtube_url,
                        metadata=album_metadata,
                        quiet=True,
                        progress_callback=update_progress
                    )
                    # Mark as complete
                    file_progress.update(file_task_id, completed=100)
                
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
                    # Apply metadata to all split files (reuse pre-fetched cover art)
                    downloaded_count = 0
                    for split_file, timestamp_info in zip(split_files, track_timestamps):
                        track = timestamp_info['track']
                        try:
                            self.metadata_service.apply_metadata_with_cover_art(
                                split_file, track, release_info, console, cover_art_data=cover_art_data
                            )
                            downloaded_count += 1
                        except Exception as e:
                            downloaded_count += 1  # Count as downloaded even if metadata fails
                            if not silent and console:
                                console.print(f"[yellow]⚠[/yellow] Could not apply metadata to {track.title}: {e}")
                    
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
    
    def _are_titles_similar(self, track_title: str, album_title: str) -> bool:
        """Check if track title is similar to album title."""
        from ..utils.string_utils import normalize_string
        
        track_title_norm = normalize_string(track_title)
        album_title_norm = normalize_string(album_title)
        
        return (
            track_title_norm == album_title_norm or
            track_title_norm in album_title_norm or
            album_title_norm in track_title_norm or
            # Check if they share significant words (at least 2 words in common)
            len(set(track_title_norm.split()) & set(album_title_norm.split())) >= 2
        )
    
    def _build_track_search_query(self, track: Track, release_info: ReleaseInfo) -> str:
        """
        Build an optimized YouTube search query for a track.
        
        When track title matches or is similar to album name, adds disambiguating terms
        to improve search results and avoid interviews, live versions, etc.
        """
        # Check if track title is similar to album title
        titles_similar = self._are_titles_similar(track.title, release_info.title)
        
        # Build base query
        query_parts = [track.artist, track.title]
        
        # If titles are similar, add disambiguating terms
        if titles_similar:
            # Add "album" to help find the album version
            query_parts.append("album")
            
            # Add year if available to make it more specific
            if release_info.release_date:
                year = release_info.release_date[:4] if len(release_info.release_date) >= 4 else None
                if year and year.isdigit():
                    query_parts.append(year)
        
        # Join query parts
        search_query = " ".join(query_parts)
        
        return search_query
    
    def _match_playlist_video_to_track(
        self,
        video_title: str,
        track: Track,
        release_info: ReleaseInfo
    ) -> float:
        """
        Calculate a match score between a playlist video and a track.
        Returns a score between 0.0 and 1.0, where 1.0 is a perfect match.
        """
        if not video_title or not track.title:
            return 0.0
        
        # Normalize strings for comparison
        video_normalized = self._normalize_for_matching(video_title)
        track_normalized = self._normalize_for_matching(track.title)
        artist_normalized = self._normalize_for_matching(release_info.artist)
        
        score = 0.0
        
        # Check if track title is in video title (most important)
        if track_normalized in video_normalized:
            score += 0.6
        else:
            # Check for partial matches (words from track title)
            track_words = [w for w in track_normalized.split() if len(w) > 2]
            if track_words:
                matching_words = sum(1 for word in track_words if word in video_normalized)
                score += 0.4 * (matching_words / len(track_words))
        
        # Check if artist is in video title
        if artist_normalized in video_normalized:
            score += 0.3
        else:
            # Check for partial artist match
            artist_words = [w for w in artist_normalized.split() if len(w) > 2]
            if artist_words:
                matching_words = sum(1 for word in artist_words if word in video_normalized)
                score += 0.2 * (matching_words / len(artist_words))
        
        # Penalize if video appears to be live or non-album content
        if self._is_live_version(video_title) or self._is_reaction_or_review_video(video_title):
            score *= 0.3  # Heavy penalty
        
        return min(score, 1.0)
    
    def _download_from_playlist(
        self,
        release_info: ReleaseInfo,
        track_numbers: List[int],
        quality: str,
        silent: bool = False
    ) -> Tuple[int, int]:
        """
        Strategy 2: Download from YouTube playlist.
        
        Optimized to fetch cover art once per release and reuse it for all tracks.
        """
        console = self.display_manager.console
        
        if not silent:
            console.print("[cyan]🎵 Strategy 2: Searching for playlist...[/cyan]")
        
        # Fetch cover art once for the entire release (optimization)
        cover_art_data = None
        if not silent:
            cover_art_data = self.metadata_service.fetch_cover_art_for_release(release_info, console)
        else:
            # Still fetch cover art in silent mode, just don't print messages
            cover_art_data = self.metadata_service.fetch_cover_art_for_release(release_info, None)
        
        # Search for playlists
        playlists = self.display_manager.show_loading_spinner(
            f"Searching for playlist: {release_info.title}",
            self.search_service.search_playlist,
            release_info.artist,
            release_info.title,
            3
        )
        
        if not playlists:
            if not silent:
                console.print("[yellow]⚠[/yellow] No playlist found. Trying next strategy...")
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
                
                # First pass: try to find exact/very good matches
                for track in selected_tracks:
                    best_match = None
                    best_score = 0.5  # Minimum threshold
                    
                    for video in playlist_videos:
                        if video['id'] in used_videos:
                            continue
                        
                        score = self._match_playlist_video_to_track(
                            video['title'],
                            track,
                            release_info
                        )
                        
                        if score > best_score:
                            best_score = score
                            best_match = video
                    
                    if best_match:
                        track_to_video[track] = best_match
                        used_videos.add(best_match['id'])
                
                # Check how many tracks we matched
                matched_count = len(track_to_video)
                if matched_count < len(selected_tracks) * 0.5:  # Less than 50% matched
                    if not silent:
                        console.print(f"[yellow]⚠[/yellow] Only matched {matched_count}/{len(selected_tracks)} tracks. Trying next playlist...")
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
                            from ..models.search_results import YouTubeVideo
                            video = YouTubeVideo(
                                title=video_info['title'],
                                video_id=video_info['id'],
                                url_suffix=f"watch?v={video_info['id']}"
                            )
                            
                            is_valid, reason = self._validate_video_for_track(
                                video, track, silent
                            )
                            
                            if not is_valid:
                                if not silent:
                                    console.print(f"[yellow]⚠[/yellow] Skipping invalid video for {track.title}: {reason}")
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
                            metadata_dict = {
                                'title': track.title,
                                'artist': track.artist,
                                'album': release_info.title,
                                'year': int(release_info.release_date[:4]) if release_info.release_date and len(release_info.release_date) >= 4 else None,
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
                            with file_progress:
                                if quality == 'audio':
                                    downloaded_path = self.download_service.download_high_quality_audio(
                                        video_url,
                                        metadata=metadata_dict,
                                        quiet=True,
                                        progress_callback=update_file_progress
                                    )
                                else:
                                    downloaded_path = self.download_service.download_video(
                                        video_url,
                                        quality=quality,
                                        audio_only=(quality == 'audio'),
                                        metadata=metadata_dict,
                                        quiet=True,
                                        progress_callback=update_file_progress
                                    )
                                
                                file_progress.update(file_task_id, completed=100)
                            
                            if downloaded_path:
                                # Apply metadata with cover art (reuse pre-fetched cover art)
                                try:
                                    self.metadata_service.apply_metadata_with_cover_art(
                                        downloaded_path, track, release_info, console, cover_art_data=cover_art_data
                                    )
                                except Exception as e:
                                    # If metadata application fails, still count as downloaded but log the error
                                    if not silent and console:
                                        console.print(f"[yellow]⚠[/yellow] Could not apply metadata to {track.title}: {e}")
                                if not silent:
                                    self.display_manager.display_track_download_result(
                                        track.title, True, str(downloaded_path)
                                    )
                                downloaded_count += 1
                            else:
                                if not silent:
                                    self.display_manager.display_track_download_result(track.title, False)
                                failed_count += 1
                        
                        except Exception as e:
                            failed_count += 1
                            if not silent:
                                console.print(f"[bold red]✗[/bold red] Error downloading [white]{track.title}[/white]: {e}")
                            else:
                                console.print(f"[yellow]⚠[/yellow] Error downloading track {track.position}: {track.title} - {str(e)[:50]}")
                        
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
            console.print("[yellow]⚠[/yellow] All playlists failed. Trying next strategy...")
        return None, None
    
    def _download_individual_tracks(
        self,
        release_info: ReleaseInfo,
        track_numbers: List[int],
        quality: str,
        silent: bool = False
    ) -> Tuple[int, int]:
        """
        Download individual tracks from a release.
        
        Optimized to fetch cover art once per release and reuse it for all tracks.
        Strategy 3: Download individual tracks (fallback).
        """
        console = self.display_manager.console
        
        if not silent:
            console.print("[cyan]🎵 Strategy 3: Downloading individual tracks...[/cyan]")
        
        # Fetch cover art once for the entire release (optimization)
        cover_art_data = None
        if not silent:
            cover_art_data = self.metadata_service.fetch_cover_art_for_release(release_info, console)
        else:
            # Still fetch cover art in silent mode, just don't print messages
            cover_art_data = self.metadata_service.fetch_cover_art_for_release(release_info, None)
        
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
                
                # Build a better search query, especially when track title matches album name
                search_query = self._build_track_search_query(track, release_info)
                
                # Check if we need more results (when track title is similar to album name)
                titles_similar = self._are_titles_similar(track.title, release_info.title)
                max_results = 10 if titles_similar else 5  # Get more results when titles are similar
                
                try:
                    videos = self.display_manager.show_loading_spinner(
                        f"Searching YouTube for: {track.title}",
                        self.search_service.search_youtube,
                        search_query,
                        max_results
                    )
                    
                    if not videos:
                        if not silent:
                            console.print(f"[bold red]✗[/bold red] No YouTube results found for: [white]{track.title}[/white]")
                        failed_count += 1
                        progress.update(task, advance=1)
                        continue
                    
                    # Try videos until we find a valid one (not live)
                    selected_video = None
                    for video in videos:
                        # Validate video (check for live versions, duration, etc.)
                        is_valid, reason = self._validate_video_for_track(
                            video, track, silent
                        )
                        
                        if is_valid:
                            selected_video = video
                            break
                        elif not silent:
                            console.print(f"[yellow]⚠[/yellow] Skipping invalid video: {reason}")
                    
                    # If no valid video found, skip this track
                    if not selected_video:
                        if not silent:
                            console.print(f"[bold red]✗[/bold red] No valid (non-live) video found for: [white]{track.title}[/white]")
                        failed_count += 1
                        progress.update(task, advance=1)
                        continue
                    
                    # Create metadata for download
                    # Use "Various Artists" for folder structure if this is a compilation
                    # but keep the actual track artist in metadata
                    is_compilation = self._is_compilation(release_info)
                    folder_artist = "Various Artists" if is_compilation else track.artist
                    
                    metadata_dict = {
                        'title': track.title,
                        'artist': folder_artist,  # Use "Various Artists" for folder structure in compilations
                        'album': release_info.title,
                        'year': int(release_info.release_date[:4]) if release_info.release_date and len(release_info.release_date) >= 4 else None,
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
                        # Use percentage for progress (0-100)
                        percent = progress_info.get('percent', 0)
                        file_progress.update(file_task_id, completed=percent)
                        
                        # Update description
                        desc = f"Track {track.position}: {track.title[:35]}"
                        file_progress.update(file_task_id, description=desc)
                    
                    # Download the track with progress
                    youtube_url = selected_video.youtube_url
                    
                    with file_progress:
                        if quality == 'audio':
                            downloaded_path = self.download_service.download_high_quality_audio(
                                youtube_url,
                                metadata=metadata_dict,
                                quiet=True,
                                progress_callback=update_file_progress
                            )
                        else:
                            downloaded_path = self.download_service.download_video(
                                youtube_url,
                                quality=quality,
                                audio_only=(quality == 'audio'),
                                metadata=metadata_dict,
                                quiet=True,
                                progress_callback=update_file_progress
                            )
                        
                        # Mark as complete
                    file_progress.update(file_task_id, completed=100)
                    
                    if downloaded_path:
                        # Apply metadata with cover art (reuse pre-fetched cover art)
                        try:
                            self.metadata_service.apply_metadata_with_cover_art(
                                downloaded_path, track, release_info, console, cover_art_data=cover_art_data
                            )
                        except Exception as e:
                            # If metadata application fails, still count as downloaded but log the error
                            if not silent and console:
                                console.print(f"[yellow]⚠[/yellow] Could not apply metadata to {track.title}: {e}")
                        if not silent:
                            self.display_manager.display_track_download_result(
                                track.title, True, str(downloaded_path)
                            )
                        downloaded_count += 1
                    else:
                        if not silent:
                            self.display_manager.display_track_download_result(track.title, False)
                        failed_count += 1
                        
                except subprocess.TimeoutExpired:
                    # Timeout occurred during download
                    failed_count += 1
                    if not silent:
                        console.print(f"[yellow]⚠[/yellow] Timeout downloading track {track.position}: {track.title}")
                except Exception as e:
                    # Log other exceptions but continue with next track
                    failed_count += 1
                    if not silent:
                        console.print(f"[bold red]✗[/bold red] Error downloading [white]{track.title}[/white]: {e}")
                    else:
                        console.print(f"[yellow]⚠[/yellow] Error downloading track {track.position}: {track.title} - {str(e)[:50]}")
                
                progress.update(task, advance=1)
        
        return downloaded_count, failed_count
    
    def download_release_tracks(
        self,
        release_info: ReleaseInfo,
        track_numbers: List[int],
        quality: str,
        silent: bool = False
    ) -> Tuple[int, int]:
        """Download selected tracks from a release using multi-strategy approach."""
        console = self.display_manager.console
        
        # Strategy 1: Try full album video
        downloaded, failed = self._download_full_album_and_split(
            release_info, track_numbers, quality, silent
        )
        if downloaded is not None:
            # Success with full album
            if not silent:
                console.print()
                summary_content = f"[bold green]✓[/bold green] Successfully downloaded: [green]{downloaded}[/green] track{'s' if downloaded != 1 else ''}\n"
                if failed > 0:
                    summary_content += f"[bold red]✗[/bold red] Failed downloads: [red]{failed}[/red] track{'s' if failed != 1 else ''}\n"
                summary_content += f"[blue]ℹ[/blue] Total tracks processed: [cyan]{len(track_numbers)}[/cyan]"
                
                from rich.panel import Panel
                from rich import box
                console.print(Panel(
                    summary_content,
                    title="[bold cyan]📊 DOWNLOAD SUMMARY[/bold cyan]",
                    border_style="cyan",
                    box=box.ROUNDED,
                    padding=(1, 2)
                ))
                console.print()
            return downloaded, failed
        
        # Strategy 2: Try playlist
        downloaded, failed = self._download_from_playlist(
            release_info, track_numbers, quality, silent
        )
        if downloaded is not None:
            # Success with playlist
            if not silent:
                console.print()
                summary_content = f"[bold green]✓[/bold green] Successfully downloaded: [green]{downloaded}[/green] track{'s' if downloaded != 1 else ''}\n"
                if failed > 0:
                    summary_content += f"[bold red]✗[/bold red] Failed downloads: [red]{failed}[/red] track{'s' if failed != 1 else ''}\n"
                summary_content += f"[blue]ℹ[/blue] Total tracks processed: [cyan]{len(track_numbers)}[/cyan]"
                
                from rich.panel import Panel
                from rich import box
                console.print(Panel(
                    summary_content,
                    title="[bold cyan]📊 DOWNLOAD SUMMARY[/bold cyan]",
                    border_style="cyan",
                    box=box.ROUNDED,
                    padding=(1, 2)
                ))
                console.print()
            return downloaded, failed
        
        # Strategy 3: Fall back to individual tracks
        downloaded, failed = self._download_individual_tracks(
            release_info, track_numbers, quality, silent
        )
        
        # Summary (only if not silent)
        if not silent:
            console.print()
            summary_content = f"[bold green]✓[/bold green] Successfully downloaded: [green]{downloaded}[/green] track{'s' if downloaded != 1 else ''}\n"
            if failed > 0:
                summary_content += f"[bold red]✗[/bold red] Failed downloads: [red]{failed}[/red] track{'s' if failed != 1 else ''}\n"
            summary_content += f"[blue]ℹ[/blue] Total tracks processed: [cyan]{len(track_numbers)}[/cyan]"
            
            from rich.panel import Panel
            from rich import box
            console.print(Panel(
                summary_content,
                title="[bold cyan]📊 DOWNLOAD SUMMARY[/bold cyan]",
                border_style="cyan",
                box=box.ROUNDED,
                padding=(1, 2)
            ))
            console.print()
        
        return downloaded, failed

