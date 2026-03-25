"""
Deep linking configuration for CampusHub mobile app.
Handles both custom URL scheme (campushub://) and universal/app links (https://).
"""

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class DeepLinkType(Enum):
    """Types of deep links supported."""

    RESOURCE = "resource"
    COURSE = "course"
    UNIT = "unit"
    PROFILE = "profile"
    ANNOUNCEMENT = "announcement"
    NOTIFICATION = "notification"
    SEARCH = "search"
    AUTH = "auth"


@dataclass
class DeepLink:
    """Represents a parsed deep link."""

    type: DeepLinkType
    action: str  # view, edit, download, etc.
    params: Dict[str, Any]
    original_url: str


class DeepLinkParser:
    """
    Parser for CampusHub deep links.

    URL Schemes:
    - campushub:// - Custom URL scheme (iOS/Android)
    - https://campushub.com/ - Universal/App links (HTTPS)

    Supported Paths:
    - /resources/{id} - View resource
    - /resources/{id}/download - Download resource
    - /courses/{id} - View course
    - /units/{id} - View unit
    - /profile/{id} - View profile
    - /announcements/{id} - View announcement
    - /search?q={query} - Search
    - /auth/login - Open login
    - /auth/register - Open register
    """

    # URL scheme host
    SCHEME_HOST = "campushub"
    WEB_HOST = "campushub.com"

    # Path patterns
    PATTERNS = {
        # Resources
        r"resources/(?P<id>[^/]+)": DeepLinkType.RESOURCE,
        r"resources/(?P<id>[^/]+)/download": DeepLinkType.RESOURCE,
        # Courses
        r"courses/(?P<id>[^/]+)": DeepLinkType.COURSE,
        # Units
        r"units/(?P<id>[^/]+)": DeepLinkType.UNIT,
        # Profile
        r"profile/(?P<id>[^/]+)": DeepLinkType.PROFILE,
        r"profile": DeepLinkType.PROFILE,
        # Announcements
        r"announcements/(?P<id>[^/]+)": DeepLinkType.ANNOUNCEMENT,
        # Search
        r"search": DeepLinkType.SEARCH,
        # Auth
        r"auth/login": DeepLinkType.AUTH,
        r"auth/register": DeepLinkType.AUTH,
    }

    @classmethod
    def _scheme_host(cls) -> str:
        """Resolve deep-link scheme from settings when available."""
        try:
            from django.conf import settings

            return getattr(settings, "MOBILE_DEEPLINK_SCHEME", cls.SCHEME_HOST)
        except Exception:
            return cls.SCHEME_HOST

    @classmethod
    def _web_host(cls) -> str:
        """Resolve deep-link web host from settings when available."""
        try:
            from django.conf import settings

            return getattr(settings, "MOBILE_DEEPLINK_HOST", cls.WEB_HOST)
        except Exception:
            return cls.WEB_HOST

    @classmethod
    def parse(cls, url: str) -> Optional[DeepLink]:
        """
        Parse a deep link URL into components.

        Args:
            url: The deep link URL to parse

        Returns:
            DeepLink object if valid, None otherwise
        """
        import re
        from urllib.parse import urlparse

        scheme_host = cls._scheme_host()
        web_host = cls._web_host()

        parsed_url = urlparse(url or "")
        scheme = (parsed_url.scheme or "").lower()

        # Handle custom URL scheme: campushub://path
        if scheme == scheme_host:
            path = f"{parsed_url.netloc}{parsed_url.path}"
            if parsed_url.query:
                path = f"{path}?{parsed_url.query}"

        # Handle universal/app links over HTTP(S).
        elif scheme in {"https", "http"}:
            host = (parsed_url.netloc or "").split(":", 1)[0].lower()
            normalized_host = host[4:] if host.startswith("www.") else host
            configured_host = str(web_host or "").lower()
            configured_host = (
                configured_host[4:] if configured_host.startswith("www.") else configured_host
            )
            allowed_hosts = {
                configured_host,
                cls.WEB_HOST.lower(),
            }
            if normalized_host not in allowed_hosts:
                return None

            path = parsed_url.path.lstrip("/")
            if parsed_url.query:
                path = f"{path}?{parsed_url.query}"
        else:
            return None

        # Remove trailing slash
        path = path.rstrip("/")

        if not path:
            return None

        # Extract query parameters
        params = {}
        if "?" in path:
            path_part, query_part = path.split("?", 1)
            path = path_part

            # Parse query string
            for param in query_part.split("&"):
                if "=" in param:
                    key, value = param.split("=", 1)
                    params[key] = value

        # Match against patterns
        for pattern, link_type in cls.PATTERNS.items():
            match = re.match(pattern, path)
            if match:
                # Determine action from path
                action = "view"
                if "download" in path:
                    action = "download"
                elif "edit" in path:
                    action = "edit"
                elif "search" in path:
                    action = "search"
                elif "login" in path or "register" in path:
                    action = path.split("/")[-1]  # login or register

                # Build params from regex groups
                all_params = {**match.groupdict(), **params}
                # Remove None values
                all_params = {k: v for k, v in all_params.items() if v is not None}

                return DeepLink(
                    type=link_type, action=action, params=all_params, original_url=url
                )

        return None

    @classmethod
    def build(cls, link_type: DeepLinkType, action: str = "view", **params) -> str:
        """
        Build a deep link URL from components.

        Args:
            link_type: Type of deep link
            action: Action to perform (view, edit, download, etc.)
            **params: Additional parameters

        Returns:
            Deep link URL string
        """
        base = f"{cls._scheme_host()}://"

        path_map = {
            DeepLinkType.RESOURCE: f"resources/{params.get('id', '')}",
            DeepLinkType.COURSE: f"courses/{params.get('id', '')}",
            DeepLinkType.UNIT: f"units/{params.get('id', '')}",
            DeepLinkType.PROFILE: f"profile/{params.get('id', '')}",
            DeepLinkType.ANNOUNCEMENT: f"announcements/{params.get('id', '')}",
            DeepLinkType.SEARCH: "search",
            DeepLinkType.AUTH: (
                f"auth/{action}" if action in ["login", "register"] else "auth"
            ),
            DeepLinkType.NOTIFICATION: f"notifications/{params.get('id', '')}",
        }

        path = path_map.get(link_type, "")

        if action and action != "view" and link_type != DeepLinkType.AUTH:
            path = f"{path}/{action}"

        # Add query parameters
        query_params = {k: v for k, v in params.items() if k != "id"}
        if query_params:
            query_string = "&".join([f"{k}={v}" for k, v in query_params.items()])
            path = f"{path}?{query_string}"

        return f"{base}{path}"

    @classmethod
    def get_mobile_route(cls, deep_link: DeepLink) -> Dict[str, Any]:
        """
        Get the mobile navigation route for a deep link.

        Args:
            deep_link: Parsed DeepLink object

        Returns:
            Dictionary with screen name and params for mobile navigation
        """
        route_map = {
            DeepLinkType.RESOURCE: {
                "screen": "ResourceDetail",
                "params": {"resourceId": deep_link.params.get("id")},
            },
            DeepLinkType.COURSE: {
                "screen": "CourseDetail",
                "params": {"courseId": deep_link.params.get("id")},
            },
            DeepLinkType.UNIT: {
                "screen": "UnitDetail",
                "params": {"unitId": deep_link.params.get("id")},
            },
            DeepLinkType.PROFILE: {
                "screen": "Profile",
                "params": {"userId": deep_link.params.get("id")},
            },
            DeepLinkType.ANNOUNCEMENT: {
                "screen": "AnnouncementDetail",
                "params": {"announcementId": deep_link.params.get("id")},
            },
            DeepLinkType.SEARCH: {
                "screen": "Search",
                "params": {"query": deep_link.params.get("q", "")},
            },
            DeepLinkType.AUTH: {
                "screen": "Register" if deep_link.action == "register" else "Login",
                "params": {},
            },
            DeepLinkType.NOTIFICATION: {
                "screen": "NotificationDetail",
                "params": {"notificationId": deep_link.params.get("id")},
            },
        }

        return route_map.get(deep_link.type, {"screen": "Home", "params": {}})


