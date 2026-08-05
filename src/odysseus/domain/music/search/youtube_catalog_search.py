"""YouTube video, full-album, and playlist catalog search."""

import re
from typing import Any, Dict, List, Optional

from ....models.search_results import YouTubeVideo
from ....utils.pattern_matcher import PatternMatcher


class YouTubeCatalogSearch:
    """Search YouTube for tracks, full albums, and playlists."""

    def __init__(self, youtube_client_factory):
        self.youtube_client_factory = youtube_client_factory
        self.youtube_client = None

    def search_youtube(
        self, query: str, max_results: int = 3, offset: int = 0
    ) -> List[YouTubeVideo]:
        """Search YouTube for videos."""
        offset = max(0, offset)
        fetch_limit = max_results + offset
        self.youtube_client = self.youtube_client_factory(query, fetch_limit)
        return self.youtube_client.videos[offset:offset + max_results]

    def search_full_album(
        self,
        artist: str,
        album: str,
        max_results: int = 5,
        release_year: Optional[str] = None,
    ) -> List[YouTubeVideo]:
        """
        Search YouTube for full album videos (complete album in one video).

        Args:
            artist: Artist name
            album: Album title
            max_results: Maximum number of results to return
            release_year: Optional release year to improve search accuracy
        """
        queries = self._build_full_album_queries(artist, album, release_year)
        all_results = []
        seen_ids = set()

        for query in queries:
            client = self.youtube_client_factory(query, max_results)
            for video in client.videos:
                if video.video_id and video.video_id not in seen_ids:
                    if not PatternMatcher.has_full_album_keyword(video.title):
                        continue

                    if PatternMatcher.is_live_or_non_album_video(video.title):
                        continue

                    all_results.append(video)
                    seen_ids.add(video.video_id)
                    if len(all_results) >= max_results:
                        return all_results[:max_results]

        return all_results[:max_results]

    def _build_full_album_queries(
        self, artist: str, album: str, release_year: Optional[str] = None
    ) -> List[str]:
        """
        Build search queries for full album videos.

        Args:
            artist: Artist name
            album: Album title
            release_year: Optional release year

        Returns:
            List of search query strings
        """
        if release_year:
            return [
                f'"{artist}" "{album}" {release_year} full album',
                f"{artist} {album} {release_year} full album",
                f"{artist} {album} full album {release_year}",
                f"{artist} {album} full album",
                f"{artist} {album} complete album",
            ]
        else:
            return [
                f'"{artist}" "{album}" full album',  # Use quotes for exact phrase matching
                f"{artist} {album} full album",
                f"{artist} {album} complete album",
                f"{artist} {album} album full",
                f"{artist} {album} full",
            ]

    def search_playlist(
        self,
        artist: str,
        album: str,
        max_results: int = 5,
        track_titles: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
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
                client = self.youtube_client_factory(query, results_per_query)
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
