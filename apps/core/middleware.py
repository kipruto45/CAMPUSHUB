"""Core middleware used across API and web requests."""

from __future__ import annotations

import os
import time
import uuid

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

# Allow importing compatibility submodules like
# `apps.core.middleware.api_version_headers` even though this module is
# historically a single-file middleware module.
__path__ = [os.path.join(os.path.dirname(__file__), "middleware")]


class RequestContextMiddleware:
    """
    Attach request context headers used by mobile and backend observability.

    - Generates or propagates a request id.
    - Exposes request id in `X-Request-ID` response header.
    - Exposes mobile API version header for `/api/mobile/` requests.
    """

    request_id_header = "HTTP_X_REQUEST_ID"
    response_request_id_header = "X-Request-ID"
    response_api_version_header = "X-API-Version"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = (request.META.get(self.request_id_header) or "").strip()
        if not request_id:
            request_id = uuid.uuid4().hex

        # Keep request id bounded to avoid header abuse.
        request.request_id = request_id[:128]

        response = self.get_response(request)
        response[self.response_request_id_header] = request.request_id

        if request.path.startswith("/api/mobile/"):
            response[self.response_api_version_header] = str(
                getattr(settings, "MOBILE_API_VERSION", "1.0")
            )

        return response


class APIUsageLoggingMiddleware:
    """
    Middleware to log API usage for analytics.
    Only logs requests to /api/ endpoints.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only log API requests
        if request.path.startswith('/api/') and not request.path.startswith('/api/docs'):
            start_time = time.time()
            
            response = self.get_response(request)
            
            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Get response size
            response_size = len(response.content) if hasattr(response, 'content') else 0
            
            # Get user
            user = None
            if hasattr(request, 'user') and request.user.is_authenticated:
                user = request.user
            
            # Log to database (async in production)
            try:
                from apps.core.models import APIUsageLog
                
                # Get request data (limited size)
                request_data = {}
                if request.method in ['POST', 'PUT', 'PATCH']:
                    try:
                        if hasattr(request, 'data'):
                            data = request.data
                            if isinstance(data, dict):
                                # Remove sensitive fields
                                request_data = {
                                    k: v for k, v in data.items() 
                                    if k.lower() not in ['password', 'token', 'secret', 'key']
                                }
                                # Truncate long values
                                request_data = {
                                    k: (str(v)[:100] if len(str(v)) > 100 else str(v))
                                    for k, v in request_data.items()
                                }
                    except Exception:
                        pass
                
                # Create log entry
                APIUsageLog.objects.create(
                    user=user,
                    endpoint=request.path,
                    method=request.method,
                    status_code=response.status_code,
                    response_time_ms=response_time_ms,
                    ip_address=self.get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                    request_data=request_data,
                    response_size_bytes=response_size,
                )
            except Exception:
                # Don't fail the request if logging fails
                pass
            
            return response
        else:
            return self.get_response(request)
    
    def get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class APIVersionHeadersMiddleware(MiddlewareMixin):
    """
    Inject versioning headers for API responses.

    Note: We keep `/api/mobile/` on the mobile API version string while the
    unversioned `/api/` namespace is marked as legacy (deprecated).
    """

    def process_response(self, request, response):
        latest_version = "v1"
        path = getattr(request, "path", "") or ""

        if path.startswith("/api/mobile/"):
            version = str(getattr(settings, "MOBILE_API_VERSION", "1.0"))
        elif "/api/v1/" in path:
            version = "v1"
        elif "/api/v2/" in path:
            version = "v2"
        elif path.startswith("/api/"):
            version = "legacy"
        else:
            version = getattr(request, "version", None) or "legacy"

        response["X-API-Version"] = str(version)

        # Mark deprecated when not on the latest advertised version.
        if str(version) == "legacy":
            response["Deprecation"] = "true"
        elif str(version) != latest_version and str(version).startswith("v"):
            response["Deprecation"] = "false"
        else:
            response["Deprecation"] = "false"

        return response
