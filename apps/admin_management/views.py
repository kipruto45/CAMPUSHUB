"""Views for admin management module."""

import json
import os
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, extend_schema_view
from drf_spectacular.plumbing import build_basic_type
from rest_framework import generics, status, serializers
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.serializers import UserActivitySerializer
from apps.admin_management.permissions import IsAdmin
from apps.admin_management.serializers import (
    AdminAnnouncementSerializer, AdminCourseSerializer,
    AdminDashboardSerializer, AdminDepartmentSerializer,
    AdminFacultySerializer, AdminReportResolveDismissSerializer,
    AdminReportSerializer, AdminReportUpdateSerializer,
    AdminResourceRejectSerializer, AdminResourceReviewSerializer,
    AdminResourceSerializer, AdminStudyGroupSerializer,
    AdminStudyGroupUpdateSerializer, AdminUnitSerializer, AdminUserDetailSerializer,
    AdminUserListSerializer, AdminUserRoleUpdateSerializer,
    AdminUserStatusUpdateSerializer)
from apps.admin_management.services import (announcement_lifecycle_action,
                                            can_manage_target_user,
                                            delete_resource,
                                            get_academic_stats,
                                            get_admin_dashboard_data,
                                            get_moderation_queues,
                                            get_resource_management_stats,
                                            get_system_health,
                                            get_user_management_stats,
                                            admin_global_search,
                                            log_admin_activity,
                                            review_resource,
                                            update_report_status,
                                            update_user_role,
                                            update_user_status)
from apps.announcements.models import Announcement
from apps.core.pagination import StandardPagination
from apps.courses.models import Course, Unit
from apps.faculties.models import Department, Faculty
from apps.reports.models import Report
from apps.resources.models import Resource
from apps.social.models import StudyGroup

# Gamification imports
from apps.gamification.models import (
    Badge, UserBadge, UserPoints, UserStats, Achievement, Leaderboard
)


# =========================
# Shared serializers
# =========================

