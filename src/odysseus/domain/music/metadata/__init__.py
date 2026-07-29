"""
Music metadata domain module.
"""

from .metadata_service import MetadataService
from .duration_recovery import DurationRecoveryService

__all__ = [
    'MetadataService',
    'DurationRecoveryService'
]
