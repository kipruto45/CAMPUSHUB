"""
Views for announcements app.
"""

from django.core.cache import cache
from rest_framework import generics, parsers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from apps.core.pagination import StandardResultsSetPagination

from .models import Announcement, AnnouncementStatus
from .serializers import (AnnouncementCreateSerializer,
                          AnnouncementDetailSerializer,
                          AnnouncementListSerializer,
                          AnnouncementUpdateSerializer)
from .services import AnnouncementService


class IsAdminOrReadOnly:
    """Permission to allow read for all, write only for admin."""

    def has_permission(self, request, view):
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return True
        return request.user and request.user.is_staff


class AnnouncementViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing announcements."""

    serializer_class = AnnouncementListSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = StandardResultsSetPagination
    lookup_field = "slug"

    def get_queryset(self):
        base_queryset = Announcement.objects.select_related(
            "created_by",
            "target_faculty",
            "target_department",
            "target_course",
        ).prefetch_related("attachments")

        if getattr(self, "swagger_fake_view", False):
            return base_queryset.none()
        user = self.request.user

        # Staff can see all announcements
        if user.is_staff:
            return base_queryset.order_by("-is_pinned", "-published_at")

        # Regular users only see published announcements
        return AnnouncementService.get_visible_announcements(user).select_related(
            "created_by",
            "target_faculty",
            "target_department",
            "target_course",
        ).prefetch_related("attachments")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AnnouncementDetailSerializer
        return AnnouncementListSerializer

    def list(self, request, *args, **kwargs):
        if request.user.is_staff:
            return super().list(request, *args, **kwargs)
        if not request.user.is_authenticated:
            return super().list(request, *args, **kwargs)

        cache_key = f"announcements:list:{request.user.id}:{request.get_full_path()}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            cache.set(cache_key, response.data, 120)
        return response

    @action(detail=False, methods=["get"])
    def pinned(self, request, *args, **kwargs):
        """Get pinned announcements."""
        cache_key = "announcements:pinned"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
        announcements = AnnouncementService.get_pinned_announcements()
        serializer = self.get_serializer(announcements, many=True)
        cache.set(cache_key, serializer.data, 300)
        return Response(serializer.data)


class AnnouncementAdminViewSet(viewsets.ModelViewSet):
    """ViewSet for managing announcements (admin only)."""

    serializer_class = AnnouncementListSerializer
    permission_classes = [IsAdminUser]
    pagination_class = StandardResultsSetPagination
    lookup_field = "slug"
    parser_classes = [
        parsers.JSONParser,
        parsers.FormParser,
        parsers.MultiPartParser,
    ]

    def get_queryset(self):
        return Announcement.objects.select_related(
            "created_by",
            "target_faculty",
            "target_department",
            "target_course",
        ).prefetch_related("attachments").order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "create":
            return AnnouncementCreateSerializer
        if self.action in ["update", "partial_update"]:
            return AnnouncementUpdateSerializer
        if self.action == "retrieve":
            return AnnouncementDetailSerializer
        return AnnouncementListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        announcement = serializer.save(created_by=request.user)
        announcement = self._sync_status_transition(
            announcement,
            previous_status=None,
        )
        headers = self.get_success_headers(serializer.data)
        response_serializer = AnnouncementDetailSerializer(
            announcement,
            context=self.get_serializer_context(),
        )
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        previous_status = instance.status
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        announcement = serializer.save()
        announcement = self._sync_status_transition(
            announcement,
            previous_status=previous_status,
        )
        response_serializer = AnnouncementDetailSerializer(
            announcement,
            context=self.get_serializer_context(),
        )
        return Response(response_serializer.data)

    def _sync_status_transition(self, announcement, previous_status):
        if announcement.status == AnnouncementStatus.PUBLISHED:
            if previous_status != AnnouncementStatus.PUBLISHED:
                return AnnouncementService.publish_announcement(announcement)
            return announcement

        if announcement.status == AnnouncementStatus.ARCHIVED:
            if previous_status != AnnouncementStatus.ARCHIVED:
                return AnnouncementService.archive_announcement(announcement)
            return announcement

        if previous_status == AnnouncementStatus.PUBLISHED:
            return AnnouncementService.unpublish_announcement(announcement)

        if announcement.status == AnnouncementStatus.DRAFT and announcement.published_at:
            announcement.published_at = None
            announcement.save(update_fields=["published_at", "updated_at"])

        return announcement

    @action(detail=True, methods=["post"])
    def publish(self, request, slug=None, *args, **kwargs):
        """Publish an announcement."""
        announcement = self.get_object()
        announcement = AnnouncementService.publish_announcement(announcement)
        return Response(AnnouncementDetailSerializer(announcement).data)

    @action(detail=True, methods=["post"])
    def archive(self, request, slug=None, *args, **kwargs):
        """Archive an announcement."""
        announcement = self.get_object()
        announcement = AnnouncementService.archive_announcement(announcement)
        return Response(AnnouncementDetailSerializer(announcement).data)

    @action(detail=True, methods=["post"])
    def unpublish(self, request, slug=None, *args, **kwargs):
        """Unpublish an announcement."""
        announcement = self.get_object()
        announcement = AnnouncementService.unpublish_announcement(announcement)
        return Response(AnnouncementDetailSerializer(announcement).data)


class DashboardAnnouncementsView(generics.ListAPIView):
    """View for dashboard announcement preview."""

    serializer_class = AnnouncementListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Announcement.objects.none()
        user = self.request.user
        return AnnouncementService.get_dashboard_announcements(
            user,
            limit=5,
        ).select_related(
            "created_by",
            "target_faculty",
            "target_department",
            "target_course",
        ).prefetch_related("attachments")

    def list(self, request, *args, **kwargs):
        cache_key = f"announcements:dashboard:{request.user.id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            cache.set(cache_key, response.data, 120)
        return response
