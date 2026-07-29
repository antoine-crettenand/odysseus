"""Reusable parsing for numbered CLI selections."""

from typing import List


def parse_numeric_selection(
    value: str,
    maximum: int,
    *,
    allow_all: bool = True,
) -> List[int]:
    """Parse comma-separated numbers/ranges and validate every selection."""
    normalized = value.strip().lower()
    if allow_all and normalized == "all":
        return list(range(1, maximum + 1))
    if not normalized:
        raise ValueError("Selection cannot be empty")

    selected = set()
    for part in normalized.split(","):
        part = part.strip()
        if "-" in part:
            start, end = (int(bound.strip()) for bound in part.split("-", 1))
            if start > end:
                raise ValueError("Selection ranges must be ascending")
            selected.update(range(start, end + 1))
        else:
            selected.add(int(part))

    if not selected or any(number < 1 or number > maximum for number in selected):
        raise ValueError(f"Selections must be between 1 and {maximum}")
    return sorted(selected)
