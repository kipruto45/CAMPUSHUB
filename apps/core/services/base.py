"""
Base Service Classes for CampusHub Service Layer.

This module provides the foundation for service-based architecture:
- BaseService: Abstract base class for all services
- ReadOnlyService: For read-only operations
- WriteService: For CRUD operations
- ServiceResult: Standardized service response
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from django.db import models
from django.db.models import QuerySet
from django.db import transaction


T = TypeVar('T', bound=models.Model)
R = TypeVar('R')


@dataclass
class ServiceResult(Generic[R]):
    """
    Standardized service response.
    
    Attributes:
        success: Whether the operation succeeded
        data: The result data
        error: Error message if failed
        errors: List of validation errors
        warnings: List of warnings
    """
    success: bool
    data: R | None = None
    error: str | None = None
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    
    @classmethod
    def ok(cls, data: R = None, warnings: list[str] = None) -> 'ServiceResult[R]':
        """Create a successful result."""
        return cls(success=True, data=data, warnings=warnings or [])
    
    @classmethod
    def error(cls, error: str, errors: list[dict] = None) -> 'ServiceResult[R]':
        """Create an error result."""
        return cls(success=False, error=error, errors=errors or [])
    
    @classmethod
    def validation_error(cls, errors: list[dict]) -> 'ServiceResult[R]':
        """Create a validation error result."""
        return cls(success=False, error="Validation failed", errors=errors)
    
    @property
    def is_error(self) -> bool:
        return not self.success
    
    @property
    def is_ok(self) -> bool:
        return self.success


class BaseService(ABC):
    """
    Abstract base class for all services.
    
    Provides common functionality:
    - Logging
    - Validation
    - Error handling
    - Cache integration
    """
    
    # Enable caching for this service
    use_cache: bool = False
    
    # Cache timeout in seconds
    cache_timeout: int = 300
    
    def __init__(self, context: ServiceContext | None = None):
        self._logger = None
        self.context = context or ServiceContext()
    
    @property
    def logger(self):
        """Lazy-load logger."""
        if self._logger is None:
            import logging
            self._logger = logging.getLogger(self.__class__.__module__)
        return self._logger
    
    def log_info(self, message: str, **kwargs):
        """Log info message."""
        self.logger.info(message, extra=kwargs)
    
    def log_error(self, message: str, **kwargs):
        """Log error message."""
        self.logger.error(message, extra=kwargs)
    
    def log_warning(self, message: str, **kwargs):
        """Log warning message."""
        self.logger.warning(message, extra=kwargs)


class ReadOnlyService(BaseService, Generic[T]):
    """
    Service for read-only operations.
    
    Provides:
    - Query building
    - Caching
    - Pagination
    """
    
    model_class: type[T] | None = None
    
    def __init__(self):
        super().__init__()
        self._queryset: QuerySet[T] | None = None
    
    @property
    def queryset(self) -> QuerySet[T]:
        """Get base queryset."""
        if self._queryset is None:
            if self.model_class:
                self._queryset = self.model_class.objects.all()
            else:
                raise NotImplementedError("model_class must be defined")
        return self._queryset
    
    def get_queryset(self) -> QuerySet[T]:
        """Override to customize queryset."""
        return self.queryset
    
    def filter(self, **kwargs) -> QuerySet[T]:
        """Apply filters to queryset."""
        return self.get_queryset().filter(**kwargs)
    
    def get(self, **kwargs) -> T | None:
        """Get single object."""
        return self.get_queryset().filter(**kwargs).first()
    
    def get_or_404(self, **kwargs) -> T:
        """Get single object or raise Http404."""
        from django.http import Http404
        obj = self.get(**kwargs)
        if obj is None:
            raise Http404(f"{self.model_class.__name__} not found")
        return obj
    
    def all(self) -> QuerySet[T]:
        """Get all objects."""
        return self.get_queryset()
    
    def count(self, **kwargs) -> int:
        """Count objects with optional filters."""
        return self.filter(**kwargs).count()
    
    def exists(self, **kwargs) -> bool:
        """Check if object exists."""
        return self.filter(**kwargs).exists()
    
    def list(self, page: int = 1, page_size: int = 20) -> list[T]:
        """Get paginated list."""
        offset = (page - 1) * page_size
        return list(self.get_queryset()[offset:offset + page_size])
    
    def first(self) -> T | None:
        """Get first object."""
        return self.get_queryset().first()
    
    def last(self) -> T | None:
        """Get last object."""
        return self.get_queryset().last()
    
    def order_by(self, *fields: str) -> QuerySet[T]:
        """Order queryset."""
        return self.get_queryset().order_by(*fields)


class WriteService(ReadOnlyService[T], Generic[T]):
    """
    Service for CRUD operations.
    
    Provides:
    - Create, Update, Delete operations
    - Validation
    - Cache invalidation
    - Transaction handling
    """
    
    def __init__(self):
        super().__init__()
        self._validation_errors: list[dict] = []
    
    def validate(self, data: dict, partial: bool = False) -> bool:
        """
        Validate data before save.
        
        Override in subclass for custom validation.
        Returns True if valid, False otherwise.
        """
        self._validation_errors = []
        return True
    
    def _get_validation_errors(self) -> list[dict]:
        return self._validation_errors
    
    def _add_validation_error(self, field: str, message: str, code: str = None):
        error = {"field": field, "message": message}
        if code:
            error["code"] = code
        self._validation_errors.append(error)
    
    def create(self, data: dict, commit: bool = True) -> ServiceResult[T]:
        """Create new object."""
        # Validate
        if not self.validate(data, partial=False):
            return ServiceResult.validation_error(self._get_validation_errors())

        try:
            if self.model_class is None:
                raise NotImplementedError("model_class must be defined")

            obj = self.model_class(**data)

            if commit:
                with transaction.atomic():
                    obj.save()
                    self._after_create(obj, data)

            return ServiceResult.ok(obj)

        except Exception as e:
            self.log_error(f"Create failed: {str(e)}")
            return ServiceResult.error(f"Failed to create: {str(e)}")

    def update(self, instance: T, data: dict, commit: bool = True) -> ServiceResult[T]:
        """Update existing object."""
        # Validate
        if not self.validate(data, partial=True):
            return ServiceResult.validation_error(self._get_validation_errors())

        try:
            for key, value in data.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)

            if commit:
                with transaction.atomic():
                    instance.save()
                    self._after_update(instance, data)

            return ServiceResult.ok(instance)

        except Exception as e:
            self.log_error(f"Update failed: {str(e)}")
            return ServiceResult.error(f"Failed to update: {str(e)}")

    def delete(self, instance: T, commit: bool = True) -> ServiceResult[None]:
        """Delete object."""
        try:
            obj_id = instance.pk
            if commit:
                with transaction.atomic():
                    instance.delete()
                    self._after_delete(instance, obj_id)

            return ServiceResult.ok()

        except Exception as e:
            self.log_error(f"Delete failed: {str(e)}")
            return ServiceResult.error(f"Failed to delete: {str(e)}")
    
    def _after_create(self, instance: T, data: dict):
        """Hook after create."""
        pass
    
    def _after_update(self, instance: T, data: dict):
        """Hook after update."""
        pass
    
    def _after_delete(self, instance: T, instance_id: Any):
        """Hook after delete."""
        pass


class BulkWriteService(WriteService[T], Generic[T]):
    """
    Service for bulk operations.
    """
    
    def bulk_create(self, data_list: list[dict], batch_size: int = 100) -> ServiceResult[list[T]]:
        """Bulk create objects."""
        try:
            if self.model_class is None:
                raise NotImplementedError("model_class must be defined")

            # Validate all first
            for data in data_list:
                if not self.validate(data, partial=False):
                    return ServiceResult.validation_error(self._get_validation_errors())

            # Create objects
            objects = [self.model_class(**data) for data in data_list]
            with transaction.atomic():
                self.model_class.objects.bulk_create(objects, batch_size=batch_size)

            return ServiceResult.ok(objects)

        except Exception as e:
            self.log_error(f"Bulk create failed: {str(e)}")
            return ServiceResult.error(f"Failed to bulk create: {str(e)}")

    def bulk_update(self, data_list: list[tuple[T, dict]], fields: list[str], batch_size: int = 100) -> ServiceResult[int]:
        """Bulk update objects."""
        try:
            if self.model_class is None:
                raise NotImplementedError("model_class must be defined")

            count = 0
            for instance, data in data_list:
                for key, value in data.items():
                    if key in fields:
                        setattr(instance, key, value)
                count += 1

            with transaction.atomic():
                self.model_class.objects.bulk_update(
                    [i for i, _ in data_list], fields, batch_size=batch_size
                )

            return ServiceResult.ok(count)

        except Exception as e:
            self.log_error(f"Bulk update failed: {str(e)}")
            return ServiceResult.error(f"Failed to bulk update: {str(e)}")


class CacheableServiceMixin:
    """Mixin for adding cache to services."""
    
    def get_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key."""
        from apps.core.cache import CacheService
        return CacheService.generate_key(prefix, *args, **kwargs)
    
    def get_cached(self, key: str, default: Any = None) -> Any:
        """Get from cache."""
        from apps.core.cache import CacheService
        return CacheService.get(key, default)
    
    def set_cached(self, key: str, value: Any, timeout: int = None) -> bool:
        """Set in cache."""
        from apps.core.cache import CacheService
        timeout = timeout or self.cache_timeout
        return CacheService.set(key, value, timeout)
    
    def invalidate_cache(self, key: str) -> bool:
        """Invalidate cache."""
        from apps.core.cache import CacheService
        return CacheService.delete(key)


class ServiceContext:
    """
    Service context for passing user/request information.
    
    Usage:
        context = ServiceContext(user=request.user, request=request)
        service = ResourceService(context=context)
    """
    
    def __init__(self, user=None, request=None, **kwargs):
        self.user = user
        self.request = request
        self.extra = kwargs
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get extra attribute."""
        return self.extra.get(key, default)
    
    @property
    def is_authenticated(self) -> bool:
        return self.user is not None and self.user.is_authenticated
    
    @property
    def is_admin(self) -> bool:
        return hasattr(self.user, 'is_admin') and self.user.is_admin
    
    @property
    def is_moderator(self) -> bool:
        return hasattr(self.user, 'is_moderator') and self.user.is_moderator
