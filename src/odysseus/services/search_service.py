"""
Search service that coordinates searches across multiple sources.
"""

from typing import List, Optional, Dict, Any, Tuple
from ..models.song import SongData
from ..models.search_results import SearchResult, MusicBrainzSong, YouTubeVideo
from ..clients.musicbrainz import MusicBrainzClient
from ..clients.youtube import YouTubeClient


class SearchService:
    """Service for searching music across multiple sources."""
    
    def __init__(self):
        self.musicbrainz_client = MusicBrainzClient()
        self.youtube_client = None  # Will be initialized when needed
    
    def _normalize_string(self, s: Optional[str]) -> str:
        """Normalize a string for comparison (lowercase, strip whitespace)."""
        if not s:
            return ""
        return s.lower().strip()
    
    def _get_release_year(self, release_date: Optional[str]) -> Optional[str]:
        """Extract year from release date string."""
        if not release_date:
            return None
        # Extract first 4 digits (year)
        year_part = release_date[:4] if len(release_date) >= 4 else None
        return year_part if year_part and year_part.isdigit() else None
    
    def _create_deduplication_key(self, result: MusicBrainzSong) -> Tuple[str, str, Optional[str]]:
        """
        Create a deduplication key for a search result.
        For releases: uses album (or title if album is empty), artist, and year
        For recordings: uses title, artist, and year (album is optional)
        """
        # Normalize title and album
        title = self._normalize_string(result.title)
        album = self._normalize_string(result.album)
        artist = self._normalize_string(result.artist)
        year = self._get_release_year(result.release_date)
        
        # For releases, prioritize album; for recordings, prioritize title
        # If both title and album exist and are the same, use album
        if album and title and album == title:
            primary_key = album
        elif album:
            primary_key = album  # Release with album
        elif title:
            primary_key = title  # Recording with title
        else:
            primary_key = ""  # Fallback
        
        return (primary_key, artist, year)
    
    def _deduplicate_results(self, results: List[MusicBrainzSong]) -> List[MusicBrainzSong]:
        """
        Remove duplicate results based on title/album, artist, and year.
        When duplicates are found, keeps the one with the highest score.
        """
        if not results:
            return results
        
        seen: Dict[Tuple[str, str, Optional[str]], MusicBrainzSong] = {}
        
        for result in results:
            key = self._create_deduplication_key(result)
            
            # If we haven't seen this combination before, add it
            if key not in seen:
                seen[key] = result
            else:
                # If duplicate, keep the one with higher score
                existing = seen[key]
                existing_score = existing.score if existing.score else 0
                result_score = result.score if result.score else 0
                
                if result_score > existing_score:
                    seen[key] = result
        
        return list(seen.values())
    
    def search_recordings(self, song_data: SongData, offset: int = 0, limit: Optional[int] = None) -> List[MusicBrainzSong]:
        """Search for recordings in MusicBrainz."""
        results = self.musicbrainz_client.search_recording(song_data, offset=offset, limit=limit)
        return self._deduplicate_results(results)
    
    def search_releases(self, song_data: SongData, offset: int = 0, limit: Optional[int] = None) -> List[MusicBrainzSong]:
        """Search for releases in MusicBrainz."""
        results = self.musicbrainz_client.search_release(song_data, offset=offset, limit=limit)
        return self._deduplicate_results(results)
    
    def search_artist_releases(self, artist: str, year: Optional[int] = None) -> List[MusicBrainzSong]:
        """Search for releases by a specific artist."""
        results = self.musicbrainz_client.search_artist_releases(artist, year)
        return self._deduplicate_results(results)
    
    def get_release_info(self, release_mbid: str) -> Optional[Any]:
        """Get detailed release information."""
        return self.musicbrainz_client.get_release_info(release_mbid)
    
    def search_youtube(self, query: str, max_results: int = 3, offset: int = 0) -> List[YouTubeVideo]:
        """Search YouTube for videos."""
        # For reshuffle, create a new client to get fresh results
        # YouTube doesn't have offset, so we'll just search again which may return different results
        self.youtube_client = YouTubeClient(query, max_results)
        return self.youtube_client.videos
    
    def search_all_sources(self, song_data: SongData) -> Dict[str, List[SearchResult]]:
        """Search all available sources for a song."""
        results = {}
        
        # Search MusicBrainz
        try:
            results['musicbrainz'] = self.search_recordings(song_data)
        except Exception as e:
            print(f"MusicBrainz search failed: {e}")
            results['musicbrainz'] = []
        
        # Search YouTube
        try:
            query = f"{song_data.artist} {song_data.title}"
            results['youtube'] = self.search_youtube(query)
        except Exception as e:
            print(f"YouTube search failed: {e}")
            results['youtube'] = []
        
        return results
