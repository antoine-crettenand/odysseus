"""
Spotify Client Module
A client for parsing Spotify URLs and extracting track information.
"""

import re
import requests
import base64
from typing import List, Optional, Dict, Any
from ..models.releases import Track, ReleaseInfo
from ..models.search_results import SpotifyTrack
from ..utils.file_duration_reader import format_duration_ms


class SpotifyClient:
    """Spotify client for parsing URLs and extracting track information."""

    def __init__(self, http_client=None):
        self.base_url = "https://api.spotify.com/v1"
        self.auth_url = "https://accounts.spotify.com/api/token"
        self.client_id = None
        self.client_secret = None
        self.access_token = None
        self.timeout = 30
        if http_client is None:
            from ..core.http import HttpClient
            http_client = HttpClient(
                default_timeout=self.timeout,
                default_request_delay=0.1,
            )
        self.http_client = http_client

        # Try to get credentials from environment
        import os
        self.client_id = os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

        # Authenticate if credentials are available
        if self.client_id and self.client_secret:
            self._authenticate()

    def _register_session_headers(self) -> None:
        if not hasattr(self.http_client, "session_manager"):
            return
        session_manager = self.http_client.session_manager
        headers = self._get_headers()
        if hasattr(session_manager, "register_headers"):
            session_manager.register_headers("spotify", headers)
        else:
            session_manager.get_session("spotify").headers.update(headers)

    def _authenticate(self) -> bool:
        """Authenticate with Spotify API using client credentials flow."""
        if not self.client_id or not self.client_secret:
            return False

        try:
            # Encode client credentials
            credentials = f"{self.client_id}:{self.client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()

            headers = {
                "Authorization": f"Basic {encoded_credentials}",
                "Content-Type": "application/x-www-form-urlencoded"
            }

            data = {"grant_type": "client_credentials"}

            response = requests.post(
                self.auth_url,
                headers=headers,
                data=data,
                timeout=self.timeout
            )

            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get("access_token")
                self._register_session_headers()
                return True
            else:
                return False
        except Exception:
            return False

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def _request_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        retry_auth: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Make a resilient Spotify request and refresh an expired token once."""
        response = self.http_client.get(
            url,
            params=params,
            headers=self._get_headers(),
            timeout=self.timeout,
            handle_rate_limit=True,
            rate_limit_codes=(429,),
            rate_limit_wait=30,
            session_name="spotify",
            accepted_status_codes=(401,),
        )
        if response is None:
            return None
        if response.status_code == 401:
            if retry_auth and self._authenticate():
                return self._request_json(url, params=params, retry_auth=False)
            return None
        try:
            return response.json()
        except ValueError:
            return None

    def search_items(
        self,
        query: str,
        item_type: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search a Spotify item type through the resilient transport."""
        data = self._request_json(
            f"{self.base_url}/search",
            params={
                "q": query,
                "type": item_type,
                "limit": min(max(1, limit), 50),
            },
        )
        if not data:
            return []
        return data.get(f"{item_type}s", {}).get("items", []) or []

    def parse_spotify_url(self, url: str) -> Optional[Dict[str, str]]:
        """
        Parse a Spotify URL and extract type and ID.

        Supports:
        - Playlist: https://open.spotify.com/playlist/{id}
        - Album: https://open.spotify.com/album/{id}
        - Track: https://open.spotify.com/track/{id}
        - Short URLs: spotify:playlist:{id}, spotify:album:{id}, etc.

        Returns:
            Dict with 'type' (playlist/album/track) and 'id', or None if invalid
        """
        if not url:
            return None

        collection_match = re.search(
            r"open\.spotify\.com/user/([a-zA-Z0-9]+)/collection",
            url,
        )
        if collection_match:
            return {"type": "collection", "id": collection_match.group(1)}

        # Handle spotify: URIs
        if url.startswith("spotify:"):
            parts = url.split(":")
            if len(parts) >= 3:
                return {"type": parts[1], "id": parts[2].split("?")[0]}

        # Handle web URLs (with optional locale prefixes like /intl-fr/, /intl-en/, etc.)
        patterns = [
            r"open\.spotify\.com(?:/[^/]+)?/(playlist|album|track)/([a-zA-Z0-9]+)",
            r"spotify\.com(?:/[^/]+)?/(playlist|album|track)/([a-zA-Z0-9]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return {"type": match.group(1), "id": match.group(2)}

        return None

    def _extract_cover_art(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract cover art URL from images array."""
        images = data.get("images", [])
        return images[0].get("url") if images else None

    def _build_track_from_data(self, item: Dict[str, Any], default_artist: str, position: Optional[int] = None) -> Optional[Track]:
        """Build Track object from Spotify track data."""
        # Handle nested track data (playlists)
        track_data = item.get("track") if item.get("track") is not None else item

        if not track_data:
            return None

        track_name = track_data.get("name", "Unknown")
        artists = track_data.get("artists", [])
        artist_name = artists[0].get("name", default_artist) if artists else default_artist
        duration_ms = track_data.get("duration_ms", 0)
        duration = format_duration_ms(duration_ms)

        track_position = position if position is not None else track_data.get("track_number", 1)

        return Track(
            position=track_position,
            title=track_name,
            artist=artist_name,
            duration=duration
        )

    def _fetch_paginated_items(self, url: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch paginated items from Spotify API."""
        items, offset = [], 0
        while True:
            data = self._request_json(
                url,
                params={"limit": limit, "offset": offset},
            )
            if not data:
                break
            page_items = data.get("items", [])
            if not page_items:
                break
            items.extend(page_items)
            if not data.get("next"):
                break
            offset += limit
        return items

    def _get_release_info(self, resource_type: str, resource_id: str) -> Optional[ReleaseInfo]:
        """Unified method to get release info for playlists, albums, or tracks."""
        if not self.access_token:
            raise Exception("Spotify API authentication required. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables.")

        try:
            url = f"{self.base_url}/{resource_type}s/{resource_id}"
            resource_data = self._request_json(url)
            if not resource_data:
                return None
            config = {
                "playlist": {
                    "title": resource_data.get("name", "Unknown Playlist"),
                    "artist": resource_data.get("owner", {}).get("display_name", "Unknown"),
                    "release_type": "Playlist",
                    "release_date": None,
                    "genre": None,
                    "tracks_url": f"{url}/tracks",
                    "limit": 100,
                    "use_nested": True
                },
                "album": {
                    "title": resource_data.get("name", "Unknown Album"),
                    "artist": (resource_data.get("artists", [])[0].get("name", "Unknown Artist") if resource_data.get("artists") else "Unknown Artist"),
                    "release_type": "Album",
                    "release_date": resource_data.get("release_date"),
                    "genre": (resource_data.get("genres", [])[0] if resource_data.get("genres") else None),
                    "tracks_url": f"{url}/tracks",
                    "limit": 50,
                    "use_nested": False
                },
                "track": {
                    "title": resource_data.get("album", {}).get("name", "Unknown Album"),
                    "artist": (resource_data.get("artists", [])[0].get("name", "Unknown Artist") if resource_data.get("artists") else "Unknown Artist"),
                    "release_type": "Track",
                    "release_date": None,
                    "genre": None,
                    "tracks_url": None,
                    "limit": None,
                    "use_nested": False
                }
            }[resource_type]

            cover_art_data = resource_data if resource_type != "track" else resource_data.get("album", {})
            tracks = []

            if resource_type == "track":
                track = self._build_track_from_data(resource_data, config["artist"], position=1)
                if track:
                    tracks = [track]
            else:
                items = self._fetch_paginated_items(config["tracks_url"], config["limit"])
                for idx, item in enumerate(items, start=1):
                    track = self._build_track_from_data(item, config["artist"], position=idx if config["use_nested"] else None)
                    if track:
                        tracks.append(track)

            return ReleaseInfo(
                title=config["title"],
                artist=config["artist"],
                release_date=config["release_date"],
                genre=config["genre"],
                release_type=config["release_type"],
                url=f"https://open.spotify.com/{resource_type}/{resource_id}",
                cover_art_url=self._extract_cover_art(cover_art_data),
                tracks=tracks
            )
        except Exception as e:
            raise Exception(f"Failed to get {resource_type} tracks: {str(e)}")

    def get_playlist_tracks(self, playlist_id: str) -> Optional[ReleaseInfo]:
        return self._get_release_info("playlist", playlist_id)

    def get_album_tracks(self, album_id: str) -> Optional[ReleaseInfo]:
        return self._get_release_info("album", album_id)

    def get_track_info(self, track_id: str) -> Optional[ReleaseInfo]:
        return self._get_release_info("track", track_id)

    def get_tracks_from_url(self, url: str) -> Optional[ReleaseInfo]:
        """
        Parse a Spotify URL and get tracks from it.

        Supports playlists, albums, and tracks.

        Returns:
            ReleaseInfo object with tracks, or None if failed
        """
        parsed = self.parse_spotify_url(url)
        if not parsed:
            raise ValueError(f"Invalid Spotify URL: {url}")

        url_type = parsed["type"]
        url_id = parsed["id"]

        if url_type == "playlist":
            return self.get_playlist_tracks(url_id)
        elif url_type == "album":
            return self.get_album_tracks(url_id)
        elif url_type == "track":
            return self.get_track_info(url_id)
        else:
            raise ValueError(f"Unsupported Spotify URL type: {url_type}")

    def _extract_release_year(self, release_date: Optional[str]) -> Optional[int]:
        """
        Extract year from Spotify release_date field.

        Spotify release_date can be in formats:
        - "YYYY" (e.g., "1972")
        - "YYYY-MM" (e.g., "1972-03")
        - "YYYY-MM-DD" (e.g., "1972-03-15")

        Returns:
            Year as integer, or None if not available
        """
        if not release_date:
            return None

        # Extract year (first 4 digits)
        match = re.match(r'^(\d{4})', release_date)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    def get_playlist_releases(self, playlist_id: str) -> List[tuple]:
        """Get unique artist-album-year tuples from a Spotify playlist."""
        if not self.access_token:
            raise Exception("Spotify API authentication required. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables.")

        artist_albums = set()
        items = self._fetch_paginated_items(f"{self.base_url}/playlists/{playlist_id}/tracks", limit=100)

        for item in items:
            track_data = item.get("track")
            if not track_data:
                continue
            artists = track_data.get("artists", [])
            artist_name = artists[0].get("name", "Unknown Artist") if artists else "Unknown Artist"
            album_data = track_data.get("album", {})
            release_year = self._extract_release_year(album_data.get("release_date"))
            artist_albums.add((artist_name, album_data.get("name", "Unknown Album"), release_year))

        return sorted(artist_albums, key=lambda x: (x[0].lower(), x[1].lower(), x[2] or 0))

    def _fetch_user_collection_items(
        self,
        access_token: str,
        collection_type: str,
    ) -> List[Dict[str, Any]]:
        endpoint = "tracks" if collection_type == "tracks" else "albums"
        url = f"{self.base_url}/me/{endpoint}"
        params = {"limit": 50}
        items = []
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        while url:
            response = self.http_client.get(
                url,
                params=params,
                headers=headers,
                session_name="spotify-user",
                accepted_status_codes=(401,),
                handle_rate_limit=True,
            )
            if response is None:
                raise RuntimeError("Failed to fetch Spotify user collection")
            if response.status_code == 401:
                raise ValueError("Spotify user access token is invalid or expired")
            data = response.json()
            items.extend(data.get("items", []))
            url = data.get("next")
            params = None
        return items

    def get_user_collection_releases(
        self,
        access_token: str,
        collection_type: str = "tracks",
    ) -> List[tuple]:
        """Return unique releases from liked tracks and/or saved albums."""
        if collection_type not in {"tracks", "albums", "both"}:
            raise ValueError("Collection type must be tracks, albums, or both")
        requested = (
            ("tracks", "albums")
            if collection_type == "both"
            else (collection_type,)
        )
        releases = set()
        for item_type in requested:
            for item in self._fetch_user_collection_items(
                access_token,
                item_type,
            ):
                if item_type == "tracks":
                    track = item.get("track") or {}
                    album = track.get("album") or {}
                    artists = track.get("artists") or album.get("artists") or []
                else:
                    album = item.get("album") or {}
                    artists = album.get("artists") or []
                artist = (
                    artists[0].get("name", "Unknown Artist")
                    if artists
                    else "Unknown Artist"
                )
                releases.add(
                    (
                        artist,
                        album.get("name", "Unknown Album"),
                        self._extract_release_year(album.get("release_date")),
                    )
                )
        return sorted(
            releases,
            key=lambda row: (row[0].lower(), row[1].lower(), row[2] or 0),
        )

    def is_authenticated(self) -> bool:
        """Check if Spotify API is authenticated."""
        return self.access_token is not None

    def search_release(self, album: str, artist: str, release_year: Optional[int] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for albums/releases on Spotify."""
        if not self.access_token:
            return []

        try:
            query_parts = [f'artist:"{artist}"' if artist else '', f'album:"{album}"' if album else '']
            query = ' '.join(q for q in query_parts if q) or f'{artist} {album}'

            albums = self.search_items(query, "album", limit=limit)
            results = []
            for album_data in albums:
                release_year_spotify = self._extract_release_year(album_data.get("release_date", ""))
                if release_year and release_year_spotify and release_year_spotify != release_year:
                    continue
                artists = album_data.get("artists", [])
                images = album_data.get("images", [])
                album_id = album_data.get("id", "")
                results.append({
                    "album": album_data.get("name", ""),
                    "artist": artists[0].get("name", "") if artists else "",
                    "release_date": album_data.get("release_date", ""),
                    "release_year": release_year_spotify,
                    "cover_art_url": images[0].get("url") if images else None,
                    "spotify_id": album_id,
                    "url": f"https://open.spotify.com/album/{album_id}",
                    "popularity": album_data.get("popularity", 0)
                })
            return results
        except Exception:
            return []
