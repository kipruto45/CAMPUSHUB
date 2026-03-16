"""
Business logic services for activity app.
"""

from datetime import timedelta

from django.utils import timezone

from .models import ActivityType, RecentActivity


class ActivityService:
    """Service for handling activity tracking operations."""

    @staticmethod
    def log_resource_view(user, resource, request=None):
        """
        Log a resource view activity.

        Args:
            user: The user viewing the resource
            resource: The Resource object being viewed
            request: Optional HTTP request for metadata

        Returns:
            RecentActivity: The created activity record
        """
        # Check for recent duplicate (within 5 minutes)
        recent_window = timezone.now() - timedelta(minutes=5)
        existing = RecentActivity.objects.filter(
            user=user,
            resource=resource,
            activity_type=ActivityType.VIEWED_RESOURCE,
            created_at__gte=recent_window,
        ).first()

        if existing:
            # Update timestamp instead of creating new
            existing.save()  # Updates modified timestamp
            return existing

        # Get IP if request provided
        ip_address = None
        if request:
            from apps.core.utils import get_client_ip

            ip_address = get_client_ip(request)

        return RecentActivity.objects.create(
            user=user,
            activity_type=ActivityType.VIEWED_RESOURCE,
            resource=resource,
            ip_address=ip_address,
        )

    @staticmethod
    def log_personal_file_open(user, personal_file, request=None):
        """
        Log a personal file open activity.

        Args:
            user: The user opening the file
            personal_file: The PersonalResource object
            request: Optional HTTP request for metadata

        Returns:
            RecentActivity: The created activity record
        """
        recent_window = timezone.now() - timedelta(minutes=5)
        existing = RecentActivity.objects.filter(
            user=user,
            personal_file=personal_file,
            activity_type=ActivityType.OPENED_PERSONAL_FILE,
            created_at__gte=recent_window,
        ).first()

        if existing:
            existing.save()
            return existing

        ip_address = None
        if request:
            from apps.core.utils import get_client_ip

            ip_address = get_client_ip(request)

        return RecentActivity.objects.create(
            user=user,
            activity_type=ActivityType.OPENED_PERSONAL_FILE,
            personal_file=personal_file,
            ip_address=ip_address,
        )

    @staticmethod
    def log_download(user, resource=None, personal_file=None, request=None):
        """
        Log a download activity.

        Args:
            user: The user downloading
            resource: Optional Resource being downloaded
            personal_file: Optional PersonalResource being downloaded
            request: Optional HTTP request for metadata

        Returns:
            RecentActivity: The created activity record
        """
        if resource:
            activity_type = ActivityType.DOWNLOADED_RESOURCE
        else:
            activity_type = ActivityType.DOWNLOADED_PERSONAL_FILE

        # Deduplicate accidental double-write from multiple automation hooks.
        recent_window = timezone.now() - timedelta(seconds=30)
        existing = RecentActivity.objects.filter(
            user=user,
            activity_type=activity_type,
            resource=resource,
            personal_file=personal_file,
            created_at__gte=recent_window,
        ).first()
        if existing:
            return existing

        ip_address = None
        if request:
            from apps.core.utils import get_client_ip

            ip_address = get_client_ip(request)

        return RecentActivity.objects.create(
            user=user,
            activity_type=activity_type,
            resource=resource,
            personal_file=personal_file,
            ip_address=ip_address,
        )

    @staticmethod
    def log_bookmark(user, bookmark):
        """
        Log a bookmark activity.

        Args:
            user: The user bookmarking
            bookmark: The Bookmark object

        Returns:
            RecentActivity: The created activity record
        """
        recent_window = timezone.now() - timedelta(seconds=30)
        existing = RecentActivity.objects.filter(
            user=user,
            activity_type=ActivityType.BOOKMARKED_RESOURCE,
            bookmark=bookmark,
            created_at__gte=recent_window,
        ).first()
        if existing:
            return existing

        return RecentActivity.objects.create(
            user=user,
            activity_type=ActivityType.BOOKMARKED_RESOURCE,
            bookmark=bookmark,
            resource=bookmark.resource if bookmark else None,
        )

    @staticmethod
    def get_recent_activities(user, limit=20, activity_type=None):
        """
        Get recent activities for a user.

        Args:
            user: The user to get activities for
            limit: Maximum number of activities to return
            activity_type: Optional filter by activity type

        Returns:
            QuerySet: Recent activities
        """
        queryset = RecentActivity.objects.filter(user=user)

        if activity_type:
            queryset = queryset.filter(activity_type=activity_type)

        return queryset.select_related(
            "resource", "personal_file", "bookmark", "bookmark__resource"
        )[:limit]

    @staticmethod
    def get_recent_resources(user, limit=10):
        """
        Get recently viewed resources.

        Args:
            user: The user to get activities for
            limit: Maximum number to return

        Returns:
            QuerySet: Recent resource views
        """
        return RecentActivity.objects.filter(
            user=user, activity_type=ActivityType.VIEWED_RESOURCE
        ).select_related("resource")[:limit]

    @staticmethod
    def get_recent_personal_files(user, limit=10):
        """
        Get recently opened personal files.

        Args:
            user: The user to get activities for
            limit: Maximum number to return

        Returns:
            QuerySet: Recent personal file opens
        """
        return RecentActivity.objects.filter(
            user=user, activity_type=ActivityType.OPENED_PERSONAL_FILE
        ).select_related("personal_file")[:limit]

    @staticmethod
    def get_recent_downloads(user, limit=10):
        """
        Get recently downloaded items.

        Args:
            user: The user to get activities for
            limit: Maximum number to return

        Returns:
            QuerySet: Recent downloads
        """
        return RecentActivity.objects.filter(
            user=user,
            activity_type__in=[
                ActivityType.DOWNLOADED_RESOURCE,
                ActivityType.DOWNLOADED_PERSONAL_FILE,
            ],
        ).select_related("resource", "personal_file")[:limit]

    @staticmethod
    def get_activity_stats(user):
        """
        Get activity statistics for a user.

        Args:
            user: The user to get stats for

        Returns:
            dict: Activity statistics
        """
        return {
            "total_activities": RecentActivity.objects.filter(user=user).count(),
            "viewed_count": RecentActivity.objects.filter(
                user=user, activity_type=ActivityType.VIEWED_RESOURCE
            ).count(),
            "downloaded_count": RecentActivity.objects.filter(
                user=user,
                activity_type__in=[
                    ActivityType.DOWNLOADED_RESOURCE,
                    ActivityType.DOWNLOADED_PERSONAL_FILE,
                ],
            ).count(),
            "bookmarked_count": RecentActivity.objects.filter(
                user=user, activity_type=ActivityType.BOOKMARKED_RESOURCE
            ).count(),
            "opened_files_count": RecentActivity.objects.filter(
                user=user, activity_type=ActivityType.OPENED_PERSONAL_FILE
            ).count(),
        }

    @staticmethod
    def clear_old_activities(user, days=90):
        """
        Clear old activities for a user.

        Args:
            user: The user to clear activities for
            days: Number of days to keep

        Returns:
            int: Number of deleted records
        """
        threshold = timezone.now() - timedelta(days=days)
        return RecentActivity.objects.filter(
            user=user, created_at__lt=threshold
        ).delete()[0]
