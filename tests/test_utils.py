"""
Tests for utility modules.
"""

import pytest
from unittest.mock import patch, MagicMock
from odysseus.utils.string_utils import normalize_string
from odysseus.utils.colors import Colors, print_header, print_success, print_error


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


class TestColors:
    """Tests for Colors utility class."""

    def test_colorize_with_tty(self):
        """Test colorize when terminal is a TTY."""
        with patch("sys.stdout.isatty", return_value=True):
            with patch("odysseus.utils.colors.COLORS", {"RED": "\033[31m", "END": "\033[0m"}):
                result = Colors.colorize("test", "red")
                assert "\033[31m" in result
                assert "test" in result

    def test_colorize_without_tty(self):
        """Test colorize when terminal is not a TTY."""
        with patch("sys.stdout.isatty", return_value=False):
            result = Colors.colorize("test", "red")
            assert result == "test"

    def test_bold(self):
        """Test bold method."""
        with patch("sys.stdout.isatty", return_value=True):
            with patch.object(Colors, "colorize", return_value="bold_text"):
                result = Colors.bold("test")
                assert result == "bold_text"

    def test_red(self):
        """Test red method."""
        with patch("sys.stdout.isatty", return_value=True):
            with patch.object(Colors, "colorize", return_value="red_text"):
                result = Colors.red("test")
                assert result == "red_text"

    def test_green(self):
        """Test green method."""
        with patch("sys.stdout.isatty", return_value=True):
            with patch.object(Colors, "colorize", return_value="green_text"):
                result = Colors.green("test")
                assert result == "green_text"

    def test_yellow(self):
        """Test yellow method."""
        with patch("sys.stdout.isatty", return_value=True):
            with patch.object(Colors, "colorize", return_value="yellow_text"):
                result = Colors.yellow("test")
                assert result == "yellow_text"

    def test_blue(self):
        """Test blue method."""
        with patch("sys.stdout.isatty", return_value=True):
            with patch.object(Colors, "colorize", return_value="blue_text"):
                result = Colors.blue("test")
                assert result == "blue_text"

    def test_cyan(self):
        """Test cyan method."""
        with patch("sys.stdout.isatty", return_value=True):
            with patch.object(Colors, "colorize", return_value="cyan_text"):
                result = Colors.cyan("test")
                assert result == "cyan_text"

    def test_magenta(self):
        """Test magenta method."""
        with patch("sys.stdout.isatty", return_value=True):
            with patch.object(Colors, "colorize", return_value="magenta_text"):
                result = Colors.magenta("test")
                assert result == "magenta_text"

    def test_white(self):
        """Test white method."""
        with patch("sys.stdout.isatty", return_value=True):
            with patch.object(Colors, "colorize", return_value="white_text"):
                result = Colors.white("test")
                assert result == "white_text"


class TestPrintFunctions:
    """Tests for print utility functions."""

    @patch("builtins.print")
    def test_print_header(self, mock_print):
        """Test print_header function."""
        with patch("odysseus.utils.colors.Colors.bold", return_value="bold"):
            with patch("odysseus.utils.colors.Colors.cyan", return_value="cyan"):
                print_header("Test")
                mock_print.assert_called_once()

    @patch("builtins.print")
    def test_print_success(self, mock_print):
        """Test print_success function."""
        with patch("odysseus.utils.colors.Colors.green", return_value="green"):
            print_success("Test")
            mock_print.assert_called_once()

    @patch("builtins.print")
    def test_print_error(self, mock_print):
        """Test print_error function."""
        with patch("odysseus.utils.colors.Colors.red", return_value="red"):
            print_error("Test")
            mock_print.assert_called_once()
