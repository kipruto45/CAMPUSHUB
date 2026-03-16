"""
URL configuration for CampusHub project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import RedirectView
from drf_spectacular.views import (SpectacularAPIView, SpectacularRedocView,
                                   SpectacularSwaggerView)
from graphene_django.views import GraphQLView

from apps.api import deeplinks as deeplink_views
from apps.library import views as library_views
from apps.social import views as social_views
from config.schema_fallback import apply_schema_fallback

# Keep OpenAPI generation resilient for legacy APIViews without serializer_class.
apply_schema_fallback()

urlpatterns = [
    # Root
    path("", RedirectView.as_view(url="/api/docs/", permanent=False)),
    path(
        "share/library/<uuid:file_id>/<str:token>/",
        library_views.SharedLibraryFileView.as_view(),
        name="library-share-link",
    ),
    path(
        "groups/invite/<str:token>/",
        social_views.StudyGroupInviteLandingView.as_view(),
        name="study-group-invite-landing",
    ),
    path(
        ".well-known/assetlinks.json",
        deeplink_views.assetlinks_json_view,
        name="assetlinks-json",
    ),
    path(
        ".well-known/apple-app-site-association",
        deeplink_views.apple_app_site_association_view,
        name="apple-app-site-association",
    ),
    path(
        "apple-app-site-association",
        deeplink_views.apple_app_site_association_view,
        name="apple-app-site-association-root",
    ),
    # Admin panel
    path("admin/", admin.site.urls),
    # Health checks
    path("health/", include("apps.core.health_urls")),
    # API Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # Authentication endpoints
    path("api/auth/", include("apps.accounts.urls")),
    # Faculty endpoints
    path("api/", include("apps.faculties.urls")),
    # Course endpoints
    path("api/", include("apps.courses.urls")),
    # Resource endpoints
    path("api/", include("apps.resources.urls")),
    # Bookmark endpoints
    path("api/", include("apps.bookmarks.urls")),
    # Comment endpoints
    path("api/", include("apps.comments.urls")),
    # Rating endpoints
    path("api/", include("apps.ratings.urls")),
    # Download endpoints
    path("api/downloads/", include("apps.downloads.urls")),
    # Storage endpoints
    path("api/storage/", include("apps.core.storage.urls")),
    # Activity endpoints
    path("api/activity/", include("apps.activity.urls")),
    # Favorites endpoints
    path("api/favorites/", include("apps.favorites.urls")),
    # Announcements endpoints
    path("api/announcements/", include("apps.announcements.urls")),
    # Admin Management endpoints
    path("api/admin-management/", include("apps.admin_management.urls")),
    # Notification endpoints
    path("api/", include("apps.notifications.urls")),
    # Search endpoints
    path("api/search/", include("apps.search.urls")),
    # Analytics endpoints
    path("api/analytics/", include("apps.analytics.urls")),
    # Dashboard endpoints
    path("api/dashboard/", include("apps.dashboard.urls")),
    # Moderation endpoints
    path("api/moderation/", include("apps.moderation.urls")),
    # Report endpoints
    path("api/", include("apps.reports.urls")),
    # Library endpoints (Storage & Trash Management)
    path("api/library/", include("apps.library.urls")),
    # Recommendation endpoints
    path("api/recommendations/", include("apps.recommendations.urls")),
    # Gamification endpoints
    path("api/gamification/", include("apps.gamification.urls")),
    # Social / study groups endpoints
    path("api/social/", include("apps.social.urls")),
    # GraphQL endpoint
    path("graphql/", csrf_exempt(GraphQLView.as_view(graphiql=settings.DEBUG))),
    # Mobile API endpoints
    path("api/", include("apps.api.urls")),
]

# Debug toolbar URLs (development only).
if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    try:
        import debug_toolbar

        urlpatterns += [
            path("__debug__/", include(debug_toolbar.urls)),
        ]
    except Exception:
        # Keep development server running even if toolbar import fails.
        pass

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
