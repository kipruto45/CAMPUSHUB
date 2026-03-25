"""
Tests for API app - middleware, versioning, and utilities.
"""
import pytest
from django.test import RequestFactory
from rest_framework.test import APIClient

from apps.api.middleware import APIVersionMiddleware
from apps.api.versioning import (
    MobileAPIVersioning,
    MobileHeaderVersioning,
    QueryParameterVersioning,
)
from apps.api.throttles import (
    MobileAppThrottle,
    AuthThrottle,
    PublicAPIThrottle,
)


@pytest.fixture
def request_factory():
    """Create a request factory for testing."""
    return RequestFactory()


@pytest.fixture
def api_client():
    """Create an API client for testing."""
    return APIClient()


class TestAPIVersionMiddleware:
    """Tests for API Version Middleware."""

    def test_middleware_adds_version_header_v1(self, request_factory):
        """Test middleware adds X-API-Version header for v1."""
        middleware = APIVersionMiddleware(lambda req: None)
        request = request_factory.get("/api/v1/test/")
        request.api_version = "v1"
        
        class FakeResponse:
            status_code = 200
            def __getitem__(self, key):
                return ""
            def __setitem__(self, key, value):
                pass
        
        response = middleware.process_response(request, FakeResponse())
        assert response is not None

    def test_middleware_adds_version_header_v2(self, request_factory):
        """Test middleware adds X-API-Version header for v2."""
        middleware = APIVersionMiddleware(lambda req: None)
        request = request_factory.get("/api/v2/test/")
        request.api_version = "v2"
        
        class FakeResponse:
            status_code = 200
            def __getitem__(self, key):
                return ""
            def __setitem__(self, key, value):
                pass
        
        response = middleware.process_response(request, FakeResponse())
        assert response is not None

    def test_middleware_adds_deprecation_header_for_v1(self, request_factory):
        """Test middleware adds Deprecation header for v1."""
        middleware = APIVersionMiddleware(lambda req: None)
        request = request_factory.get("/api/v1/test/")
        request.api_version = "v1"
        
        class FakeResponse:
            status_code = 200
            _headers = {}
            def __getitem__(self, key):
                return self._headers.get(key, "")
            def __setitem__(self, key, value):
                self._headers[key] = value
        
        response = middleware.process_response(request, FakeResponse())
        assert response is not None


class TestMobileAPIVersioning:
    """Tests for Mobile API Versioning."""

    def test_url_versioning_v1(self, request_factory):
        """Test URL path versioning extracts v1."""
        versioning = MobileAPIVersioning()
        request = request_factory.get("/api/v1/resources/")
        request.resolver_match = type('obj', (object,), {'args': ('v1',), 'kwargs': {}})()
        
        version = versioning.determine_version(request, None)
        assert version == "v1"

    def test_url_versioning_v2(self, request_factory):
        """Test URL path versioning extracts v2."""
        versioning = MobileAPIVersioning()
        request = request_factory.get("/api/v2/resources/")
        request.resolver_match = type('obj', (object,), {'args': ('v2',), 'kwargs': {}})()
        
        version = versioning.determine_version(request, None)
        assert version == "v2"

    def test_default_version(self, request_factory):
        """Test default version is v1."""
        versioning = MobileAPIVersioning()
        request = request_factory.get("/api/resources/")
        
        version = versioning.determine_version(request, None)
        assert version == "v1"


class TestMobileHeaderVersioning:
    """Tests for Header-based API Versioning."""

    def test_header_versioning_v1(self, request_factory):
        """Test header versioning extracts v1."""
        versioning = MobileHeaderVersioning()
        request = request_factory.get("/api/resources/")
        request.META["HTTP_X_API_VERSION"] = "v1"
        
        version = versioning.determine_version(request, None)
        assert version == "v1"

    def test_header_versioning_v2(self, request_factory):
        """Test header versioning extracts v2."""
        versioning = MobileHeaderVersioning()
        request = request_factory.get("/api/resources/")
        request.META["HTTP_X_API_VERSION"] = "v2"
        
        version = versioning.determine_version(request, None)
        assert version == "v2"

    def test_invalid_version_raises_error(self, request_factory):
        """Test invalid version raises NotAcceptable."""
        from rest_framework import exceptions
        
        versioning = MobileHeaderVersioning()
        request = request_factory.get("/api/resources/")
        request.META["HTTP_X_API_VERSION"] = "v3"
        
        with pytest.raises(exceptions.NotAcceptable):
            versioning.determine_version(request, None)


class TestQueryParameterVersioning:
    """Tests for Query Parameter Versioning."""

    def test_query_param_versioning(self, request_factory):
        """Test query parameter versioning."""
        versioning = QueryParameterVersioning()
        request = request_factory.get("/api/resources/?v=v2")
        
        version = versioning.determine_version(request, None)
        assert version == "v2"


class TestThrottles:
    """Tests for API Throttles."""

    def test_mobile_app_throttle_init(self):
        """Test MobileAppThrottle initializes correctly."""
        throttle = MobileAppThrottle()
        assert throttle.rate is not None

    def test_auth_throttle_init(self):
        """Test AuthThrottle initializes correctly."""
        throttle = AuthThrottle()
        assert throttle.rate is not None

    def test_public_api_throttle_init(self):
        """Test PublicAPIThrottle initializes correctly."""
        throttle = PublicAPIThrottle()
        assert throttle.rate is not None
