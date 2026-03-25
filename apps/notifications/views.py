"""
Views for notifications app.
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.pagination import StandardResultsSetPagination

from .models import DeviceToken, Notification
from .serializers import (MarkNotificationReadSerializer,
                          NotificationListSerializer, NotificationSerializer)


class NotificationViewSet(viewsets.ModelViewSet):
    """ViewSet for Notification model."""

    serializer_class = NotificationListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        queryset = Notification.objects.filter(recipient=self.request.user)

        # Filter by read status
        is_read = self.request.query_params.get("is_read")
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == "true")

        # Filter by notification type
        notification_type = self.request.query_params.get("type")
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)

        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return NotificationSerializer
        return NotificationListSerializer

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        """Get count of unread notifications."""
        count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()
        return Response({"unread_count": count})

    @action(detail=False, methods=["get"])
    def unread(self, request):
        """Get all unread notifications."""
        notifications = Notification.objects.filter(
            recipient=request.user, is_read=False
        )
        serializer = self.get_serializer(notifications, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        """Mark all notifications as read."""
        updated_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).update(is_read=True)
        return Response(
            {
                "message": "All notifications marked as read.",
                "updated_count": updated_count,
            }
        )

    @action(detail=False, methods=["post"])
    def mark_multiple_read(self, request):
        """Mark specific notifications as read."""
        serializer = MarkNotificationReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        notification_ids = serializer.validated_data.get("notification_ids", [])

        if notification_ids:
            update_qs = Notification.objects.filter(
                recipient=request.user, id__in=notification_ids, is_read=False
            )
            updated_count = update_qs.update(is_read=True)
        else:
            # If no IDs provided, mark all as read
            update_qs = Notification.objects.filter(recipient=request.user, is_read=False)
            updated_count = update_qs.update(is_read=True)

        return Response(
            {
                "message": "Notifications marked as read.",
                "updated_count": updated_count,
            }
        )

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        """Mark a notification as read."""
        notification = self.get_object()

        # Ensure ownership
        if notification.recipient != request.user:
            return Response(
                {"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN
            )

        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read", "updated_at"])

        return Response(
            {
                "id": str(notification.id),
                "is_read": notification.is_read,
            }
        )

    @action(detail=False, methods=["post"])
    def register_device(self, request):
        """Register a device token for push notifications."""
        expo_push_token = request.data.get("expo_push_token")
        device_id = request.data.get("device_id", "")
        device_name = request.data.get("device_name", "")
        platform = request.data.get("platform", "android")

        if not expo_push_token:
            return Response(
                {"error": "expo_push_token is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get device type from platform
        device_type = "android" if platform.lower() == "android" else "ios"

        # Create or update device token
        token, created = DeviceToken.objects.update_or_create(
            device_token=expo_push_token,
            user=request.user,
            defaults={
                "device_type": device_type,
                "device_name": device_name,
                "is_active": True,
            }
        )

        return Response(
            {
                "message": "Device registered successfully",
                "device_id": token.id
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    @action(detail=False, methods=["post"])
    def unregister_device(self, request):
        """Unregister a device token."""
        expo_push_token = request.data.get("expo_push_token")

        if not expo_push_token:
            return Response(
                {"error": "expo_push_token is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        deleted, _ = DeviceToken.objects.filter(
            device_token=expo_push_token,
            user=request.user
        ).delete()

        if deleted:
            return Response({"message": "Device unregistered successfully"})
        else:
            return Response(
                {"error": "Device token not found"},
                status=status.HTTP_404_NOT_FOUND
            )


class AdminNotificationViewSet(viewsets.ModelViewSet):
    """ViewSet for admin-specific notifications."""

    serializer_class = NotificationListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        
        # Only admin notifications
        queryset = Notification.objects.filter(
            recipient=self.request.user,
            is_admin_notification=True,
        )

        # Filter by read status
        is_read = self.request.query_params.get("is_read")
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == "true")

        # Filter by priority
        priority = self.request.query_params.get("priority")
        if priority:
            queryset = queryset.filter(priority=priority)

        # Filter by notification type
        notification_type = self.request.query_params.get("type")
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)

        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return NotificationSerializer
        return NotificationListSerializer

    def get_permissions(self):
        """Only allow staff users."""
        if not self.request.user.is_staff:
            return []
        return super().get_permissions()

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get admin notification statistics."""
        from .services import AdminNotificationService
        
        stats = AdminNotificationService.get_admin_notification_stats(request.user)
        return Response(stats)

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        """Get count of unread admin notifications."""
        count = Notification.objects.filter(
            recipient=request.user,
            is_admin_notification=True,
            is_read=False,
        ).count()
        return Response({"unread_count": count})

    @action(detail=False, methods=["get"])
    def urgent(self, request):
        """Get urgent unread admin notifications."""
        notifications = Notification.objects.filter(
            recipient=request.user,
            is_admin_notification=True,
            is_read=False,
            priority__in=['high', 'urgent'],
        )
        serializer = self.get_serializer(notifications, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        """Mark all admin notifications as read."""
        updated = Notification.objects.filter(
            recipient=request.user,
            is_admin_notification=True,
            is_read=False,
        ).update(is_read=True)
        return Response(
            {
                "message": f"Marked {updated} notifications as read.",
                "updated_count": updated,
            }
        )
