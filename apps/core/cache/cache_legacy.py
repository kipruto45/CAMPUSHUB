"""
Caching utilities for CampusHub.
Provides caching service with in-memory (locmem) backend.
"""

import hashlib
import json
import logging
from functools import wraps
from typing import Any, Callable

from django.core.cache import cache

logger = logging.getLogger(__name__)


class CacheService:
    """
    Centralized caching service using in-memory cache.
    Provides methods for caching, invalidation, and smart cache management.
    """

    # Cache key prefixes
    USER_PREFIX = "user"
    RESOURCE_PREFIX = "resource"
    ANALYTICS_PREFIX = "analytics"
    NOTIFICATION_PREFIX = "notification"
    SEARCH_PREFIX = "search"
    RECOMMENDATION_PREFIX = "recommendation"
    DASHBOARD_PREFIX = "dashboard"

    # Default timeout (1 hour)
    DEFAULT_TIMEOUT = 3600

    @staticmethod
    def generate_key(prefix: str, *args, **kwargs) -> str:
        """
        Generate a unique cache key from prefix and arguments.

        Args:
            prefix: Key prefix (e.g., 'user', 'resource')
            *args: Positional arguments to include in key
            **kwargs: Keyword arguments to include in key

        Returns:
            Unique cache key string
        """
        parts = [prefix]

        # Add positional args
        for arg in args:
            if arg is not None:
                parts.append(str(arg))

        # Add sorted kwargs
        if kwargs:
            kwargs_str = json.dumps(kwargs, sort_keys=True, default=str)
            kwargs_hash = hashlib.md5(kwargs_str.encode()).hexdigest()[:8]
            parts.append(kwargs_hash)

        return ":".join(parts)

    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """
        Get value from cache.

        Args:
            key: Cache key
            default: Default value if key not found

        Returns:
            Cached value or default
        """
        try:
            value = cache.get(key, default)
            return default if value is None else value
        except Exception as e:
            logger.warning(f"Cache get error for key {key}: {e}")
            return default

    @staticmethod
    def set(key: str, value: Any, timeout: int = None) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            timeout: Timeout in seconds (default: 1 hour)

        Returns:
            True if successful
        """
        try:
            timeout = timeout or CacheService.DEFAULT_TIMEOUT
            cache.set(key, value, timeout)
            return True
        except Exception as e:
            logger.warning(f"Cache set error for key {key}: {e}")
            return False

    @staticmethod
    def delete(key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key to delete

        Returns:
            True if successful
        """
        try:
            cache.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete error for key {key}: {e}")
            return False

    @staticmethod
    def delete_pattern(pattern: str) -> int:
        """
        Delete all keys matching pattern.

        Args:
            pattern: Key pattern (e.g., 'user:*')

        Returns:
            Number of keys deleted
        """
        try:
            # Redis cache keys
            from django.core.cache.backends.redis import RedisCache

            if isinstance(cache, RedisCache):
                # Use Redis client directly for pattern deletion
                redis_client = cache.client.get_client()
                keys = list(redis_client.scan_iter(match=pattern))
                if keys:
                    return redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Cache delete pattern error for {pattern}: {e}")
            return 0

    @staticmethod
    def get_many(keys: list) -> dict:
        """
        Get multiple values from cache.

        Args:
            keys: List of cache keys

        Returns:
            Dictionary of key-value pairs
        """
        try:
            return cache.get_many(keys)
        except Exception as e:
            logger.warning(f"Cache get_many error: {e}")
            return {}

    @staticmethod
    def set_many(data: dict, timeout: int = None) -> bool:
        """
        Set multiple values in cache.

        Args:
            data: Dictionary of key-value pairs
            timeout: Timeout in seconds

        Returns:
            True if successful
        """
        try:
            timeout = timeout or CacheService.DEFAULT_TIMEOUT
            cache.set_many(data, timeout)
            return True
        except Exception as e:
            logger.warning(f"Cache set_many error: {e}")
            return False

    # Smart caching methods for common use cases

    @staticmethod
    def cache_user_data(user_id: int, data: Any, timeout: int = 1800) -> bool:
        """
        Cache user-specific data (30 min default).
        """
        key = CacheService.generate_key(CacheService.USER_PREFIX, user_id)
        return CacheService.set(key, data, timeout)

    @staticmethod
    def get_user_data(user_id: int, default: Any = None) -> Any:
        """
        Get cached user data.
        """
        key = CacheService.generate_key(CacheService.USER_PREFIX, user_id)
        return CacheService.get(key, default)

    @staticmethod
    def invalidate_user_cache(user_id: int) -> bool:
        """
        Invalidate all cache for a specific user.
        """
        pattern = f"{CacheService.USER_PREFIX}:{user_id}*"
        return CacheService.delete_pattern(pattern) > 0

    @staticmethod
    def cache_resource(resource_id: int, data: Any, timeout: int = 600) -> bool:
        """
        Cache resource data (10 min default).
        """
        key = CacheService.generate_key(CacheService.RESOURCE_PREFIX, resource_id)
        return CacheService.set(key, data, timeout)

    @staticmethod
    def get_resource(resource_id: int, default: Any = None) -> Any:
        """
        Get cached resource data.
        """
        key = CacheService.generate_key(CacheService.RESOURCE_PREFIX, resource_id)
        return CacheService.get(key, default)

    @staticmethod
    def invalidate_resource_cache(resource_id: int) -> bool:
        """
        Invalidate cache for a specific resource.
        """
        key = CacheService.generate_key(CacheService.RESOURCE_PREFIX, resource_id)
        return CacheService.delete(key)

    @staticmethod
    def cache_analytics(key_suffix: str, data: Any, timeout: int = 3600) -> bool:
        """
        Cache analytics data (1 hour default).
        """
        key = CacheService.generate_key(CacheService.ANALYTICS_PREFIX, key_suffix)
        return CacheService.set(key, data, timeout)

    @staticmethod
    def get_analytics(key_suffix: str, default: Any = None) -> Any:
        """
        Get cached analytics data.
        """
        key = CacheService.generate_key(CacheService.ANALYTICS_PREFIX, key_suffix)
        return CacheService.get(key, default)

    @staticmethod
    def invalidate_analytics_cache() -> bool:
        """
        Invalidate all analytics cache.
        """
        pattern = f"{CacheService.ANALYTICS_PREFIX}:*"
        return CacheService.delete_pattern(pattern) > 0

    @staticmethod
    def cache_search_results(
        query: str, filters: dict, data: Any, timeout: int = 300
    ) -> bool:
        """
        Cache search results (5 min default).
        """
        key = CacheService.generate_key(
            CacheService.SEARCH_PREFIX, query=query, **filters
        )
        return CacheService.set(key, data, timeout)

    @staticmethod
    def get_search_results(query: str, filters: dict, default: Any = None) -> Any:
        """
        Get cached search results.
        """
        key = CacheService.generate_key(
            CacheService.SEARCH_PREFIX, query=query, **filters
        )
        return CacheService.get(key, default)


