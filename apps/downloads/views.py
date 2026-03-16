"""
Views for downloads app.
"""

from rest_framework import generics, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.activity.services import ActivityService
from apps.core.pagination import StandardResultsSetPagination
from apps.core.utils import get_client_ip, get_user_agent
from apps.core.storage.utils import build_storage_download_path
from apps.resources.models import PersonalResource, Resource

from .models import Download
from .serializers import (DownloadHistorySerializer, DownloadStatsSerializer,
                          PersonalFileDownloadSerializer,
                          ResourceDownloadSerializer)


class DownloadHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing download history."""

    serializer_class = DownloadHistorySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Download.objects.none()
        return Download.objects.filter(user=self.request.user).select_related(
            "resource", "personal_file"
        )


class RecentDownloadsView(generics.ListAPIView):
    """View for recent downloads."""

    serializer_class = DownloadHistorySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Download.objects.none()
        return Download.objects.filter(user=self.request.user).select_related(
            "resource", "personal_file"
        )[:10]


class DownloadStatsView(generics.RetrieveAPIView):
    """View for download statistics."""

    permission_classes = [IsAuthenticated]
    serializer_class = DownloadStatsSerializer

    def retrieve(self, request, *args, **kwargs):
        user = request.user

        # Total downloads
        total_downloads = Download.objects.filter(user=user).count()

        # Unique resources downloaded
        unique_resources = (
            Download.objects.filter(user=user, resource__isnull=False)
            .values("resource")
            .distinct()
            .count()
        )

        # Recent downloads
        recent_downloads = Download.objects.filter(user=user).select_related(
            "resource", "personal_file"
        )[:10]

        data = {
            "total_downloads": total_downloads,
            "unique_resources": unique_resources,
            "recent_downloads": recent_downloads,
        }

        serializer = self.get_serializer(data)
        return Response(serializer.data)


class DownloadResourceView(generics.CreateAPIView):
    """Download a public resource."""

    permission_classes = [IsAuthenticated]
    serializer_class = ResourceDownloadSerializer

    def create(self, request, *args, **kwargs):
        resource_id = kwargs.get("resource_id")

        try:
            resource = Resource.objects.get(id=resource_id, status="approved")
        except Resource.DoesNotExist:
            return Response(
                {"detail": "Resource not found or not approved."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if file exists
        if not resource.file:
            return Response(
                {"detail": "File not available."}, status=status.HTTP_404_NOT_FOUND
            )

        # Create download record
        download = Download.objects.create(
            user=request.user,
            resource=resource,
            personal_file=None,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )

        # Increment download count
        resource.increment_download_count()

        # Update user profile total downloads if available
        if hasattr(request.user, "profile"):
            profile = request.user.profile
            profile.total_downloads = (profile.total_downloads or 0) + 1
            profile.save(update_fields=["total_downloads"])

        # Track recent activity feed entry.
        ActivityService.log_download(
            user=request.user,
            resource=resource,
            request=request,
        )

        # Build file URL
        file_url = request.build_absolute_uri(
            build_storage_download_path(resource.file.name, public=True)
        )

        return Response(
            {
                "download_id": str(download.id),
                "file_url": file_url,
                "resource_title": resource.title,
                "file_name": resource.file.name.split("/")[-1],
                "message": "Download recorded successfully.",
            }
        )


class DownloadPersonalFileView(generics.CreateAPIView):
    """Download a personal file from user's library."""

    permission_classes = [IsAuthenticated]
    serializer_class = PersonalFileDownloadSerializer

    def create(self, request, *args, **kwargs):
        file_id = kwargs.get("file_id")

        try:
            personal_file = PersonalResource.objects.get(id=file_id, user=request.user)
        except PersonalResource.DoesNotExist:
            return Response(
                {"detail": "Personal file not found or access denied."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if file exists
        if not personal_file.file:
            return Response(
                {"detail": "File not available."}, status=status.HTTP_404_NOT_FOUND
            )

        # Create download record for personal file
        download = Download.objects.create(
            user=request.user,
            resource=None,
            personal_file=personal_file,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )

        if hasattr(request.user, "profile"):
            profile = request.user.profile
            profile.total_downloads = (profile.total_downloads or 0) + 1
            profile.save(update_fields=["total_downloads"])

        ActivityService.log_download(
            user=request.user,
            personal_file=personal_file,
            request=request,
        )

        # Build file URL
        file_url = request.build_absolute_uri(
            build_storage_download_path(personal_file.file.name, public=False)
        )

        return Response(
            {
                "download_id": str(download.id),
                "file_url": file_url,
                "file_name": personal_file.file.name.split("/")[-1],
                "message": "Download recorded successfully.",
            }
        )


class ResourceDownloadCountView(generics.RetrieveAPIView):
    """Get download count for a resource."""

    permission_classes = [IsAuthenticated]

    def retrieve(self, request, *args, **kwargs):
        resource_id = kwargs.get("resource_id")

        try:
            resource = Resource.objects.get(id=resource_id)
        except Resource.DoesNotExist:
            return Response(
                {"detail": "Resource not found."}, status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            {
                "resource_id": str(resource.id),
                "download_count": resource.download_count,
                "view_count": resource.view_count,
            }
        )


class UserDownloadCheckView(generics.RetrieveAPIView):
    """Check if user has downloaded a resource."""

    permission_classes = [IsAuthenticated]

    def retrieve(self, request, *args, **kwargs):
        resource_id = kwargs.get("resource_id")

        try:
            resource = Resource.objects.get(id=resource_id)
        except Resource.DoesNotExist:
            return Response(
                {"detail": "Resource not found."}, status=status.HTTP_404_NOT_FOUND
            )

        has_downloaded = Download.objects.filter(
            user=request.user, resource=resource
        ).exists()

        return Response(
            {
                "resource_id": str(resource.id),
                "has_downloaded": has_downloaded,
            }
        )
