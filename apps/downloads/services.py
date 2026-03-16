"""
Business logic services for downloads app.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.core.storage.utils import build_storage_download_path
from apps.resources.models import Resource

from .models import Download


class DownloadService:
    """Service for handling download operations."""

    @staticmethod
    @transaction.atomic
    def download_public_resource(user, resource, request):
        """
        Handle public resource download.

        Args:
            user: The user downloading the resource
            resource: The Resource object to download
            request: The HTTP request object

        Returns:
            dict: Download result with file URL and metadata
        """
        # Verify resource is approved
        if resource.status != "approved":
            raise ValueError("Resource is not available for download")

        # Verify file exists
        if not resource.file:
            raise ValueError("File not available")

        # Get client info
        from apps.core.utils import get_client_ip, get_user_agent

        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)

        # Create download record
        download = Download.objects.create(
            user=user, resource=resource, ip_address=ip_address, user_agent=user_agent
        )

        # Increment download count
        resource.increment_download_count()

        # Update user profile if available
        if hasattr(user, "profile"):
            profile = user.profile
            profile.total_downloads = (profile.total_downloads or 0) + 1
            profile.save(update_fields=["total_downloads"])

        return {
            "download_id": str(download.id),
            "file_url": build_storage_download_path(resource.file.name, public=True),
            "file_name": resource.file.name.split("/")[-1],
            "resource_title": resource.title,
        }

    @staticmethod
    @transaction.atomic
    def download_personal_file(user, personal_file, request):
        """
        Handle personal file download.

        Args:
            user: The user downloading the file
            personal_file: The PersonalResource object to download
            request: The HTTP request object

        Returns:
            dict: Download result with file URL and metadata
        """
        # Verify ownership
        if personal_file.user != user:
            raise PermissionError("You do not have permission to download this file")

        # Verify file exists
        if not personal_file.file:
            raise ValueError("File not available")

        # Get client info
        from apps.core.utils import get_client_ip, get_user_agent

        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)

        # Create download record
        download = Download.objects.create(
            user=user,
            resource=None,
            personal_file=personal_file,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Keep profile counters synchronized.
        if hasattr(user, "profile"):
            profile = user.profile
            profile.total_downloads = (profile.total_downloads or 0) + 1
            profile.save(update_fields=["total_downloads"])

        return {
            "download_id": str(download.id),
            "file_url": build_storage_download_path(
                personal_file.file.name, public=False
            ),
            "file_name": personal_file.file.name.split("/")[-1],
        }

    @staticmethod
    def get_user_download_history(user, limit=None):
        """
        Get user's download history.

        Args:
            user: The user to get history for
            limit: Optional limit for number of records

        Returns:
            QuerySet: Download history records
        """
        queryset = Download.objects.filter(user=user).select_related("resource")

        if limit:
            return queryset[:limit]
        return queryset

    @staticmethod
    def get_user_download_stats(user):
        """
        Get download statistics for a user.

        Args:
            user: The user to get stats for

        Returns:
            dict: Download statistics
        """
        total_downloads = Download.objects.filter(user=user).count()

        unique_resources = (
            Download.objects.filter(user=user).values("resource").distinct().count()
        )

        # Downloads in last 7 days
        week_ago = timezone.now() - timedelta(days=7)
        recent_downloads = Download.objects.filter(
            user=user, created_at__gte=week_ago
        ).count()

        return {
            "total_downloads": total_downloads,
            "unique_resources": unique_resources,
            "recent_downloads": recent_downloads,
        }

    @staticmethod
    def is_resource_downloaded_by_user(user, resource):
        """
        Check if user has downloaded a specific resource.

        Args:
            user: The user to check
            resource: The resource to check

        Returns:
            bool: True if user has downloaded
        """
        return Download.objects.filter(user=user, resource=resource).exists()

    @staticmethod
    def get_most_downloaded_resources(limit=10):
        """
        Get most downloaded resources.

        Args:
            limit: Number of resources to return

        Returns:
            QuerySet: Resources ordered by download count
        """
        return Resource.objects.filter(status="approved").order_by("-download_count")[
            :limit
        ]