def cached(timeout: int = 3600, key_prefix: str = None):
    """
    Decorator for caching function results.

    Args:
        timeout: Cache timeout in seconds
        key_prefix: Custom key prefix

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            prefix = key_prefix or func.__module__ + "." + func.__name__
            cache_key = CacheService.generate_key(prefix, *args, **kwargs)

            # Try to get from cache
            cached_result = CacheService.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            CacheService.set(cache_key, result, timeout)

            return result

        return wrapper

    return decorator


def invalidate_on_change(model_name: str, instance_id: int):
    """
    Decorator to invalidate cache when model instance changes.

    Args:
        model_name: Name of the model
        instance_id: ID of the instance

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            # Invalidate relevant cache based on model
            if model_name.lower() == "user":
                CacheService.invalidate_user_cache(instance_id)
            elif model_name.lower() == "resource":
                CacheService.invalidate_resource_cache(instance_id)

            return result

        return wrapper

    return decorator


class CacheStats:
    """Track cache statistics."""

    @staticmethod
    def get_stats() -> dict:
        """Get cache statistics."""
        try:
            from django.core.cache.backends.redis import RedisCache

            if isinstance(cache, RedisCache):
                redis_client = cache.client.get_client()
                info = redis_client.info("stats")
                return {
                    "hits": info.get("keyspace_hits", 0),
                    "misses": info.get("keyspace_misses", 0),
                    "memory_used": info.get("used_memory_human", "N/A"),
                }
        except Exception as e:
            logger.warning(f"Error getting cache stats: {e}")

        return {"hits": 0, "misses": 0, "memory_used": "N/A"}

    @staticmethod
    def clear_all() -> bool:
        """Clear all cache."""
        try:
            cache.clear()
            return True
        except Exception as e:
            logger.warning(f"Error clearing cache: {e}")
            return False
