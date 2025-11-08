"""
String utility functions for normalization and comparison.
"""

import unicodedata
from typing import Optional


def normalize_string(s: Optional[str]) -> str:
    """
    Normalize a string for comparison (lowercase, strip whitespace, normalize special characters).
    
    Args:
        s: String to normalize
        
    Returns:
        Normalized string
    """
    if not s:
        return ""
    # First, normalize Unicode characters (NFKD normalization helps with apostrophes and special chars)
    normalized = unicodedata.normalize('NFKD', s)
    # Convert to lowercase and strip whitespace
    normalized = normalized.lower().strip()
    # Normalize "&" to "and" for better matching
    normalized = normalized.replace(" & ", " and ")
    normalized = normalized.replace("&", " and ")
    # Normalize all apostrophe variants to a standard apostrophe
    # This handles: ', ', ', ', ʼ, ʻ, ʼ, ʽ, ʾ, ʿ, ˊ, ˋ, etc.
    # After NFKD normalization, many apostrophes become U+0027 or similar
    apostrophe_chars = ["'", "'", "'", "'", "ʼ", "ʻ", "ʼ", "ʽ", "ʾ", "ʿ", "ˊ", "ˋ", "\u2018", "\u2019", "\u201A", "\u201B", "\u2032", "\u2035"]
    for char in apostrophe_chars:
        normalized = normalized.replace(char, "'")
    # Normalize different types of quotes to a standard form
    normalized = normalized.replace(""", '"')  # Left double quotation mark
    normalized = normalized.replace(""", '"')  # Right double quotation mark
    normalized = normalized.replace(""", "'")  # Left single quotation mark (if not already handled)
    normalized = normalized.replace(""", "'")  # Right single quotation mark (if not already handled)
    # Normalize dashes
    normalized = normalized.replace("–", "-")  # En dash
    normalized = normalized.replace("—", "-")  # Em dash
    # Remove multiple spaces
    normalized = " ".join(normalized.split())
    return normalized

