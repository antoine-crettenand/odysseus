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
    normalized = unicodedata.normalize('NFKD', s)
    # Remove combining characters (diacritics)
    normalized = ''.join(c for c in normalized if not unicodedata.combining(c))
    normalized = normalized.lower().strip()
    normalized = normalized.replace(" & ", " and ")
    normalized = normalized.replace("&", " and ")
    apostrophe_chars = ["'", "'", "'", "'", "ʼ", "ʻ", "ʼ", "ʽ", "ʾ", "ʿ", "ˊ", "ˋ", "\u2018", "\u2019", "\u201A", "\u201B", "\u2032", "\u2035"]
    for char in apostrophe_chars:
        normalized = normalized.replace(char, "'")
    normalized = normalized.replace(""", '"')
    normalized = normalized.replace(""", '"')
    normalized = normalized.replace(""", "'")
    normalized = normalized.replace(""", "'")
    normalized = normalized.replace("–", "-")
    normalized = normalized.replace("—", "-")
    normalized = " ".join(normalized.split())
    return normalized

