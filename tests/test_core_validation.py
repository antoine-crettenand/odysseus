"""
Tests for configuration validation utilities.
"""

import pytest
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from odysseus.core.validation import check_dependencies, validate_configuration, validate_and_raise
from odysseus.core.exceptions import ConfigurationError


class TestCheckDependencies:
    """Tests for check_dependencies function."""
    
    @patch('importlib.import_module')
    def test_check_dependencies_all_installed(self, mock_import):
        """Test check_dependencies when all dependencies are installed."""
        mock_import.return_value = MagicMock()
        
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = MagicMock(returncode=0)
            all_installed, missing = check_dependencies()
            
            assert all_installed is True
            assert len(missing) == 0
    
    @patch('importlib.import_module')
    def test_check_dependencies_missing_module(self, mock_import):
        """Test check_dependencies when a module is missing."""
        def side_effect(module_name):
            if module_name == "requests":
                raise ImportError("No module named 'requests'")
            return MagicMock()
        
        mock_import.side_effect = side_effect
        
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = MagicMock(returncode=0)
            all_installed, missing = check_dependencies()
            
            assert all_installed is False
            assert "requests" in missing
    
    @patch('importlib.import_module')
    @patch('odysseus.core.validation.subprocess.run')
    def test_check_dependencies_missing_yt_dlp_command(self, mock_subprocess, mock_import):
        """Test check_dependencies when yt-dlp command is missing."""
        mock_import.return_value = MagicMock()
        mock_subprocess.side_effect = FileNotFoundError("yt-dlp not found")
        
        all_installed, missing = check_dependencies()
        
        assert all_installed is False
        assert any("yt-dlp" in item for item in missing)


class TestValidateConfiguration:
    """Tests for validate_configuration function."""
    
    def test_validate_configuration_success(self, temp_dir):
        """Test validate_configuration with valid configuration."""
        with patch('odysseus.core.validation.check_dependencies') as mock_check:
            mock_check.return_value = (True, [])
            
            with patch('odysseus.core.validation.DOWNLOADS_DIR', temp_dir):
                with patch('odysseus.core.validation.CONFIG_DIR', temp_dir):
                    is_valid, errors = validate_configuration()
                    
                    assert is_valid is True
                    assert len(errors) == 0
    
    def test_validate_configuration_missing_dependencies(self, temp_dir):
        """Test validate_configuration with missing dependencies."""
        with patch('odysseus.core.validation.check_dependencies') as mock_check:
            mock_check.return_value = (False, ["requests"])
            
            with patch('odysseus.core.validation.DOWNLOADS_DIR', temp_dir):
                with patch('odysseus.core.validation.CONFIG_DIR', temp_dir):
                    is_valid, errors = validate_configuration()
                    
                    assert is_valid is False
                    assert len(errors) > 0
                    assert any("dependencies" in error.lower() for error in errors)
    
    def test_validate_configuration_unwritable_directory(self):
        """Test validate_configuration with unwritable directory."""
        with patch('odysseus.core.validation.check_dependencies') as mock_check:
            mock_check.return_value = (True, [])
            
            # Create a directory that can't be written to (simulated)
            with patch('pathlib.Path.mkdir') as mock_mkdir:
                mock_mkdir.side_effect = PermissionError("Permission denied")
                
                is_valid, errors = validate_configuration()
                
                assert is_valid is False
                assert len(errors) > 0
    
    @patch('odysseus.core.validation.check_dependencies')
    def test_validate_configuration_invalid_musicbrainz_delay(self, mock_check, temp_dir):
        """Test validate_configuration with invalid MusicBrainz delay."""
        mock_check.return_value = (True, [])
        
        with patch('odysseus.core.validation.DOWNLOADS_DIR', temp_dir):
            with patch('odysseus.core.validation.CONFIG_DIR', temp_dir):
                with patch('odysseus.core.validation.MUSICBRAINZ_CONFIG', {"REQUEST_DELAY": -1, "MAX_RESULTS": 3, "TIMEOUT": 30}):
                    is_valid, errors = validate_configuration()
                    
                    assert is_valid is False
                    assert any("REQUEST_DELAY" in error for error in errors)
    
    @patch('odysseus.core.validation.check_dependencies')
    def test_validate_configuration_invalid_download_quality(self, mock_check, temp_dir):
        """Test validate_configuration with invalid download quality."""
        mock_check.return_value = (True, [])
        
        with patch('odysseus.core.validation.DOWNLOADS_DIR', temp_dir):
            with patch('odysseus.core.validation.CONFIG_DIR', temp_dir):
                with patch('odysseus.core.validation.DOWNLOAD_CONFIG', {"DEFAULT_QUALITY": "invalid", "AUDIO_FORMAT": "mp3", "MAX_CONCURRENT_DOWNLOADS": 3, "TIMEOUT": 300}):
                    is_valid, errors = validate_configuration()
                    
                    assert is_valid is False
                    assert any("DEFAULT_QUALITY" in error for error in errors)


class TestValidateAndRaise:
    """Tests for validate_and_raise function."""
    
    def test_validate_and_raise_success(self, temp_dir):
        """Test validate_and_raise with valid configuration."""
        with patch('odysseus.core.validation.validate_configuration') as mock_validate:
            mock_validate.return_value = (True, [])
            
            with patch('odysseus.core.validation.DOWNLOADS_DIR', temp_dir):
                with patch('odysseus.core.validation.CONFIG_DIR', temp_dir):
                    # Should not raise
                    validate_and_raise()
    
    def test_validate_and_raise_failure(self, temp_dir):
        """Test validate_and_raise with invalid configuration."""
        with patch('odysseus.core.validation.validate_configuration') as mock_validate:
            mock_validate.return_value = (False, ["Test error"])
            
            with pytest.raises(ConfigurationError) as exc_info:
                validate_and_raise()
            
            assert "Test error" in str(exc_info.value)

