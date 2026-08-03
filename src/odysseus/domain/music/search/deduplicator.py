"""
Result deduplicator module for removing duplicate search results.
"""

from typing import List, Optional, Dict, Tuple
from ....models.search_results import MusicBrainzSong
from ....utils.string_utils import normalize_string
from ..common.date_utils import extract_year, parse_release_date


class ResultDeduplicator:
    """Handles deduplication of search results."""

    def __init__(self, year_validator=None):
        """
        Initialize result deduplicator.

        Args:
            year_validator: Optional YearValidator instance for year validation
        """
        self.year_validator = year_validator

    def _create_deduplication_key(
        self,
        result: MusicBrainzSong,
        *,
        recordings: bool = False,
    ) -> Tuple[str, str]:
        """
        Create a deduplication key for a search result (no year).

        For releases: uses album (or title if album is empty) and artist.
        For recordings: uses title and artist (album is ignored so distinct
        tracks from the same release stay distinct).
        """
        title = normalize_string(result.title)
        album = normalize_string(result.album)
        artist = normalize_string(result.artist)

        if recordings:
            primary_key = title or album or ""
            return (primary_key, artist)

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
        """Delegate release-date parsing to the shared domain utility."""
        return parse_release_date(release_date)

    def _is_remaster_or_reissue(self, result: MusicBrainzSong) -> bool:
        """
        Check if a release is likely a remaster, reissue, or re-release.
        Returns True if it appears to be a remaster/reissue.
        """
        album_lower = (result.album or "").lower()
        title_lower = (result.title or "").lower()

        remaster_keywords = [
            'remaster', 'reissue', 're-release', 'remastered', 'deluxe',
            'anniversary', 'edition', 'expanded', 'bonus', 'special edition',
            'remastered version', 'digitally remastered', 'remastered edition'
        ]

        for keyword in remaster_keywords:
            if keyword in album_lower or keyword in title_lower:
                return True

        return False

    def deduplicate_results(
        self,
        results: List[MusicBrainzSong],
        release_type: Optional[str] = None,
        *,
        recordings: bool = False,
    ) -> List[MusicBrainzSong]:
        """
        Remove duplicate results based on a normalized identity key.

        Releases key on (album, artist). Recordings key on (title, artist).
        When duplicates are found, prioritizes:
        1. Original releases (where release_date matches original_release_date)
        2. Original releases (earliest date, not remasters/reissues)
        3. Earliest original release date (strongly prefer earliest year - likely original)
        4. Cross-reference with year validator when in doubt
        5. Highest score
        """
        if not results:
            return results

        grouped_by_key: Dict[Tuple[str, str], List[MusicBrainzSong]] = {}

        for result in results:
            key = self._create_deduplication_key(result, recordings=recordings)

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
                # Separate remasters/reissues from originals
                originals = [r for r in group if not self._is_remaster_or_reissue(r)]
                remasters = [r for r in group if self._is_remaster_or_reissue(r)]

                # Prefer originals over remasters
                candidates = originals if originals else remasters

                # Separate candidates into:
                # 1. Original releases (release_date matches original_release_date)
                # 2. Re-releases (release_date differs from original_release_date)
                true_originals = []
                re_releases = []
                candidates_without_original_date = []

                for result in candidates:
                    # Different date precision ("1971" vs "1971-03-19")
                    # should not make an original edition look like a reissue.
                    original_year = extract_year(result.original_release_date)
                    edition_year = extract_year(result.release_date)
                    is_original_release = bool(
                        original_year
                        and edition_year
                        and original_year == edition_year
                    )

                    # Use original_release_date for comparison if available (this is the key!)
                    # For re-releases, original_release_date should be the original year (e.g., 1971)
                    # For true originals, original_release_date == release_date
                    comparison_date = result.original_release_date or result.release_date
                    date_tuple = self._parse_release_date(comparison_date)

                    if is_original_release and date_tuple is not None:
                        true_originals.append((result, date_tuple, result.score if result.score else 0))
                    elif date_tuple is not None:
                        re_releases.append((result, date_tuple, result.score if result.score else 0))
                    else:
                        candidates_without_original_date.append((result, result.score if result.score else 0))

                # Sort true originals by date (earliest first), then by score (highest first)
                # This ensures 1971 comes before 2021 even if 2021 has a higher score
                true_originals.sort(key=lambda x: (x[1], -x[2]))

                # Sort re-releases by original release date (earliest first), then by score
                # This ensures re-releases of 1971 albums come before re-releases of later albums
                re_releases.sort(key=lambda x: (x[1], -x[2]))

                # Select best: prefer true originals with earliest date, then re-releases with earliest original date
                best = None
                if true_originals:
                    # Always prefer the earliest true original (first in sorted list)
                    # This ensures 1971 original is preferred over 2021 original (if both exist)
                    best = true_originals[0][0]

                    # If we have multiple true originals with different years, try validation
                    if len(true_originals) > 1:
                        # Extract unique years from candidates
                        unique_years = set()
                        for result, date_tuple, _ in true_originals:
                            if date_tuple:
                                unique_years.add(date_tuple[0])

                        # Only validate if we have multiple different years
                        if len(unique_years) > 1 and self.year_validator:
                            first_candidate = true_originals[0][0]
                            artist = first_candidate.artist or ""
                            album = first_candidate.album or first_candidate.title or ""

                            if artist and album:
                                candidate_years = list(unique_years)
                                validated_year = self.year_validator.validate_year(
                                    artist, album, candidate_years, release_type
                                )

                                if validated_year:
                                    # Prefer candidates that match the validated year
                                    matching_candidates = [
                                        (r, dt, score) for r, dt, score in true_originals
                                        if dt and dt[0] == validated_year
                                    ]
                                    if matching_candidates:
                                        # Still sort by score within the validated year
                                        matching_candidates.sort(key=lambda x: -x[2])
                                        best = matching_candidates[0][0]

                # If we have both true originals and re-releases, prefer true originals
                # But if a re-release has an earlier original_release_date than any true original,
                # it might actually be the original (if metadata is incorrect)
                if true_originals and re_releases:
                    # Compare earliest true original with earliest re-release
                    earliest_true_original_date = true_originals[0][1]
                    earliest_re_release_original_date = re_releases[0][1]

                    # If re-release's original date is earlier, it's likely the actual original
                    # (metadata might be incorrect - re-release has correct original_release_date)
                    if earliest_re_release_original_date < earliest_true_original_date:
                        # Prefer the re-release with earliest original date
                        best = re_releases[0][0]
                    # Otherwise, keep the true original (already set above)
                elif re_releases:
                    # If we have multiple re-releases with different original years
                    if len(re_releases) > 1:
                        unique_years = set()
                        for result, date_tuple, _ in re_releases:
                            if date_tuple:
                                unique_years.add(date_tuple[0])

                        # Only validate if we have multiple different years
                        if len(unique_years) > 1 and self.year_validator:
                            first_candidate = re_releases[0][0]
                            artist = first_candidate.artist or ""
                            album = first_candidate.album or first_candidate.title or ""

                            if artist and album:
                                candidate_years = list(unique_years)
                                validated_year = self.year_validator.validate_year(
                                    artist, album, candidate_years, release_type
                                )

                                if validated_year:
                                    matching_candidates = [
                                        (r, dt, score) for r, dt, score in re_releases
                                        if dt and dt[0] == validated_year
                                    ]
                                    if matching_candidates:
                                        matching_candidates.sort(key=lambda x: -x[2])
                                        best = matching_candidates[0][0]

                    if not best:
                        best = re_releases[0][0]
                elif candidates_without_original_date:
                    # If no dates, try to get year from validator
                    if len(candidates_without_original_date) > 1 and self.year_validator:
                        first_candidate = candidates_without_original_date[0][0]
                        artist = first_candidate.artist or ""
                        album = first_candidate.album or first_candidate.title or ""

                        if artist and album:
                            validated_year = self.year_validator.get_release_year(artist, album, release_type)

                            if validated_year:
                                # Check if any candidate's release_date matches validated year
                                for result, score in candidates_without_original_date:
                                    if result.release_date:
                                        try:
                                            year = int(result.release_date[:4])
                                            if year == validated_year:
                                                best = result
                                                break
                                        except (ValueError, IndexError):
                                            continue

                    if not best:
                        # If no dates, use highest score
                        candidates_without_original_date.sort(key=lambda x: -x[1])
                        best = candidates_without_original_date[0][0]
                else:
                    # Fallback: just take first candidate
                    best = candidates[0] if candidates else None

                if best:
                    deduplicated.append(best)

        return deduplicated

    def deduplicate_with_priority(
        self,
        mb_results: List[MusicBrainzSong],
        discogs_results: List[MusicBrainzSong]
    ) -> List[MusicBrainzSong]:
        """
        Deduplicate results prioritizing MusicBrainz over Discogs.
        Only keeps Discogs results that don't have a matching MusicBrainz result.
        """
        # First, deduplicate MusicBrainz results internally
        mb_deduped = self.deduplicate_results(mb_results, release_type=None)

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
