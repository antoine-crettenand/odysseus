"""
Year validator module for validating and retrieving release years from external sources.
"""

import re
from typing import List, Optional, Dict, Tuple
from ....utils.string_utils import normalize_string


class YearValidator:
    """Handles year validation using external sources like Spotify and Discogs."""

    def __init__(self, spotify_client_getter=None, discogs_client=None):
        """
        Initialize year validator.

        Args:
            spotify_client_getter: Optional callable that returns SpotifyClient instance
            discogs_client: Optional DiscogsClient instance
        """
        self._spotify_client_getter = spotify_client_getter
        self.discogs_client = discogs_client
        self._year_validation_cache: Dict[Tuple[str, str, str], Optional[int]] = {}

    def _get_spotify_client(self):
        """Get Spotify client using the getter."""
        if self._spotify_client_getter:
            return self._spotify_client_getter()
        return None

    @staticmethod
    def _normalize_artist(artist: str) -> str:
        """Normalize provider-specific artist disambiguation suffixes."""
        without_discogs_suffix = re.sub(r"\s*\(\d+\)\s*$", "", artist or "")
        return normalize_string(without_discogs_suffix)

    @classmethod
    def _matches_release(
        cls,
        candidate_artist: str,
        candidate_album: str,
        artist: str,
        album: str,
    ) -> bool:
        """Require an exact normalized identity before trusting a year."""
        return (
            cls._normalize_artist(candidate_artist) == cls._normalize_artist(artist)
            and normalize_string(candidate_album or "")
            == normalize_string(album or "")
        )

    def _get_release_year_from_spotify(self, artist: str, album: str) -> Optional[int]:
        """
        Search Spotify for release year validation.

        Args:
            artist: Artist name
            album: Album name

        Returns:
            Release year if found, None otherwise
        """
        cache_key = (normalize_string(artist), normalize_string(album), 'spotify')
        if cache_key in self._year_validation_cache:
            return self._year_validation_cache[cache_key]

        spotify_client = self._get_spotify_client()
        if not spotify_client or not hasattr(spotify_client, 'access_token') or not spotify_client.access_token:
            self._year_validation_cache[cache_key] = None
            return None

        try:
            query = f"album:{album} artist:{artist}"
            albums = spotify_client.search_items(query, "album", limit=5)

            if not albums:
                self._year_validation_cache[cache_key] = None
                return None

            # Spotify exposes edition dates, so only use exact matches and
            # choose the earliest matching edition as a low-authority fallback.
            matching_years = []
            for album_data in albums:
                album_name = album_data.get('name', '')
                artists = album_data.get('artists', [])
                artist_name = artists[0].get('name', '') if artists else ''

                if self._matches_release(
                    artist_name, album_name, artist, album
                ):
                    release_date = album_data.get('release_date', '')
                    if release_date and len(release_date) >= 4:
                        try:
                            matching_years.append(int(release_date[:4]))
                        except ValueError:
                            continue

            if matching_years:
                year = min(matching_years)
                self._year_validation_cache[cache_key] = year
                return year

            self._year_validation_cache[cache_key] = None
            return None

        except Exception:
            self._year_validation_cache[cache_key] = None
            return None

    def _get_release_year_from_discogs(
        self,
        artist: str,
        album: str,
        release_type: Optional[str] = None
    ) -> Optional[int]:
        """
        Search Discogs for release year validation.

        Args:
            artist: Artist name
            album: Album name
            release_type: Optional release type filter

        Returns:
            Release year if found, None otherwise
        """
        if not self.discogs_client:
            return None

        cache_key = (normalize_string(artist), normalize_string(album), release_type or 'discogs')
        if cache_key in self._year_validation_cache:
            return self._year_validation_cache[cache_key]

        try:
            from ....models.song import SongData
            song_data = SongData(
                title="",
                artist=artist,
                album=album
            )

            # Search for releases (limit to 5 for performance)
            discogs_results = self.discogs_client.search_release(
                song_data, limit=5, release_type=release_type
            )

            if not discogs_results:
                self._year_validation_cache[cache_key] = None
                return None

            year = self.resolve_discogs_year(
                artist, album, discogs_results
            )
            if year:
                self._year_validation_cache[cache_key] = year
                return year

            self._year_validation_cache[cache_key] = None
            return None

        except Exception:
            self._year_validation_cache[cache_key] = None
            return None

    def resolve_discogs_year(
        self,
        artist: str,
        album: str,
        discogs_results: list,
    ) -> Optional[int]:
        """Resolve and annotate the original year from fetched Discogs rows."""
        matching_results = [
            result
            for result in discogs_results
            if self._matches_release(
                result.artist or "",
                result.album or "",
                artist,
                album,
            )
        ]
        if not matching_results:
            return None

        # A Discogs master represents the release family and is a better
        # original-year signal than any particular physical edition.
        master_years_by_id: Dict[str, int] = {}
        get_master_year = getattr(self.discogs_client, "get_master_year", None)
        if callable(get_master_year):
            for result in matching_results:
                master_id = str(getattr(result, "master_id", "") or "")
                if not master_id:
                    continue
                if master_id not in master_years_by_id:
                    try:
                        master_year = get_master_year(master_id)
                    except Exception:
                        master_year = None
                    if master_year:
                        master_years_by_id[master_id] = master_year
                if master_id in master_years_by_id:
                    result.master_year = master_years_by_id[master_id]

        if master_years_by_id:
            return min(master_years_by_id.values())

        # Without master metadata, the earliest exact Discogs edition is a
        # safer fallback than an unrelated first search result. Do not label
        # that fallback as a confirmed master year.
        edition_years = []
        for result in matching_results:
            try:
                year = int(result.year or 0)
            except (TypeError, ValueError):
                continue
            if year > 0:
                edition_years.append(year)
        return min(edition_years) if edition_years else None

    def validate_year(
        self,
        artist: str,
        album: str,
        candidate_years: List[int],
        release_type: Optional[str] = None
    ) -> Optional[int]:
        """
        Cross-reference release year from Spotify and Discogs when there's doubt.

        Args:
            artist: Artist name
            album: Album name
            candidate_years: List of candidate years to validate
            release_type: Optional release type filter

        Returns:
            Validated year if found, None otherwise
        """
        # Discogs masters describe the original release family. Spotify only
        # describes the particular digital edition returned by search.
        discogs_year = self._get_release_year_from_discogs(artist, album, release_type)
        spotify_year = self._get_release_year_from_spotify(artist, album)

        if spotify_year and discogs_year and spotify_year == discogs_year:
            return discogs_year if discogs_year in candidate_years else None

        if discogs_year and discogs_year in candidate_years:
            return discogs_year

        # A conflicting Spotify edition year must not override Discogs.
        if discogs_year and spotify_year and discogs_year != spotify_year:
            return None

        if spotify_year and spotify_year in candidate_years:
            return spotify_year

        return None

    def get_release_year(
        self,
        artist: str,
        album: str,
        release_type: Optional[str] = None
    ) -> Optional[int]:
        """
        Get release year from external sources.

        Args:
            artist: Artist name
            album: Album name
            release_type: Optional release type filter

        Returns:
            Release year if found, None otherwise
        """
        # Prefer Discogs master/earliest-edition metadata. Spotify is a
        # last-resort edition-year fallback.
        discogs_year = self._get_release_year_from_discogs(artist, album, release_type)
        if discogs_year:
            return discogs_year
        return self._get_release_year_from_spotify(artist, album)
