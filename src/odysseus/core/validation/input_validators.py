"""User-input validation helpers."""

from typing import Optional, Tuple

from ..config import VALIDATION_RULES


def validate_user_input(
    field_name: str,
    value: str,
    max_length: Optional[int] = None,
) -> str:
    """Validate and sanitize a user-provided string."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")

    value = value.strip()
    min_length = VALIDATION_RULES.get(f"MIN_{field_name.upper()}_LENGTH", 1)
    if len(value) < min_length:
        raise ValueError(
            f"{field_name} must be at least {min_length} character(s) long"
        )

    if max_length is None:
        max_length = VALIDATION_RULES.get(
            f"MAX_{field_name.upper()}_LENGTH",
            500,
        )
    if len(value) > max_length:
        value = value[:max_length]

    return value


def validate_year(year: Optional[int], *, coerce: bool = False) -> Optional[int]:
    """
    Validate a release year.

    Args:
        year: Year to validate
        coerce: If True, out-of-range years become ``None`` instead of raising

    Returns:
        The year when valid, or ``None`` when ``year`` is ``None`` / coerced away

    Raises:
        ValueError: When the year is out of range and ``coerce`` is False
    """
    if year is None:
        return None
    min_year = VALIDATION_RULES.get("MIN_YEAR", 1900)
    max_year = VALIDATION_RULES.get("MAX_YEAR", 2030)
    if min_year <= year <= max_year:
        return year
    if coerce:
        return None
    raise ValueError(f"Year must be between {min_year} and {max_year}")


def validate_year_range(
    year: Optional[int] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
) -> Tuple[Optional[int], Optional[int]]:
    """Validate an exact year or inclusive range and return normalized bounds."""
    if year is not None and (year_from is not None or year_to is not None):
        raise ValueError("--year cannot be combined with --year-from or --year-to")

    if year is not None:
        validated_year = validate_year(year)
        return validated_year, validated_year

    validated_from = validate_year(year_from)
    validated_to = validate_year(year_to)
    if (
        validated_from is not None
        and validated_to is not None
        and validated_from > validated_to
    ):
        raise ValueError("--year-from must be less than or equal to --year-to")
    return validated_from, validated_to


def validate_string_length(
    value: str,
    min_length: int = 1,
    max_length: Optional[int] = None,
) -> str:
    """Trim a string and enforce its minimum and optional maximum length."""
    if not isinstance(value, str):
        raise ValueError("Value must be a string")

    value = value.strip()
    if len(value) < min_length:
        raise ValueError(
            f"String must be at least {min_length} character(s) long"
        )
    if max_length is not None and len(value) > max_length:
        return value[:max_length]
    return value


def validate_required_fields(**kwargs) -> bool:
    """Validate that every named field has a non-blank value."""
    for field_name, value in kwargs.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError(f"{field_name} is required")
    return True
