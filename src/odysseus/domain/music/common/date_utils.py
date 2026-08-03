"""
Date parsing utilities for music domain.
"""

from typing import Any, Optional, Tuple


def extract_year(release_date: Optional[str]) -> Optional[str]:
    """Extract year from release date string."""
    if not release_date:
        return None
    normalized = str(release_date).strip()
    year_part = normalized[:4] if len(normalized) >= 4 else None
    return year_part if year_part and year_part.isdigit() else None


def get_edition_release_year(release: Any) -> Optional[int]:
    """Return the year of the specific release/edition."""
    year = extract_year(getattr(release, "release_date", None))
    return int(year) if year is not None else None


def get_original_release_year(release: Any) -> Optional[int]:
    """Return the original work year, falling back to the edition year."""
    original_year = extract_year(
        getattr(release, "original_release_date", None)
    )
    if original_year is not None:
        return int(original_year)
    return get_edition_release_year(release)


def format_release_date_label(release: Any) -> str:
    """Format original and edition dates without conflating the two."""
    original_date = getattr(release, "original_release_date", None)
    edition_date = getattr(release, "release_date", None)
    original_year = extract_year(original_date)
    edition_year = extract_year(edition_date)

    if original_year and edition_year and original_year != edition_year:
        return f"{original_date} · edition {edition_date}"
    return str(original_date or edition_date or "—")


def parse_release_date(release_date: Optional[str]) -> Optional[Tuple[int, int, int]]:
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


def release_year_in_range(
    release: Any,
    year_from: Optional[int],
    year_to: Optional[int],
) -> bool:
    """Return whether a release's original year is within inclusive bounds."""
    if year_from is None and year_to is None:
        return True

    year = get_original_release_year(release)
    if year is None:
        return False

    if year_from is not None and year < year_from:
        return False
    if year_to is not None and year > year_to:
        return False
    return True
