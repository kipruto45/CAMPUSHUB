"""
URL configuration for CampusHub project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import RedirectView
from drf_spectacular.views import (SpectacularAPIView, SpectacularRedocView,
                                   SpectacularSwaggerView)
from graphene_django.views import GraphQLView

from apps.admin_management import views as admin_management_views
from apps.api import deeplinks as deeplink_views
from apps.library import views as library_views
from apps.social import views as social_views
from apps.resources import views as resource_views
from config.schema_fallback import apply_schema_fallback

# Keep OpenAPI generation resilient for legacy APIViews without serializer_class.
apply_schema_fallback()


def v2_not_implemented(request, *args, **kwargs):
    """Stub endpoint for future API v2 features."""
    version = kwargs.get("version", "v2")
    return JsonResponse(
        {
            "detail": "Endpoint not yet implemented",
            "version": version,
            "status": "not_implemented",
        },
        status=501,
    )

urlpatterns = [
    # Root
    path("", RedirectView.as_view(url="/api/docs/", permanent=False)),
    path("offline/", RedirectView.as_view(url="/static/pwa/offline.html", permanent=False), name="offline"),
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
        "role-invite/<str:token>/",
        admin_management_views.AdminRoleInvitationLandingView.as_view(),
        name="role-invitation-landing",
    ),
    path(
        "resources/<slug:slug>/",
        resource_views.ResourceShareLandingView.as_view(),
        name="resource-share-landing",
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
    # API Documentation (shared)
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # Versioned API namespaces
    path("api/v1/", include(([
        path("auth/", include("apps.accounts.urls")),
        path("", include("apps.faculties.urls")),
        path("", include("apps.courses.urls")),
        path("", include("apps.resources.urls")),
        path("", include("apps.bookmarks.urls")),
        path("", include("apps.comments.urls")),
        path("", include("apps.ratings.urls")),
        path("downloads/", include("apps.downloads.urls")),
        path("storage/", include("apps.core.storage.urls")),
        path("activity/", include("apps.activity.urls")),
        path("favorites/", include("apps.favorites.urls")),
        path("announcements/", include("apps.announcements.urls")),
        path("calendar/", include("apps.calendar.urls")),
        path("admin-management/", include("apps.admin_management.urls")),
        path("", include("apps.notifications.urls")),
        path("search/", include("apps.search.urls")),
        path("analytics/", include("apps.analytics.urls")),
        path("dashboard/", include("apps.dashboard.urls")),
        path("moderation/", include("apps.moderation.urls")),
        path("", include("apps.reports.urls")),
        path("library/", include("apps.library.urls")),
        path("recommendations/", include("apps.recommendations.urls")),
        path("gamification/", include("apps.gamification.urls")),
        path("social/", include("apps.social.urls")),
        path("payments/", include("apps.payments.urls")),
        path("referrals/", include("apps.referrals.urls")),
        path("cloud-storage/", include("apps.cloud_storage.urls")),
        path("ai/", include("apps.ai.urls")),
        path("live-rooms/", include("apps.live_rooms.urls")),
        path("learning/", include("apps.learning_analytics.urls")),
        path("calendar-sync/", include("apps.calendar_sync.urls")),
        path(
            "integrations/google-classroom/",
            include("apps.integrations.google_classroom.urls"),
        ),
        path(
            "integrations/microsoft-teams/",
            include("apps.integrations.microsoft_teams.urls"),
        ),
        path("institutions/", include("apps.institutions.urls")),
        path("tutoring/", include("apps.peer_tutoring.urls")),
        path("certificates/", include("apps.certificates.urls")),
        path("", include("apps.api.urls")),
    ], "api-v1"), namespace="api-v1"), {"version": "v1"}),
    # Mobile API namespace (legacy alias used by the Expo app + infra checks)
    path("api/", include(("apps.api.urls", "api"), namespace="api")),
    # Direct namespaced aliases used by tests and integrations.
    path("api/auth/", include(("apps.accounts.urls", "accounts"), namespace="accounts")),
    path(
        "api/admin-management/",
        include(("apps.admin_management.urls", "admin_management"), namespace="admin_management"),
    ),
    path("api/bookmarks/", include(("apps.bookmarks.urls", "bookmarks"), namespace="bookmarks")),
    path("api/comments/", include(("apps.comments.urls", "comments"), namespace="comments")),
    path("api/courses/", include(("apps.courses.urls", "courses"), namespace="courses")),
    path("api/dashboard/", include(("apps.dashboard.urls", "dashboard"), namespace="dashboard")),
    path("api/downloads/", include(("apps.downloads.urls", "downloads"), namespace="downloads")),
    path("api/favorites/", include(("apps.favorites.urls", "favorites"), namespace="favorites")),
    path("api/notifications/", include(("apps.notifications.urls", "notifications"), namespace="notifications")),
    path("api/ratings/", include(("apps.ratings.urls", "ratings"), namespace="ratings")),
    path("api/recommendations/", include(("apps.recommendations.urls", "recommendations"), namespace="recommendations")),
    path("api/reports/", include(("apps.reports.urls", "reports"), namespace="reports")),
    path("api/search/", include(("apps.search.urls", "search"), namespace="search")),
    path("api/", include(("apps.resources.urls", "resources"), namespace="resources")),
    path("api/activity/", include(("apps.activity.urls", "activity"), namespace="activity")),
    path("api/analytics/", include(("apps.analytics.urls", "analytics"), namespace="analytics")),
    path("api/social/", include(("apps.social.urls", "social"), namespace="social")),
    # Legacy unversioned alias (deprecated)
    path("api/", include(([
        path("auth/", include("apps.accounts.urls")),
        path("", include("apps.faculties.urls")),
        path("", include("apps.courses.urls")),
        path("", include("apps.resources.urls")),
        path("", include("apps.bookmarks.urls")),
        path("", include("apps.comments.urls")),
        path("", include("apps.ratings.urls")),
        path("downloads/", include("apps.downloads.urls")),
        path("storage/", include("apps.core.storage.urls")),
        path("activity/", include("apps.activity.urls")),
        path("favorites/", include("apps.favorites.urls")),
        path("announcements/", include("apps.announcements.urls")),
        path("calendar/", include("apps.calendar.urls")),
        path("admin-management/", include("apps.admin_management.urls")),
        path("", include("apps.notifications.urls")),
        path("search/", include("apps.search.urls")),
        path("analytics/", include("apps.analytics.urls")),
        path("dashboard/", include("apps.dashboard.urls")),
        path("moderation/", include("apps.moderation.urls")),
        path("", include("apps.reports.urls")),
        path("library/", include("apps.library.urls")),
        path("recommendations/", include("apps.recommendations.urls")),
        path("gamification/", include("apps.gamification.urls")),
        path("social/", include("apps.social.urls")),
        path("payments/", include("apps.payments.urls")),
        path("cloud-storage/", include("apps.cloud_storage.urls")),
        path("ai/", include("apps.ai.urls")),
        path("live-rooms/", include("apps.live_rooms.urls")),
        path("notes/", include("apps.notes.urls")),
        path("learning/", include("apps.learning_analytics.urls")),
        path("calendar-sync/", include("apps.calendar_sync.urls")),
        path(
            "integrations/google-classroom/",
            include("apps.integrations.google_classroom.urls"),
        ),
        path(
            "integrations/microsoft-teams/",
            include("apps.integrations.microsoft_teams.urls"),
        ),
        path("institutions/", include("apps.institutions.urls")),
        path("tutoring/", include("apps.peer_tutoring.urls")),
        path("certificates/", include("apps.certificates.urls")),
    ], "api-legacy"), namespace="api-legacy"), {"version": "legacy"}),
    # API v2 stub namespace
    path("api/v2/", include(([
        path("status/", v2_not_implemented, {"version": "v2"}, name="status"),
        path("placeholder/", v2_not_implemented, {"version": "v2"}, name="placeholder"),
    ], "api-v2"), namespace="api-v2"), {"version": "v2"}),
    # GraphQL endpoint
    path("graphql/", csrf_exempt(GraphQLView.as_view(graphiql=settings.DEBUG))),
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
