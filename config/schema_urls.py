"""Canonical URLConf used for OpenAPI schema generation."""

from django.urls import include, path


urlpatterns = [
    path(
        "api/v1/",
        include(
            (
                [
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
                ],
                "api-v1",
            ),
            namespace="api-v1",
        ),
        {"version": "v1"},
    ),
]
