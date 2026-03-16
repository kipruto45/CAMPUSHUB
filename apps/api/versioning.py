"""
API Versioning for CampusHub Mobile API.
Supports URL path versioning and header versioning.
"""

from rest_framework import exceptions
from rest_framework.versioning import BaseVersioning, URLPathVersioning


class MobileAPIVersioning(URLPathVersioning):
    """
    URL-based API versioning for mobile apps.

    Examples:
        /api/v1/resources/
        /api/v2/resources/

    Benefits:
    - Version in URL is visible and cacheable
    - Easy to test and debug
    - Works well with mobile apps
    """

    default_version = "v1"
    allowed_versions = ["v1", "v2"]
    version_param = "v"

    def determine_version(self, request, view):
        """Determine API version from URL."""
        version = super().determine_version(request, view)

        # Add version to request for use in views
        request.api_version = version

        return version


class MobileHeaderVersioning(BaseVersioning):
    """
    Header-based API versioning.

    Examples:
        Accept: application/vnd.campushub.v1+json
        X-API-Version: v1

    Benefits:
    - Clean URLs
    - Client specifies version in request
    """

    header_name = "X-API-Version"
    default_version = "v1"
    allowed_versions = ["v1", "v2"]

    def determine_version(self, request, view):
        """Determine API version from header."""
        version = request.META.get(
            f'HTTP_{self.header_name.upper().replace("-", "_")}', self.default_version
        )

        if version not in self.allowed_versions:
            raise exceptions.NotAcceptable(
                f"Invalid API version '{version}'. Allowed: {', '.join(self.allowed_versions)}"
            )

        request.api_version = version
        return version


class QueryParameterVersioning:
    """
    Query parameter-based versioning.

    Examples:
        /api/resources/?version=v1
        /api/resources/?v=v2

    Benefits:
    - No URL changes needed
    - Easy A/B testing
    """

    default_version = "v1"
    allowed_versions = ["v1", "v2"]
    version_param = "version"

    def determine_version(self, request, view):
        """Determine API version from query parameter."""
        version = request.query_params.get(self.version_param, self.default_version)

        if version not in self.allowed_versions:
            raise exceptions.NotAcceptable(
                f"Invalid API version '{version}'. Allowed: {', '.join(self.allowed_versions)}"
            )

        request.api_version = version
        return version


class VersionedViewMixin:
    """
    Mixin for views to access API version-specific behavior.

    Usage:
        class MyView(VersionedViewMixin, APIView):
            def get(self, request):
                if request.api_version == 'v1':
                    # Handle v1
                elif request.api_version == 'v2':
                    # Handle v2
    """

    @property
    def is_v1(self) -> bool:
        """Check if request is for API v1."""
        return getattr(self.request, "api_version", "v1") == "v1"

    @property
    def is_v2(self) -> bool:
        """Check if request is for API v2."""
        return getattr(self.request, "api_version", "v1") == "v2"

    def get_versioned_serializer_class(self, v1_class, v2_class):
        """Get serializer class based on API version."""
        if self.is_v2:
            return v2_class
        return v1_class


class VersioningConfig:
    """
    Configuration for API versioning changes between versions.

    Use this to document what changed between versions.
    """

    # Version 1.x
    V1_CHANGES = {
        "initial_release": True,
        "endpoints": [
            "/api/mobile/register/",
            "/api/mobile/login/",
            "/api/mobile/resources/",
            "/api/mobile/dashboard/",
            "/api/mobile/notifications/",
        ],
        "features": [
            "JWT authentication",
            "Basic resource CRUD",
            "Push notifications (FCM)",
            "Offline sync",
        ],
    }

    # Version 2.x
    V2_CHANGES = {
        "initial_release": False,
        "changes_from_v1": [
            "Added APNs support for iOS",
            "Added WebSocket real-time",
            "Added deep linking",
            "Enhanced offline support",
            "Added rate limiting",
            "Added typing indicators",
            "Added online presence",
        ],
        "new_endpoints": [
            "/api/mobile/info/",
            "/api/mobile/sync/",
            "/api/mobile/stats/",
            "/api/mobile/topic/subscribe/",
            "/api/mobile/topic/unsubscribe/",
        ],
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
    }

    @classmethod
    def get_version_info(cls, version: str) -> dict:
        """Get information about a specific version."""
        if version == "v1":
            return cls.V1_CHANGES
        elif version == "v2":
            return cls.V2_CHANGES
        return {}

    @classmethod
    def get_supported_versions(cls) -> list:
        """Get list of supported versions."""
        return ["v1", "v2"]

    @classmethod
    def get_latest_version(cls) -> str:
        """Get the latest API version."""
        return "v2"

    @classmethod
    def is_supported(cls, version: str) -> bool:
        """Check if a version is supported."""
        return version in cls.get_supported_versions()


def get_api_version_info(request) -> dict:
    """
    Get API version information for response headers.

    Usage:
        response = Response(data)
        version_info = get_api_version_info(request)
        response['X-API-Version'] = version_info['version']
        response['X-API-Latest'] = version_info['latest']
        return response
    """
    current_version = getattr(request, "api_version", "v1")
    latest_version = VersioningConfig.get_latest_version()

    return {
        "version": current_version,
        "latest": latest_version,
        "is_latest": current_version == latest_version,
        "deprecated": current_version == "v1",
    }
