"""
Views for reports app.
"""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import IsAdminOrModerator
from apps.moderation.services import ModerationService
from apps.notifications.services import NotificationService

from .models import Report
from .serializers import (ReportCreateSerializer, ReportListSerializer,
                          ReportSerializer, ReportUpdateSerializer)


class ReportViewSet(viewsets.ModelViewSet):
    """ViewSet for Report model."""

    queryset = Report.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "reason_type"]
    lookup_field = "pk"
    lookup_url_kwarg = "id"

    def get_queryset(self):
        user = self.request.user
        # Regular users can only see their own reports
        if user.is_admin or user.is_moderator:
            return Report.objects.all()
        return Report.objects.filter(reporter=user)

    def get_serializer_class(self):
        if self.action == "list":
            return ReportListSerializer
        if self.action == "create":
            return ReportCreateSerializer
        if self.action in ["update", "partial_update"]:
            return ReportUpdateSerializer
        return ReportSerializer

    def get_permissions(self):
        if self.action in ["update", "partial_update", "resolve", "dismiss"]:
            return [IsAdminOrModerator()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = serializer.save(reporter=request.user)
        return Response(ReportSerializer(report).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        previous_status = serializer.instance.status
        report = serializer.save(reviewed_by=self.request.user)
        if report.status != previous_status and report.status in [
            "in_review",
            "resolved",
            "dismissed",
        ]:
            NotificationService.notify_report_status(report)
        if report.status in ["resolved", "dismissed"]:
            ModerationService.maybe_release_comment_after_report_decision(report)

    @action(detail=True, methods=["post"])
    def resolve(self, request, id=None, pk=None):
        """Resolve a report (admin/moderator only)."""
        report = self.get_object()
        resolution_note = request.data.get("resolution_note", "")

        report.status = "resolved"
        report.reviewed_by = request.user
        report.resolution_note = resolution_note
        report.save()

        NotificationService.notify_report_status(report)
        ModerationService.maybe_release_comment_after_report_decision(report)

        return Response(ReportSerializer(report).data)

    @action(detail=True, methods=["post"])
    def dismiss(self, request, id=None, pk=None):
        """Dismiss a report (admin/moderator only)."""
        report = self.get_object()
        resolution_note = request.data.get("resolution_note", "")

        report.status = "dismissed"
        report.reviewed_by = request.user
        report.resolution_note = resolution_note
        report.save()
        NotificationService.notify_report_status(report)
        ModerationService.maybe_release_comment_after_report_decision(report)

        return Response(ReportSerializer(report).data)

    @action(detail=False, methods=["get"])
    def my_reports(self, request):
        """Get current user's reports."""
        reports = Report.objects.filter(reporter=request.user)
        serializer = ReportListSerializer(reports, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def pending(self, request):
        """Get pending reports (admin/moderator only)."""
        if not (request.user.is_admin or request.user.is_moderator):
            return Response(
                {"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN
            )
        reports = Report.objects.filter(status="open")
        serializer = ReportListSerializer(reports, many=True)
        return Response(serializer.data)
