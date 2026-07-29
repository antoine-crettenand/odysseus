"""Tests for utility modules."""

from odysseus.utils.string_utils import normalize_string
from odysseus.utils.file_duration_reader import format_duration_ms


class TestNormalizeString:
    """Tests for normalize_string function."""

    def test_normalize_string_basic(self):
        """Test basic string normalization."""
        assert normalize_string("Test String") == "test string"
        assert normalize_string("  Test  ") == "test"

    def test_normalize_string_empty(self):
        """Test normalization of empty strings."""
        assert normalize_string("") == ""
        assert normalize_string(None) == ""

    def test_normalize_string_special_chars(self):
        """Test normalization of special characters."""
        assert normalize_string("Test & String") == "test and string"
        assert normalize_string("Test's String") == "test's string"
        assert normalize_string("Test – String") == "test - string"
        assert normalize_string("Test—String") == "test-string"

    def test_normalize_string_unicode(self):
        """Test normalization of unicode characters."""
        assert normalize_string("Café") == "cafe"
        assert normalize_string("naïve") == "naive"

    def test_normalize_string_quotes(self):
        """Test normalization of quotes."""
        assert normalize_string('Test "String"') == 'test "string"'
        assert normalize_string("Test 'String'") == "test 'string'"

    def test_normalize_string_multiple_spaces(self):
        """Test normalization of multiple spaces."""
        assert normalize_string("Test    String") == "test string"
        assert normalize_string("Test\n\tString") == "test string"


def test_format_duration_ms_uses_shared_duration_format():
    assert format_duration_ms(210_000) == "3:30"
    assert format_duration_ms(None) is None
