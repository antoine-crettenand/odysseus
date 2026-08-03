"""Optional Apple Music catalog client used for edition enrichment."""

from typing import Any, Dict, List, Optional

from ..core.config import APPLE_MUSIC_CONFIG
from ..models.releases import ReleaseInfo, Track
from ..utils.file_duration_reader import format_duration_ms
from ..utils.string_utils import normalize_string


class AppleMusicClient:
    """Search Apple Music without making it an original-date authority."""

    def __init__(
        self,
        http_client=None,
        *,
        developer_token: Optional[str] = None,
        storefront: Optional[str] = None,
    ) -> None:
        if http_client is None:
            from ..core.http import HttpClient

            http_client = HttpClient()
        self.http_client = http_client
        self.base_url = APPLE_MUSIC_CONFIG["BASE_URL"]
        self.developer_token = (
            APPLE_MUSIC_CONFIG["DEVELOPER_TOKEN"]
            if developer_token is None
            else developer_token
        )
        self.storefront = storefront or APPLE_MUSIC_CONFIG["STOREFRONT"]
        self.timeout = APPLE_MUSIC_CONFIG["TIMEOUT"]
        self.request_delay = APPLE_MUSIC_CONFIG["REQUEST_DELAY"]
        self.max_results = APPLE_MUSIC_CONFIG["MAX_RESULTS"]

    def is_authenticated(self) -> bool:
        """Return whether a developer token was configured."""
        return bool(self.developer_token)

    def set_credentials(self, developer_token: Optional[str], storefront: str) -> None:
        """Apply catalog credentials and storefront without recreating the client."""
        self.developer_token = developer_token or ""
        self.storefront = (storefront or "us").lower()

    @property
    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.developer_token}"}

    def _get_json(self, path: str, params: Optional[Dict[str, Any]] = None):
        if not self.is_authenticated():
            return None
        return self.http_client.get_json(
            f"{self.base_url}{path}",
            params=params,
            headers=self._headers,
            timeout=self.timeout,
            handle_rate_limit=True,
            session_name="applemusic",
            request_delay=self.request_delay,
        )

    @staticmethod
    def _artwork_url(artwork: Optional[Dict[str, Any]], size: int = 500) -> Optional[str]:
        template = (artwork or {}).get("url")
        if not template:
            return None
        return template.replace("{w}", str(size)).replace("{h}", str(size))

    @staticmethod
    def _album_artist_matches(attributes: Dict[str, Any], album: str, artist: str) -> bool:
        return (
            normalize_string(attributes.get("name", "")) == normalize_string(album)
            and normalize_string(attributes.get("artistName", ""))
            == normalize_string(artist)
        )

    def search_release(
        self,
        *,
        album: str,
        artist: str,
        release_year: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return exact catalog-album matches in the configured storefront."""
        if not self.is_authenticated() or not album or not artist:
            return []
        requested_limit = max(1, min(limit or self.max_results, 25))
        data = self._get_json(
            f"/catalog/{self.storefront}/search",
            {
                "term": f"{artist} {album}",
                "types": "albums",
                "limit": requested_limit,
            },
        )
        albums = (((data or {}).get("results") or {}).get("albums") or {}).get("data", [])
        results = []
        for item in albums:
            attributes = item.get("attributes") or {}
            if not self._album_artist_matches(attributes, album, artist):
                continue
            release_date = attributes.get("releaseDate")
            if release_year and str(release_date or "")[:4] != str(release_year):
                continue
            results.append(
                {
                    "id": item.get("id", ""),
                    "album": attributes.get("name", ""),
                    "artist": attributes.get("artistName", ""),
                    "release_date": release_date,
                    "release_type": "Compilation" if attributes.get("isCompilation") else "Album",
                    "cover_art_url": self._artwork_url(attributes.get("artwork")),
                    "url": attributes.get("url", ""),
                    "genre": (attributes.get("genreNames") or [None])[0],
                    "label": attributes.get("recordLabel"),
                    "barcode": attributes.get("upc"),
                    "track_count": attributes.get("trackCount"),
                    "copyright": attributes.get("copyright"),
                }
            )
        return results

    def get_album_tracks(self, album_id: str) -> Optional[ReleaseInfo]:
        """Load an Apple Music edition and its storefront track listing."""
        data = self._get_json(
            f"/catalog/{self.storefront}/albums/{album_id}",
            {"include": "tracks"},
        )
        albums = (data or {}).get("data", [])
        if not albums:
            return None
        album = albums[0]
        attributes = album.get("attributes") or {}
        track_rows = (((album.get("relationships") or {}).get("tracks") or {}).get("data", []))
        disc_track_counts: Dict[int, int] = {}
        for row in track_rows:
            row_attributes = row.get("attributes") or {}
            disc_number = row_attributes.get("discNumber") or 1
            disc_track_counts[disc_number] = (
                disc_track_counts.get(disc_number, 0) + 1
            )
        total_discs = max(disc_track_counts, default=1)
        tracks = []
        for index, row in enumerate(track_rows, start=1):
            track = row.get("attributes") or {}
            duration_ms = track.get("durationInMillis")
            disc_number = track.get("discNumber") or 1
            tracks.append(
                Track(
                    position=index,
                    title=track.get("name", ""),
                    artist=track.get("artistName") or attributes.get("artistName", ""),
                    duration=format_duration_ms(duration_ms) if duration_ms else None,
                    mbid=None,
                    isrc=track.get("isrc"),
                    source_id=row.get("id"),
                    disc_number=disc_number,
                    disc_track_number=track.get("trackNumber") or index,
                    disc_total_tracks=disc_track_counts.get(disc_number),
                )
            )
        return ReleaseInfo(
            title=attributes.get("name", ""),
            artist=attributes.get("artistName", ""),
            release_date=attributes.get("releaseDate"),
            original_release_date=None,
            genre=(attributes.get("genreNames") or [None])[0],
            release_type="Compilation" if attributes.get("isCompilation") else "Album",
            release_status="Official",
            label=attributes.get("recordLabel"),
            barcode=attributes.get("upc"),
            media_format="Digital Media",
            mbid=album_id,
            url=attributes.get("url", ""),
            cover_art_url=self._artwork_url(attributes.get("artwork")),
            tracks=tracks,
            copyright=attributes.get("copyright"),
            total_discs=total_discs,
            source="applemusic",
        )
