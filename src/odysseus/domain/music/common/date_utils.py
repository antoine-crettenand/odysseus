"""
Date parsing utilities for music domain.
"""

from typing import Optional, Tuple


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