def parse_deep_link(url: str) -> Optional[DeepLink]:
    """Convenience function to parse a deep link."""
    return DeepLinkParser.parse(url)


def build_deep_link(link_type: DeepLinkType, action: str = "view", **params) -> str:
    """Convenience function to build a deep link."""
    return DeepLinkParser.build(link_type, action, **params)


def get_mobile_route(url: str) -> Optional[Dict[str, Any]]:
    """
    Get mobile navigation route from a deep link URL.

    Returns None if URL is not a valid deep link.
    """
    deep_link = parse_deep_link(url)
    if deep_link:
        return DeepLinkParser.get_mobile_route(deep_link)
    return None


def parse_deep_link_view(request):
    """Parse a deep-link URL and return mobile navigation metadata."""
    from django.http import JsonResponse

    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": {"message": "Method not allowed"}}, status=405
        )

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse(
            {"success": False, "error": {"message": "Invalid JSON body"}}, status=400
        )

    url = payload.get("url", "")
    if not url:
        return JsonResponse(
            {"success": False, "error": {"message": "url is required"}}, status=400
        )

    parsed = parse_deep_link(url)
    if not parsed:
        return JsonResponse(
            {"success": False, "error": {"message": "Invalid deep link"}}, status=400
        )

    return JsonResponse(
        {
            "success": True,
            "data": {
                "type": parsed.type.value,
                "action": parsed.action,
                "params": parsed.params,
                "route": DeepLinkParser.get_mobile_route(parsed),
            },
        }
    )