class AdminBadgeListSerializer(serializers.ModelSerializer):
    earned_count = serializers.SerializerMethodField()

    class Meta:
        model = Badge
        ref_name = "AdminBadgeListSerializer"
        fields = [
            'id', 'name', 'slug', 'description', 'icon', 'category',
            'points_required', 'requirement_type', 'requirement_value',
            'is_active', 'earned_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_earned_count(self, obj) -> int:
        return UserBadge.objects.filter(badge=obj).count()


class AdminBadgeDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        ref_name = "AdminBadgeDetailSerializer"
        fields = [
            'id', 'name', 'slug', 'description', 'icon', 'category',
            'points_required', 'requirement_type', 'requirement_value',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AdminDashboardView(APIView):
    """Get admin dashboard overview."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        data = get_admin_dashboard_data()
        serializer = AdminDashboardSerializer(data)
        return Response(serializer.data)


class AdminStatsView(APIView):
    """Get targeted admin stats."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        stats_type = request.query_params.get("type", "dashboard").strip().lower()
        if stats_type == "users":
            return Response(get_user_management_stats())
        if stats_type == "resources":
            return Response(get_resource_management_stats())
        if stats_type == "academics":
            return Response(get_academic_stats())
        if stats_type == "moderation":
            return Response(get_moderation_queues())
        return Response(get_admin_dashboard_data())


class AdminUserListView(generics.ListAPIView):
    """List users for admins with filters."""

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = AdminUserListSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        queryset = (
            User.objects.select_related("faculty", "department", "course")
            .annotate(
                uploads_count=Count("uploads", distinct=True),
                reports_count=Count("reports_made", distinct=True),
            )
            .order_by("-date_joined")
        )

        role = self.request.query_params.get("role")
        if role:
            queryset = queryset.filter(role__iexact=role)

        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        is_verified = self.request.query_params.get("is_verified")
        if is_verified is not None:
            queryset = queryset.filter(is_verified=is_verified.lower() == "true")

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(registration_number__icontains=search)
            )

        return queryset


class AdminUserDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve and update user details."""

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = AdminUserDetailSerializer
    lookup_url_kwarg = "user_id"

    def get_queryset(self):
        return User.objects.select_related("profile", "faculty", "department", "course")


class AdminUserActivityListView(generics.ListAPIView):
    """List a target user's account activity for admins."""

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = UserActivitySerializer
    pagination_class = StandardPagination
    lookup_url_kwarg = "user_id"
    queryset = User.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return User.objects.none()
        return (
            self.get_user()
            .activities.select_related("resource")
            .order_by("-created_at")
        )

    def get_user(self):
        return get_object_or_404(User.objects.all(), id=self.kwargs["user_id"])


class AdminUserStatusUpdateView(APIView):
    """Activate/deactivate user accounts."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def patch(self, request, user_id):
        target = get_object_or_404(User, id=user_id)
        if not can_manage_target_user(actor=request.user, target=target):
            return Response(
                {"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN
            )

        serializer = AdminUserStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = update_user_status(
            actor=request.user,
            target=target,
            is_active=serializer.validated_data["is_active"],
        )
        response_status = (
            status.HTTP_200_OK if result["success"] else status.HTTP_400_BAD_REQUEST
        )
        return Response(result, status=response_status)


class AdminUserRoleUpdateView(APIView):
    """Update user role."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def patch(self, request, user_id):
        target = get_object_or_404(User, id=user_id)
        if not can_manage_target_user(actor=request.user, target=target):
            return Response(
                {"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN
            )

        serializer = AdminUserRoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = update_user_role(
            actor=request.user,
            target=target,
            role=serializer.validated_data["role"],
        )
        response_status = (
            status.HTTP_200_OK if result["success"] else status.HTTP_400_BAD_REQUEST
        )
        return Response(result, status=response_status)


class AdminResourceListView(generics.ListAPIView):
    """List resources for admin moderation."""

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = AdminResourceSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        queryset = (
            Resource.objects.select_related("uploaded_by", "course", "unit")
            .annotate(
                report_items_count=Count("reports", distinct=True),
                comments_total=Count("comments", distinct=True),
            )
            .order_by("-created_at")
        )

        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        resource_type = self.request.query_params.get("resource_type")
        if resource_type:
            queryset = queryset.filter(resource_type=resource_type)

        uploaded_by = self.request.query_params.get("uploaded_by")
        if uploaded_by:
            queryset = queryset.filter(uploaded_by_id=uploaded_by)

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )

        return queryset


class AdminResourceDetailView(generics.RetrieveDestroyAPIView):
    """Retrieve and delete resources."""

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = AdminResourceSerializer
    lookup_url_kwarg = "resource_id"

    def get_queryset(self):
        return Resource.objects.select_related(
            "uploaded_by", "course", "unit"
        ).annotate(
            report_items_count=Count("reports", distinct=True),
            comments_total=Count("comments", distinct=True),
        )

    def destroy(self, request, *args, **kwargs):
        resource = self.get_object()
        result = delete_resource(resource=resource, actor=request.user)
        return Response(result, status=status.HTTP_200_OK)


class AdminApproveResourceView(APIView):
    """Approve a pending resource."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, resource_id):
        resource = get_object_or_404(Resource, id=resource_id)
        serializer = AdminResourceReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        review_resource(
            resource=resource,
            reviewer=request.user,
            approve=True,
            reason=serializer.validated_data.get("reason", ""),
        )

        resource.refresh_from_db()
        return Response(
            AdminResourceSerializer(resource).data, status=status.HTTP_200_OK
        )


class AdminRejectResourceView(APIView):
    """Reject a pending resource."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, resource_id):
        resource = get_object_or_404(Resource, id=resource_id)
        serializer = AdminResourceRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        review_resource(
            resource=resource,
            reviewer=request.user,
            approve=False,
            reason=serializer.validated_data["reason"],
        )

        resource.refresh_from_db()
        return Response(
            AdminResourceSerializer(resource).data, status=status.HTTP_200_OK
        )


class AdminPinResourceView(APIView):
    """
    Pin or unpin a resource to make it appear at the top.
    POST /api/admin-management/resources/{id}/pin/
    {
        "pin": true  # or false to unpin
    }
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, resource_id):
        from apps.resources.models import Resource
        import uuid
        
        # Handle both UUID object and string
        try:
            if isinstance(resource_id, str):
                resource_uuid = uuid.UUID(resource_id)
            else:
                resource_uuid = resource_id
        except (ValueError, AttributeError) as e:
            return Response(
                {"error": f"Invalid resource ID format: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Handle both boolean and string values
        pin_value = request.data.get('pin', True)
        if isinstance(pin_value, str):
            pin = pin_value.lower() in ('true', '1', 'yes')
        else:
            pin = bool(pin_value)
        
        try:
            resource = Resource.objects.get(id=resource_uuid)
        except Resource.DoesNotExist:
            return Response(
                {"error": "Resource not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        resource.is_pinned = pin
        resource.save()
        
        return Response(
            {
                "message": f"Resource {'pinned' if pin else 'unpinned'} successfully",
                "is_pinned": resource.is_pinned
            },
            status=status.HTTP_200_OK
        )


class AdminBulkResourceActionView(APIView):
    """
    Perform bulk actions on resources.
    POST /api/admin-management/resources/bulk-action/
    {
        "action": "delete" | "approve" | "reject" | "archive",
        "resource_ids": [1, 2, 3],
        "reason": "Optional reason for reject action"
    }
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request):
        action = request.data.get("action")
        resource_ids = request.data.get("resource_ids", [])
        reason = request.data.get("reason", "")

        if not resource_ids:
            return Response(
                {"error": "No resources specified"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if action not in ["delete", "approve", "reject", "archive"]:
            return Response(
                {"error": "Invalid action. Must be delete, approve, reject, or archive"},
                status=status.HTTP_400_BAD_REQUEST
            )

        from apps.resources.models import Resource
        from apps.moderation.models import ResourceModeration

        resources = Resource.objects.filter(id__in=resource_ids)
        updated_count = 0
        errors = []

        for resource in resources:
            try:
                if action == "delete":
                    resource.delete()
                    updated_count += 1
                elif action == "approve":
                    resource.status = "approved"
                    resource.approved_by = request.user
                    resource.approved_at = timezone.now()
                    resource.save()
                    ResourceModeration.objects.create(
                        resource=resource,
                        reviewer=request.user,
                        approve=True,
                        reason="Bulk approved"
                    )
                    updated_count += 1
                elif action == "reject":
                    resource.status = "rejected"
                    resource.rejection_reason = reason or "Bulk rejected"
                    resource.save()
                    ResourceModeration.objects.create(
                        resource=resource,
                        reviewer=request.user,
                        approve=False,
                        reason=reason or "Bulk rejected"
                    )
                    updated_count += 1
                elif action == "archive":
                    resource.status = "archived"
                    resource.save()
                    updated_count += 1
            except Exception as e:
                errors.append(f"Error processing resource {resource.id}: {str(e)}")

        return Response({
            "success": True,
            "updated_count": updated_count,
            "errors": errors,
            "action": action,
        })


class AdminReportListView(generics.ListAPIView):
    """List submitted reports for moderation."""

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = AdminReportSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        queryset = Report.objects.select_related(
            "reporter", "reviewed_by", "resource", "comment", "comment__user"
        ).order_by("-created_at")

        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        reason_type = self.request.query_params.get("reason_type")
        if reason_type:
            queryset = queryset.filter(reason_type=reason_type)

        target_type = self.request.query_params.get("target_type")
        if target_type == "resource":
            queryset = queryset.filter(resource__isnull=False)
        elif target_type == "comment":
            queryset = queryset.filter(comment__isnull=False)

        return queryset


class AdminReportDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve and update report status."""

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = AdminReportSerializer
    lookup_url_kwarg = "report_id"

    def get_queryset(self):
        return Report.objects.select_related(
            "reporter", "reviewed_by", "resource", "comment", "comment__user"
        )

    def get_serializer_class(self):
        if self.request.method in ["PATCH", "PUT"]:
            return AdminReportUpdateSerializer
        return AdminReportSerializer

    def update(self, request, *args, **kwargs):
        report = self.get_object()
        serializer = self.get_serializer(report, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data.get("status", report.status)
        resolution_note = serializer.validated_data.get(
            "resolution_note", report.resolution_note
        )

        updated = update_report_status(
            report=report,
            reviewer=request.user,
            status=new_status,
            resolution_note=resolution_note,
        )
        return Response(AdminReportSerializer(updated).data, status=status.HTTP_200_OK)


class AdminResolveReportView(APIView):
    """Resolve a report."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, report_id):
        report = get_object_or_404(Report, id=report_id)
        serializer = AdminReportResolveDismissSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated = update_report_status(
            report=report,
            reviewer=request.user,
            status="resolved",
            resolution_note=serializer.validated_data.get("resolution_note", ""),
        )
        return Response(AdminReportSerializer(updated).data, status=status.HTTP_200_OK)


class AdminDismissReportView(APIView):
    """Dismiss a report."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, report_id):
        report = get_object_or_404(Report, id=report_id)
        serializer = AdminReportResolveDismissSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated = update_report_status(
            report=report,
            reviewer=request.user,
            status="dismissed",
            resolution_note=serializer.validated_data.get("resolution_note", ""),
        )
        return Response(AdminReportSerializer(updated).data, status=status.HTTP_200_OK)


class AdminAnnouncementListView(generics.ListCreateAPIView):
    """List and create announcements."""

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = AdminAnnouncementSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        queryset = Announcement.objects.select_related(
            "created_by", "target_faculty", "target_department", "target_course"
        ).order_by("-is_pinned", "-published_at", "-created_at")

        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        announcement_type = self.request.query_params.get("announcement_type")
        if announcement_type:
            queryset = queryset.filter(announcement_type=announcement_type)

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class AdminAuditCreateUpdateMixin:
    """Write admin activity logs for create/update endpoints."""

    create_action = ""
    update_action = ""
    target_type = ""
    target_title_attr = "name"

    def _target_title(self, obj) -> str:
        return getattr(obj, self.target_title_attr, "") or ""

    def perform_create(self, serializer):
        instance = serializer.save()
        if self.create_action:
            log_admin_activity(
                admin=self.request.user,
                action=self.create_action,
                target_type=self.target_type,
                target_id=instance.id,
                target_title=self._target_title(instance),
            )

    def perform_update(self, serializer):
        instance = serializer.save()
        if self.update_action:
            log_admin_activity(
                admin=self.request.user,
                action=self.update_action,
                target_type=self.target_type,
                target_id=instance.id,
                target_title=self._target_title(instance),
            )


class AdminAnnouncementDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete an announcement."""

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = AdminAnnouncementSerializer
    lookup_url_kwarg = "announcement_id"

    def get_queryset(self):
        return Announcement.objects.select_related("created_by")


class AdminStudyGroupListView(generics.ListAPIView):
    """List all study groups for admin management."""

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = AdminStudyGroupSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        queryset = (
            StudyGroup.objects.select_related("creator", "course", "faculty", "department")
            .annotate(
                active_member_count=Count(
                    "memberships",
                    filter=Q(memberships__status="active"),
                    distinct=True,
                )
            )
            .order_by("-created_at")
        )

        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        privacy_filter = self.request.query_params.get("privacy")
        if privacy_filter == "public":
            queryset = queryset.filter(is_public=True)
        elif privacy_filter == "private":
            queryset = queryset.filter(is_public=False)

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(description__icontains=search)
                | Q(creator__email__icontains=search)
                | Q(creator__first_name__icontains=search)
                | Q(creator__last_name__icontains=search)
                | Q(course__name__icontains=search)
            )

        year_of_study = self.request.query_params.get("year_of_study")
        if year_of_study:
            queryset = queryset.filter(year_of_study=year_of_study)

        return queryset


class AdminStudyGroupDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update and archive study groups."""

    permission_classes = [IsAuthenticated, IsAdmin]
    lookup_url_kwarg = "group_id"

    def get_queryset(self):
        return (
            StudyGroup.objects.select_related("creator", "course", "faculty", "department")
            .annotate(
                active_member_count=Count(
                    "memberships",
                    filter=Q(memberships__status="active"),
                    distinct=True,
                )
            )
        )

    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return AdminStudyGroupUpdateSerializer
        return AdminStudyGroupSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        refreshed = self.get_queryset().get(id=instance.id)
        return Response(
            AdminStudyGroupSerializer(
                refreshed, context=self.get_serializer_context()
            ).data
        )

    def perform_destroy(self, instance):
        instance.status = "archived"
        instance.save(update_fields=["status", "updated_at"])


class AdminPublishAnnouncementView(APIView):
    """Publish announcement."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, announcement_id):
        announcement = get_object_or_404(Announcement, id=announcement_id)
        updated = announcement_lifecycle_action(
            announcement=announcement, action="publish", actor=request.user
        )
        return Response(
            AdminAnnouncementSerializer(updated).data, status=status.HTTP_200_OK
        )


class AdminArchiveAnnouncementView(APIView):
    """Archive announcement."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, announcement_id):
        announcement = get_object_or_404(Announcement, id=announcement_id)
        updated = announcement_lifecycle_action(
            announcement=announcement, action="archive", actor=request.user
        )
        return Response(
            AdminAnnouncementSerializer(updated).data, status=status.HTTP_200_OK
        )


class AdminUnpublishAnnouncementView(APIView):
    """Move announcement back to draft."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, announcement_id):
        announcement = get_object_or_404(Announcement, id=announcement_id)
        updated = announcement_lifecycle_action(
            announcement=announcement, action="unpublish", actor=request.user
        )
        return Response(
            AdminAnnouncementSerializer(updated).data, status=status.HTTP_200_OK
        )


class AdminFacultyListView(AdminAuditCreateUpdateMixin, generics.ListCreateAPIView):
    """List and create faculties."""

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = AdminFacultySerializer
    pagination_class = StandardPagination
    create_action = "faculty_created"
    target_type = "faculty"

    def get_queryset(self):
        queryset = Faculty.objects.all().order_by("name")
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")
        return queryset


class AdminFacultyDetailView(
    AdminAuditCreateUpdateMixin, generics.RetrieveUpdateDestroyAPIView
):
    """Retrieve, update, delete faculty."""

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = AdminFacultySerializer
    lookup_url_kwarg = "faculty_id"
    update_action = "faculty_updated"
    target_type = "faculty"

    def get_queryset(self):
        return Faculty.objects.all()


class AdminDepartmentListView(
    AdminAuditCreateUpdateMixin, generics.ListCreateAPIView
):
    """List and create departments."""

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = AdminDepartmentSerializer
    pagination_class = StandardPagination
    create_action = "department_created"
    target_type = "department"

    def get_queryset(self):
        queryset = Department.objects.select_related("faculty").order_by("name")

        faculty_id = self.request.query_params.get("faculty")
        if faculty_id:
            queryset = queryset.filter(faculty_id=faculty_id)

        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        return queryset


class AdminDepartmentDetailView(
    AdminAuditCreateUpdateMixin, generics.RetrieveUpdateDestroyAPIView
):
    """Retrieve, update, delete department."""

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = AdminDepartmentSerializer
    lookup_url_kwarg = "department_id"
    update_action = "department_updated"
    target_type = "department"

    def get_queryset(self):
        return Department.objects.select_related("faculty")


class AdminCourseListView(AdminAuditCreateUpdateMixin, generics.ListCreateAPIView):
    """List and create courses."""

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = AdminCourseSerializer
    pagination_class = StandardPagination
    create_action = "course_created"
    target_type = "course"

    def get_queryset(self):
        queryset = Course.objects.select_related("department").order_by("name")

        department_id = self.request.query_params.get("department")
        if department_id:
            queryset = queryset.filter(department_id=department_id)

        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        return queryset


class AdminCourseDetailView(
    AdminAuditCreateUpdateMixin, generics.RetrieveUpdateDestroyAPIView
):
    """Retrieve, update, delete course."""

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = AdminCourseSerializer
    lookup_url_kwarg = "course_id"
    update_action = "course_updated"
    target_type = "course"

    def get_queryset(self):
        return Course.objects.select_related("department")


class AdminUnitListView(AdminAuditCreateUpdateMixin, generics.ListCreateAPIView):
    """List and create units."""

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = AdminUnitSerializer
    pagination_class = StandardPagination
    create_action = "unit_created"
    target_type = "unit"

    def get_queryset(self):
        queryset = Unit.objects.select_related("course").order_by(
            "year_of_study", "semester", "code"
        )

        course_id = self.request.query_params.get("course")
        if course_id:
            queryset = queryset.filter(course_id=course_id)

        return queryset


class AdminUnitDetailView(
    AdminAuditCreateUpdateMixin, generics.RetrieveUpdateDestroyAPIView
):
    """Retrieve, update, delete unit."""

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = AdminUnitSerializer
    lookup_url_kwarg = "unit_id"
    update_action = "unit_updated"
    target_type = "unit"

    def get_queryset(self):
        return Unit.objects.select_related("course")


class AdminGlobalSearchView(APIView):
    """Global search across the platform."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        query = request.query_params.get("query", "").strip()
        limit = request.query_params.get("limit", 20)
        try:
            limit = int(limit)
        except (ValueError, TypeError):
            limit = 20

        results = admin_global_search(query, limit=limit)
        return Response(results)


class AdminSystemHealthView(APIView):
    """Get system health and storage metrics."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        health_data = get_system_health()
        return Response(health_data)


# ===========================================
# GAMIFICATION MANAGEMENT VIEWS
# ===========================================

class AdminBadgeListView(generics.ListCreateAPIView):
    """List and create badges for gamification."""

    permission_classes = [IsAuthenticated, IsAdmin]
    queryset = Badge.objects.all()

    def get_serializer_class(self):
        return AdminBadgeListSerializer


class AdminBadgeDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete a badge."""

    permission_classes = [IsAuthenticated, IsAdmin]
    queryset = Badge.objects.all()

    def get_serializer_class(self):
        return AdminBadgeDetailSerializer


class AdminBadgeEarnersView(APIView):
    """Get list of users who earned a specific badge."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, badge_id):
        try:
            badge = Badge.objects.get(id=badge_id)
        except Badge.DoesNotExist:
            return Response(
                {"detail": "Badge not found."}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        earners = UserBadge.objects.filter(badge=badge).select_related('user')
        
        from apps.accounts.serializers import UserSummarySerializer
        
        data = []
        for user_badge in earners:
            data.append({
                'user': UserSummarySerializer(user_badge.user).data,
                'earned_at': user_badge.earned_at,
            })
        
        return Response(data)


class AdminGamificationStatsView(APIView):
    """Get overall gamification statistics."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        from django.db.models import Sum, Count
        
        # Total points across all users
        total_points = UserStats.objects.aggregate(Sum('total_points'))['total_points__sum'] or 0
        
        # Total badges earned
        total_badges_earned = UserBadge.objects.count()
        
        # Total users with gamification
        users_with_gamification = UserStats.objects.count()
        
        # Total achievements
        total_achievements = Achievement.objects.count()
        
        # Badges by category
        badges_by_category = Badge.objects.values('category').annotate(
            count=Count('id')
        ).order_by('category')
        
        # Top performers this week
        from datetime import timedelta
        week_ago = timezone.now() - timedelta(days=7)
        
        top_uploaders = User.objects.annotate(
            upload_count=Count('uploads')
        ).filter(upload_count__gt=0).order_by('-upload_count')[:10]
        
        from apps.accounts.serializers import UserSummarySerializer
        
        return Response({
            'total_points': total_points,
            'total_badges_earned': total_badges_earned,
            'total_users_with_gamification': users_with_gamification,
            'total_achievements': total_achievements,
            'badges_by_category': list(badges_by_category),
            'top_uploaders': UserSummarySerializer(top_uploaders, many=True).data,
            'total_badges_available': Badge.objects.count(),
            'active_badges': Badge.objects.filter(is_active=True).count(),
        })


class AdminUserGamificationView(APIView):
    """Get gamification details for a specific user."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get or create user stats
        stats, _ = UserStats.objects.get_or_create(user=user)
        
        # Get earned badges
        earned_badges = UserBadge.objects.filter(user=user).select_related('badge')
        
        # Get points history
        points_history = UserPoints.objects.filter(user=user).order_by('-created_at')[:20]
        
        # Get achievements
        achievements = Achievement.objects.filter(user=user)
        
        return Response({
            'user_id': user.id,
            'total_points': stats.total_points,
            'total_uploads': stats.total_uploads,
            'total_downloads': stats.total_downloads,
            'total_ratings': stats.total_ratings,
            'total_comments': stats.total_comments,
            'consecutive_login_days': stats.consecutive_login_days,
            'earned_badges': [
                {
                    'badge_id': ub.badge.id,
                    'badge_name': ub.badge.name,
                    'badge_icon': ub.badge.icon,
                    'badge_category': ub.badge.category,
                    'earned_at': ub.earned_at,
                }
                for ub in earned_badges
            ],
            'points_history': [
                {
                    'action': ph.action,
                    'points': ph.points,
                    'description': ph.description,
                    'created_at': ph.created_at,
                }
                for ph in points_history
            ],
            'achievements': [
                {
                    'title': a.title,
                    'description': a.description,
                    'points_earned': a.points_earned,
                    'created_at': a.created_at,
                }
                for a in achievements
            ],
        })


class AdminLeaderboardView(APIView):
    """Get leaderboard rankings."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        period = request.query_params.get('period', 'all_time')
        limit = request.query_params.get('limit', 50)
        
        try:
            limit = int(limit)
        except (ValueError, TypeError):
            limit = 50
        
        valid_periods = ['daily', 'weekly', 'monthly', 'all_time']
        if period not in valid_periods:
            period = 'all_time'
        
        # Get leaderboard entries
        leaderboard = Leaderboard.objects.filter(
            period=period
        ).select_related('user').order_by('rank')[:limit]
        
        from apps.accounts.serializers import UserSummarySerializer
        
        data = []
        for entry in leaderboard:
            data.append({
                'rank': entry.rank,
                'points': entry.points,
                'user': UserSummarySerializer(entry.user).data,
                'updated_at': entry.updated_at,
            })
        
        return Response({
            'period': period,
            'entries': data,
        })


class AdminLeaderboardRefreshView(APIView):
    """Manually refresh leaderboard rankings."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request):
        from apps.gamification.services import GamificationService
        
        period = request.data.get('period', 'all_time')
        
        try:
            GamificationService.refresh_leaderboards(periods=[period])
            return Response({
                'message': f'Leaderboard for {period} refreshed successfully.',
            })
        except Exception as e:
            return Response(
                {"detail": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdminPointsConfigurationView(APIView):
    """Get points configuration for different actions."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        # Get current points configuration from UserPoints.ACTION_CHOICES
        from apps.gamification.models import UserPoints
        
        # Define default points configuration
        default_points = {
            'upload_resource': 10,
            'download_resource': 2,
            'rate_resource': 3,
            'comment_resource': 5,
            'complete_profile': 20,
            'daily_login': 5,
            'share_resource': 8,
            'report_content': 10,
            'verify_email': 15,
            'first_upload': 25,
            'first_download': 15,
            'referral': 50,
            'earn_badge': 15,
        }
        
        # Get all unique actions that have been used
        used_actions = UserPoints.objects.values_list('action', flat=True).distinct()
        
        # Get statistics for each action
        from django.db.models import Sum, Count, Avg
        action_stats = UserPoints.objects.values('action').annotate(
            total_points=Sum('points'),
            count=Count('id'),
            avg_points=Avg('points')
        ).order_by('-count')
        
        return Response({
            'default_points': default_points,
            'action_statistics': list(action_stats),
            'total_transactions': UserPoints.objects.count(),
        })


class AdminAwardPointsView(APIView):
    """Manually award points to a user."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request):
        user_id = request.data.get('user_id')
        points = request.data.get('points')
        action = request.data.get('action', 'manual_award')
        description = request.data.get('description', 'Manual points award by admin')
        
        if not user_id or not points:
            return Response(
                {"detail": "user_id and points are required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            points = int(points)
        except (ValueError, TypeError):
            return Response(
                {"detail": "points must be an integer."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get or create user stats
        stats, _ = UserStats.objects.get_or_create(user=user)
        
        # Add points
        stats.total_points += points
        stats.save()
        
        # Create points history entry
        UserPoints.objects.create(
            user=user,
            action=action,
            points=points,
            description=description,
        )
        
        # Log admin activity
        log_admin_activity(
            admin=request.user,
            action='points_awarded',
            target_type='user',
            target_id=str(user.id),
            target_title=user.email,
            metadata={'points': points, 'action': action},
        )
        
        return Response({
            'message': f'Successfully awarded {points} points to {user.email}',
            'new_total': stats.total_points,
        })


# ===========================================
# EMAIL CAMPAIGN MANAGEMENT VIEWS
# ===========================================

class AdminEmailCampaignListView(APIView):
    """List all email campaigns."""

    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        operation_id="admin_email_campaigns_list",
        tags=["Admin Email Campaigns"],
    )
    def get(self, request):
        from django.db.models import Q
        from apps.core.models import EmailCampaign
        
        # Get filter parameters
        status_filter = request.query_params.get('status')
        campaign_type = request.query_params.get('type')
        
        campaigns = EmailCampaign.objects.all()
        
        if status_filter:
            campaigns = campaigns.filter(status=status_filter)
        if campaign_type:
            campaigns = campaigns.filter(campaign_type=campaign_type)
        
        campaigns = campaigns.order_by('-created_at')[:50]
        
        data = []
        for campaign in campaigns:
            data.append({
                'id': campaign.id,
                'name': campaign.name,
                'subject': campaign.subject,
                'campaign_type': campaign.campaign_type,
                'status': campaign.status,
                'recipient_count': campaign.recipient_count,
                'sent_count': campaign.sent_count,
                'opened_count': campaign.opened_count,
                'clicked_count': campaign.clicked_count,
                'scheduled_at': campaign.scheduled_at,
                'sent_at': campaign.sent_at,
                'created_at': campaign.created_at,
            })
        
        return Response(data)


class AdminEmailCampaignCreateView(APIView):
    """Create a new email campaign."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request):
        name = request.data.get('name')
        subject = request.data.get('subject')
        body = request.data.get('body')
        campaign_type = request.data.get('campaign_type', 'general')
        
        # Target filters
        target_faculty_ids = request.data.get('target_faculties', [])
        target_department_ids = request.data.get('target_departments', [])
        target_course_ids = request.data.get('target_courses', [])
        target_year_of_study = request.data.get('target_year_of_study')
        target_user_roles = request.data.get('target_user_roles', [])
        
        # Scheduling
        scheduled_at = request.data.get('scheduled_at')
        send_now = request.data.get('send_now', False)
        
        if not name or not subject or not body:
            return Response(
                {"detail": "name, subject, and body are required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from apps.core.models import EmailCampaign
        
        # Build target filter
        target_filters = {}
        if target_faculty_ids:
            target_filters['faculty_ids'] = target_faculty_ids
        if target_department_ids:
            target_filters['department_ids'] = target_department_ids
        if target_course_ids:
            target_filters['course_ids'] = target_course_ids
        if target_year_of_study:
            target_filters['year_of_study'] = target_year_of_study
        if target_user_roles:
            target_filters['user_roles'] = target_user_roles
        
        # Count recipients
        from django.db.models import Q
        users_query = Q()
        
        if target_faculty_ids:
            users_query &= Q(faculty_id__in=target_faculty_ids)
        if target_department_ids:
            users_query &= Q(department_id__in=target_department_ids)
        if target_course_ids:
            users_query &= Q(course_id__in=target_course_ids)
        if target_year_of_study:
            users_query &= Q(year_of_study=target_year_of_study)
        if target_user_roles:
            users_query &= Q(role__in=target_user_roles)
        
        if target_filters:
            recipient_count = User.objects.filter(users_query).count()
        else:
            recipient_count = User.objects.count()
        
        # Parse scheduled_at
        from django.utils.dateparse import parse_datetime
        scheduled_at_dt = None
        if scheduled_at:
            scheduled_at_dt = parse_datetime(scheduled_at)
        
        # Create campaign
        campaign = EmailCampaign.objects.create(
            name=name,
            subject=subject,
            body=body,
            campaign_type=campaign_type,
            target_filters=target_filters,
            recipient_count=recipient_count,
            scheduled_at=scheduled_at_dt,
            status='scheduled' if scheduled_at_dt else ('sent' if send_now else 'draft'),
            created_by=request.user,
        )
        
        # Log admin activity
        log_admin_activity(
            admin=request.user,
            action='email_campaign_created',
            target_type='system',
            target_id=str(campaign.id),
            target_title=name,
            metadata={
                'recipient_count': recipient_count,
                'campaign_type': campaign_type,
            },
        )
        
        # Send now if requested
        if send_now:
            from apps.core.emails import AdminEmailService
            try:
                AdminEmailService.send_campaign_emails(campaign.id)
            except Exception as e:
                pass  # Don't fail the creation
        
        return Response({
            'id': campaign.id,
            'name': campaign.name,
            'status': campaign.status,
            'recipient_count': recipient_count,
            'message': 'Campaign created successfully.'
        }, status=status.HTTP_201_CREATED)


class AdminEmailCampaignDetailView(APIView):
    """Get details of an email campaign."""

    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        operation_id="admin_email_campaigns_retrieve",
        tags=["Admin Email Campaigns"],
    )
    def get(self, request, campaign_id):
        from apps.core.models import EmailCampaign
        
        try:
            campaign = EmailCampaign.objects.get(id=campaign_id)
        except EmailCampaign.DoesNotExist:
            return Response(
                {"detail": "Campaign not found."}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response({
            'id': campaign.id,
            'name': campaign.name,
            'subject': campaign.subject,
            'body': campaign.body,
            'campaign_type': campaign.campaign_type,
            'status': campaign.status,
            'target_filters': campaign.target_filters,
            'recipient_count': campaign.recipient_count,
            'sent_count': campaign.sent_count,
            'opened_count': campaign.opened_count,
            'clicked_count': campaign.clicked_count,
            'failed_count': campaign.failed_count,
            'scheduled_at': campaign.scheduled_at,
            'sent_at': campaign.sent_at,
            'created_at': campaign.created_at,
            'created_by': campaign.created_by.email if campaign.created_by else None,
        })


class AdminEmailCampaignSendView(APIView):
    """Send or schedule an email campaign."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, campaign_id):
        from apps.core.models import EmailCampaign
        
        try:
            campaign = EmailCampaign.objects.get(id=campaign_id)
        except EmailCampaign.DoesNotExist:
            return Response(
                {"detail": "Campaign not found."}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        if campaign.status == 'sent':
            return Response(
                {"detail": "Campaign already sent."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Schedule for later
        scheduled_at = request.data.get('scheduled_at')
        if scheduled_at:
            from django.utils.dateparse import parse_datetime
            scheduled_at_dt = parse_datetime(scheduled_at)
            campaign.scheduled_at = scheduled_at_dt
            campaign.status = 'scheduled'
            campaign.save()
            return Response({
                'message': f'Campaign scheduled for {scheduled_at}',
            })
        
        # Send now
        from apps.core.emails import AdminEmailService
        try:
            AdminEmailService.send_campaign_emails(campaign.id)
            campaign.status = 'sent'
            campaign.sent_at = timezone.now()
            campaign.save()
            
            # Log admin activity
            log_admin_activity(
                admin=request.user,
                action='email_campaign_sent',
                target_type='system',
                target_id=str(campaign.id),
                target_title=campaign.name,
            )
            
            return Response({
                'message': 'Campaign sent successfully.',
                'sent_count': campaign.sent_count,
            })
        except Exception as e:
            return Response(
                {"detail": f"Failed to send campaign: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdminEmailCampaignCancelView(APIView):
    """Cancel a scheduled email campaign."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, campaign_id):
        from apps.core.models import EmailCampaign
        
        try:
            campaign = EmailCampaign.objects.get(id=campaign_id)
        except EmailCampaign.DoesNotExist:
            return Response(
                {"detail": "Campaign not found."}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        if campaign.status not in ['draft', 'scheduled']:
            return Response(
                {"detail": "Can only cancel draft or scheduled campaigns."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        campaign.status = 'cancelled'
        campaign.save()
        
        return Response({
            'message': 'Campaign cancelled successfully.',
        })


class AdminEmailCampaignDeleteView(APIView):
    """Delete an email campaign."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def delete(self, request, campaign_id):
        from apps.core.models import EmailCampaign
        
        try:
            campaign = EmailCampaign.objects.get(id=campaign_id)
        except EmailCampaign.DoesNotExist:
            return Response(
                {"detail": "Campaign not found."}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        if campaign.status == 'sending':
            return Response(
                {"detail": "Cannot delete campaign while sending."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        campaign.delete()
        
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminEmailCampaignStatsView(APIView):
    """Get email campaign statistics."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        from apps.core.models import EmailCampaign
        from django.db.models import Sum, Avg, Count
        
        # Overall stats
        total_campaigns = EmailCampaign.objects.count()
        total_sent = EmailCampaign.objects.aggregate(
            total=Sum('sent_count')
        )['total'] or 0
        total_opened = EmailCampaign.objects.aggregate(
            total=Sum('opened_count')
        )['total'] or 0
        total_clicked = EmailCampaign.objects.aggregate(
            total=Sum('clicked_count')
        )['total'] or 0
        
        # Calculate open rate and click rate
        open_rate = (total_opened / total_sent * 100) if total_sent > 0 else 0
        click_rate = (total_clicked / total_sent * 100) if total_sent > 0 else 0
        
        # Recent campaigns
        recent_campaigns = EmailCampaign.objects.order_by('-created_at')[:10]
        
        return Response({
            'total_campaigns': total_campaigns,
            'total_sent': total_sent,
            'total_opened': total_opened,
            'total_clicked': total_clicked,
            'open_rate': round(open_rate, 2),
            'click_rate': round(click_rate, 2),
            'recent_campaigns': [
                {
                    'id': c.id,
                    'name': c.name,
                    'status': c.status,
                    'sent_count': c.sent_count,
                    'opened_count': c.opened_count,
                    'clicked_count': c.clicked_count,
                    'sent_at': c.sent_at,
                }
                for c in recent_campaigns
            ],
        })


# ===========================================
# API USAGE ANALYTICS VIEWS
# ===========================================

class AdminAPIUsageStatsView(APIView):
    """Get API usage statistics."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        from apps.core.models import APIUsageLog
        from django.db.models import Count, Avg, Max, Min
        from django.db.models.functions import TruncDate, TruncHour
        
        # Get time range
        days = request.query_params.get('days', 7)
        try:
            days = int(days)
        except (ValueError, TypeError):
            days = 7
        
        from datetime import timedelta
        since = timezone.now() - timedelta(days=days)
        
        # Total requests
        total_requests = APIUsageLog.objects.filter(created_at__gte=since).count()
        
        # Requests by status
        status_counts = APIUsageLog.objects.filter(
            created_at__gte=since
        ).values('status_code').annotate(count=Count('id'))
        
        # Average response time
        avg_response_time = APIUsageLog.objects.filter(
            created_at__gte=since
        ).aggregate(avg=Avg('response_time_ms'))['avg'] or 0
        
        # Requests over time (hourly)
        requests_over_time = APIUsageLog.objects.filter(
            created_at__gte=since
        ).annotate(
            hour=TruncHour('created_at')
        ).values('hour').annotate(count=Count('id')).order_by('hour')
        
        # Top endpoints
        top_endpoints = APIUsageLog.objects.filter(
            created_at__gte=since
        ).values('endpoint').annotate(
            count=Count('id'),
            avg_time=Avg('response_time_ms')
        ).order_by('-count')[:20]
        
        # Top users
        top_users = APIUsageLog.objects.filter(
            created_at__gte=since,
            user__isnull=False
        ).values('user__email').annotate(
            count=Count('id'),
            avg_time=Avg('response_time_ms')
        ).order_by('-count')[:10]
        
        # Error rate
        error_requests = APIUsageLog.objects.filter(
            created_at__gte=since,
            status_code__gte=400
        ).count()
        error_rate = (error_requests / total_requests * 100) if total_requests > 0 else 0
        
        return Response({
            'total_requests': total_requests,
            'average_response_time_ms': round(avg_response_time, 2),
            'error_rate': round(error_rate, 2),
            'status_distribution': list(status_counts),
            'requests_over_time': [
                {'hour': r['hour'], 'count': r['count']}
                for r in requests_over_time
            ],
            'top_endpoints': [
                {
                    'endpoint': e['endpoint'],
                    'count': e['count'],
                    'avg_time_ms': round(e['avg_time'], 2) if e['avg_time'] else 0
                }
                for e in top_endpoints
            ],
            'top_users': [
                {
                    'email': u['user__email'],
                    'count': u['count'],
                    'avg_time_ms': round(u['avg_time'], 2) if u['avg_time'] else 0
                }
                for u in top_users
            ],
        })


class AdminAPIEndpointDetailView(APIView):
    """Get detailed stats for a specific API endpoint."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        from apps.core.models import APIUsageLog
        from django.db.models import Count, Avg, Max, Min
        
        endpoint = request.query_params.get('endpoint')
        if not endpoint:
            return Response(
                {"detail": "endpoint parameter is required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get time range
        days = request.query_params.get('days', 7)
        try:
            days = int(days)
        except (ValueError, TypeError):
            days = 7
        
        from datetime import timedelta
        since = timezone.now() - timedelta(days=days)
        
        # Stats for this endpoint
        stats = APIUsageLog.objects.filter(
            created_at__gte=since,
            endpoint__icontains=endpoint
        ).aggregate(
            total_requests=Count('id'),
            avg_response_time=Avg('response_time_ms'),
            max_response_time=Max('response_time_ms'),
            min_response_time=Min('response_time_ms'),
        )
        
        # Status code distribution
        status_dist = APIUsageLog.objects.filter(
            created_at__gte=since,
            endpoint__icontains=endpoint
        ).values('status_code').annotate(count=Count('id'))
        
        # Method distribution
        method_dist = APIUsageLog.objects.filter(
            created_at__gte=since,
            endpoint__icontains=endpoint
        ).values('method').annotate(count=Count('id'))
        
        return Response({
            'endpoint_pattern': endpoint,
            'total_requests': stats['total_requests'],
            'avg_response_time_ms': round(stats['avg_response_time'], 2) if stats['avg_response_time'] else 0,
            'max_response_time_ms': stats['max_response_time'] or 0,
            'min_response_time_ms': stats['min_response_time'] or 0,
            'status_distribution': list(status_dist),
            'method_distribution': list(method_dist),
        })


class AdminAPIUsageUserView(APIView):
    """Get API usage for a specific user."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, user_id):
        from apps.core.models import APIUsageLog
        from django.db.models import Count, Avg
        
        # Get time range
        days = request.query_params.get('days', 30)
        try:
            days = int(days)
        except (ValueError, TypeError):
            days = 30
        
        from datetime import timedelta
        since = timezone.now() - timedelta(days=days)
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Usage stats
        usage = APIUsageLog.objects.filter(
            created_at__gte=since,
            user=user
        ).aggregate(
            total_requests=Count('id'),
            avg_response_time=Avg('response_time_ms'),
        )
        
        # Top endpoints
        top_endpoints = APIUsageLog.objects.filter(
            created_at__gte=since,
            user=user
        ).values('endpoint').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Recent requests
        recent_requests = APIUsageLog.objects.filter(
            created_at__gte=since,
            user=user
        ).order_by('-created_at')[:50]
        
        return Response({
            'user_id': user.id,
            'user_email': user.email,
            'total_requests': usage['total_requests'] or 0,
            'avg_response_time_ms': round(usage['avg_response_time'], 2) if usage['avg_response_time'] else 0,
            'top_endpoints': [
                {'endpoint': e['endpoint'], 'count': e['count']}
                for e in top_endpoints
            ],
            'recent_requests': [
                {
                    'endpoint': r.endpoint,
                    'method': r.method,
                    'status_code': r.status_code,
                    'response_time_ms': r.response_time_ms,
                    'created_at': r.created_at,
                }
                for r in recent_requests
            ],
        })


# AI Content Moderation Views
class AIModerationQueueView(APIView):
    """View for AI-powered content moderation queue."""
    
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def get(self, request):
        """Get resources pending AI moderation analysis."""
        from apps.core.ai_moderation import ModerationQueueService
        
        pending = ModerationQueueService.get_pending_resources()
        flagged = ModerationQueueService.get_flagged_resources()
        
        # Serialize resources
        from apps.resources.serializers import ResourceListSerializer
        
        return Response({
            'pending_count': pending.count(),
            'flagged_count': flagged.count(),
            'pending': ResourceListSerializer(pending[:20], many=True, context={'request': request}).data,
            'flagged': ResourceListSerializer(flagged[:20], many=True, context={'request': request}).data,
        })


class AIModerationAnalyzeView(APIView):
    """View for analyzing a single resource with AI moderation."""
    
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def post(self, request):
        """Analyze a resource with AI moderation."""
        from apps.core.ai_moderation import AIContentModerationService
        
        resource_id = request.data.get('resource_id')
        if not resource_id:
            return Response(
                {'error': 'resource_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        resource = get_object_or_404(Resource, id=resource_id)
        result = AIContentModerationService.analyze_resource(resource)
        
        return Response({
            'resource_id': resource.id,
            'resource_title': resource.title,
            'is_safe': result.is_safe,
            'risk_level': result.risk_level.value,
            'categories': [c.value for c in result.categories],
            'confidence_score': result.confidence_score,
            'flagged_words': result.flagged_words,
            'recommendation': result.recommendation,
            'details': result.details,
        })


class AIModerationBatchView(APIView):
    """View for batch AI moderation."""
    
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def post(self, request):
        """Run AI moderation on all pending resources."""
        from apps.core.ai_moderation import ModerationQueueService
        
        # Run auto-moderation
        results = ModerationQueueService.auto_moderate_resources()
        
        return Response({
            'message': 'Batch moderation complete',
            'auto_approved': results['auto_approved'],
            'auto_flagged': results['auto_flagged'],
            'auto_blocked': results['auto_blocked'],
            'details': results['details'][:50],  # Limit details
        })


class AIModerationStatsView(APIView):
    """View for AI moderation statistics."""
    
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def get(self, request):
        """Get AI moderation statistics."""
        from apps.core.ai_moderation import AIContentModerationService
        
        # Get all resources
        resources = Resource.objects.all()
        
        stats = AIContentModerationService.get_moderation_stats(resources)
        
        # Get additional stats
        pending_count = Resource.objects.filter(moderation_status='pending').count()
        approved_count = Resource.objects.filter(moderation_status='approved').count()
        flagged_count = Resource.objects.filter(moderation_status='flagged').count()
        blocked_count = Resource.objects.filter(moderation_status='blocked').count()
        
        return Response({
            'ai_analysis': stats,
            'moderation_status': {
                'pending': pending_count,
                'approved': approved_count,
                'flagged': flagged_count,
                'blocked': blocked_count,
            },
        })


# Predictive Analytics Views
class PredictiveEngagementView(APIView):
    """View for predictive user engagement analysis."""
    
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def get(self, request):
        """Get engagement prediction for a specific user."""
        from apps.core.predictive_analytics import PredictiveAnalyticsService
        
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response(
                {'error': 'user_id query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = PredictiveAnalyticsService.predict_user_engagement(int(user_id))
        
        return Response({
            'prediction_type': result.prediction_type,
            'score': result.score,
            'confidence': result.confidence,
            'factors': result.factors,
            'recommendation': result.recommendation,
            'details': result.details,
        })


class PredictiveChurnRiskView(APIView):
    """View for user churn risk predictions."""
    
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def get(self, request):
        """Get users at risk of churning."""
        from apps.core.predictive_analytics import PredictiveAnalyticsService
        
        churn_risks = PredictiveAnalyticsService.predict_churn_risk()
        
        return Response({
            'total_at_risk': len(churn_risks),
            'users': churn_risks[:50],
        })


class PredictiveContentTrendsView(APIView):
    """View for content trend predictions."""
    
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def get(self, request):
        """Get content trend analysis and predictions."""
        from apps.core.predictive_analytics import PredictiveAnalyticsService
        
        trends = PredictiveAnalyticsService.get_content_trends()
        
        return Response(trends)


class PredictiveSummaryView(APIView):
    """View for predictive analytics summary."""
    
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def get(self, request):
        """Get summary of all predictive analytics."""
        from apps.core.predictive_analytics import PredictiveAnalyticsService
        
        user_summary = PredictiveAnalyticsService.get_user_predictions_summary()
        resource_summary = PredictiveAnalyticsService.get_resource_predictions_summary()
        
        return Response({
            'user_predictions': user_summary,
            'resource_predictions': resource_summary,
        })


# Dashboard Builder Views
class DashboardWidgetsView(APIView):
    """View for available dashboard widgets."""
    
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def get(self, request):
        """Get available widget types and configurations."""
        from apps.admin_management.dashboard_builder import DashboardBuilderService
        
        widgets = DashboardBuilderService.get_available_widgets()
        return Response({'widgets': widgets})


class DashboardLayoutsView(APIView):
    """View for dashboard layouts."""
    
    permission_classes = [IsAuthenticated, IsAdmin]
    
    @extend_schema(
        operation_id="admin_dashboard_layouts_list",
        tags=["Admin Dashboard"]
    )
    def get(self, request):
        """Get predefined and custom dashboard layouts."""
        from apps.admin_management.dashboard_builder import DashboardBuilderService
        
        layouts = DashboardBuilderService.get_default_layouts()
        return Response({'layouts': layouts})

    @extend_schema(
        operation_id="admin_dashboard_layouts_create",
        tags=["Admin Dashboard"]
    )
    def post(self, request):
        """Create a custom dashboard layout."""
        from apps.admin_management.dashboard_builder import DashboardBuilderService
        
        name = request.data.get('name')
        widgets = request.data.get('widgets', [])
        columns = request.data.get('columns', 12)
        rows = request.data.get('rows', 12)
        
        if not name:
            return Response(
                {'error': 'name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        layout_json = DashboardBuilderService.create_custom_layout(
            name, widgets, columns, rows
        )
        
        return Response({
            'message': 'Layout created successfully',
            'layout': json.loads(layout_json),
        })


class DashboardLayoutDetailView(APIView):
    """View for a specific dashboard layout."""
    
    permission_classes = [IsAuthenticated, IsAdmin]
    
    @extend_schema(
        operation_id="admin_dashboard_layouts_retrieve",
        tags=["Admin Dashboard"]
    )
    def get(self, request, layout_id):
        """Get a specific dashboard layout."""
        from apps.admin_management.dashboard_builder import DashboardBuilderService
        
        layout_json = DashboardBuilderService.get_layout_json(layout_id)
        
        if layout_json:
            return Response({'layout': json.loads(layout_json)})
        
        return Response(
            {'error': 'Layout not found'},
            status=status.HTTP_404_NOT_FOUND
        )


# Multi-tenant Admin Views
class AdminScopeView(APIView):
    """View for admin scope and role information."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get current admin's scope and role information."""
        from apps.admin_management.multitenant import MultiTenantAdminService
        
        scope_info = MultiTenantAdminService.get_admin_scope_info(request.user)
        navigation_menu = MultiTenantAdminService.get_navigation_menu(request.user)
        
        return Response({
            'scope': scope_info,
            'navigation_menu': navigation_menu,
        })


class AdminFeatureAccessView(APIView):
    """View for checking admin feature access."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Check access to various admin features."""
        from apps.admin_management.multitenant import MultiTenantAdminService
        
        features = request.query_params.getlist('features')
        
        if not features:
            # Return all feature permissions
            all_features = [
                'manage_users', 'manage_faculties', 'manage_departments',
                'moderate_content', 'view_analytics', 'export_data',
                'system_settings', 'manage_billing'
            ]
            features = all_features
        
        permissions = {}
        for feature in features:
            permissions[feature] = MultiTenantAdminService.can_access_admin_feature(
                request.user, feature
            )
        
        return Response({'permissions': permissions})


# Report Builder Views
class ReportListView(APIView):
    """View for available reports."""
    
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def get(self, request):
        """Get list of available report types."""
        from apps.admin_management.report_builder import ReportBuilderService
        
        reports = ReportBuilderService.get_available_reports()
        return Response({'reports': reports})


class ReportGenerateView(APIView):
    """View for generating reports."""
    
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def post(self, request):
        """Generate a report with given parameters."""
        from apps.admin_management.report_builder import ReportBuilderService
        
        report_type = request.data.get('report_type')
        filters = request.data.get('filters', {})
        fields = request.data.get('fields')
        format = request.data.get('format', 'json')
        
        if not report_type:
            return Response(
                {'error': 'report_type is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = ReportBuilderService.generate_report(
            report_type, filters, fields, format
        )
        
        return Response(result)


class ReportSummaryView(APIView):
    """View for report summaries."""
    
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def get(self, request):
        """Get summary statistics for a report."""
        from apps.admin_management.report_builder import ReportBuilderService
        
        report_type = request.query_params.get('report_type')
        filters = request.query_params.dict()
        filters.pop('report_type', None)
        
        if not report_type:
            return Response(
                {'error': 'report_type query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        summary = ReportBuilderService.get_report_summary(report_type, filters)
        
        return Response({'summary': summary})


# Bulk Operations Views
class BulkResourceUpdateView(APIView):
    """View for bulk resource updates."""
    
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def post(self, request):
        """Bulk update resources."""
        from apps.admin_management.report_builder import BulkOperationsService
        
        resource_ids = request.data.get('resource_ids', [])
        updates = request.data.get('updates', {})
        
        if not resource_ids:
            return Response(
                {'error': 'resource_ids is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = BulkOperationsService.bulk_update_resources(resource_ids, updates)
        
        return Response(result)


class BulkResourceDeleteView(APIView):
    """View for bulk resource deletion."""
    
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def post(self, request):
        """Bulk delete resources."""
        from apps.admin_management.report_builder import BulkOperationsService
        
        resource_ids = request.data.get('resource_ids', [])
        soft = request.data.get('soft_delete', True)
        
        if not resource_ids:
            return Response(
                {'error': 'resource_ids is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = BulkOperationsService.bulk_delete_resources(resource_ids, soft)
        
        return Response(result)


class BulkModerationView(APIView):
    """View for bulk content moderation."""
    
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def post(self, request):
        """Bulk moderate resources."""
        from apps.admin_management.report_builder import BulkOperationsService
        
        resource_ids = request.data.get('resource_ids', [])
        action = request.data.get('action')  # approve, reject, flag
        reason = request.data.get('reason', '')
        
        if not resource_ids or not action:
            return Response(
                {'error': 'resource_ids and action are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = BulkOperationsService.bulk_moderate_resources(resource_ids, action, reason)
        
        return Response(result)


class BulkResourceUploadView(APIView):
    """
    View for admin bulk resource upload.
    
    Allows admins to upload multiple resources at once, grouped by type.
    Accepts a JSON payload with resource metadata and file URLs/content.
    """
    
    permission_classes = [IsAuthenticated, IsAdmin]
    
    parser_classes = [MultiPartParser, JSONParser]
    
    RESOURCE_TYPE_CHOICES = [
        "notes", "past_paper", "assignment", "book", "slides", "tutorial", "other"
    ]
    
    def post(self, request):
        """Bulk upload resources."""
        from apps.resources.models import Resource
        from django.utils.text import slugify
        from uuid import uuid4
        import os
        
        # Get common metadata from request
        faculty_id = request.data.get('faculty_id')
        department_id = request.data.get('department_id')
        course_id = request.data.get('course_id')
        unit_id = request.data.get('unit_id')
        semester = request.data.get('semester', '')
        year_of_study = request.data.get('year_of_study')
        
        # Get resource type - this determines which files to upload
        resource_type = request.data.get('resource_type', 'notes')
        if resource_type not in self.RESOURCE_TYPE_CHOICES:
            return Response(
                {'error': f'Invalid resource_type. Must be one of: {self.RESOURCE_TYPE_CHOICES}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get files - can be uploaded as multipart or as a list of URLs
        files = request.FILES.getlist('files')
        file_urls = request.data.get('file_urls', [])  # List of URLs to fetch
        
        # Get titles/descriptions - can be single or lists
        titles = request.data.getlist('titles') or request.data.get('titles', '')
        descriptions = request.data.getlist('descriptions') or request.data.get('descriptions', '')
        tags = request.data.get('tags', '')
        
        # If single title/description provided, apply to all
        if isinstance(titles, str):
            titles = [titles] * max(len(files), len(file_urls))
        if isinstance(descriptions, str):
            descriptions = [descriptions] * max(len(files), len(file_urls))
        
        # Validate at least one file source
        if not files and not file_urls:
            return Response(
                {'error': 'No files provided. Send files as multipart or file_urls as JSON array.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Process uploaded files
        resources_created = 0
        errors = []
        
        # Handle multipart file uploads
        for idx, uploaded_file in enumerate(files):
            try:
                title = titles[idx] if idx < len(titles) else f"{resource_type.title()} {idx + 1}"
                description = descriptions[idx] if idx < len(descriptions) else ''
                
                # Generate unique slug
                unique_id = str(uuid4())[:8]
                slug = slugify(f"{title}-{unique_id}")
                
                # Create resource
                resource = Resource.objects.create(
                    title=title,
                    slug=slug,
                    description=description,
                    resource_type=resource_type,
                    file=uploaded_file,
                    file_size=uploaded_file.size,
                    file_type=uploaded_file.content_type,
                    normalized_filename=uploaded_file.name,
                    faculty_id=faculty_id if faculty_id else None,
                    department_id=department_id if department_id else None,
                    course_id=course_id if course_id else None,
                    unit_id=unit_id if unit_id else None,
                    semester=semester,
                    year_of_study=int(year_of_study) if year_of_study else None,
                    tags=tags,
                    uploaded_by=request.user,
                    status='approved',  # Admin uploads are auto-approved
                )
                
                resources_created += 1
                
            except Exception as e:
                errors.append({'file': uploaded_file.name, 'error': str(e)})
        
        # Handle file URLs (for resources already hosted elsewhere)
        for idx, url in enumerate(file_urls):
            try:
                title = titles[idx + len(files)] if idx + len(files) < len(titles) else f"{resource_type.title()} from URL {idx + 1}"
                description = descriptions[idx + len(files)] if idx + len(files) < len(descriptions) else ''
                
                # Generate unique slug
                unique_id = str(uuid4())[:8]
                slug = slugify(f"{title}-{unique_id}")
                
                # Create resource with external URL
                resource = Resource.objects.create(
                    title=title,
                    slug=slug,
                    description=description,
                    resource_type=resource_type,
                    file=url,  # Store URL as file field
                    file_size=0,  # Unknown size for external URLs
                    file_type='external',
                    normalized_filename=url.split('/')[-1] if '/' in url else url,
                    faculty_id=faculty_id if faculty_id else None,
                    department_id=department_id if department_id else None,
                    course_id=course_id if course_id else None,
                    unit_id=unit_id if unit_id else None,
                    semester=semester,
                    year_of_study=int(year_of_study) if year_of_study else None,
                    tags=tags,
                    uploaded_by=request.user,
                    status='approved',
                )
                
                resources_created += 1
                
            except Exception as e:
                errors.append({'url': url, 'error': str(e)})
        
        result = {
            'status': 'success',
            'message': f'Successfully uploaded {resources_created} resources',
            'resource_type': resource_type,
            'resources_created': resources_created,
            'errors': errors if errors else None
        }
        
        return Response(result, status=status.HTTP_201_CREATED if resources_created > 0 else status.HTTP_400_BAD_REQUEST)


class BulkResourceByTypeView(APIView):
    """
    View for admin to upload resources by type.
    
    Accepts multiple files with a specified resource type.
    Each file becomes a separate resource with the same type.
    """
    
    permission_classes = [IsAuthenticated, IsAdmin]
    
    parser_classes = [MultiPartParser, JSONParser]
    
    def post(self, request):
        """Bulk upload resources by type."""
        from apps.resources.models import Resource
        from django.utils.text import slugify
        from uuid import uuid4
        
        # Validate resource type
        resource_type = request.data.get('resource_type', 'notes')
        valid_types = ['notes', 'past_paper', 'assignment', 'book', 'slides', 'tutorial', 'other']
        
        if resource_type not in valid_types:
            return Response(
                {'error': f'Invalid resource_type. Must be one of: {valid_types}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get common metadata
        faculty_id = request.data.get('faculty_id')
        department_id = request.data.get('department_id')
        course_id = request.data.get('course_id')
        unit_id = request.data.get('unit_id')
        semester = request.data.get('semester', '')
        year_of_study = request.data.get('year_of_study')
        tags = request.data.get('tags', '')
        description = request.data.get('description', '')
        
        # Get all uploaded files
        files = request.FILES.getlist('files')
        
        if not files:
            return Response(
                {'error': 'No files provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get optional titles (one per file)
        titles = request.data.getlist('titles')
        
        resources_created = 0
        created_resources = []
        errors = []
        
        for idx, uploaded_file in enumerate(files):
            try:
                # Use provided title or generate from filename
                if idx < len(titles):
                    title = titles[idx]
                else:
                    # Remove file extension and capitalize
                    name_without_ext = os.path.splitext(uploaded_file.name)[0]
                    title = name_without_ext.replace('_', ' ').replace('-', ' ').title()
                
                # Generate unique slug
                unique_id = str(uuid4())[:8]
                slug = slugify(f"{title}-{unique_id}")
                
                # Determine file type
                content_type = uploaded_file.content_type or 'application/octet-stream'
                
                # Create resource
                resource = Resource.objects.create(
                    title=title,
                    slug=slug,
                    description=description,
                    resource_type=resource_type,
                    file=uploaded_file,
                    file_size=uploaded_file.size,
                    file_type=content_type,
                    normalized_filename=uploaded_file.name,
                    faculty_id=faculty_id if faculty_id else None,
                    department_id=department_id if department_id else None,
                    course_id=course_id if course_id else None,
                    unit_id=unit_id if unit_id else None,
                    semester=semester,
                    year_of_study=int(year_of_study) if year_of_study else None,
                    tags=tags,
                    uploaded_by=request.user,
                    status='approved',
                )
                
                resources_created += 1
                created_resources.append({
                    'id': str(resource.id),
                    'title': resource.title,
                    'file': request.build_absolute_uri(resource.file.url) if resource.file else None
                })
                
            except Exception as e:
                errors.append({'file': uploaded_file.name, 'error': str(e)})
        
        return Response({
            'status': 'success',
            'message': f'Successfully uploaded {resources_created} {resource_type} resources',
            'resource_type': resource_type,
            'resources_created': resources_created,
            'resources': created_resources,
            'errors': errors if errors else None
        }, status=status.HTTP_201_CREATED if resources_created > 0 else status.HTTP_400_BAD_REQUEST)
