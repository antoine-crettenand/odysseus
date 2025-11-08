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
        self.youtube_client = None
    
    
    def _get_release_year(self, release_date: Optional[str]) -> Optional[str]:
        """Extract year from release date string."""
        if not release_date or release_date.strip() == "":
            return None
        year_part = release_date[:4] if len(release_date) >= 4 else None
        return year_part if year_part and year_part.isdigit() else None
    
    def _create_deduplication_key(self, result: MusicBrainzSong) -> Tuple[str, str]:
        """
        Create a deduplication key for a search result (album + artist only, no year).
        For releases: uses album (or title if album is empty) and artist
        For recordings: uses title and artist (album is optional)
        """
        title = normalize_string(result.title)
        album = normalize_string(result.album)
        artist = normalize_string(result.artist)
        
        if album and title and album == title:
            primary_key = album
        elif album:
            primary_key = album
        elif title:
            primary_key = title
        else:
            primary_key = ""
        
        return (primary_key, artist)
    
    def _parse_release_date(self, release_date: Optional[str]) -> Optional[tuple]:
        """
        Parse release date to a comparable tuple (year, month, day).
        Returns None if date is invalid or missing.
        """
        if not release_date or release_date.strip() == "":
            return None
        
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
        
        grouped_by_key: Dict[Tuple[str, str], List[MusicBrainzSong]] = {}
        
        for result in results:
            key = self._create_deduplication_key(result)
            
            if not key[0]:
                continue
            
            if key not in grouped_by_key:
                grouped_by_key[key] = []
            grouped_by_key[key].append(result)
        
        deduplicated = []
        for key, group in grouped_by_key.items():
            if len(group) == 1:
                deduplicated.append(group[0])
            else:
                earliest = None
                earliest_date = None
                earliest_score = -1
                
                for result in group:
                    date_tuple = self._parse_release_date(result.release_date)
                    score = result.score if result.score else 0
                    
                    if date_tuple is None:
                        continue
                    
                    if earliest_date is None or date_tuple < earliest_date:
                        earliest_date = date_tuple
                        earliest = result
                        earliest_score = score
                    elif date_tuple == earliest_date:
                        if score > earliest_score:
                            earliest = result
                            earliest_score = score
                        elif score == earliest_score:
                            if result.mbid and (not earliest.mbid or result.mbid < earliest.mbid):
                                earliest = result
                
                if earliest is None:
                    best_score = max((r.score if r.score else 0) for r in group)
                    candidates = [r for r in group if (r.score if r.score else 0) == best_score]
                    earliest = next((r for r in candidates if r.mbid), candidates[0])
                
                deduplicated.append(earliest)
        
        return deduplicated
    
    def _deduplicate_with_priority(self, mb_results: List[MusicBrainzSong], discogs_results: List[MusicBrainzSong]) -> List[MusicBrainzSong]:
        """
        Deduplicate results prioritizing MusicBrainz over Discogs.
        Only keeps Discogs results that don't have a matching MusicBrainz result.
        This ensures Discogs complements MusicBrainz without polluting good results.
        """
        # First, deduplicate MusicBrainz results internally
        mb_deduped = self._deduplicate_results(mb_results)
        
        # Create a set of keys for MusicBrainz results
        mb_keys = set()
        for result in mb_deduped:
            key = self._create_deduplication_key(result)
            if key[0]:  # Only add non-empty keys
                mb_keys.add(key)
        
        # Only keep Discogs results that don't match any MusicBrainz result
        complementary_discogs = []
        for discogs_result in discogs_results:
            key = self._create_deduplication_key(discogs_result)
            if key[0] and key not in mb_keys:
                complementary_discogs.append(discogs_result)
        
        # Combine: MusicBrainz first (prioritized), then complementary Discogs
        return mb_deduped + complementary_discogs
    
    def search_recordings(self, song_data: SongData, offset: int = 0, limit: Optional[int] = None) -> List[MusicBrainzSong]:
        """Search for recordings in MusicBrainz."""
        results = self.musicbrainz_client.search_recording(song_data, offset=offset, limit=limit)
        return self._deduplicate_results(results)
    
    def search_releases(self, song_data: SongData, offset: int = 0, limit: Optional[int] = None, release_type: Optional[str] = None) -> List[MusicBrainzSong]:
        """Search for releases in MusicBrainz and Discogs in parallel.
        MusicBrainz results are prioritized; Discogs only fills gaps.
        
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
        
        # Convert Discogs to MusicBrainz format
        discogs_formatted = self._convert_discogs_to_mb_format(discogs_results)
        
        # Use priority-based deduplication: MusicBrainz first, Discogs only fills gaps
        all_results = self._deduplicate_with_priority(mb_results, discogs_formatted)
        
        if release_type:
            filtered_results = []
            for result in all_results:
                if result.release_type and result.release_type.lower() == release_type.lower():
                    filtered_results.append(result)
            all_results = filtered_results
        
        if limit and len(all_results) > limit:
            all_results = all_results[:limit]
        
        return all_results
    
    def search_artist_releases(self, artist: str, year: Optional[int] = None, release_type: Optional[str] = None) -> List[MusicBrainzSong]:
        """Search for releases by a specific artist in MusicBrainz and Discogs in parallel.
        MusicBrainz results are prioritized; Discogs only fills gaps.
        
        Args:
            artist: Artist name to search for
            year: Optional year filter
            release_type: Optional release type filter (e.g., "Album", "Single", "EP", "Compilation", "Live", etc.)
        """
        # Search both sources in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            mb_future = executor.submit(
                self.musicbrainz_client.search_artist_releases,
                artist, year, None
            )
            discogs_future = executor.submit(
                self.discogs_client.search_artist_releases,
                artist, year, None, None
            )
            
            mb_results = mb_future.result()
            discogs_results = discogs_future.result()
        
        # Convert Discogs to MusicBrainz format
        discogs_formatted = self._convert_discogs_to_mb_format(discogs_results)
        
        # Use priority-based deduplication: MusicBrainz first, Discogs only fills gaps
        all_results = self._deduplicate_with_priority(mb_results, discogs_formatted)
        
        if release_type:
            filtered_results = []
            for result in all_results:
                if result.release_type and result.release_type.lower() == release_type.lower():
                    filtered_results.append(result)
            all_results = filtered_results
        
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
            release_date = str(discogs_result.year) if discogs_result.year else None
            
            mb_result = MusicBrainzSong(
                title=discogs_result.title or discogs_result.album or "",
                artist=discogs_result.artist,
                album=discogs_result.album,
                release_date=release_date,
                genre=discogs_result.genre,
                release_type=discogs_result.format,
                mbid=discogs_result.discogs_id,
                score=discogs_result.score,
                url=discogs_result.url,
                source="discogs"
            )
            mb_results.append(mb_result)
        return mb_results
    
    def search_youtube(self, query: str, max_results: int = 3, offset: int = 0) -> List[YouTubeVideo]:
        """Search YouTube for videos."""
        self.youtube_client = YouTubeClient(query, max_results)
        return self.youtube_client.videos
    
    def search_full_album(self, artist: str, album: str, max_results: int = 5) -> List[YouTubeVideo]:
        """Search YouTube for full album videos (complete album in one video)."""
        queries = [
            f"{artist} {album} full album",
            f"{artist} {album} complete album",
            f"{artist} {album} album full",
            f"{artist} {album} full",
            f"{artist} {album} full album -live -concert",
        ]
        
        all_results = []
        seen_ids = set()
        
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
                    title_lower = video.title.lower()
                    
                    has_full_album_keyword = any(
                        keyword in title_lower 
                        for keyword in ['full album', 'complete album', 'album full', 'full lp']
                    )
                    
                    if not has_full_album_keyword:
                        continue
                    
                    is_live = any(keyword in title_lower for keyword in live_keywords)
                    is_non_album = any(keyword in title_lower for keyword in non_album_keywords)
                    if is_live or is_non_album:
                        continue
                    
                    all_results.append(video)
                    seen_ids.add(video.video_id)
                    if len(all_results) >= max_results:
                        return all_results[:max_results]
        
        return all_results[:max_results]
    
    def search_playlist(self, artist: str, album: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search YouTube for playlists matching the album."""
        # Include queries for vinyl "Side 1" and "Side 2" playlists
        queries = [
            f"{artist} {album} playlist",
            f"{artist} {album} album playlist",
            f"{artist} {album} side 1",
            f"{artist} {album} side 2",
            f"{artist} {album} vinyl side 1",
            f"{artist} {album} vinyl side 2",
            f"{artist} {album} side a",
            f"{artist} {album} side b",
        ]
        
        all_results = []
        seen_ids = set()
        # Separate lists for regular playlists and side playlists (prioritize side playlists)
        side_playlists = []
        regular_playlists = []
        
        for query in queries:
            client = YouTubeClient(query, max_results * 2)
            for video in client.videos:
                if video.url_suffix and 'list=' in video.url_suffix:
                    match = re.search(r'list=([^&]+)', video.url_suffix)
                    if match:
                        playlist_id = match.group(1)
                        
                        # Skip Radio playlists (RD prefix) - these are auto-generated and often inaccessible
                        if playlist_id.startswith('RD'):
                            continue
                        
                        if playlist_id not in seen_ids:
                            playlist_info = {
                                'playlist_id': playlist_id,
                                'title': video.title,
                                'url': f"https://www.youtube.com/playlist?list={playlist_id}",
                                'video': video
                            }
                            
                            # Check if this is a "Side 1" or "Side 2" playlist
                            title_lower = video.title.lower()
                            is_side_playlist = any(
                                keyword in title_lower 
                                for keyword in ['side 1', 'side 2', 'side a', 'side b', 'side one', 'side two']
                            )
                            
                            if is_side_playlist:
                                side_playlists.append(playlist_info)
                            else:
                                regular_playlists.append(playlist_info)
                            
                            seen_ids.add(playlist_id)
                            
                            # If we have enough results, combine and return
                            if len(side_playlists) + len(regular_playlists) >= max_results * 2:
                                # Prioritize side playlists, then regular playlists
                                all_results = side_playlists + regular_playlists
                                return all_results[:max_results]
        
        # Combine results with side playlists first
        all_results = side_playlists + regular_playlists
        return all_results[:max_results]
    
    def search_all_sources(self, song_data: SongData) -> Dict[str, List[SearchResult]]:
        """Search all available sources for a song."""
        results = {}
        
        try:
            results['musicbrainz'] = self.search_recordings(song_data)
        except Exception as e:
            print(f"MusicBrainz search failed: {e}")
            results['musicbrainz'] = []
        
        try:
            discogs_results = self.discogs_client.search_release(song_data)
            results['discogs'] = discogs_results
        except Exception as e:
            print(f"Discogs search failed: {e}")
            results['discogs'] = []
        
        try:
            query = f"{song_data.artist} {song_data.title}"
            results['youtube'] = self.search_youtube(query)
        except Exception as e:
            print(f"YouTube search failed: {e}")
            results['youtube'] = []
        
        return results
