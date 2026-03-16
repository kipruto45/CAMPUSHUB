"""
Storage System for CampusHub.

This module provides:
- Storage service abstraction
- Storage backends
- Access control
- Quota management
"""

from apps.core.storage.service import (
    # Enums
    FileCategory,
    FileVisibility,
    StorageType,
    # Data classes
    FileMetadata,
    StorageResult,
    # Service
    StorageService,
    get_storage_service,
    # Access control
    FileAccessControl,
    # Quota
    StorageQuota,
    # Backends
    LocalStorageBackend,
    CloudinaryStorageBackend,
)

__all__ = [
    # Enums
    "FileCategory",
    "FileVisibility",
    "StorageType",
    # Data classes
    "FileMetadata",
    "StorageResult",
    # Service
    "StorageService",
    "get_storage_service",
    # Access control
    "FileAccessControl",
    # Quota
    "StorageQuota",
    # Backends
    "LocalStorageBackend",
    "CloudinaryStorageBackend",
]
