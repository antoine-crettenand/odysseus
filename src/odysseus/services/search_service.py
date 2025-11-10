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
from .result_deduplicator import ResultDeduplicator
from .year_validator import YearValidator


class SearchService:
    """Service for searching music across multiple sources."""
    
    def __init__(self):
        self.musicbrainz_client = MusicBrainzClient()
        self.discogs_client = DiscogsClient()
        self.youtube_client = None
        
        # Initialize helper services
        self.year_validator = YearValidator(
            spotify_client_getter=self._get_spotify_client,
            discogs_client=self.discogs_client
        )
        self.deduplicator = ResultDeduplicator(year_validator=self.year_validator)
        
        self._spotify_client = None  # Lazy initialization
    
    
    def _get_release_year(self, release_date: Optional[str]) -> Optional[str]:
        """Extract year from release date string."""
        if not release_date or release_date.strip() == "":
            return None
        year_part = release_date[:4] if len(release_date) >= 4 else None
        return year_part if year_part and year_part.isdigit() else None
    
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
    
    def _get_spotify_client(self):
        """Get Spotify client with lazy initialization."""
        if self._spotify_client is None:
            try:
                from ..clients.spotify import SpotifyClient
                self._spotify_client = SpotifyClient()
            except Exception:
                self._spotify_client = False  # Mark as unavailable
        return self._spotify_client if self._spotify_client else None
    
    def _deduplicate_results(self, results: List[MusicBrainzSong], release_type: Optional[str] = None) -> List[MusicBrainzSong]:
        """Delegate to ResultDeduplicator."""
        return self.deduplicator.deduplicate_results(results, release_type)
    
    def _deduplicate_with_priority(self, mb_results: List[MusicBrainzSong], discogs_results: List[MusicBrainzSong]) -> List[MusicBrainzSong]:
        """Delegate to ResultDeduplicator."""
        return self.deduplicator.deduplicate_with_priority(mb_results, discogs_results)
    
    def search_recordings(self, song_data: SongData, offset: int = 0, limit: Optional[int] = None) -> List[MusicBrainzSong]:
        """Search for recordings in MusicBrainz."""
        results = self.musicbrainz_client.search_recording(song_data, offset=offset, limit=limit)
        return self.deduplicator.deduplicate_results(results, release_type=None)
    
    def search_releases(self, song_data: SongData, offset: int = 0, limit: Optional[int] = None, release_type: Optional[str] = None) -> List[MusicBrainzSong]:
        """Search for releases in MusicBrainz and Discogs in parallel.
        MusicBrainz results are prioritized; Discogs only fills gaps.
        
        Args:
            song_data: Song information to search for
            offset: Offset for pagination
            limit: Maximum number of results
            release_type: Optional release type filter (e.g., "Album", "Single", "EP", "Compilation", "Live", etc.)
        """
        # Fetch more results than needed to ensure we get all duplicates for proper deduplication
        # This ensures we can find the earliest release even if it's not in the first page
        # We need to fetch enough to get all duplicates, then deduplicate, then paginate
        fetch_limit = (limit or self.max_results) * 5 if limit else 50  # Fetch 5x the limit to ensure we get all duplicates
        
        # Search both sources in parallel - always start from 0 to get all results for proper deduplication
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            mb_future = executor.submit(
                self.musicbrainz_client.search_release,
                song_data, 0, fetch_limit, None  # Always start from 0, fetch more results
            )
            discogs_future = executor.submit(
                self.discogs_client.search_release,
                song_data, 0, fetch_limit, release_type  # Always start from 0
            )
            
            mb_results = mb_future.result()
            discogs_results = discogs_future.result()
        
        # Convert Discogs to MusicBrainz format
        discogs_formatted = self._convert_discogs_to_mb_format(discogs_results)
        
        # Use priority-based deduplication: MusicBrainz first, Discogs only fills gaps
        # This deduplicates ALL results to find the best (earliest) release
        all_results = self._deduplicate_with_priority(mb_results, discogs_formatted)
        
        if release_type:
            filtered_results = []
            for result in all_results:
                if result.release_type and result.release_type.lower() == release_type.lower():
                    filtered_results.append(result)
            all_results = filtered_results
        
        # Sort results by original release date (earliest first) to prioritize original releases
        # Use original_release_date if available, otherwise use release_date
        # This ensures that even if deduplication kept the earliest, the display order is correct
        all_results.sort(key=lambda r: (
            self._parse_release_date(r.original_release_date or r.release_date) or (9999, 12, 31),  # Put items without dates at end
            -(r.score if r.score else 0)  # Then by score descending
        ))
        
        # Apply pagination AFTER deduplication and sorting
        if offset > 0:
            all_results = all_results[offset:]
        
        if limit and len(all_results) > limit:
            all_results = all_results[:limit]
        
        return all_results
    
    def search_artist_releases(self, artist: str, year: Optional[int] = None, release_type: Optional[str] = None, include_compilations: bool = False) -> List[MusicBrainzSong]:
        """Search for releases by a specific artist in MusicBrainz.
        Discogs is only consulted during deduplication for year validation when there's ambiguity.
        
        Args:
            artist: Artist name to search for
            year: Optional year filter
            release_type: Optional release type filter (e.g., "Album", "Single", "EP", "Compilation", "Live", etc.)
            include_compilations: If True, also search for compilations where the artist appears as a track artist
        """
        # Search MusicBrainz only - it usually has comprehensive coverage
        # Discogs is only used for year validation during deduplication when there's ambiguity
        mb_results = self.musicbrainz_client.search_artist_releases(artist, year, None, release_type)
        
        # Deduplicate MusicBrainz results only (no initial Discogs search)
        # Pass release_type so validation can filter Discogs searches
        all_results = self._deduplicate_results(mb_results, release_type=release_type)
        
        # If include_compilations is True, also search for compilations where artist appears on tracks
        if include_compilations:
            compilation_results = self.musicbrainz_client.search_artist_compilations(artist, year)
            # Deduplicate compilation results against existing results
            existing_keys = {self._create_deduplication_key(r) for r in all_results}
            for comp_result in compilation_results:
                comp_key = self._create_deduplication_key(comp_result)
                if comp_key[0] and comp_key not in existing_keys:
                    all_results.append(comp_result)
                    existing_keys.add(comp_key)
        
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
    
    def search_full_album(self, artist: str, album: str, max_results: int = 5, release_year: Optional[str] = None) -> List[YouTubeVideo]:
        """
        Search YouTube for full album videos (complete album in one video).
        
        Args:
            artist: Artist name
            album: Album title
            max_results: Maximum number of results to return
            release_year: Optional release year to improve search accuracy
        """
        # Build queries with year if available (helps distinguish between albums with similar names)
        if release_year:
            queries = [
                f'"{artist}" "{album}" {release_year} full album',
                f"{artist} {album} {release_year} full album",
                f"{artist} {album} full album {release_year}",
                f"{artist} {album} full album",
                f"{artist} {album} complete album",
            ]
        else:
            queries = [
                f'"{artist}" "{album}" full album',  # Use quotes for exact phrase matching
                f"{artist} {album} full album",
                f"{artist} {album} complete album",
                f"{artist} {album} album full",
                f"{artist} {album} full",
            ]
        
        all_results = []
        seen_ids = set()
        
        # Use word boundaries to avoid matching "live" in words like "lives", "alive", "deliver", etc.
        live_keyword_patterns = [
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
        # Keywords that don't need word boundaries
        live_keywords_simple = [
            'unplugged',
            'mtv unplugged',
            'kexp',
            'npr tiny desk',
            'audience',
            'applause',
            'encore'
        ]
        
        # Known concert venues (these are strong indicators of live performances)
        concert_venues = [
            'red rocks',
            'madison square garden',
            'msg',
            'royal albert hall',
            'apollo theater',
            'apollo theatre',
            'fillmore',
            'hollywood bowl',
            'coachella',
            'glastonbury',
            'woodstock',
            'monterey pop',
            'newport folk',
            'newport jazz',
            'montreux jazz',
            'blue note',
            'village vanguard',
            'ronnie scott\'s',
            'ronnie scotts',
            'troubadour',
            'whisky a go go',
            'cbgb',
            'palladium',
            'hammersmith',
            'brixton academy',
            'o2 arena',
            'wembley',
            'festival',
            'festival de',
            'rock in rio',
            'lollapalooza',
            'bonnaroo',
            'sxsw',
            'austin city limits',
            'acoustic',
            'acoustic session'
        ]
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
                    
                    # Check for live keywords using word boundaries to avoid false positives
                    is_live = False
                    for pattern in live_keyword_patterns:
                        if re.search(pattern, title_lower):
                            is_live = True
                            break
                    if not is_live:
                        # Check for "at [venue]" pattern (e.g., "at Red Rocks", "at Madison Square Garden")
                        # This catches live performances at venues even without the word "live"
                        if re.search(r'\bat\s+[a-z\s]+(?:rocks|garden|hall|theater|theatre|bowl|arena|festival|acoustic)', title_lower):
                            is_live = True
                    if not is_live:
                        # Check for known concert venues
                        is_live = any(venue in title_lower for venue in concert_venues)
                    if not is_live:
                        # Check for standalone "live" word (e.g., "PHANTOM ISLAND LIVE")
                        if re.search(r'\blive\b', title_lower):
                            is_live = True
                    if not is_live:
                        is_live = any(keyword in title_lower for keyword in live_keywords_simple)
                    if not is_live:
                        # Check for year patterns that suggest live recordings (e.g., "at Red Rocks 2024")
                        # Pattern: "at [venue] [year]" where year is 4 digits
                        if re.search(r'\bat\s+[a-z\s]+\s+\d{4}\b', title_lower):
                            is_live = True
                    
                    is_non_album = any(keyword in title_lower for keyword in non_album_keywords)
                    if is_live or is_non_album:
                        continue
                    
                    all_results.append(video)
                    seen_ids.add(video.video_id)
                    if len(all_results) >= max_results:
                        return all_results[:max_results]
        
        return all_results[:max_results]
    
    def search_playlist(self, artist: str, album: str, max_results: int = 5, track_titles: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Search YouTube for playlists matching the album.
        
        Args:
            artist: Artist name
            album: Album name
            max_results: Maximum number of playlists to return
            track_titles: Optional list of track titles from the album to search for playlists containing them
        """
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
            f"{artist} {album}",  # More general search
            f"{album} playlist",  # Search without artist (in case of compilation albums)
        ]
        
        # Also search for playlists using individual track titles (helps find playlists that contain the tracks)
        if track_titles:
            # Use first few track titles to find playlists that might contain album tracks
            for track_title in track_titles[:3]:  # Limit to first 3 tracks to avoid too many queries
                queries.append(f"{artist} {track_title} playlist")
                queries.append(f"{track_title} playlist")
        
        all_results = []
        seen_ids = set()
        # Separate lists for regular playlists and side playlists (prioritize side playlists)
        side_playlists = []
        regular_playlists = []
        
        # Increase results per query to be more thorough
        results_per_query = max(max_results * 3, 15)
        
        for query in queries:
            try:
                client = YouTubeClient(query, results_per_query)
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
            except Exception:
                # Continue with next query if one fails
                continue
        
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
