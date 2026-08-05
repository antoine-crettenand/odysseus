"""
Tests for custom exceptions.
"""

from odysseus.core.exceptions import (
    OdysseusError,
    SearchError,
    DownloadError,
    MetadataError,
    ConfigurationError,
    APIError,
    NetworkError,
    ValidationError,
)


class TestOdysseusError:
    """Tests for base OdysseusError exception."""

    def test_odysseus_error_basic(self):
        """Test basic error creation."""
        error = OdysseusError("Test error")

        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.details == {}

    def test_odysseus_error_with_details(self):
        """Test error with details."""
        error = OdysseusError("Test error", details={"key": "value", "code": 404})

        assert error.message == "Test error"
        assert error.details == {"key": "value", "code": 404}
        assert "key=value" in str(error)
        assert "code=404" in str(error)

    def test_odysseus_error_inheritance(self):
        """Test that OdysseusError inherits from Exception."""
        error = OdysseusError("Test")

        assert isinstance(error, Exception)


class TestSpecializedExceptions:
    """Tests for specialized exception classes."""

    def test_search_error(self):
        """Test SearchError exception."""
        error = SearchError("Search failed")

        assert isinstance(error, OdysseusError)
        assert isinstance(error, Exception)
        assert str(error) == "Search failed"

    def test_download_error(self):
        """Test DownloadError exception."""
        error = DownloadError("Download failed")

        assert isinstance(error, OdysseusError)
        assert isinstance(error, Exception)
        assert str(error) == "Download failed"

    def test_metadata_error(self):
        """Test MetadataError exception."""
        error = MetadataError("Metadata failed")

        assert isinstance(error, OdysseusError)
        assert isinstance(error, Exception)
        assert str(error) == "Metadata failed"

    def test_configuration_error(self):
        """Test ConfigurationError exception."""
        error = ConfigurationError("Config failed")

        assert isinstance(error, OdysseusError)
        assert isinstance(error, Exception)
        assert str(error) == "Config failed"

    def test_api_error(self):
        """Test APIError exception."""
        error = APIError("API failed")

        assert isinstance(error, OdysseusError)
        assert isinstance(error, Exception)
        assert str(error) == "API failed"

    def test_network_error(self):
        """Test NetworkError exception."""
        error = NetworkError("Network failed")

        assert isinstance(error, OdysseusError)
        assert isinstance(error, ConnectionError)
        assert isinstance(error, Exception)
        assert str(error) == "Network failed"

    def test_validation_error(self):
        """Test ValidationError exception."""
        error = ValidationError("Validation failed")

        assert isinstance(error, OdysseusError)
        assert isinstance(error, Exception)
        assert str(error) == "Validation failed"