def build_deep_link_view(request):
    """Build a deep-link URL from type/action/params payload."""
    from django.http import JsonResponse

    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": {"message": "Method not allowed"}}, status=405
        )

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse(
            {"success": False, "error": {"message": "Invalid JSON body"}}, status=400
        )

    type_value = payload.get("type")
    if not type_value:
        return JsonResponse(
            {"success": False, "error": {"message": "type is required"}}, status=400
        )

    try:
        link_type = DeepLinkType(type_value)
    except ValueError:
        return JsonResponse(
            {"success": False, "error": {"message": "Unsupported deep link type"}},
            status=400,
        )

    action = payload.get("action", "view")
    params = payload.get("params", {}) or {}
    if not isinstance(params, dict):
        return JsonResponse(
            {"success": False, "error": {"message": "params must be an object"}},
            status=400,
        )

    url = build_deep_link(link_type, action=action, **params)
    return JsonResponse({"success": True, "data": {"url": url}})


def assetlinks_json_view(request):
    """Serve Android App Links association file."""
    from django.conf import settings
    from django.http import JsonResponse

    package_name = getattr(settings, "ANDROID_APP_PACKAGE", "com.campushub.app")
    fingerprints = getattr(settings, "ANDROID_SHA256_CERT_FINGERPRINTS", [])

    payload = []
    if package_name and fingerprints:
        payload.append(
            {
                "relation": ["delegate_permission/common.handle_all_urls"],
                "target": {
                    "namespace": "android_app",
                    "package_name": package_name,
                    "sha256_cert_fingerprints": fingerprints,
                },
            }
        )

    return JsonResponse(payload, safe=False)


def apple_app_site_association_view(request):
    """Serve iOS Universal Links and App Clips association file."""
    from django.conf import settings
    from django.http import JsonResponse

    team_id = getattr(settings, "IOS_TEAM_ID", "") or getattr(
        settings, "APNS_TEAM_ID", ""
    )
    bundle_id = getattr(settings, "IOS_BUNDLE_ID", "") or getattr(
        settings, "APNS_BUNDLE_ID", ""
    )
    app_id = f"{team_id}.{bundle_id}" if team_id and bundle_id else ""
    
    # App clip bundle ID
    app_clip_bundle_id = getattr(settings, "IOS_APP_CLIP_BUNDLE_ID", f"{bundle_id}.clip" if bundle_id else "")
    app_clip_id = f"{team_id}.{app_clip_bundle_id}" if team_id and app_clip_bundle_id else ""

    details = []
    if app_id:
        details.append(
            {
                "appID": app_id,
                "paths": [
                    "/resources/*",
                    "/courses/*",
                    "/units/*",
                    "/announcements/*",
                    "/profile/*",
                    "/search*",
                ],
            }
        )
    
    # Add app clip details if configured
    if app_clip_id:
        details.append(
            {
                "appID": app_clip_id,
                "paths": [
                    "/clip/resources/*",
                    "/clip/announcements/*",
                    "/clip/search/*",
                ],
            }
        )

    payload = {
        "applinks": {
            "apps": [],
            "details": details,
        }
    }
    return JsonResponse(payload)
