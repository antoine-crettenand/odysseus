"""Source-neutral identity matching for releases and tracks."""

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Any, List, Optional

from ...utils.string_utils import normalize_string


_IGNORED_ARTICLES = {"a", "an", "the"}
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _value(candidate: Any, *names: str) -> Any:
    """Read the first populated field from a mapping or object."""
    for name in names:
        if isinstance(candidate, dict):
            value = candidate.get(name)
        else:
            value = getattr(candidate, name, None)
        if value not in (None, ""):
            return value
    return None


def _tokens(value: Optional[str], *, drop_articles: bool = False) -> List[str]:
    tokens = _TOKEN_PATTERN.findall(normalize_string(value or ""))
    if drop_articles:
        tokens = [token for token in tokens if token not in _IGNORED_ARTICLES]
    return tokens


def text_similarity(
    left: Optional[str],
    right: Optional[str],
    *,
    drop_articles: bool = False,
) -> float:
    """Return a conservative, token-aware similarity score from 0 to 1."""
    left_tokens = _tokens(left, drop_articles=drop_articles)
    right_tokens = _tokens(right, drop_articles=drop_articles)
    if not left_tokens or not right_tokens:
        return 0.0
    if left_tokens == right_tokens:
        return 1.0

    left_text = " ".join(left_tokens)
    right_text = " ".join(right_tokens)

    # Short values are too collision-prone for fuzzy or substring matching.
    if min(len(left_text), len(right_text)) < 4:
        return 0.0

    left_set = set(left_tokens)
    right_set = set(right_tokens)
    token_overlap = len(left_set & right_set) / max(len(left_set), len(right_set))
    sequence_score = SequenceMatcher(None, left_text, right_text).ratio()
    return max(token_overlap, sequence_score)


def extract_year(value: Any) -> Optional[int]:
    """Extract a four-digit year from an integer or date-like value."""
    if isinstance(value, int):
        return value
    if value:
        match = re.match(r"^\s*(\d{4})", str(value))
        if match:
            return int(match.group(1))
    return None


@dataclass(frozen=True)
class ReleaseMatch:
    """Detailed release identity comparison."""

    album_similarity: float
    artist_similarity: float
    year_distance: Optional[int]
    type_matches: Optional[bool]
    score: float
    accepted: bool


def compare_release(
    candidate: Any,
    *,
    expected_album: str,
    expected_artist: str,
    expected_year: Optional[int] = None,
    expected_type: Optional[str] = None,
) -> ReleaseMatch:
    """Compare a provider result to the expected source-neutral identity."""
    candidate_album = _value(candidate, "album", "title")
    candidate_artist = _value(candidate, "artist")
    candidate_year = extract_year(
        _value(candidate, "release_year", "release_date", "year")
    )
    candidate_type = _value(candidate, "release_type", "album_type", "type")

    album_similarity = text_similarity(expected_album, candidate_album)
    artist_similarity = text_similarity(
        expected_artist,
        candidate_artist,
        drop_articles=True,
    )
    year_distance = (
        abs(expected_year - candidate_year)
        if expected_year is not None and candidate_year is not None
        else None
    )
    type_matches = (
        normalize_string(expected_type) == normalize_string(str(candidate_type))
        if expected_type and candidate_type
        else None
    )

    score = album_similarity * 50 + artist_similarity * 40
    if year_distance is not None:
        score += 5 if year_distance == 0 else 2 if year_distance <= 1 else 0
    if type_matches is True:
        score += 5

    # Both primary identity fields are mandatory. Year and type refine ranking
    # but do not reject legitimate reissues or provider classification drift.
    accepted = album_similarity >= 0.82 and artist_similarity >= 0.82
    return ReleaseMatch(
        album_similarity=album_similarity,
        artist_similarity=artist_similarity,
        year_distance=year_distance,
        type_matches=type_matches,
        score=score,
        accepted=accepted,
    )


def select_best_release_match(
    candidates: List[Any],
    *,
    expected_album: str,
    expected_artist: str,
    expected_year: Optional[int] = None,
    expected_type: Optional[str] = None,
) -> Optional[Any]:
    """Return the highest-confidence acceptable candidate, never a fallback."""
    ranked = [
        (
            compare_release(
                candidate,
                expected_album=expected_album,
                expected_artist=expected_artist,
                expected_year=expected_year,
                expected_type=expected_type,
            ),
            candidate,
        )
        for candidate in candidates
    ]
    accepted = [(match, candidate) for match, candidate in ranked if match.accepted]
    if not accepted:
        return None
    return max(accepted, key=lambda item: item[0].score)[1]


def track_titles_match(expected: str, candidate: str) -> bool:
    """Conservatively match track titles when exact filenames are unavailable."""
    return text_similarity(expected, candidate) >= 0.92
