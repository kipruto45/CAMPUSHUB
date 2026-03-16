"""
URL configuration for mobile API endpoints.
"""

from django.conf import settings
from django.urls import path

from . import deeplinks, mobile_views

app_name = "api"


def api_info(request):
    """Return API configuration for mobile apps."""
    from django.http import JsonResponse

    ws_scheme = "wss" if request.is_secure() else "ws"

    return JsonResponse(
        {
            "success": True,
            "version": getattr(settings, "MOBILE_API_VERSION", "1.0"),
            "api_base": "/api/",
            "endpoints": {
                "auth": {
                    "register": "/api/mobile/register/",
                    "login": "/api/mobile/login/",
                    "logout": "/api/mobile/logout/",
                    "refresh_token": "/api/mobile/refresh/",
                    "forgot_password": "/api/mobile/password/reset/",
                    "reset_password_confirm": "/api/mobile/password/reset/confirm/<str:token>/",
                    "verify_email": "/api/mobile/verify-email/<str:token>/",
                    "resend_verification": "/api/mobile/verify-email/resend/",
                    "google_oauth_url": "/api/auth/google/url/",
                    "google_oauth_exchange": "/api/auth/google/",
                    "google_oauth_native": "/api/auth/google/native/",
                    "microsoft_oauth_url": "/api/auth/microsoft/url/",
                    "microsoft_oauth_exchange": "/api/auth/microsoft/",
                    "microsoft_oauth_native": "/api/auth/microsoft/native/",
                },
                "resources": {
                    "list": "/api/mobile/resources/",
                    "detail": "/api/mobile/resources/<uuid:id>/",
                    "upload": "/api/mobile/resources/upload/",
                    "bookmark_toggle": "/api/mobile/resources/<uuid:id>/bookmark/",
                    "favorite_toggle": "/api/mobile/resources/<uuid:id>/favorite/",
                    "download": "/api/mobile/resources/<uuid:id>/download/",
                    "save_to_library": "/api/mobile/resources/<uuid:id>/save-to-library/",
                    "share_link": "/api/resources/<slug_or_uuid:id>/share-link/",
                    "share_track": "/api/resources/<slug_or_uuid:id>/share/",
                },
                "bookmarks": {
                    "list": "/api/mobile/bookmarks/",
                },
                "favorites": {
                    "list": "/api/mobile/favorites/",
                },
                "dashboard": "/api/mobile/dashboard/",
                "gamification": {
                    "stats": "/api/gamification/stats/",
                    "leaderboard": "/api/gamification/leaderboard/",
                    "check_badges": "/api/gamification/check-badges/",
                },
                "social": {
                    "study_groups": "/api/social/study-groups/",
                    "study_group_detail": "/api/social/study-groups/<uuid:group_id>/",
                    "study_group_join": "/api/social/study-groups/<uuid:group_id>/join/",
                    "study_group_leave": "/api/social/study-groups/<uuid:group_id>/leave/",
                },
                "notifications": "/api/mobile/notifications/",
                "courses": "/api/mobile/courses/",
                "faculties": "/api/mobile/faculties/",
                "sync": "/api/mobile/sync/",
                "stats": "/api/mobile/stats/",
                "library": {
                    "summary": "/api/mobile/library/summary/",
                    "files": "/api/mobile/library/files/",
                    "folders": "/api/mobile/library/folders/",
                },
                "deeplinks": {
                    "parse": "/api/mobile/deeplink/parse/",
                    "build": "/api/mobile/deeplink/build/",
                },
                "device": {
                    "register": "/api/mobile/device/register/",
                    "subscribe_topic": "/api/mobile/topic/subscribe/",
                    "unsubscribe_topic": "/api/mobile/topic/unsubscribe/",
                },
            },
            "websocket": {
                "enabled": True,
                "url": f"{ws_scheme}://" + request.get_host() + "/ws/notifications/",
                "admin_notifications": f"{ws_scheme}://"
                + request.get_host()
                + "/ws/admin/notifications/",
                "activity": f"{ws_scheme}://" + request.get_host() + "/ws/activity/",
            },
            "features": {
                "push_notifications": {
                    "fcm": {
                        "enabled": getattr(settings, "FCM_ENABLED", False),
                        "configured": bool(getattr(settings, "FCM_SERVER_KEY", "")),
                    },
                    "apns": {
                        "enabled": getattr(settings, "APNS_ENABLED", False),
                        "configured": bool(
                            getattr(settings, "APNS_TEAM_ID", "")
                            and getattr(settings, "APNS_KEY_ID", "")
                            and (
                                getattr(settings, "APNS_AUTH_KEY", "")
                                or getattr(settings, "APNS_AUTH_KEY_PATH", "")
                            )
                        ),
                    },
                },
                "deep_linking": True,
                "offline_sync": True,
                "rate_limiting": True,
            },
            "limits": {
                "upload": "10/day",
                "download": "100/hour",
                "api_calls": "200/hour",
            },
        }
    )


