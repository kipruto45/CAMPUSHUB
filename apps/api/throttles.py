"""
Rate limiting and throttling for mobile API endpoints.
"""

from rest_framework.throttling import SimpleRateThrottle, UserRateThrottle


class MobileUserRateThrottle(UserRateThrottle):
    """
    Custom throttle for mobile authenticated users.
    Limits requests based on user authentication status.
    """

    # Higher rate for authenticated users
    scope = "mobile_authenticated"
    rate = "500/hour"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            # Authenticated users get higher limits
            ident = request.user.pk
        else:
            # Anonymous users get lower limits (IP-based)
            ident = self.get_ident(request)

        return self.cache_format % {"scope": self.scope, "ident": ident}


class MobileAnonRateThrottle(SimpleRateThrottle):
    """
    Throttle for anonymous mobile API requests.
    Uses IP-based rate limiting.
    """

    scope = "mobile_anon"
    cache_format = "throttle_anon_%(scope)s_%(ident)s"
    rate = "30/minute"

    def get_cache_key(self, request, view):
        # Only throttle POST, PUT, DELETE for anonymous
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return None

        ident = self.get_ident(request)
        return self.cache_format % {
            "scope": self.scope,
            "ident": ident,
        }


class MobileAuthRateThrottle(SimpleRateThrottle):
    """
    Throttle for authenticated mobile requests.
    Higher limits for authenticated users.
    """

    scope = "mobile_auth"
    cache_format = "throttle_auth_%(scope)s_%(ident)s"
    rate = "200/hour"

    def get_cache_key(self, request, view):
        """Throttle authenticated mobile requests by user id (fallback IP)."""
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            "scope": self.scope,
            "ident": ident,
        }


class MobileUploadThrottle(SimpleRateThrottle):
    """
    Strict throttle for resource uploads.
    Prevents abuse of upload functionality.
    """

    scope = "mobile_upload"
    cache_format = "throttle_upload_%(scope)s_%(ident)s"
    rate = "10/day"  # Only 10 uploads per day

    def get_cache_key(self, request, view):
        # Only throttle upload actions/paths.
        action = getattr(view, "action", None)
        if action:
            if action != "create":
                return None
        else:
            if request.method != "POST" or "upload" not in request.path.lower():
                return None

        ident = (
            request.user.pk
            if request.user and request.user.is_authenticated
            else self.get_ident(request)
        )
        return self.cache_format % {
            "scope": self.scope,
            "ident": ident,
        }


class MobileDownloadThrottle(SimpleRateThrottle):
    """
    Throttle for resource downloads.
    """

    scope = "mobile_download"
    cache_format = "throttle_download_%(scope)s_%(ident)s"
    rate = "100/hour"  # 100 downloads per hour

    def get_cache_key(self, request, view):
        # Only throttle download actions/paths.
        action = getattr(view, "action", None)
        if action:
            if action != "download":
                return None
        else:
            if (
                request.method not in ["GET", "POST"]
                or "download" not in request.path.lower()
            ):
                return None

        ident = (
            request.user.pk
            if request.user and request.user.is_authenticated
            else self.get_ident(request)
        )
        return self.cache_format % {
            "scope": self.scope,
            "ident": ident,
        }


class MobileAuthenticateThrottle(SimpleRateThrottle):
    """
    Throttle for login/registration attempts.
    Prevents brute force attacks.
    """

    scope = "mobile_auth_attempt"
    cache_format = "throttle_auth_attempt_%(scope)s_%(ident)s"
    rate = "10/minute"  # 10 login attempts per minute

    def get_cache_key(self, request, view):
        # Only throttle auth endpoints. Support both ViewSets and function-based views.
        action = getattr(view, "action", None)
        if action:
            if action not in [
                "login",
                "register",
                "create",
                "refresh",
                "token_refresh",
            ]:
                return None
        else:
            url_name = (
                (
                    getattr(request, "resolver_match", None)
                    and request.resolver_match.url_name
                )
                or ""
            ).lower()
            if url_name:
                if url_name not in {
                    "mobile_login",
                    "mobile_register",
                    "mobile_refresh_token",
                }:
                    return None
            else:
                path = request.path.lower()
                if not any(
                    path.endswith(suffix)
                    for suffix in (
                        "/mobile/login/",
                        "/mobile/register/",
                        "/mobile/refresh/",
                    )
                ):
                    return None

        # Use email/identifier for cache key
        ident = request.data.get("email", "") or request.data.get(
            "registration_number", ""
        )
        if not ident:
            ident = self.get_ident(request)

        return self.cache_format % {"scope": self.scope, "ident": ident}


class BurstRateThrottle(SimpleRateThrottle):
    """
    Burst rate throttle - allows short bursts of requests.
    Good for initial page loads.
    """

    scope = "burst"
    rate = "20/minute"


class SustainedRateThrottle(SimpleRateThrottle):
    """
    Sustained rate throttle - limits over longer periods.
    Good for continuous API usage.
    """

    scope = "sustained"
    rate = "100/hour"


# Default throttle rates for mobile API
MOBILE_THROTTLE_RATES = {
    "mobile_anon": "30/minute",
    "mobile_auth": "200/hour",
    "mobile_upload": "10/day",
    "mobile_download": "100/hour",
    "mobile_auth_attempt": "10/minute",
    "mobile_authenticated": "500/hour",
    "burst": "60/minute",
    "sustained": "200/hour",
}


def get_client_ip(request):
    """Get client IP address from request."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


class IPBasedThrottle(SimpleRateThrottle):
    """
    IP-based throttle for additional security.
    """

    scope = "ip_based"
    rate = "50/minute"

    def get_cache_key(self, request, view):
        ident = get_client_ip(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class DeviceThrottle(SimpleRateThrottle):
    """
    Throttle based on device token.
    Useful for identifying specific devices.
    """

    scope = "device"
    rate = "150/hour"

    def get_cache_key(self, request, view):
        device_token = request.headers.get("X-Device-Token")
        if device_token:
            return self.cache_format % {
                "scope": self.scope,
                "ident": device_token[:50],  # Truncate for cache key
            }
        return None  # No device token, use other throttles
