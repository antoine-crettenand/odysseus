"""Local ranking and filtering of release-search candidates."""

from typing import List, Optional

from ....models.search_results import MusicBrainzSong
from ..common.date_utils import parse_release_date, release_year_in_range
from .release_snapshot import ReleaseSearchSnapshot


class ReleaseRanker:
    """Apply type/year filters, provider priority, deduplication, and sort."""

    def __init__(self, deduplicator, deduplicate_with_priority=None):
        self.deduplicator = deduplicator
        self._deduplicate_with_priority = deduplicate_with_priority

    def _dedupe_with_priority(self, primary, secondary):
        if self._deduplicate_with_priority is not None:
            return self._deduplicate_with_priority(primary, secondary)
        return self.deduplicator.deduplicate_with_priority(primary, secondary)

    @staticmethod
    def _filter_release_type(
        results: List[MusicBrainzSong],
        release_type: Optional[str],
    ) -> List[MusicBrainzSong]:
        """Filter candidates before cross-provider deduplication."""
        if not release_type:
            return results
        expected = release_type.casefold()
        return [
            result
            for result in results
            if result.release_type
            and result.release_type.casefold() == expected
        ]

    @staticmethod
    def _filter_release_years(
        results: List[MusicBrainzSong],
        year_from: Optional[int],
        year_to: Optional[int],
    ) -> List[MusicBrainzSong]:
        """Filter releases by inclusive year bounds before deduplication."""
        return [
            result
            for result in results
            if release_year_in_range(result, year_from, year_to)
        ]

    def _rank_release_candidates(
        self,
        snapshot: ReleaseSearchSnapshot,
        release_type: Optional[str],
        year_from: Optional[int],
        year_to: Optional[int],
    ) -> List[MusicBrainzSong]:
        """Apply local refinements, provider priority, deduplication, and sort."""
        spotify_results = self._filter_release_type(
            snapshot.spotify, release_type
        )
        apple_music_results = self._filter_release_type(
            snapshot.apple_music, release_type
        )
        mb_results = self._filter_release_type(
            snapshot.musicbrainz, release_type
        )
        discogs_results = self._filter_release_type(
            snapshot.discogs, release_type
        )

        spotify_results = self._filter_release_years(
            spotify_results, year_from, year_to
        )
        apple_music_results = self._filter_release_years(
            apple_music_results, year_from, year_to
        )
        mb_results = self._filter_release_years(
            mb_results, year_from, year_to
        )
        discogs_results = self._filter_release_years(
            discogs_results, year_from, year_to
        )

        # MusicBrainz is the metadata authority, followed by Discogs, Apple
        # Music, and Spotify for editions absent from the preceding catalogs.
        all_results = self._dedupe_with_priority(mb_results, discogs_results)
        all_results = self._dedupe_with_priority(
            all_results, apple_music_results
        )
        all_results = self._dedupe_with_priority(all_results, spotify_results)

        def sort_key(result):
            original_date = parse_release_date(
                result.original_release_date
            ) or (9999, 12, 31)
            edition_date = parse_release_date(
                result.release_date
            ) or (9999, 12, 31)
            primary_date = min(original_date, edition_date)
            is_true_original = bool(
                result.original_release_date
                and result.release_date
                and result.original_release_date == result.release_date
            )
            return (
                primary_date,
                0 if is_true_original else 1,
                -(result.score or 0),
            )

        all_results.sort(key=sort_key)
        return all_results
