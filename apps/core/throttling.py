"""
Rate Limiting and Throttling for CampusHub API Protection.
Uses Django's in-memory cache (locmem) for rate limiting.
"""

import time

from django.core.cache import cache
from rest_framework.throttling import (AnonRateThrottle, SimpleRateThrottle,
                                       UserRateThrottle)


class CampusHubUserRateThrottle(UserRateThrottle):
    """
    Custom user throttle that uses in-memory cache for rate limiting.
    """

    scope = "user"
    rate = "100/minute"  # Default rate for authenticated users

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {"scope": self.scope, "ident": ident}


class CampusHubAnonRateThrottle(AnonRateThrottle):
    """
    Custom anonymous throttle that uses in-memory cache for rate limiting.
    """

    scope = "anon"
    rate = "20/minute"  # Default rate for anonymous users

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return None  # Don't throttle authenticated users here

        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class LoginRateThrottle(SimpleRateThrottle):
    """
    Throttle for login attempts to prevent brute force attacks.
    """

    scope = "login"
    rate = "5/minute"

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class RegistrationRateThrottle(SimpleRateThrottle):
    """
    Throttle for registration attempts to prevent spam registrations.
    """

    scope = "registration"
    rate = "3/hour"

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class ResourceUploadThrottle(SimpleRateThrottle):
    """
    Throttle for resource uploads to prevent abuse.
    """

    scope = "upload"
    rate = "10/hour"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {"scope": self.scope, "ident": ident}


class DownloadThrottle(SimpleRateThrottle):
    """
    Throttle for downloads to prevent bandwidth abuse.
    """

    scope = "download"
    rate = "50/minute"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {"scope": self.scope, "ident": ident}


class SearchThrottle(SimpleRateThrottle):
    """
    Throttle for search requests to prevent abuse.
    """

    scope = "search"
    rate = "30/minute"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {"scope": self.scope, "ident": ident}


class APIKeyThrottle(SimpleRateThrottle):
    """
    Throttle based on API keys for external integrations.
    """

    scope = "api_key"
    rate = "1000/minute"

    def get_cache_key(self, request, view):
        api_key = request.META.get("HTTP_X_API_KEY")
        if not api_key:
            return None

        return self.cache_format % {"scope": self.scope, "ident": api_key}


class BurstRateThrottle(SimpleRateThrottle):
    """
    Short burst throttle for API endpoints.
    Allows short bursts of requests.
    """

    scope = "burst"
    rate = "20/second"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {"scope": self.scope, "ident": ident}


class SustainedRateThrottle(SimpleRateThrottle):
    """
    Sustained rate throttle for continuous usage.
    """

    scope = "sustained"
    rate = "1000/hour"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {"scope": self.scope, "ident": ident}


class DynamicRateThrottle(SimpleRateThrottle):
    """
    Dynamic rate throttle that can be adjusted based on user tier.
    """

    tier_rates = {
        "free": "20/minute",
        "basic": "100/minute",
        "premium": "500/minute",
        "enterprise": "1000/minute",
    }

    def get_rate(self):
        # Get rate based on user tier
        if hasattr(self, "request") and self.request.user.is_authenticated:
            user = self.request.user
            tier = getattr(user, "subscription_tier", "free")
            return self.tier_rates.get(tier, self.tier_rates["free"])

        return self.tier_rates["free"]

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {"scope": self.scope, "ident": ident}


class IPBasedThrottle(SimpleRateThrottle):
    """
    IP-based throttle for additional security.
    """

    scope = "ip"
    rate = "100/minute"

    def get_cache_key(self, request, view):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")

        return self.cache_format % {"scope": self.scope, "ident": ip}


class ThrottleManager:
    """
    Manager for handling multiple throttle rates.
    """

    # Tier-based throttling
    USER_TIERS = {
        "free": {
            "user": "20/minute",
            "upload": "5/hour",
            "download": "30/minute",
            "search": "10/minute",
        },
        "basic": {
            "user": "100/minute",
            "upload": "20/hour",
            "download": "100/minute",
            "search": "50/minute",
        },
        "premium": {
            "user": "500/minute",
            "upload": "50/hour",
            "download": "500/minute",
            "search": "200/minute",
        },
        "enterprise": {
            "user": "1000/minute",
            "upload": "200/hour",
            "download": "1000/minute",
            "search": "500/minute",
        },
    }

    @classmethod
    def get_throttle_rates(cls, tier="free"):
        """Get throttle rates for a specific tier."""
        return cls.USER_TIERS.get(tier, cls.USER_TIERS["free"])

    @classmethod
    def get_user_tier(cls, user):
        """Get user's subscription tier."""
        if hasattr(user, "subscription_tier"):
            return user.subscription_tier
        return "free"


class CustomThrottle(SimpleRateThrottle):
    """
    Customizable throttle that can be configured dynamically.
    """

    default_rate = "60/minute"

    def __init__(self):
        super().__init__()
        self.rate = self.default_rate

    def allow_request(self, request, view):
        """
        Implement the check here.
        """
        self.key = self.get_cache_key(request, view)
        if self.key is None:
            return True

        self.history = cache.get(self.key, [])
        self.now = time.time()

        # Drop old requests from history
        while self.history and self.now - self.history[-1] >= self.duration:
            self.history.pop()

        if len(self.history) >= self.num_requests:
            return self.throttle_failure()

        return True

    def throttle_failure(self):
        """
        Handle when throttle limit is exceeded.
        """
        return False

    def throttle_success(self):
        """
        Record successful request.
        """
        self.history.insert(0, self.now)
        cache.set(self.key, self.history, self.duration)
        return True

    def wait(self):
        """
        Calculate the wait time before next request is allowed.
        """
        if self.history:
            remaining_duration = self.duration - (self.now - self.history[-1])
            available_requests = self.num_requests - len(self.history) + 1
            if available_requests <= 0:
                return remaining_duration
        return None


class SlidingWindowThrottle(SimpleRateThrottle):
    """
    Sliding window throttle for more accurate rate limiting.
    """

    scope = "sliding"
    rate = "60/minute"
    window_size = 60  # seconds

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {"scope": self.scope, "ident": ident}

    def allow_request(self, request, view):
        self.key = self.get_cache_key(request, view)
        if self.key is None:
            return True

        self.now = time.time()
        window_start = self.now - self.window_size

        # Get history and filter by window
        history = cache.get(self.key, [])
        self.history = [ts for ts in history if ts > window_start]

        if len(self.history) >= self.num_requests:
            return False

        return True

    def throttle_success(self):
        self.history.insert(0, self.now)
        cache.set(self.key, self.history, self.window_size)
        return True
