"""
Custom exceptions for Odysseus.
"""
from typing import Optional, Dict, Any


class OdysseusError(Exception):
    """Base exception for Odysseus."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Initialize exception.
        
        Args:
            message: Error message
            details: Optional dictionary with additional error details
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        """Return formatted error message."""
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


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


class ValidationError(OdysseusError):
    """Exception raised when validation fails."""
    pass
