"""
Shared validation utilities.
"""
from typing import Optional
from ..core.exceptions import ValidationError
from ..core.config import VALIDATION_RULES


def validate_year(year: Optional[int]) -> bool:
    """
    Validate year is within acceptable range.
    
    Args:
        year: Year to validate
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If year is out of range
    """
    if year is None:
        return True
    
    min_year = VALIDATION_RULES["MIN_YEAR"]
    max_year = VALIDATION_RULES["MAX_YEAR"]
    
    if not (min_year <= year <= max_year):
        raise ValidationError(
            f"Year must be between {min_year} and {max_year}",
            details={"year": year, "min_year": min_year, "max_year": max_year}
        )
    
    return True


def validate_string_length(
    text: str,
    field_name: str,
    min_len: Optional[int] = None,
    max_len: Optional[int] = None
) -> bool:
    """
    Validate string length.
    
    Args:
        text: String to validate
        field_name: Name of the field (for error messages)
        min_len: Minimum length (optional)
        max_len: Maximum length (optional)
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If string length is invalid
    """
    if min_len is not None and len(text) < min_len:
        raise ValidationError(
            f"{field_name} must be at least {min_len} characters",
            details={"field": field_name, "length": len(text), "min_length": min_len}
        )
    
    if max_len is not None and len(text) > max_len:
        raise ValidationError(
            f"{field_name} must be at most {max_len} characters",
            details={"field": field_name, "length": len(text), "max_length": max_len}
        )
    
    return True


def validate_required_fields(**kwargs) -> bool:
    """
    Validate that required fields are present and not empty.
    
    Args:
        **kwargs: Field name -> value mapping
        
    Returns:
        True if all required fields are valid
        
    Raises:
        ValidationError: If any required field is missing or empty
    """
    errors = []
    
    for field_name, value in kwargs.items():
        if value is None:
            errors.append(f"{field_name} is required")
        elif isinstance(value, str) and not value.strip():
            errors.append(f"{field_name} cannot be empty")
    
    if errors:
        raise ValidationError(
            "Validation failed",
            details={"errors": errors}
        )
    
    return True

