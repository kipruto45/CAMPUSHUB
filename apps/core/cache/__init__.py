"""
Cache package compatibility layer.

This module preserves the legacy public API used across the project and test
suite while still exposing the newer enhanced cache utilities.
"""

import hashlib
import json
from functools import wraps
from typing import Any, Callable

from django.core.cache import cache

from apps.core.cache.cache_legacy import CacheService as _OldCacheService
from apps.core.cache.enhanced import (
    CacheInvalidator,
    CacheOptions,
    CacheStrategy,
    EnhancedCacheService,
    cache_context,
    cache_on_action,
    cached as enhanced_cached,
    cached_property,
    get_cache_service,
)


class CacheService:
    """Legacy-compatible cache service bound to this module's cache object."""

    DEFAULT_TIMEOUT = 3600

    @staticmethod
    def generate_key(prefix: str, *args, **kwargs) -> str:
        parts = [prefix]
        for arg in args:
            if arg is not None:
                parts.append(str(arg))
        if kwargs:
            kwargs_str = json.dumps(kwargs, sort_keys=True, default=str)
            kwargs_hash = hashlib.md5(kwargs_str.encode()).hexdigest()[:8]
            parts.append(kwargs_hash)
        return ":".join(parts)

    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        value = cache.get(key, default)
        return default if value is None else value

    @staticmethod
    def set(key: str, value: Any, timeout: int | None = None) -> bool:
        cache.set(key, value, timeout or CacheService.DEFAULT_TIMEOUT)
        return True

    @staticmethod
    def delete(key: str) -> bool:
        cache.delete(key)
        return True

    @staticmethod
    def clear() -> bool:
        cache.clear()
        return True

    @staticmethod
    def cache_user_data(user_id: int, data: Any, timeout: int = 1800) -> bool:
        key = CacheService.generate_key("user", user_id)
        return CacheService.set(key, data, timeout)

    @staticmethod
    def get_user_data(user_id: int, default: Any = None) -> Any:
        key = CacheService.generate_key("user", user_id)
        return CacheService.get(key, default)

    @staticmethod
    def cache_resource(resource_id: int, data: Any, timeout: int = 600) -> bool:
        key = CacheService.generate_key("resource", resource_id)
        return CacheService.set(key, data, timeout)

    @staticmethod
    def get_resource(resource_id: int, default: Any = None) -> Any:
        key = CacheService.generate_key("resource", resource_id)
        return CacheService.get(key, default)

    @staticmethod
    def cache_analytics(analytics_type: str, data: Any, timeout: int = 300) -> bool:
        key = CacheService.generate_key("analytics", analytics_type)
        return CacheService.set(key, data, timeout)

    @staticmethod
    def get_analytics(analytics_type: str, default: Any = None) -> Any:
        key = CacheService.generate_key("analytics", analytics_type)
        return CacheService.get(key, default)


def cached(timeout: int = 3600, key_prefix: str | None = None):
    """Legacy-compatible cache decorator bound to this module's cache object."""

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            prefix = key_prefix or func.__name__
            cache_key = CacheService.generate_key(prefix, *args, **kwargs)
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            return result

        return wrapper

    return decorator


class CacheStats:
    """Legacy-compatible cache stats helper."""

    @staticmethod
    def clear_all() -> bool:
        cache.clear()
        return True


__all__ = [
    "cache",
    "CacheService",
    "CacheStats",
    "EnhancedCacheService",
    "CacheStrategy",
    "CacheOptions",
    "get_cache_service",
    "cached",
    "enhanced_cached",
    "cached_property",
    "cache_on_action",
    "cache_context",
    "CacheInvalidator",
    "_OldCacheService",
]
