"""
Tests for color utility functions.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from odysseus.utils.colors import (
    Colors,
    print_header,
    print_success,
    print_error,
    print_warning,
    print_info,
    print_separator,
    print_track_number,
    print_score,
    print_duration,
    print_views,
    print_channel,
    print_artist,
    print_album,
    print_title
)


class TestColors:
    """Tests for Colors class."""
    
    @patch('sys.stdout.isatty')
    def test_colorize_with_tty(self, mock_isatty):
        """Test colorize when terminal is a TTY."""
        mock_isatty.return_value = True
        result = Colors.colorize("test", "red")
        # Should contain color codes
        assert result != "test"
        assert "test" in result
    
    @patch('sys.stdout.isatty')
    def test_colorize_without_tty(self, mock_isatty):
        """Test colorize when terminal is not a TTY."""
        mock_isatty.return_value = False
        result = Colors.colorize("test", "red")
        # Should return plain text
        assert result == "test"
    
    def test_bold(self):
        """Test bold method."""
        with patch('sys.stdout.isatty', return_value=True):
            result = Colors.bold("test")
            assert "test" in result
    
    def test_red(self):
        """Test red method."""
        with patch('sys.stdout.isatty', return_value=True):
            result = Colors.red("test")
            assert "test" in result
    
    def test_green(self):
        """Test green method."""
        with patch('sys.stdout.isatty', return_value=True):
            result = Colors.green("test")
            assert "test" in result
    
    def test_yellow(self):
        """Test yellow method."""
        with patch('sys.stdout.isatty', return_value=True):
            result = Colors.yellow("test")
            assert "test" in result
    
    def test_blue(self):
        """Test blue method."""
        with patch('sys.stdout.isatty', return_value=True):
            result = Colors.blue("test")
            assert "test" in result
    
    def test_cyan(self):
        """Test cyan method."""
        with patch('sys.stdout.isatty', return_value=True):
            result = Colors.cyan("test")
            assert "test" in result
    
    def test_magenta(self):
        """Test magenta method."""
        with patch('sys.stdout.isatty', return_value=True):
            result = Colors.magenta("test")
            assert "test" in result
    
    def test_white(self):
        """Test white method."""
        with patch('sys.stdout.isatty', return_value=True):
            result = Colors.white("test")
            assert "test" in result


class TestPrintFunctions:
    """Tests for print utility functions."""
    
    @patch('builtins.print')
    @patch('sys.stdout.isatty', return_value=True)
    def test_print_header(self, mock_isatty, mock_print):
        """Test print_header function."""
        print_header("Test Header")
        mock_print.assert_called_once()
        call_args = str(mock_print.call_args)
        assert "Test Header" in call_args
    
    @patch('builtins.print')
    @patch('sys.stdout.isatty', return_value=True)
    def test_print_success(self, mock_isatty, mock_print):
        """Test print_success function."""
        print_success("Success message")
        mock_print.assert_called_once()
        call_args = str(mock_print.call_args)
        assert "Success message" in call_args
    
    @patch('builtins.print')
    @patch('sys.stdout.isatty', return_value=True)
    def test_print_error(self, mock_isatty, mock_print):
        """Test print_error function."""
        print_error("Error message")
        mock_print.assert_called_once()
        call_args = str(mock_print.call_args)
        assert "Error message" in call_args
    
    @patch('builtins.print')
    @patch('sys.stdout.isatty', return_value=True)
    def test_print_warning(self, mock_isatty, mock_print):
        """Test print_warning function."""
        print_warning("Warning message")
        mock_print.assert_called_once()
        call_args = str(mock_print.call_args)
        assert "Warning message" in call_args
    
    @patch('builtins.print')
    @patch('sys.stdout.isatty', return_value=True)
    def test_print_info(self, mock_isatty, mock_print):
        """Test print_info function."""
        print_info("Info message")
        mock_print.assert_called_once()
        call_args = str(mock_print.call_args)
        assert "Info message" in call_args
    
    @patch('builtins.print')
    @patch('sys.stdout.isatty', return_value=True)
    def test_print_separator(self, mock_isatty, mock_print):
        """Test print_separator function."""
        print_separator(40)
        mock_print.assert_called_once()
        call_args = str(mock_print.call_args)
        assert "-" * 40 in call_args or "40" in call_args
    
    @patch('sys.stdout.isatty', return_value=True)
    def test_print_track_number(self, mock_isatty):
        """Test print_track_number function."""
        result = print_track_number(5)
        assert "5" in result
    
    @patch('sys.stdout.isatty', return_value=True)
    def test_print_score_high(self, mock_isatty):
        """Test print_score with high score."""
        result = print_score(95)
        assert "95" in result
    
    @patch('sys.stdout.isatty', return_value=True)
    def test_print_score_medium(self, mock_isatty):
        """Test print_score with medium score."""
        result = print_score(75)
        assert "75" in result
    
    @patch('sys.stdout.isatty', return_value=True)
    def test_print_score_low(self, mock_isatty):
        """Test print_score with low score."""
        result = print_score(50)
        assert "50" in result
    
    @patch('sys.stdout.isatty', return_value=True)
    def test_print_duration(self, mock_isatty):
        """Test print_duration function."""
        result = print_duration("3:45")
        assert "3:45" in result
    
    @patch('sys.stdout.isatty', return_value=True)
    def test_print_views(self, mock_isatty):
        """Test print_views function."""
        result = print_views("1000")
        assert "1000" in result
    
    @patch('sys.stdout.isatty', return_value=True)
    def test_print_channel(self, mock_isatty):
        """Test print_channel function."""
        result = print_channel("Test Channel")
        assert "Test Channel" in result
    
    @patch('sys.stdout.isatty', return_value=True)
    def test_print_artist(self, mock_isatty):
        """Test print_artist function."""
        result = print_artist("Test Artist")
        assert "Test Artist" in result
    
    @patch('sys.stdout.isatty', return_value=True)
    def test_print_album(self, mock_isatty):
        """Test print_album function."""
        result = print_album("Test Album")
        assert "Test Album" in result
    
    @patch('sys.stdout.isatty', return_value=True)
    def test_print_title(self, mock_isatty):
        """Test print_title function."""
        result = print_title("Test Title")
        assert "Test Title" in result

