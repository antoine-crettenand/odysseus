"""
Date parsing utilities for music domain.
"""

from typing import Any, Optional, Tuple


def extract_year(release_date: Optional[str]) -> Optional[str]:
    """Extract year from release date string."""
    if not release_date or release_date.strip() == "":
        return None
    year_part = release_date[:4] if len(release_date) >= 4 else None
    return year_part if year_part and year_part.isdigit() else None


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
    """Return whether a release's dated edition is within inclusive bounds."""
    if year_from is None and year_to is None:
        return True

    release_date = getattr(release, "release_date", None)
    original_date = getattr(release, "original_release_date", None)
    year_text = extract_year(release_date or original_date)
    if year_text is None:
        return False

    year = int(year_text)
    if year_from is not None and year < year_from:
        return False
    if year_to is not None and year > year_to:
        return False
    return True
