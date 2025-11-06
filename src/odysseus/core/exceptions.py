"""
Custom exceptions for Odysseus.
"""


class OdysseusError(Exception):
    """Base exception for Odysseus."""
    pass


class SearchError(OdysseusError):
    """Exception raised when search operations fail."""
    pass


class DownloadError(OdysseusError):
    """Exception raised when download operations fail."""
    pass


class MetadataError(OdysseusError):
    """Exception raised when metadata operations fail."""
    pass


class ConfigurationError(OdysseusError):
    """Exception raised when configuration is invalid."""
    pass


class APIError(OdysseusError):
    """Exception raised when API calls fail."""
    pass


class NetworkError(OdysseusError, ConnectionError):
    """Exception raised when network operations fail."""
    pass
