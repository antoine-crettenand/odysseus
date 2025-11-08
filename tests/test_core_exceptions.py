"""
Tests for custom exceptions.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from odysseus.core.exceptions import (
    OdysseusError,
    SearchError,
    DownloadError,
    MetadataError,
    ConfigurationError,
    APIError,
    NetworkError
)


class TestExceptions:
    """Tests for custom exception classes."""
    
    def test_odysseus_error_is_exception(self):
        """Test that OdysseusError is an Exception."""
        assert issubclass(OdysseusError, Exception)
    
    def test_odysseus_error_can_be_raised(self):
        """Test that OdysseusError can be raised."""
        with pytest.raises(OdysseusError):
            raise OdysseusError("Test error")
    
    def test_search_error_inherits_from_odysseus_error(self):
        """Test that SearchError inherits from OdysseusError."""
        assert issubclass(SearchError, OdysseusError)
    
    def test_search_error_can_be_raised(self):
        """Test that SearchError can be raised."""
        with pytest.raises(SearchError):
            raise SearchError("Search failed")
    
    def test_download_error_inherits_from_odysseus_error(self):
        """Test that DownloadError inherits from OdysseusError."""
        assert issubclass(DownloadError, OdysseusError)
    
    def test_download_error_can_be_raised(self):
        """Test that DownloadError can be raised."""
        with pytest.raises(DownloadError):
            raise DownloadError("Download failed")
    
    def test_metadata_error_inherits_from_odysseus_error(self):
        """Test that MetadataError inherits from OdysseusError."""
        assert issubclass(MetadataError, OdysseusError)
    
    def test_metadata_error_can_be_raised(self):
        """Test that MetadataError can be raised."""
        with pytest.raises(MetadataError):
            raise MetadataError("Metadata failed")
    
    def test_configuration_error_inherits_from_odysseus_error(self):
        """Test that ConfigurationError inherits from OdysseusError."""
        assert issubclass(ConfigurationError, OdysseusError)
    
    def test_configuration_error_can_be_raised(self):
        """Test that ConfigurationError can be raised."""
        with pytest.raises(ConfigurationError):
            raise ConfigurationError("Configuration failed")
    
    def test_api_error_inherits_from_odysseus_error(self):
        """Test that APIError inherits from OdysseusError."""
        assert issubclass(APIError, OdysseusError)
    
    def test_api_error_can_be_raised(self):
        """Test that APIError can be raised."""
        with pytest.raises(APIError):
            raise APIError("API failed")
    
    def test_network_error_inherits_from_odysseus_error(self):
        """Test that NetworkError inherits from OdysseusError."""
        assert issubclass(NetworkError, OdysseusError)
    
    def test_network_error_inherits_from_connection_error(self):
        """Test that NetworkError inherits from ConnectionError."""
        assert issubclass(NetworkError, ConnectionError)
    
    def test_network_error_can_be_raised(self):
        """Test that NetworkError can be raised."""
        with pytest.raises(NetworkError):
            raise NetworkError("Network failed")
    
    def test_exception_message_preserved(self):
        """Test that exception messages are preserved."""
        error = SearchError("Custom message")
        assert str(error) == "Custom message"
    
    def test_exception_chaining(self):
        """Test that exceptions can be chained."""
        try:
            raise ValueError("Original error")
        except ValueError as e:
            with pytest.raises(APIError) as exc_info:
                raise APIError("Wrapped error") from e
            
            assert exc_info.value.__cause__ == e

