"""
Pattern matching utilities for YouTube titles and video content.
Consolidates pattern matching logic from search_service and video_validator.
"""

import re
from typing import List


class PatternMatcher:
    """Utility class for pattern matching in YouTube titles."""

    # Full album keywords
    FULL_ALBUM_KEYWORDS = ['full album', 'complete album', 'album full', 'full lp']

    # Non-album keywords
    NON_ALBUM_KEYWORDS = [
        'reaction', 'react', 'reacting', 'reacts', 'first reaction', 'first time listening',
        'review', 'album review', 'unboxing', 'reaction to', 'reacting to', 'my reaction',
        'listening to', 'listening session', 'rate', 'rating', 'ranking', 'breakdown',
        'analysis', 'explained', 'discussion', 'podcast', 'interview', 'trailer', 'teaser',
        'preview', 'snippet', 'clip', 'mashup', 'remix', 'cover', 'covers', 'tribute',
        'parody', 'meme', 'tier list', 'top 10', 'top 5',
        'vinyl', 'needle drop', 'needledrop', 'turntable', 'record player',
        'lp rip', 'listening party'
    ]

    # Live keyword patterns (with word boundaries)
    LIVE_KEYWORD_PATTERNS = [
        r'\blive\s+concert\b',
        r'\blive\s+performance\b',
        r'\blive\s+on\s+stage\b',
        r'\brecorded\s+live\b',
        r'\blive\s+session\b',
        r'\blive\s+recording\b',
        r'\blive\s+from\b',
        r'\blive\s+@\b',
        r'\blive\s+in\b',
        r'\blive\s+at\b',
        r'\blive\s+version\b',
        r'\blive\s+take\b',
        r'\blive\s+acoustic\b',
        r'\blive\s+bootleg\b',
        r'\blive\s+broadcast\b',
    ]

    # Concert venues
    CONCERT_VENUES = [
        'red rocks', 'madison square garden', 'msg', 'royal albert hall',
        'apollo theater', 'apollo theatre', 'fillmore', 'hollywood bowl',
        'coachella', 'glastonbury', 'woodstock', 'monterey pop',
        'newport folk', 'newport jazz', 'montreux jazz', 'blue note',
        'village vanguard', 'ronnie scott\'s', 'ronnie scotts',
        'troubadour', 'whisky a go go', 'cbgb', 'palladium',
        'hammersmith', 'brixton academy', 'o2 arena', 'wembley',
        'festival', 'festival de', 'rock in rio', 'lollapalooza',
        'bonnaroo', 'sxsw', 'austin city limits', 'acoustic', 'acoustic session'
    ]

    # Simple live keywords
    LIVE_KEYWORDS_SIMPLE = [
        'unplugged', 'mtv unplugged', 'kexp', 'npr tiny desk',
        'audience', 'applause', 'encore'
    ]

    @staticmethod
    def has_full_album_keyword(title: str) -> bool:
        return any(kw in title.lower() for kw in PatternMatcher.FULL_ALBUM_KEYWORDS)

    @staticmethod
    def is_live_or_non_album_video(title: str) -> bool:
        title_lower = title.lower()
        return PatternMatcher.matches_live_patterns(title_lower) or any(kw in title_lower for kw in PatternMatcher.NON_ALBUM_KEYWORDS)

    @staticmethod
    def matches_live_patterns(title_lower: str) -> bool:
        # Check live keyword patterns
        for pattern in PatternMatcher.LIVE_KEYWORD_PATTERNS:
            if re.search(pattern, title_lower):
                return True

        # Check for "at [venue]" pattern
        if re.search(r'\bat\s+[a-z\s]+(?:rocks|garden|hall|theater|theatre|bowl|arena|festival|acoustic)', title_lower):
            return True

        # Check for known concert venues
        if any(venue in title_lower for venue in PatternMatcher.CONCERT_VENUES):
            return True

        # Check for standalone "live" word
        if re.search(r'\blive\b', title_lower):
            return True

        # Check for simple live keywords
        if any(keyword in title_lower for keyword in PatternMatcher.LIVE_KEYWORDS_SIMPLE):
            return True

        # Check for year patterns that suggest live recordings (e.g., "at Red Rocks 2024")
        if re.search(r'\bat\s+[a-z\s]+\s+\d{4}\b', title_lower):
            return True

        return False

    @staticmethod
    def is_live_in_track_title(video_title_lower: str, track_title_lower: str) -> bool:
        if not track_title_lower or not re.search(r'\blive\b', track_title_lower):
            return False
        track_words = set(re.findall(r'\b\w+\b', track_title_lower))
        video_words = set(re.findall(r'\b\w+\b', video_title_lower))
        return bool(track_words) and len(track_words.intersection(video_words)) / len(track_words) >= 0.6
