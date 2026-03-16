"""
Enhanced Caching System for CampusHub.

Provides:
- Multi-layer caching (Redis + memory)
- Cache invalidation strategies
- Cache decorators
- Cache statistics
"""

import functools
import hashlib
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Generic, TypeVar

from django.core.cache import cache

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheStrategy(Enum):
    """Cache strategies."""
    CACHE_FIRST = "cache_first"  # Try cache, fallback to function
    FUNCTION_FIRST = "function_first"  # Try function, cache result
    STALE_WHILE_REVALIDATE = "stale_while_revalidate"  # Return stale while revalidating


@dataclass
class CacheOptions:
    """Cache options."""
    timeout: int = 300  # Cache timeout in seconds
    prefix: str = "default"  # Cache key prefix
    strategy: CacheStrategy = CacheStrategy.CACHE_FIRST
    stale_timeout: int = 60  # Stale cache timeout
    tags: list[str] = field(default_factory=list)


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    value: Any
    created_at: datetime
    expires_at: datetime
    tags: list[str] = field(default_factory=list)
    is_stale: bool = False
    
    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at


class CacheBackend(ABC):
    """Abstract cache backend."""
    
    @abstractmethod
    def get(self, key: str) -> Any:
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, timeout: int) -> bool:
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        pass


class RedisCacheBackend(CacheBackend):
    """Redis cache backend."""
    
    def __init__(self, cache_instance=None):
        self._cache = cache_instance or cache
    
    def get(self, key: str) -> Any:
        try:
            return self._cache.get(key)
        except Exception as e:
            logger.warning(f"Redis get error for key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, timeout: int) -> bool:
        try:
            self._cache.set(key, value, timeout)
            return True
        except Exception as e:
            logger.warning(f"Redis set error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        try:
            self._cache.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis delete error for key {key}: {e}")
            return False
    
    def clear(self) -> bool:
        try:
            self._cache.clear()
            return True
        except Exception as e:
            logger.warning(f"Redis clear error: {e}")
            return False


class MemoryCacheBackend(CacheBackend):
    """In-memory cache backend for local development."""
    
    def __init__(self):
        self._cache: dict[str, CacheEntry] = {}
    
    def get(self, key: str) -> Any:
        entry = self._cache.get(key)
        if entry is None:
            return None
        if entry.is_expired:
            del self._cache[key]
            return None
        return entry.value
    
    def set(self, key: str, value: Any, timeout: int) -> bool:
        now = datetime.now()
        self._cache[key] = CacheEntry(
            value=value,
            created_at=now,
            expires_at=now + timedelta(seconds=timeout),
        )
        return True
    
    def delete(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def clear(self) -> bool:
        self._cache.clear()
        return True


class EnhancedCacheService:
    """
    Enhanced cache service with multi-backend support.
    
    Features:
    - Automatic key generation
    - Cache tagging
    - Stale-while-revalidate pattern
    - Cache statistics
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Use Redis by default
        try:
            self._backend = RedisCacheBackend()
        except Exception:
            logger.warning("Redis not available, using memory cache")
            self._backend = MemoryCacheBackend()
        
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0,
        }
        self._initialized = True
    
    @staticmethod
    def generate_key(prefix: str, *args, **kwargs) -> str:
        """Generate cache key."""
        parts = [prefix]
        
        # Add positional args
        for arg in args:
            if arg is not None:
                parts.append(str(arg))
        
        # Add sorted kwargs
        if kwargs:
            kwargs_str = str(sorted(kwargs.items()))
            kwargs_hash = hashlib.md5(kwargs_str.encode()).hexdigest()[:8]
            parts.append(kwargs_hash)
        
        return ":".join(parts)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        try:
            value = self._backend.get(key)
            if value is not None:
                self._stats["hits"] += 1
                return value
            self._stats["misses"] += 1
            return default
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            self._stats["errors"] += 1
            return default
    
    def set(self, key: str, value: Any, timeout: int = 300, tags: list[str] = None) -> bool:
        """Set value in cache."""
        try:
            result = self._backend.set(key, value, timeout)
            if result:
                self._stats["sets"] += 1
            return result
        except Exception as e:
            logger.warning(f"Cache set error: {e}")
            self._stats["errors"] += 1
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            result = self._backend.delete(key)
            if result:
                self._stats["deletes"] += 1
            return result
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")
            self._stats["errors"] += 1
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern."""
        # For Redis, use scan_iter
        try:
            from django.core.cache.backends.redis import RedisCache
            if isinstance(self._backend, RedisCacheBackend) or isinstance(cache, RedisCache):
                redis_client = cache.client.get_client()
                keys = list(redis_client.scan_iter(match=pattern))
                if keys:
                    return redis_client.delete(*keys)
        except Exception as e:
            logger.warning(f"Cache delete pattern error: {e}")
        return 0
    
    def get_many(self, keys: list[str]) -> dict:
        """Get multiple values."""
        result = {}
        for key in keys:
            value = self.get(key)
            if value is not None:
                result[key] = value
        return result
    
    def set_many(self, data: dict, timeout: int = 300) -> bool:
        """Set multiple values."""
        success = True
        for key, value in data.items():
            if not self.set(key, value, timeout):
                success = False
        return success
    
    def clear(self) -> bool:
        """Clear all cache."""
        return self._backend.clear()
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0
        
        return {
            **self._stats,
            "total_requests": total,
            "hit_rate": round(hit_rate, 2),
        }
    
    def reset_stats(self):
        """Reset statistics."""
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0,
        }


# Singleton instance
_cache_service = None


def get_cache_service() -> EnhancedCacheService:
    """Get cache service singleton."""
    global _cache_service
    if _cache_service is None:
        _cache_service = EnhancedCacheService()
    return _cache_service


# Decorators
def cached(timeout: int = 300, key_prefix: str = None):
    """
    Decorator for caching function results.
    
    Usage:
        @cached(timeout=600, key_prefix="user")
        def get_user_data(user_id):
            # Expensive operation
            return data
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            prefix = key_prefix or f"{func.__module__}.{func.__name__}"
            cache_key = EnhancedCacheService.generate_key(prefix, *args, **kwargs)
            
            # Try cache first
            cache = get_cache_service()
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            cache.set(cache_key, result, timeout)
            
            return result
        
        # Add cache invalidation method
        wrapper.invalidate = lambda *args, **kwargs: (
            get_cache_service().delete(
                EnhancedCacheService.generate_key(
                    key_prefix or f"{func.__module__}.{func.__name__}",
                    *args, **kwargs
                )
            )
        )
        
        return wrapper
    
    return decorator


def cache_on_action(model_name: str, action: str = "save"):
    """
    Decorator to invalidate cache on model action.
    
    Usage:
        @cache_on_action("user", "save")
        def update_user(user):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Invalidate related caches
            cache = get_cache_service()
            pattern = f"{model_name}:*"
            cache.delete_pattern(pattern)
            
            return result
        
        return wrapper
    
    return decorator


def cached_property(timeout: int = 300):
    """
    Decorator for caching property results.
    
    Usage:
        class User:
            @cached_property(timeout=600)
            def profile_data(self):
                return expensive_calculation()
    """
    def decorator(func: Callable) -> Callable:
        attr_name = f"_cached_{func.__name__}"
        
        @property
        @functools.wraps(func)
        def wrapper(self):
            if not hasattr(self, attr_name):
                cache_key = f"{self.__class__.__name__}:{getattr(self, 'pk', id(self))}:{func.__name__}"
                cache = get_cache_service()
                
                cached_value = cache.get(cache_key)
                if cached_value is not None:
                    setattr(self, attr_name, cached_value)
                    return cached_value
                
                result = func(self)
                setattr(self, attr_name, result)
                cache.set(cache_key, result, timeout)
                return result
            
            return getattr(self, attr_name)
        
        return wrapper
    
    return decorator


# Context manager for cache
class cache_context:
    """Context manager for cache operations."""
    
    def __init__(self, key: str, timeout: int = 300):
        self.key = key
        self.timeout = timeout
        self.value = None
        self.cache = get_cache_service()
    
    def __enter__(self):
        self.value = self.cache.get(self.key)
        return self.value
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # Only cache if no exception
            pass
    
    def set(self, value):
        self.cache.set(self.key, value, self.timeout)


# Lazy cache invalidation
class CacheInvalidator:
    """Batch cache invalidation."""
    
    def __init__(self):
        self._invalidate_queue: list[str] = []
    
    def add(self, key: str):
        self._invalidate_queue.append(key)
    
    def add_pattern(self, pattern: str):
        self._invalidate_queue.append(f"_pattern:{pattern}")
    
    def commit(self):
        """Execute all invalidations."""
        cache = get_cache_service()
        
        for item in self._invalidate_queue:
            if item.startswith("_pattern:"):
                pattern = item[9:]
                cache.delete_pattern(pattern)
            else:
                cache.delete(item)
        
        self._invalidate_queue.clear()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.commit()


# Import the old CacheService for backwards compatibility
from apps.core.cache.cache_legacy import CacheService as OldCacheService


class CacheService:
    """Unified cache service - combines old and new."""
    
    # Delegate to new implementation
    DEFAULT_TIMEOUT = 300
    
    @staticmethod
    def generate_key(prefix: str, *args, **kwargs) -> str:
        return EnhancedCacheService.generate_key(prefix, *args, **kwargs)
    
    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        return get_cache_service().get(key, default)
    
    @staticmethod
    def set(key: str, value: Any, timeout: int = None) -> bool:
        timeout = timeout or CacheService.DEFAULT_TIMEOUT
        return get_cache_service().set(key, value, timeout)
    
    @staticmethod
    def delete(key: str) -> bool:
        return get_cache_service().delete(key)
    
    @staticmethod
    def delete_pattern(pattern: str) -> int:
        return get_cache_service().delete_pattern(pattern)
    
    @staticmethod
    def get_many(keys: list) -> dict:
        return get_cache_service().get_many(keys)
    
    @staticmethod
    def set_many(data: dict, timeout: int = None) -> bool:
        timeout = timeout or CacheService.DEFAULT_TIMEOUT
        return get_cache_service().set_many(data, timeout)
    
    @staticmethod
    def clear() -> bool:
        return get_cache_service().clear()
    
    @staticmethod
    def get_stats() -> dict:
        return get_cache_service().get_stats()
    
    @staticmethod
    def reset_stats():
        return get_cache_service().reset_stats()
    
    # Smart caching methods (from old implementation)
    @staticmethod
    def cache_user_data(user_id: int, data: Any, timeout: int = 1800) -> bool:
        key = CacheService.generate_key("user", user_id)
        return CacheService.set(key, data, timeout)
    
    @staticmethod
    def get_user_data(user_id: int, default: Any = None) -> Any:
        key = CacheService.generate_key("user", user_id)
        return CacheService.get(key, default)
    
    @staticmethod
    def invalidate_user_cache(user_id: int) -> bool:
        pattern = f"user:{user_id}*"
        return CacheService.delete_pattern(pattern) > 0
    
    @staticmethod
    def cache_resource(resource_id: int, data: Any, timeout: int = 600) -> bool:
        key = CacheService.generate_key("resource", resource_id)
        return CacheService.set(key, data, timeout)
    
    @staticmethod
    def get_resource(resource_id: int, default: Any = None) -> Any:
        key = CacheService.generate_key("resource", resource_id)
        return CacheService.get(key, default)
    
    @staticmethod
    def invalidate_resource_cache(resource_id: int) -> bool:
        key = CacheService.generate_key("resource", resource_id)
        return CacheService.delete(key)
    
    @staticmethod
    def cache_analytics(key_suffix: str, data: Any, timeout: int = 3600) -> bool:
        key = CacheService.generate_key("analytics", key_suffix)
        return CacheService.set(key, data, timeout)
    
    @staticmethod
    def get_analytics(key_suffix: str, default: Any = None) -> Any:
        key = CacheService.generate_key("analytics", key_suffix)
        return CacheService.get(key, default)
    
    @staticmethod
    def invalidate_analytics_cache() -> bool:
        pattern = "analytics:*"
        return CacheService.delete_pattern(pattern) > 0