urlpatterns = [
    # API Info
    path("mobile/info/", api_info, name="api_info"),
    # Authentication
    path("mobile/register/", mobile_views.mobile_register, name="mobile_register"),
    path("mobile/login/", mobile_views.mobile_login, name="mobile_login"),
    path("mobile/logout/", mobile_views.mobile_logout, name="mobile_logout"),
    path(
        "mobile/password/reset/",
        mobile_views.mobile_password_reset_request,
        name="mobile_password_reset_request",
    ),
    path(
        "mobile/password/reset/confirm/<str:token>/",
        mobile_views.mobile_password_reset_confirm,
        name="mobile_password_reset_confirm",
    ),
    path(
        "mobile/verify-email/resend/",
        mobile_views.mobile_resend_verification_email,
        name="mobile_resend_verification_email",
    ),
    path(
        "mobile/verify-email/<str:token>/",
        mobile_views.mobile_verify_email,
        name="mobile_verify_email",
    ),
    # Public academic data for registration
    path("public/faculties/", mobile_views.public_faculties, name="public_faculties"),
    path("public/departments/", mobile_views.public_departments, name="public_departments"),
    path("public/courses/", mobile_views.public_courses, name="public_courses"),
    path(
        "mobile/refresh/",
        mobile_views.mobile_refresh_token,
        name="mobile_refresh_token",
    ),
    # Dashboard
    path("mobile/dashboard/", mobile_views.mobile_dashboard, name="mobile_dashboard"),
    # Resources
    path("mobile/resources/", mobile_views.mobile_resources, name="mobile_resources"),
    path(
        "mobile/resources/upload/",
        mobile_views.mobile_upload_resource,
        name="mobile_upload_resource",
    ),
    path(
        "mobile/resources/<uuid:resource_id>/",
        mobile_views.mobile_resource_detail,
        name="mobile_resource_detail",
    ),
    path(
        "mobile/resources/<uuid:resource_id>/bookmark/",
        mobile_views.mobile_toggle_bookmark,
        name="mobile_toggle_bookmark",
    ),
    path(
        "mobile/resources/<uuid:resource_id>/favorite/",
        mobile_views.mobile_toggle_favorite,
        name="mobile_toggle_favorite",
    ),
    path(
        "mobile/resources/<uuid:resource_id>/download/",
        mobile_views.mobile_download_resource,
        name="mobile_download_resource",
    ),
    path(
        "mobile/resources/<uuid:resource_id>/save-to-library/",
        mobile_views.mobile_save_to_library,
        name="mobile_save_to_library",
    ),
    # Saved/Favorites lists
    path("mobile/bookmarks/", mobile_views.mobile_bookmarks, name="mobile_bookmarks"),
    path("mobile/favorites/", mobile_views.mobile_favorites, name="mobile_favorites"),
    # Notifications
    path(
        "mobile/notifications/",
        mobile_views.mobile_notifications,
        name="mobile_notifications",
    ),
    path(
        "mobile/notifications/<uuid:notification_id>/read/",
        mobile_views.mobile_mark_notification_read,
        name="mobile_mark_notification_read",
    ),
    path(
        "mobile/notifications/read-all/",
        mobile_views.mobile_mark_all_notifications_read,
        name="mobile_mark_all_notifications_read",
    ),
    # Device / Push Notifications
    path(
        "mobile/device/register/",
        mobile_views.mobile_register_device,
        name="mobile_register_device",
    ),
    # Courses & Units
    path("mobile/courses/", mobile_views.mobile_courses, name="mobile_courses"),
    path(
        "mobile/courses/<uuid:course_id>/units/",
        mobile_views.mobile_units,
        name="mobile_units",
    ),
    # Faculties
    path("mobile/faculties/", mobile_views.mobile_faculties, name="mobile_faculties"),
    # Offline / Sync
    path("mobile/sync/", mobile_views.mobile_sync, name="mobile_sync"),
    # Library
    path(
        "mobile/library/summary/",
        mobile_views.mobile_library_summary,
        name="mobile_library_summary",
    ),
    path(
        "mobile/library/files/",
        mobile_views.mobile_library_files,
        name="mobile_library_files",
    ),
    path(
        "mobile/library/folders/",
        mobile_views.mobile_library_folders,
        name="mobile_library_folders",
    ),
    # Stats
    path("mobile/stats/", mobile_views.mobile_stats, name="mobile_stats"),
    # Topic subscription
    path(
        "mobile/topic/subscribe/",
        mobile_views.mobile_subscribe_topic,
        name="mobile_subscribe_topic",
    ),
    path(
        "mobile/topic/unsubscribe/",
        mobile_views.mobile_unsubscribe_topic,
        name="mobile_unsubscribe_topic",
    ),
    # Resource Requests
    path(
        "mobile/resource-requests/",
        mobile_views.mobile_resource_requests,
        name="mobile_resource_requests"
    ),
    path(
        "mobile/resource-requests/<uuid:request_id>/upvote/",
        mobile_views.mobile_upvote_resource_request,
        name="mobile_upvote_resource_request"
    ),
    # Gamification / Leaderboard
    path(
        "mobile/leaderboard/",
        mobile_views.mobile_leaderboard,
        name="mobile_leaderboard"
    ),
    path(
        "mobile/system-health/",
        mobile_views.mobile_system_health,
        name="mobile_system_health"
    ),
    # Comments
    path(
        "mobile/resources/<uuid:resource_id>/comments/",
        mobile_views.mobile_resource_comments,
        name="mobile_resource_comments"
    ),
    # Deep-link tooling
    path(
        "mobile/deeplink/parse/",
        deeplinks.parse_deep_link_view,
        name="mobile_deeplink_parse",
    ),
    path(
        "mobile/deeplink/build/",
        deeplinks.build_deep_link_view,
        name="mobile_deeplink_build",
    ),
]
