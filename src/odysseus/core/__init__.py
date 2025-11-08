"""
Core module for Odysseus.
Contains configuration, exceptions, logging setup, and validation.
"""

from .config import *
from .exceptions import *
from .logger import setup_logging, get_logger
from .validation import validate_configuration, validate_and_raise, check_dependencies

__all__ = [
    'setup_logging',
    'get_logger',
    'validate_configuration',
    'validate_and_raise',
    'check_dependencies',
    'OdysseusError',
    'SearchError',
    'DownloadError',
    'MetadataError',
    'ConfigurationError',
    'APIError',
    'NetworkError',
]
