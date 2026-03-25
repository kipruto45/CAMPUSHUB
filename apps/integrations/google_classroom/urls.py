"""
URL configuration for Google Classroom integration.
"""

from django.urls import path

from . import views

app_name = "google_classroom"

urlpatterns = [
    # OAuth flow
    path(
        "connect/",
        views.ConnectGoogleClassroomView.as_view(),
        name="connect",
    ),
    path(
        "oauth/callback/",
        views.GoogleClassroomOAuthCallbackView.as_view(),
        name="oauth-callback",
    ),
    # Integration management
    path(
        "disconnect/",
        views.DisconnectGoogleClassroomView.as_view(),
        name="disconnect",
    ),
    path(
        "status/",
        views.GoogleClassroomStatusView.as_view(),
        name="status",
    ),
    path(
        "sync/",
        views.GoogleClassroomSyncView.as_view(),
        name="sync",
    ),
    # Course data
    path(
        "courses/",
        views.GoogleClassroomCoursesView.as_view(),
        name="courses",
    ),
    path(
        "courses/<uuid:course_id>/",
        views.GoogleClassroomCourseDetailView.as_view(),
        name="course-detail",
    ),
]