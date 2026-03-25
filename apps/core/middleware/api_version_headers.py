"""Inject API version headers on responses."""

from django.utils.deprecation import MiddlewareMixin


class APIVersionHeadersMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        latest_version = "v1"
        path = getattr(request, "path", "") or ""

        if "/api/v1/" in path:
            version = "v1"
        elif "/api/v2/" in path:
            version = "v2"
        elif path.startswith("/api/"):
            version = "legacy"
        else:
            version = getattr(request, "version", None) or "legacy"

        response["X-API-Version"] = str(version)

        # Mark deprecated when not on the latest advertised version
        if str(version) == "legacy":
            response["Deprecation"] = "true"
        elif str(version) != latest_version and str(version).startswith("v"):
            response["Deprecation"] = "false"
        else:
            response["Deprecation"] = "false"

        return response
