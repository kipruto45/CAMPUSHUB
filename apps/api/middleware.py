"""
API Versioning & Analytics middleware.
Adds version headers and records lightweight analytics with optional HMAC guard.
"""

import hmac
import time
from hashlib import sha256

from django.conf import settings
from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin


class APIVersionMiddleware(MiddlewareMixin):
    """
    Middleware to add API versioning headers to all responses.
    
    Headers added:
    - X-API-Version: Current API version
    - X-API-Latest: Latest available version
    - Deprecation: Warning when using outdated version
    - Sunset: Date when deprecated version will be removed
    """

    # Sunset date for v1 (when v2 is fully available)
    V1_SUNSET_DATE = "2026-12-31"
    
    # Version-specific features (for documentation)
    VERSION_FEATURES = {
        "v1": {
            "status": "deprecated",
            "sunset": V1_SUNSET_DATE,
            "migration_deadline": "2026-06-30",
            "features": [
                "JWT authentication",
                "Basic resource CRUD",
                "Push notifications (FCM)",
                "Offline sync",
            ],
        },
        "v2": {
            "status": "current",
            "sunset": None,
            "features": [
                "JWT authentication",
                "Full resource CRUD",
                "Push notifications (FCM + APNs)",
                "WebSocket real-time",
                "Deep linking",
                "Offline sync",
                "Rate limiting",
                "Online presence",
            ],
        },
    }

    def process_response(self, request, response):
        """Add versioning headers to the response."""
        # Only add headers to API responses
        if not self._is_api_request(request):
            return response

        # Get API version from request
        api_version = getattr(request, "api_version", "v1")
        
        # Add version header
        response["X-API-Version"] = api_version
        
        # Add latest version header
        response["X-API-Latest"] = "v2"
        
        # Add deprecation header for v1
        if api_version == "v1":
            response["Deprecation"] = "true"
            response["Sunset"] = self.V1_SUNSET_DATE
            response["X-API-Deprecation-Warning"] = (
                "API v1 is deprecated and will be sunset on " + self.V1_SUNSET_DATE +
                ". Please migrate to v2. See /api/v2/ for available endpoints."
            )
            
        # Add link to new version in header
        if api_version in {"legacy", "v1"}:
            path = request.path
            if "/v1/" in path:
                new_path = path.replace("/v1/", "/v2/", 1)
            elif path.startswith("/api/"):
                new_path = path.replace("/api/", "/api/v2/", 1)
            else:
                new_path = "/api/v2/"
            response["Link"] = f'<{new_path}>; rel="successor-version"'
        
        return response


class APIAnalyticsMiddleware(MiddlewareMixin):
    """
    Lightweight request/response analytics hook.
    Records API request events into AnalyticsEvent (if app installed).
    Optional protections:
    - HMAC signature (X-Analytics-Signature + X-Analytics-Timestamp)
    - Simple per-IP rate limiting to avoid noisy logs in production
    """

    SIGNATURE_HEADER = "HTTP_X_ANALYTICS_SIGNATURE"
    TIMESTAMP_HEADER = "HTTP_X_ANALYTICS_TIMESTAMP"
    MAX_SKEW_SECONDS = 300  # 5 minutes
    RATE_LIMIT_PER_MINUTE = 120

    def process_request(self, request):
        request._api_timer_start = time.time()

    def process_response(self, request, response):
        try:
            if not self._is_api_request(request):
                return response

            if not self._passes_rate_limit(request):
                return response

            if not self._verify_signature(request):
                # Skip analytics if signature missing/invalid when secret configured
                return response

            duration_ms = None
            if hasattr(request, "_api_timer_start"):
                duration_ms = int((time.time() - request._api_timer_start) * 1000)

            # Lazy import to avoid startup cost if analytics not installed
            from apps.analytics.models import AnalyticsEvent  # type: ignore

            AnalyticsEvent.objects.create(
                user=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
                session_id=request.headers.get("X-Session-Id", ""),
                event_type="api_request",
                event_name=request.path[:100],
                properties={
                    "method": request.method,
                    "status": getattr(response, "status_code", None),
                    "duration_ms": duration_ms,
                },
                referrer=request.headers.get("Referer", ""),
                device_type=request.headers.get("User-Agent", "")[:120],
            )
        except Exception:
            # Best-effort; never break the response pipeline
            pass

        return response

    def _is_api_request(self, request) -> bool:
        """Check if request is an API request."""
        return (
            request.path.startswith("/api/") or
            request.path.startswith("/graphql/") or
            request.path.startswith("/api/v1/") or
            request.path.startswith("/api/v2/")
        )

    def _client_ip(self, request) -> str:
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")

    def _passes_rate_limit(self, request) -> bool:
        """
        Basic per-IP rate limiting for analytics ingestion to avoid log spam.
        Skips analytics creation if the limit is exceeded.
        """
        key = f"analytics:ratelimit:{self._client_ip(request)}"
        current = cache.get(key)
        if current is None:
            cache.set(key, 1, timeout=60)
            return True
        if current >= self.RATE_LIMIT_PER_MINUTE:
            return False
        cache.set(key, current + 1, timeout=60)
        return True

    def _verify_signature(self, request) -> bool:
        """
        Validate optional HMAC signature to ensure only trusted producers
        record analytics. If ANALYTICS_HMAC_SECRET is unset/blank, the check
        is skipped (keeps backward compatibility).
        """
        secret = getattr(settings, "ANALYTICS_HMAC_SECRET", "") or ""
        if not secret:
            return True

        provided_sig = request.META.get(self.SIGNATURE_HEADER, "")
        ts = request.META.get(self.TIMESTAMP_HEADER, "")
        if not provided_sig or not ts:
            return False

        try:
            ts_int = int(ts)
        except (TypeError, ValueError):
            return False

        # Reject stale / future timestamps
        now = int(time.time())
        if abs(now - ts_int) > self.MAX_SKEW_SECONDS:
            return False

        message = f"{request.method}:{request.path}:{ts_int}".encode()
        expected = hmac.new(secret.encode(), message, sha256).hexdigest()
        return hmac.compare_digest(expected, provided_sig)


class APIRateLimitHeadersMiddleware(MiddlewareMixin):
    """
    Add rate limiting headers to API responses.
    """

    def process_response(self, request, response):
        """Add rate limit headers."""
        if not request.path.startswith("/api/"):
            return response

        # Check if rate limit info is available
        if hasattr(request, "throttle_data"):
            throttle = request.throttle_data
            if throttle:
                wait = throttle.get("wait", 0)
                if wait:
                    response["Retry-After"] = str(int(wait))
                    response["X-RateLimit-Remaining"] = str(
                        throttle.get("remaining", 0)
                    )
                    response["X-RateLimit-Limit"] = str(
                        throttle.get("limit", 0)
                    )

        return response


class APIVersionResponseMiddleware(MiddlewareMixin):
    """
    Add version info to error responses for better debugging.
    """

    def process_response(self, request, response):
        """Enhance error responses with version info."""
        if not request.path.startswith("/api/"):
            return response

        # Only add to error responses
        if response.status_code >= 400:
            api_version = getattr(request, "api_version", "v1")
            
            # If response is JSON, add version to body
            content_type = response.get("Content-Type", "")
            if "application/json" in content_type:
                # Only add if not already present
                try:
                    import json
                    data = json.loads(response.content)
                    if "api_version" not in data:
                        # Can't modify content directly, headers are enough
                        pass
                except:
                    pass

        return response
