"""
Middleware for tier-based access control.

This middleware enforces tier access restrictions at the API level.
"""

from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache

from .freemium import (
    Feature,
    has_feature,
    can_access_feature,
    get_user_tier,
    Tier,
)


# Feature to URL path mapping
# Maps features to URL patterns that require them
FEATURE_URL_PATTERNS = {
    Feature.AI_FEATURES: [
        "/api/ai/",
        "/api/ai/summarize",
        "/api/ai/chat",
    ],
    Feature.AI_SUMMARIZATION: [
        "/api/ai/summarize",
    ],
    Feature.AI_CHAT: [
        "/api/ai/chat",
    ],
    Feature.ADVANCED_ANALYTICS: [
        "/api/analytics/advanced",
        "/api/analytics/detailed",
    ],
    Feature.ALL_INTEGRATIONS: [
        "/api/integrations/",
    ],
    Feature.PRIORITY_SUPPORT: [
        "/api/support/priority",
    ],
    Feature.CERTIFICATES: [
        "/api/certificates/",
    ],
    Feature.CUSTOM_TIMETABLES: [
        "/api/timetables/custom",
    ],
    Feature.EXPORT_DATA: [
        "/api/export/",
    ],
    Feature.ADVANCED_SEARCH: [
        "/api/search/advanced",
    ],
    Feature.WHITE_LABEL: [
        "/api/whitelabel/",
    ],
    Feature.API_ACCESS: [
        "/api/v2/",
    ],
    Feature.SSO: [
        "/api/auth/sso",
    ],
    Feature.AUDIT_LOGS: [
        "/api/audit/",
    ],
    Feature.BULK_OPERATIONS: [
        "/api/users/bulk",
    ],
}


# Endpoints that are always accessible (no tier restriction)
PUBLIC_ENDPOINTS = [
    "/api/payments/tiers/",
    "/api/payments/feature-access/",  # Will check auth
    "/api/accounts/login/",
    "/api/accounts/register/",
    "/api/accounts/verify/",
    "/api/announcements/public/",
    "/api/health/",
]


class TierAccessMiddleware:
    """
    Middleware to enforce tier-based access control.
    
    This middleware checks if the user has access to features based on their tier
    before allowing access to protected endpoints.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip for non-API requests
        if not request.path.startswith("/api/"):
            return self.get_response(request)

        # Skip for public endpoints
        if self._is_public_endpoint(request.path):
            return self.get_response(request)

        # Skip if user is not authenticated
        if not hasattr(request, "user") or not request.user.is_authenticated:
            return self.get_response(request)

        # Check if the endpoint requires a specific feature
        required_feature = self._get_required_feature(request.path)
        
        if required_feature:
            has_access, reason = can_access_feature(request.user, required_feature)
            
            if not has_access:
                return Response(
                    {
                        "error": "Feature not available",
                        "reason": reason,
                        "feature": required_feature.value,
                        "upgrade_url": "/settings/billing/upgrade/",
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

        return self.get_response(request)

    def _is_public_endpoint(self, path: str) -> bool:
        """Check if the endpoint is publicly accessible."""
        for public_path in PUBLIC_ENDPOINTS:
            if path.startswith(public_path):
                return True
        return False

    def _get_required_feature(self, path: str) -> Feature:
        """Get the feature required to access the given path."""
        for feature, patterns in FEATURE_URL_PATTERNS.items():
            for pattern in patterns:
                if path.startswith(pattern):
                    return feature
        return None


def require_feature(feature: Feature):
    """
    Decorator to require a specific feature for a view.
    
    Usage:
        @require_feature(Feature.AI_FEATURES)
        def my_view(request):
            ...
    """
    def decorator(view_func):
        def wrapped(request, *args, **kwargs):
            if not hasattr(request, "user") or not request.user.is_authenticated:
                return Response(
                    {"error": "Authentication required"},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            has_access, reason = can_access_feature(request.user, feature)
            
            if not has_access:
                return Response(
                    {
                        "error": "Feature not available",
                        "reason": reason,
                        "feature": feature.value,
                        "upgrade_url": "/settings/billing/upgrade/",
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


def get_tier_cached(user) -> Tier:
    """
    Get user's tier with caching.
    
    Caches the tier for 5 minutes to reduce database queries.
    """
    cache_key = f"user_tier_{user.id}"
    tier = cache.get(cache_key)
    
    if tier is None:
        tier = get_user_tier(user)
        cache.set(cache_key, tier, 300)  # 5 minutes
    
    return tier


def invalidate_tier_cache(user_id: int):
    """Invalidate the tier cache for a user."""
    cache_key = f"user_tier_{user_id}"
    cache.delete(cache_key)
