"""drf-spectacular OpenAPI extensions for accounts app."""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class CampusHubJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """Expose custom JWTAuthentication as HTTP Bearer in OpenAPI."""

    target_class = "apps.accounts.authentication.JWTAuthentication"
    name = "BearerAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
