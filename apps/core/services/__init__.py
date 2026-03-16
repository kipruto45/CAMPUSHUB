"""
Core Services for CampusHub.

This module provides:
- Base service classes
- Service registry
- Common services
"""

from apps.core.services.base import (
    BaseService,
    BulkWriteService,
    CacheableServiceMixin,
    ReadOnlyService,
    ServiceContext,
    ServiceResult,
    WriteService,
)

from apps.core.services.registry import (
    ServiceRegistry,
    get_service,
)

__all__ = [
    # Base classes
    "BaseService",
    "ReadOnlyService",
    "WriteService",
    "BulkWriteService",
    "CacheableServiceMixin",
    "ServiceContext",
    "ServiceResult",
    # Registry
    "ServiceRegistry",
    "get_service",
]
