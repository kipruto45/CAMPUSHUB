"""
Tests for the cache service.
"""

import pytest
from unittest.mock import patch, MagicMock
from apps.core.cache import CacheService, CacheStats, cached


class TestCacheService:
    """Test cases for CacheService."""
    
    @patch('apps.core.cache.cache')
    def test_generate_key_with_args(self, mock_cache):
        """Test key generation with positional arguments."""
        key = CacheService.generate_key('user', 1, 2, 3)
        assert key == 'user:1:2:3'
    
    @patch('apps.core.cache.cache')
    def test_generate_key_with_kwargs(self, mock_cache):
        """Test key generation with keyword arguments."""
        key = CacheService.generate_key('resource', page=1, limit=10)
        # Key should include hash of kwargs
        assert key.startswith('resource:')
    
    @patch('apps.core.cache.cache')
    def test_get_cache_hit(self, mock_cache):
        """Test cache get when key exists."""
        mock_cache.get.return_value = {'data': 'test'}
        result = CacheService.get('test_key')
        assert result == {'data': 'test'}
    
    @patch('apps.core.cache.cache')
    def test_get_cache_miss(self, mock_cache):
        """Test cache get when key doesn't exist."""
        mock_cache.get.return_value = None
        result = CacheService.get('nonexistent_key', default='default_value')
        assert result == 'default_value'
    
    @patch('apps.core.cache.cache')
    def test_set_cache(self, mock_cache):
        """Test setting cache value."""
        result = CacheService.set('test_key', 'test_value', timeout=60)
        assert result is True
        mock_cache.set.assert_called_once()
    
    @patch('apps.core.cache.cache')
    def test_delete_cache(self, mock_cache):
        """Test deleting cache key."""
        result = CacheService.delete('test_key')
        assert result is True
        mock_cache.delete.assert_called_once_with('test_key')
    
    @patch('apps.core.cache.cache')
    def test_cache_user_data(self, mock_cache):
        """Test caching user data."""
        result = CacheService.cache_user_data(1, {'name': 'John'}, timeout=1800)
        assert result is True
        mock_cache.set.assert_called()
    
    @patch('apps.core.cache.cache')
    def test_get_user_data(self, mock_cache):
        """Test getting cached user data."""
        mock_cache.get.return_value = {'name': 'John'}
        result = CacheService.get_user_data(1)
        assert result == {'name': 'John'}
    
    @patch('apps.core.cache.cache')
    def test_cache_resource(self, mock_cache):
        """Test caching resource data."""
        result = CacheService.cache_resource(1, {'title': 'Test'}, timeout=600)
        assert result is True
    
    @patch('apps.core.cache.cache')
    def test_get_resource(self, mock_cache):
        """Test getting cached resource."""
        mock_cache.get.return_value = {'title': 'Test'}
        result = CacheService.get_resource(1)
        assert result == {'title': 'Test'}
    
    @patch('apps.core.cache.cache')
    def test_cache_analytics(self, mock_cache):
        """Test caching analytics data."""
        result = CacheService.cache_analytics('dashboard', {'total': 100})
        assert result is True
    
    @patch('apps.core.cache.cache')
    def test_get_analytics(self, mock_cache):
        """Test getting cached analytics."""
        mock_cache.get.return_value = {'total': 100}
        result = CacheService.get_analytics('dashboard')
        assert result == {'total': 100}


class TestCachedDecorator:
    """Test cases for @cached decorator."""
    
    @patch('apps.core.cache.cache')
    def test_cached_decorator_caches_result(self, mock_cache):
        """Test that decorator caches function result."""
        mock_cache.get.return_value = None
        
        @cached(timeout=60)
        def expensive_function(x):
            return x * 2
        
        result = expensive_function(5)
        assert result == 10
        mock_cache.set.assert_called()
    
    @patch('apps.core.cache.cache')
    def test_cached_decorator_returns_cached(self, mock_cache):
        """Test that decorator returns cached value."""
        mock_cache.get.return_value = 100
        
        @cached(timeout=60)
        def expensive_function(x):
            return x * 2
        
        result = expensive_function(5)
        assert result == 100
        mock_cache.set.assert_not_called()


class TestCacheStats:
    """Test cases for CacheStats."""
    
    @patch('apps.core.cache.cache')
    def test_clear_all(self, mock_cache):
        """Test clearing all cache."""
        result = CacheStats.clear_all()
        assert result is True
        mock_cache.clear.assert_called_once()
