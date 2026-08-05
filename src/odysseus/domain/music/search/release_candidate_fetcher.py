"""Fetch and normalize release candidates from catalog providers."""

import concurrent.futures
from typing import Any, Callable, Dict, List, Optional

from ....models.search_results import DiscogsRelease, MusicBrainzSong
from ....models.song import SongData
from .release_snapshot import ReleaseSearchSnapshot


class ReleaseCandidateFetcher:
    """Fetch unpaginated release candidates from all active providers."""

    def __init__(
        self,
        musicbrainz_client,
        discogs_client,
        spotify_client_getter: Optional[Callable[[], Any]] = None,
        apple_music_client_getter: Optional[Callable[[], Any]] = None,
        year_validator=None,
    ):
        self.musicbrainz_client = musicbrainz_client
        self.discogs_client = discogs_client
        self._spotify_client_getter = spotify_client_getter or (lambda: None)
        self._apple_music_client_getter = apple_music_client_getter or (lambda: None)
        self.year_validator = year_validator

    def _get_spotify_client(self):
        """Return the injected Spotify client when available."""
        return self._spotify_client_getter()

    def _get_apple_music_client(self):
        """Return the injected Apple Music client when configured."""
        return self._apple_music_client_getter()

    @staticmethod
    def _safe_provider_search(provider: str, search_func, *args) -> list:
        """Keep one provider failure from discarding another provider's results."""
        try:
            return search_func(*args) or []
        except Exception as error:
            print(f"{provider} search failed: {error}")
            return []

    @staticmethod
    def _client_is_authenticated(client) -> bool:
        """Safely report whether an optional catalog client can be queried."""
        if client is None:
            return False
        try:
            return bool(client.is_authenticated())
        except Exception:
            return False

    def _fetch_release_candidates(
        self,
        song_data: SongData,
        fetch_limit: int,
        release_type: Optional[str],
    ) -> ReleaseSearchSnapshot:
        """Fetch and normalize unpaginated candidates from all active providers."""
        spotify_results = []
        apple_music_results = []

        spotify_client = self._get_spotify_client()
        if self._client_is_authenticated(spotify_client):
            try:
                print(
                    f"Searching Spotify releases: {song_data.album} "
                    f"by {song_data.artist}"
                )
                spotify_data = spotify_client.search_release(
                    album=song_data.album or "",
                    artist=song_data.artist or "",
                    release_year=song_data.release_year,
                    limit=fetch_limit,
                )
                spotify_results = self._convert_spotify_to_mb_format(
                    spotify_data
                )
            except Exception as error:
                print(f"Spotify search failed: {error}")

        apple_music_client = self._get_apple_music_client()
        if self._client_is_authenticated(apple_music_client):
            try:
                print(
                    f"Searching Apple Music releases: "
                    f"{song_data.album} by {song_data.artist}"
                )
                apple_music_data = apple_music_client.search_release(
                    album=song_data.album or "",
                    artist=song_data.artist or "",
                    release_year=song_data.release_year,
                    limit=fetch_limit,
                )
                apple_music_results = self._convert_apple_music_to_mb_format(
                    apple_music_data
                )
            except Exception as error:
                print(f"Apple Music search failed: {error}")

        # Always start from zero so pagination happens after cross-source
        # deduplication. MusicBrainz and Discogs can run concurrently.
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            mb_future = executor.submit(
                self._safe_provider_search,
                "MusicBrainz",
                self.musicbrainz_client.search_release,
                song_data,
                0,
                fetch_limit,
                release_type,
            )
            discogs_future = executor.submit(
                self._safe_provider_search,
                "Discogs",
                self.discogs_client.search_release,
                song_data,
                0,
                fetch_limit,
                release_type,
            )

            mb_results = mb_future.result()
            discogs_results = discogs_future.result()

        # Resolve Discogs master years once, before storing a reusable snapshot.
        resolve_discogs_year = getattr(
            getattr(self, "year_validator", None),
            "resolve_discogs_year",
            None,
        )
        if (
            callable(resolve_discogs_year)
            and discogs_results
            and song_data.album
            and song_data.artist
        ):
            resolve_discogs_year(
                song_data.artist, song_data.album, discogs_results
            )

        return ReleaseSearchSnapshot(
            fetch_limit=fetch_limit,
            musicbrainz=mb_results,
            discogs=self._convert_discogs_to_mb_format(discogs_results),
            spotify=spotify_results,
            apple_music=apple_music_results,
        )

    def _convert_discogs_to_mb_format(
        self, discogs_results: List[DiscogsRelease]
    ) -> List[MusicBrainzSong]:
        """Convert DiscogsRelease results to MusicBrainzSong format for consistency."""
        mb_results = []
        for discogs_result in discogs_results:
            release_date = str(discogs_result.year) if discogs_result.year else None
            original_release_date = (
                str(discogs_result.master_year)
                if discogs_result.master_year
                else None
            )

            mb_result = MusicBrainzSong(
                title=discogs_result.title or discogs_result.album or "",
                artist=discogs_result.artist,
                album=discogs_result.album,
                release_date=release_date,
                original_release_date=original_release_date,
                genre=discogs_result.genre,
                cover_art_url=discogs_result.cover_art_url,
                release_type=discogs_result.release_type,
                release_status="Official",
                country=discogs_result.country,
                label=discogs_result.label,
                media_format=discogs_result.format,
                mbid=discogs_result.discogs_id,
                score=discogs_result.score,
                url=discogs_result.url,
                source="discogs"
            )
            mb_results.append(mb_result)
        return mb_results

    def _convert_apple_music_to_mb_format(
        self, apple_music_data: List[Dict[str, Any]]
    ) -> List[MusicBrainzSong]:
        """Convert Apple Music catalog editions to the shared result model."""
        return [
            MusicBrainzSong(
                title="",
                artist=item.get("artist", ""),
                album=item.get("album", ""),
                release_date=item.get("release_date"),
                original_release_date=None,
                genre=item.get("genre"),
                cover_art_url=item.get("cover_art_url"),
                release_type=item.get("release_type") or "Album",
                release_status="Official",
                label=item.get("label"),
                barcode=item.get("barcode"),
                media_format="Digital Media",
                track_count=item.get("track_count"),
                mbid=item.get("id", ""),
                score=0,
                url=item.get("url", ""),
                source="applemusic",
            )
            for item in apple_music_data
        ]

    def _convert_spotify_to_mb_format(
        self, spotify_data: List[Dict[str, Any]]
    ) -> List[MusicBrainzSong]:
        """Convert Spotify search results to MusicBrainzSong format for consistency."""
        mb_results = []
        for spotify_item in spotify_data:
            release_date = spotify_item.get("release_date")

            mb_result = MusicBrainzSong(
                title="",  # No title for releases
                artist=spotify_item.get("artist", ""),
                album=spotify_item.get("album", ""),
                release_date=release_date,
                # Spotify exposes the selected digital edition date, not a
                # trustworthy original release-group date.
                original_release_date=None,
                genre=None,
                cover_art_url=spotify_item.get("cover_art_url"),
                release_type=spotify_item.get("release_type") or "Album",
                mbid=spotify_item.get("spotify_id", ""),
                score=spotify_item.get("popularity", 0),  # Use popularity as score
                url=spotify_item.get("url", ""),
                source="spotify"
            )
            mb_results.append(mb_result)
        return mb_results
