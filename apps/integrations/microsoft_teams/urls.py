"""
URL configuration for Microsoft Teams integration.
"""

from django.urls import path

from . import views

app_name = "microsoft_teams"

urlpatterns = [
    # OAuth flow
    path(
        "connect/",
        views.ConnectMicrosoftTeamsView.as_view(),
        name="connect",
    ),
    path(
        "oauth/callback/",
        views.MicrosoftTeamsOAuthCallbackView.as_view(),
        name="oauth-callback",
    ),
    # Integration management
    path(
        "disconnect/",
        views.DisconnectMicrosoftTeamsView.as_view(),
        name="disconnect",
    ),
    path(
        "status/",
        views.MicrosoftTeamsStatusView.as_view(),
        name="status",
    ),
    path(
        "sync/",
        views.MicrosoftTeamsSyncView.as_view(),
        name="sync",
    ),
    # Team/Course data
    path(
        "courses/",
        views.MicrosoftTeamsCoursesView.as_view(),
        name="courses",
    ),
    path(
        "courses/<uuid:team_id>/",
        views.MicrosoftTeamsCourseDetailView.as_view(),
        name="course-detail",
    ),
]