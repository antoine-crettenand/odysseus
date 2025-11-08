"""
Tests for string utility functions.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from odysseus.utils.string_utils import normalize_string


class TestNormalizeString:
    """Tests for normalize_string function."""
    
    def test_normalize_string_basic(self):
        """Test basic string normalization."""
        assert normalize_string("Test String") == "test string"
    
    def test_normalize_string_strips_whitespace(self):
        """Test that whitespace is stripped."""
        assert normalize_string("  Test  ") == "test"
    
    def test_normalize_string_lowercase(self):
        """Test that string is lowercased."""
        assert normalize_string("TEST") == "test"
    
    def test_normalize_string_ampersand_replacement(self):
        """Test ampersand replacement."""
        assert normalize_string("A & B") == "a and b"
        assert normalize_string("A&B") == "a and b"
    
    def test_normalize_string_apostrophe_normalization(self):
        """Test apostrophe character normalization."""
        assert normalize_string("Don't") == "don't"
        assert normalize_string("Don't") == "don't"
        assert normalize_string("Don't") == "don't"
    
    def test_normalize_string_quote_normalization(self):
        """Test quote character normalization."""
        assert normalize_string('"Test"') == '"test"'
        assert normalize_string("'Test'") == "'test'"
    
    def test_normalize_string_dash_normalization(self):
        """Test dash character normalization."""
        assert normalize_string("Test–String") == "test-string"
        assert normalize_string("Test—String") == "test-string"
    
    def test_normalize_string_unicode_normalization(self):
        """Test Unicode normalization."""
        # Test with combining characters
        assert normalize_string("café") == "cafe"
        assert normalize_string("naïve") == "naive"
    
    def test_normalize_string_multiple_spaces(self):
        """Test that multiple spaces are collapsed."""
        assert normalize_string("Test    String") == "test string"
    
    def test_normalize_string_none(self):
        """Test that None returns empty string."""
        assert normalize_string(None) == ""
    
    def test_normalize_string_empty(self):
        """Test that empty string returns empty string."""
        assert normalize_string("") == ""
    
    def test_normalize_string_complex(self):
        """Test complex string normalization."""
        result = normalize_string("  The Beatles & The Rolling Stones  ")
        assert result == "the beatles and the rolling stones"
    
    def test_normalize_string_special_characters(self):
        """Test normalization with various special characters."""
        result = normalize_string("Artist's \"Song\" – Album")
        assert "artist's" in result
        assert '"song"' in result
        assert "album" in result
    
    def test_normalize_string_real_world_examples(self):
        """Test with real-world music examples."""
        assert normalize_string("Led Zeppelin") == "led zeppelin"
        assert normalize_string("Pink Floyd & Friends") == "pink floyd and friends"
        assert normalize_string("Queen's Greatest Hits") == "queen's greatest hits"

