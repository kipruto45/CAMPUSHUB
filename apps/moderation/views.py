"""
Views for moderation app.
"""

from rest_framework import generics, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import IsAdminOrModerator
from apps.resources.models import Resource
from apps.resources.serializers import ResourceListSerializer

from .models import AdminActivityLog, ModerationLog
from .serializers import (AdminActivityLogSerializer, ApproveResourceSerializer,
                         ArchiveResourceSerializer, FlagResourceSerializer,
                         ModerationLogSerializer, RejectResourceSerializer)
from .services import ModerationService


class PendingResourcesView(generics.ListAPIView):
    """List pending resources."""

    queryset = Resource.objects.none()
    serializer_class = ResourceListSerializer
    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Resource.objects.none()
        return ModerationService.build_pending_queryset()


class ApproveResourceView(generics.CreateAPIView):
    """Approve a resource."""

    permission_classes = [IsAuthenticated, IsAdminOrModerator]
    serializer_class = ApproveResourceSerializer

    def create(self, request, *args, **kwargs):
        resource_id = kwargs.get("resource_id")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            resource = Resource.objects.get(id=resource_id)
        except Resource.DoesNotExist:
            return Response(
                {"detail": "Resource not found."}, status=status.HTTP_404_NOT_FOUND
            )

        ModerationService.approve_resource(
            resource=resource,
            reviewer=request.user,
            reason=serializer.validated_data.get("reason", ""),
        )

        # Send email notification to uploader
        from django.conf import settings
        from apps.core.emails import AdminEmailService

        try:
            AdminEmailService.send_resource_approved_email(
                resource.uploaded_by, resource
            )
        except Exception:
            # Email failure should not break approval
            pass

        return Response({"message": "Resource approved successfully."})


class RejectResourceView(generics.CreateAPIView):
    """Reject a resource."""

    permission_classes = [IsAuthenticated, IsAdminOrModerator]
    serializer_class = RejectResourceSerializer

    def create(self, request, *args, **kwargs):
        resource_id = kwargs.get("resource_id")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            resource = Resource.objects.get(id=resource_id)
        except Resource.DoesNotExist:
            return Response(
                {"detail": "Resource not found."}, status=status.HTTP_404_NOT_FOUND
            )

        rejection_reason = serializer.validated_data.get("reason", "")
        ModerationService.reject_resource(
            resource=resource,
            reviewer=request.user,
            reason=rejection_reason,
        )

        # Send email notification to uploader
        from apps.core.emails import AdminEmailService

        try:
            AdminEmailService.send_resource_rejected_email(
                resource.uploaded_by, resource, rejection_reason
            )
        except Exception:
            # Email failure should not break rejection
            pass

        return Response({"message": "Resource rejected successfully."})


class FlagResourceView(generics.CreateAPIView):
    """Flag a resource for review."""

    permission_classes = [IsAuthenticated, IsAdminOrModerator]
    serializer_class = FlagResourceSerializer

    def create(self, request, *args, **kwargs):
        resource_id = kwargs.get("resource_id")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            resource = Resource.objects.get(id=resource_id)
        except Resource.DoesNotExist:
            return Response(
                {"detail": "Resource not found."}, status=status.HTTP_404_NOT_FOUND
            )

        ModerationService.flag_resource(
            resource=resource,
            reviewer=request.user,
            reason=serializer.validated_data.get("reason", ""),
        )

        return Response({"message": "Resource flagged successfully."})


class ArchiveResourceView(generics.CreateAPIView):
    """Archive a resource."""

    permission_classes = [IsAuthenticated, IsAdminOrModerator]
    serializer_class = ArchiveResourceSerializer

    def create(self, request, *args, **kwargs):
        resource_id = kwargs.get("resource_id")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            resource = Resource.objects.get(id=resource_id)
        except Resource.DoesNotExist:
            return Response(
                {"detail": "Resource not found."}, status=status.HTTP_404_NOT_FOUND
            )

        ModerationService.archive_resource(
            resource=resource,
            reviewer=request.user,
            reason=serializer.validated_data.get("reason", ""),
        )

        return Response({"message": "Resource archived successfully."})


class RestoreResourceView(generics.CreateAPIView):
    """Restore an archived or rejected resource."""

    permission_classes = [IsAuthenticated, IsAdminOrModerator]
    serializer_class = FlagResourceSerializer

    def create(self, request, *args, **kwargs):
        resource_id = kwargs.get("resource_id")

        try:
            resource = Resource.objects.get(id=resource_id)
        except Resource.DoesNotExist:
            return Response(
                {"detail": "Resource not found."}, status=status.HTTP_404_NOT_FOUND
            )

        ModerationService.restore_resource(
            resource=resource,
            reviewer=request.user,
        )

        return Response({"message": "Resource restored successfully."})


class ModerationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for moderation logs."""

    serializer_class = ModerationLogSerializer
    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    def get_queryset(self):
        return ModerationLog.objects.all()


class AdminActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for admin activity logs."""

    serializer_class = AdminActivityLogSerializer
    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    def get_queryset(self):
        queryset = AdminActivityLog.objects.all()

        # Filter by admin
        admin_id = self.request.query_params.get("admin_id")
        if admin_id:
            queryset = queryset.filter(admin_id=admin_id)

        # Filter by action
        action = self.request.query_params.get("action")
        if action:
            queryset = queryset.filter(action=action)

        # Filter by target type
        target_type = self.request.query_params.get("target_type")
        if target_type:
            queryset = queryset.filter(target_type=target_type)

        # Filter by days
        days = self.request.query_params.get("days")
        if days:
            try:
                from datetime import timedelta
                from django.utils import timezone
                days_int = int(days)
                since = timezone.now() - timedelta(days=days_int)
                queryset = queryset.filter(created_at__gte=since)
            except (ValueError, TypeError):
                pass

        return queryset.select_related("admin")
