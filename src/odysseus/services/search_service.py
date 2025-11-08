"""
Search service that coordinates searches across multiple sources.
"""

import concurrent.futures
import re
from typing import List, Optional, Dict, Any, Tuple
from ..models.song import SongData
from ..models.search_results import SearchResult, MusicBrainzSong, YouTubeVideo, DiscogsRelease
from ..clients.musicbrainz import MusicBrainzClient
from ..clients.discogs import DiscogsClient
from ..clients.youtube import YouTubeClient
from ..utils.string_utils import normalize_string


class SearchService:
    """Service for searching music across multiple sources."""
    
    def __init__(self):
        self.musicbrainz_client = MusicBrainzClient()
        self.discogs_client = DiscogsClient()
        self.youtube_client = None  # Will be initialized when needed
    
    
    def _get_release_year(self, release_date: Optional[str]) -> Optional[str]:
        """Extract year from release date string."""
        if not release_date or release_date.strip() == "":
            return None
        # Extract first 4 digits (year)
        year_part = release_date[:4] if len(release_date) >= 4 else None
        return year_part if year_part and year_part.isdigit() else None
    
    def _create_deduplication_key(self, result: MusicBrainzSong) -> Tuple[str, str]:
        """
        Create a deduplication key for a search result (album + artist only, no year).
        For releases: uses album (or title if album is empty) and artist
        For recordings: uses title and artist (album is optional)
        """
        # Normalize title and album
        title = normalize_string(result.title)
        album = normalize_string(result.album)
        artist = normalize_string(result.artist)
        
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
        
        return (primary_key, artist)
    
    def _parse_release_date(self, release_date: Optional[str]) -> Optional[tuple]:
        """
        Parse release date to a comparable tuple (year, month, day).
        Returns None if date is invalid or missing.
        """
        if not release_date or release_date.strip() == "":
            return None
        
        # Try to parse YYYY-MM-DD, YYYY-MM, or YYYY format
        parts = release_date.strip().split('-')
        if len(parts) >= 1 and parts[0].isdigit():
            year = int(parts[0])
            month = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 1
            day = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 1
            return (year, month, day)
        
        return None
    
    def _deduplicate_results(self, results: List[MusicBrainzSong]) -> List[MusicBrainzSong]:
        """
        Remove duplicate results based on normalized (album, artist) key.
        When duplicates are found, keeps the earliest release date.
        This deduplicates by release name (album) + artist, regardless of year or MBID.
        """
        if not results:
            return results
        
        # Group results by (album, artist) key
        grouped_by_key: Dict[Tuple[str, str], List[MusicBrainzSong]] = {}
        
        for result in results:
            key = self._create_deduplication_key(result)
            
            # Skip empty keys
            if not key[0]:  # Empty album/title
                continue
            
            if key not in grouped_by_key:
                grouped_by_key[key] = []
            grouped_by_key[key].append(result)
        
        # For each group, keep only the earliest release
        deduplicated = []
        for key, group in grouped_by_key.items():
            if len(group) == 1:
                deduplicated.append(group[0])
            else:
                # Find the earliest release date
                # If multiple have the same date, prefer the one with highest score
                # If same date and score, prefer the one with MBID (more complete data)
                earliest = None
                earliest_date = None
                earliest_score = -1
                
                # First, try to find the best release with a date
                for result in group:
                    date_tuple = self._parse_release_date(result.release_date)
                    score = result.score if result.score else 0
                    
                    if date_tuple is None:
                        # If no date, skip this one (prefer releases with dates)
                        continue
                    
                    # If this is earlier, or same date but higher score, keep it
                    if earliest_date is None or date_tuple < earliest_date:
                        earliest_date = date_tuple
                        earliest = result
                        earliest_score = score
                    elif date_tuple == earliest_date:
                        # Same date - prefer higher score
                        if score > earliest_score:
                            earliest = result
                            earliest_score = score
                        elif score == earliest_score:
                            # Same date and score - prefer the one with MBID (more complete)
                            if result.mbid and (not earliest.mbid or result.mbid < earliest.mbid):
                                earliest = result
                
                # If no release had a date, take the one with highest score
                # If same score, prefer the one with MBID
                if earliest is None:
                    best_score = max((r.score if r.score else 0) for r in group)
                    candidates = [r for r in group if (r.score if r.score else 0) == best_score]
                    # Prefer the one with MBID, or just take the first one
                    earliest = next((r for r in candidates if r.mbid), candidates[0])
                
                deduplicated.append(earliest)
        
        return deduplicated
    
    def search_recordings(self, song_data: SongData, offset: int = 0, limit: Optional[int] = None) -> List[MusicBrainzSong]:
        """Search for recordings in MusicBrainz."""
        results = self.musicbrainz_client.search_recording(song_data, offset=offset, limit=limit)
        return self._deduplicate_results(results)
    
    def search_releases(self, song_data: SongData, offset: int = 0, limit: Optional[int] = None, release_type: Optional[str] = None) -> List[MusicBrainzSong]:
        """Search for releases in MusicBrainz and Discogs in parallel.
        
        Args:
            song_data: Song information to search for
            offset: Offset for pagination
            limit: Maximum number of results
            release_type: Optional release type filter (e.g., "Album", "Single", "EP", "Compilation", "Live", etc.)
        """
        # Search both sources in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            mb_future = executor.submit(
                self.musicbrainz_client.search_release,
                song_data, offset, limit, None  # Get all results, filter later
            )
            discogs_future = executor.submit(
                self.discogs_client.search_release,
                song_data, offset, limit, release_type
            )
            
            mb_results = mb_future.result()
            discogs_results = discogs_future.result()
        
        # Convert Discogs results to MusicBrainzSong format for consistency
        mb_formatted_results = self._deduplicate_results(mb_results)
        discogs_formatted = self._convert_discogs_to_mb_format(discogs_results)
        
        # Combine results
        all_results = mb_formatted_results + discogs_formatted
        
        # Apply client-side filtering by release type if specified
        if release_type:
            filtered_results = []
            for result in all_results:
                if result.release_type and result.release_type.lower() == release_type.lower():
                    filtered_results.append(result)
            all_results = filtered_results
            # Deduplicate again after filtering to ensure clean results
            all_results = self._deduplicate_results(all_results)
        
        # Apply limit after filtering if specified
        if limit and len(all_results) > limit:
            all_results = all_results[:limit]
        
        return all_results
    
    def search_artist_releases(self, artist: str, year: Optional[int] = None, release_type: Optional[str] = None) -> List[MusicBrainzSong]:
        """Search for releases by a specific artist in MusicBrainz and Discogs in parallel.
        
        Args:
            artist: Artist name to search for
            year: Optional year filter
            release_type: Optional release type filter (e.g., "Album", "Single", "EP", "Compilation", "Live", etc.)
        """
        # Search both sources in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            mb_future = executor.submit(
                self.musicbrainz_client.search_artist_releases,
                artist, year, None  # Get all results, filter later
            )
            discogs_future = executor.submit(
                self.discogs_client.search_artist_releases,
                artist, year, None, None  # Get all results, filter later
            )
            
            mb_results = mb_future.result()
            discogs_results = discogs_future.result()
        
        # Convert Discogs results to MusicBrainzSong format for consistency
        mb_formatted_results = self._deduplicate_results(mb_results)
        discogs_formatted = self._convert_discogs_to_mb_format(discogs_results)
        
        # Combine results
        all_results = mb_formatted_results + discogs_formatted
        
        # Apply client-side filtering by release type if specified
        if release_type:
            filtered_results = []
            for result in all_results:
                if result.release_type and result.release_type.lower() == release_type.lower():
                    filtered_results.append(result)
            all_results = filtered_results
            # Deduplicate again after filtering to ensure clean results
            all_results = self._deduplicate_results(all_results)
        
        return all_results
    
    def get_release_info(self, release_mbid: str, batch_progress: Optional[tuple[int, int]] = None, source: str = "musicbrainz") -> Optional[Any]:
        """Get detailed release information from MusicBrainz or Discogs.
        
        Args:
            release_mbid: Release ID (MBID for MusicBrainz, Discogs ID for Discogs)
            batch_progress: Optional tuple (current, total) for batch operations
            source: Source to query ("musicbrainz" or "discogs")
        """
        if source == "discogs":
            return self.discogs_client.get_release_info(release_mbid, batch_progress=batch_progress)
        else:
            return self.musicbrainz_client.get_release_info(release_mbid, batch_progress=batch_progress)
    
    def _convert_discogs_to_mb_format(self, discogs_results: List[DiscogsRelease]) -> List[MusicBrainzSong]:
        """Convert DiscogsRelease results to MusicBrainzSong format for consistency."""
        mb_results = []
        for discogs_result in discogs_results:
            # Convert year to release_date string format
            release_date = str(discogs_result.year) if discogs_result.year else None
            
            mb_result = MusicBrainzSong(
                title=discogs_result.title or discogs_result.album or "",
                artist=discogs_result.artist,
                album=discogs_result.album,
                release_date=release_date,
                genre=discogs_result.genre,
                release_type=discogs_result.format,
                mbid=discogs_result.discogs_id,  # Store Discogs ID in mbid field
                score=discogs_result.score,
                url=discogs_result.url,
                source="discogs"  # Mark as from Discogs
            )
            mb_results.append(mb_result)
        return mb_results
    
    def search_youtube(self, query: str, max_results: int = 3, offset: int = 0) -> List[YouTubeVideo]:
        """Search YouTube for videos."""
        # For reshuffle, create a new client to get fresh results
        # YouTube doesn't have offset, so we'll just search again which may return different results
        self.youtube_client = YouTubeClient(query, max_results)
        return self.youtube_client.videos
    
    def search_full_album(self, artist: str, album: str, max_results: int = 5) -> List[YouTubeVideo]:
        """Search YouTube for full album videos (complete album in one video)."""
        # Search for full album - common patterns include "full album", "complete album", "album full"
        # Exclude live versions in search queries
        queries = [
            f"{artist} {album} full album",
            f"{artist} {album} complete album",
            f"{artist} {album} album full",
            f"{artist} {album} full",
            f"{artist} {album} full album -live -concert",  # Try to exclude live versions
        ]
        
        all_results = []
        seen_ids = set()
        
        # Keywords that indicate live versions or non-album content (to filter out)
        live_keywords = ['live', 'concert', 'performance', 'on stage', 'recorded live']
        non_album_keywords = [
            'reaction', 'react', 'reacting', 'reacts', 'first reaction', 'first time listening',
            'review', 'album review', 'unboxing', 'reaction to', 'reacting to', 'my reaction',
            'listening to', 'listening session', 'rate', 'rating', 'ranking', 'breakdown',
            'analysis', 'explained', 'discussion', 'podcast', 'interview', 'trailer', 'teaser',
            'preview', 'snippet', 'clip', 'mashup', 'remix', 'cover', 'covers', 'tribute',
            'parody', 'meme', 'tier list', 'top 10', 'top 5'
        ]
        
        for query in queries:
            client = YouTubeClient(query, max_results)
            for video in client.videos:
                if video.video_id and video.video_id not in seen_ids:
                    # Check if video title suggests it's a full album
                    title_lower = video.title.lower()
                    
                    # Must contain full album keywords
                    has_full_album_keyword = any(
                        keyword in title_lower 
                        for keyword in ['full album', 'complete album', 'album full', 'full lp']
                    )
                    
                    if not has_full_album_keyword:
                        continue
                    
                    # Filter out obvious live versions and non-album content in initial search
                    is_live = any(keyword in title_lower for keyword in live_keywords)
                    is_non_album = any(keyword in title_lower for keyword in non_album_keywords)
                    if is_live or is_non_album:
                        continue  # Skip live versions and non-album content in initial search
                    
                    all_results.append(video)
                    seen_ids.add(video.video_id)
                    if len(all_results) >= max_results:
                        return all_results[:max_results]
        
        return all_results[:max_results]
    
    def search_playlist(self, artist: str, album: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search YouTube for playlists matching the album."""
        # Search for playlists - YouTube playlist URLs start with "playlist?list="
        queries = [
            f"{artist} {album} playlist",
            f"{artist} {album} album playlist",
        ]
        
        all_results = []
        seen_ids = set()
        
        for query in queries:
            client = YouTubeClient(query, max_results * 2)  # Get more results to find playlists
            for video in client.videos:
                # Check if this video is part of a playlist by checking URL
                if video.url_suffix and 'list=' in video.url_suffix:
                    # Extract playlist ID
                    match = re.search(r'list=([^&]+)', video.url_suffix)
                    if match:
                        playlist_id = match.group(1)
                        if playlist_id not in seen_ids:
                            all_results.append({
                                'playlist_id': playlist_id,
                                'title': video.title,
                                'url': f"https://www.youtube.com/playlist?list={playlist_id}",
                                'video': video
                            })
                            seen_ids.add(playlist_id)
                            if len(all_results) >= max_results:
                                return all_results[:max_results]
        
        return all_results[:max_results]
    
    def search_all_sources(self, song_data: SongData) -> Dict[str, List[SearchResult]]:
        """Search all available sources for a song."""
        results = {}
        
        # Search MusicBrainz
        try:
            results['musicbrainz'] = self.search_recordings(song_data)
        except Exception as e:
            print(f"MusicBrainz search failed: {e}")
            results['musicbrainz'] = []
        
        # Search Discogs
        try:
            discogs_results = self.discogs_client.search_release(song_data)
            results['discogs'] = discogs_results
        except Exception as e:
            print(f"Discogs search failed: {e}")
            results['discogs'] = []
        
        # Search YouTube
        try:
            query = f"{song_data.artist} {song_data.title}"
            results['youtube'] = self.search_youtube(query)
        except Exception as e:
            print(f"YouTube search failed: {e}")
            results['youtube'] = []
        
        return results
