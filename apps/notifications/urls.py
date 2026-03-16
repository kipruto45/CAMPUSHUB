"""
URL configuration for notifications app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AdminNotificationViewSet, NotificationViewSet

app_name = "notifications"

router = DefaultRouter()
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"admin/notifications", AdminNotificationViewSet, basename="admin-notification")

urlpatterns = [
    # List notifications with filters
    # GET /api/notifications/
    # POST /api/notifications/
    # GET /api/notifications/unread/
    # GET /api/notifications/unread_count/
    # POST /api/notifications/mark_all_read/
    # POST /api/notifications/mark_multiple_read/
    # POST /api/notifications/{id}/mark_read/
    #
    # Admin notifications:
    # GET /api/admin/notifications/
    # GET /api/admin/notifications/stats/
    # GET /api/admin/notifications/unread_count/
    # GET /api/admin/notifications/urgent/
    # POST /api/admin/notifications/mark_all_read/
    path("", include(router.urls)),
]
