"""
Title and artist matching utilities for video selection.
"""

import re
from typing import Optional
from ..utils.string_utils import normalize_string


class TitleMatcher:
    """Matches video titles to albums and tracks."""
    
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
    
    def artist_matches(self, video_title: str, artist: str) -> bool:
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
    
    def title_matches_album(
        self,
        video_title: str,
        album_title: str,
        artist: str,
        release_year: Optional[str] = None
    ) -> bool:
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
        artist_matches = self.artist_matches(video_title, artist)
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
    
    def are_titles_similar(self, track_title: str, album_title: str) -> bool:
        """Check if track title is similar to album title."""
        track_title_norm = normalize_string(track_title)
        album_title_norm = normalize_string(album_title)
        
        return (
            track_title_norm == album_title_norm or
            track_title_norm in album_title_norm or
            album_title_norm in track_title_norm or
            # Check if they share significant words (at least 2 words in common)
            len(set(track_title_norm.split()) & set(album_title_norm.split())) >= 2
        )
    
    def match_playlist_video_to_track(
        self,
        video_title: str,
        track_title: str,
        artist: str,
        video_validator
    ) -> float:
        """
        Calculate a match score between a playlist video and a track.
        Returns a score between 0.0 and 1.0, where 1.0 is a perfect match.
        
        Args:
            video_title: YouTube video title
            track_title: Track title
            artist: Artist name
            video_validator: VideoValidator instance for validation checks
        """
        if not video_title or not track_title:
            return 0.0
        
        # Normalize strings for comparison
        video_normalized = self._normalize_for_matching(video_title)
        track_normalized = self._normalize_for_matching(track_title)
        artist_normalized = self._normalize_for_matching(artist)
        
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
        if video_validator.is_live_version(video_title) or video_validator.is_reaction_or_review_video(video_title):
            score *= 0.3  # Heavy penalty
        
        return min(score, 1.0)

