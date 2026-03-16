"""
Services for the Dashboard API.

This module contains business logic for aggregating data from multiple
apps to provide a comprehensive dashboard view.
"""

from apps.accounts.models import User
from apps.accounts.services import ProfileCompletionService
from apps.bookmarks.models import Bookmark
from apps.bookmarks.services import BookmarkService
from apps.downloads.models import Download
from apps.notifications.models import Notification
from apps.resources.models import PersonalResource, Resource, UserStorage


class DashboardService:
    """Service for aggregating dashboard data."""

    def __init__(self, user: User):
        self.user = user

    def get_dashboard_data(self) -> dict:
        """
        Get complete dashboard data for a user.

        Returns:
            dict: Complete dashboard data including user summary, stats, etc.
        """
        return {
            "user_summary": self._get_user_summary(),
            "quick_stats": self._get_quick_stats(),
            "recent_activity": self._get_recent_activity(),
            "recommendations": self._get_recommendations(),
            "announcements": self._get_announcements(),
            "pending_uploads": self._get_pending_uploads(),
            "notifications": self._get_notification_summary(),
        }

    def _get_user_summary(self) -> dict:
        """Get user summary including profile completion."""
        completion = ProfileCompletionService.calculate_completion(self.user)
        completion_percent = completion["percentage"]
        is_complete = completion["is_complete"]

        # Get user's course info if available
        course_name = None
        year_of_study = None

        if self.user.course:
            course_name = self.user.course.name

        if self.user.year_of_study:
            year_of_study = self.user.year_of_study

        from apps.accounts.serializers import UserSummarySerializer

        user_data = UserSummarySerializer(self.user).data

        return {
            "user": user_data,
            "profile_completion": completion_percent,
            "is_profile_complete": is_complete,
            "academic_info": {
                "faculty": self.user.faculty.name if self.user.faculty else None,
                "department": (
                    self.user.department.name if self.user.department else None
                ),
                "course": course_name,
                "year_of_study": year_of_study,
                "semester": self.user.semester,
            },
        }

    def _get_quick_stats(self) -> dict:
        """Get quick statistics for the user."""
        # Get storage info
        storage, _ = UserStorage.objects.get_or_create(user=self.user)
        storage_used_mb = storage.used_storage / (1024 * 1024)  # Convert bytes to MB
        storage_limit_mb = storage.storage_limit / (1024 * 1024)
        storage_percent = (
            (storage_used_mb / storage_limit_mb * 100) if storage_limit_mb > 0 else 0
        )

        return {
            "bookmarks_count": BookmarkService.get_user_bookmarks(self.user).count(),
            "personal_files_count": PersonalResource.objects.filter(
                user=self.user
            ).count(),
            "uploads_count": Resource.objects.filter(uploaded_by=self.user).count(),
            "downloads_count": Download.objects.filter(user=self.user).count(),
            "storage_used_mb": round(storage_used_mb, 2),
            "storage_limit_mb": round(storage_limit_mb, 2),
            "storage_percent_used": round(storage_percent, 2),
        }

    def _get_recent_activity(self) -> dict:
        """Get recent activity across different actions."""
        # Recent uploads (last 5)
        recent_uploads = Resource.objects.filter(uploaded_by=self.user).order_by(
            "-created_at"
        )[:5]

        # Recent downloads (last 5)
        recent_downloads = (
            Download.objects.filter(user=self.user)
            .select_related("resource")
            .order_by("-created_at")[:5]
        )

        # Recent bookmarks (last 5)
        recent_bookmarks = BookmarkService.get_recent_bookmarks(self.user, limit=5)

        return {
            "recent_uploads": [
                self._format_resource_activity(item, "upload")
                for item in recent_uploads
            ],
            "recent_downloads": [
                self._format_download_activity(item) for item in recent_downloads
            ],
            "recent_bookmarks": [
                self._format_bookmark_activity(item) for item in recent_bookmarks
            ],
        }

    def _format_resource_activity(self, resource: Resource, activity_type: str) -> dict:
        """Format a resource for activity display."""
        return {
            "id": resource.id,
            "type": activity_type,
            "title": resource.title,
            "description": (
                resource.description[:100] + "..."
                if resource.description and len(resource.description) > 100
                else resource.description or ""
            ),
            "timestamp": resource.created_at,
            "url": f"/resources/{resource.id}/",
            "status": resource.status,
        }

    def _format_download_activity(self, download: Download) -> dict:
        """Format a download for activity display."""
        title = (
            download.resource.title
            if download.resource
            else download.personal_file.title if download.personal_file else "Download"
        )
        url = (
            f"/resources/{download.resource.id}/" if download.resource else "/library/"
        )
        file_type = (
            download.resource.file_type
            if download.resource
            else download.personal_file.file_type if download.personal_file else "file"
        )
        return {
            "id": download.id,
            "type": "download",
            "title": title,
            "description": f"Downloaded {file_type} file",
            "timestamp": download.created_at,
            "url": url,
        }

    def _format_bookmark_activity(self, bookmark: Bookmark) -> dict:
        """Format a bookmark for activity display."""
        return {
            "id": bookmark.id,
            "type": "bookmark",
            "title": bookmark.resource.title,
            "description": f"Bookmarked {bookmark.resource.file_type} file",
            "timestamp": bookmark.created_at,
            "url": f"/resources/{bookmark.resource.id}/",
        }

    def _get_recommendations(self) -> dict:
        """Get personalized recommendations."""
        from apps.recommendations.services import (
            get_course_based_recommendations, get_for_you_recommendations,
            get_trending_resources)

        for_you = get_for_you_recommendations(self.user, limit=5)
        trending = get_trending_resources(limit=5)
        course_related = get_course_based_recommendations(self.user, limit=5)
        recently_added = (
            Resource.objects.filter(
                status="approved",
                is_public=True,
            )
            .exclude(uploaded_by=self.user)
            .order_by("-created_at")[:5]
        )

        return {
            "for_you": [self._format_recommendation(item) for item in for_you],
            "trending": [self._format_recommendation(item) for item in trending],
            "course_related": [
                self._format_recommendation(item) for item in course_related
            ],
            "recently_added": [
                self._format_recommendation(item) for item in recently_added
            ],
        }

    def _format_recommendation(self, resource: Resource) -> dict:
        """Format a resource for recommendations."""
        return {
            "id": resource.id,
            "title": resource.title,
            "description": (
                resource.description[:100] + "..."
                if resource.description and len(resource.description) > 100
                else resource.description or ""
            ),
            "file_type": resource.file_type,
            "file_size": resource.file_size,
            "download_count": resource.download_count,
            "average_rating": resource.average_rating,
            "uploaded_by": resource.uploaded_by.get_full_name()
            or resource.uploaded_by.email,
            "course_name": resource.course.name if resource.course else None,
            "url": f"/resources/{resource.id}/",
        }

    def _get_announcements(self) -> list:
        """Get latest visible announcements for dashboard."""
        from apps.announcements.services import AnnouncementService

        announcements = AnnouncementService.get_dashboard_announcements(
            self.user, limit=5
        )
        return [
            {
                "id": announcement.id,
                "title": announcement.title,
                "message": announcement.content,
                "type": announcement.announcement_type,
                "created_at": announcement.published_at or announcement.created_at,
                "is_active": announcement.status == "published",
            }
            for announcement in announcements
        ]

    def _get_pending_uploads(self) -> dict:
        """Get pending and rejected uploads."""
        pending_approval = Resource.objects.filter(
            uploaded_by=self.user, status="pending"
        ).order_by("-created_at")[:5]

        rejected = Resource.objects.filter(
            uploaded_by=self.user, status="rejected"
        ).order_by("-created_at")[:5]

        return {
            "pending_approval": [
                {
                    "id": r.id,
                    "title": r.title,
                    "description": r.description,
                    "file_type": r.file_type,
                    "course_name": r.course.name if r.course else None,
                    "uploaded_at": r.created_at,
                    "status": r.status,
                }
                for r in pending_approval
            ],
            "rejected": [
                {
                    "id": r.id,
                    "title": r.title,
                    "description": r.description,
                    "file_type": r.file_type,
                    "course_name": r.course.name if r.course else None,
                    "uploaded_at": r.created_at,
                    "status": r.status,
                    "rejection_reason": getattr(r, "rejection_reason", None),
                }
                for r in rejected
            ],
            "total_pending": Resource.objects.filter(
                uploaded_by=self.user, status="pending"
            ).count(),
            "total_rejected": Resource.objects.filter(
                uploaded_by=self.user, status="rejected"
            ).count(),
        }

    def _get_notification_summary(self) -> dict:
        """Get notification summary."""
        unread_count = Notification.objects.filter(
            recipient=self.user, is_read=False
        ).count()

        recent = Notification.objects.filter(recipient=self.user).order_by(
            "-created_at"
        )[:5]

        recent_notifications = [
            {
                "id": n.id,
                "title": n.title,
                "message": (
                    n.message[:100] + "..." if len(n.message) > 100 else n.message
                ),
                "type": n.notification_type,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
            }
            for n in recent
        ]

        return {
            "unread_count": unread_count,
            "recent_notifications": recent_notifications,
        }


class DashboardQuickStatsService:
    """Service specifically for quick stats endpoint."""

    def __init__(self, user: User):
        self.user = user

    def get_stats(self) -> dict:
        """Get quick stats for the user."""
        storage, _ = UserStorage.objects.get_or_create(user=self.user)
        storage_used_mb = storage.used_storage / (1024 * 1024)
        storage_limit_mb = storage.storage_limit / (1024 * 1024)
        storage_percent = (
            (storage_used_mb / storage_limit_mb * 100) if storage_limit_mb > 0 else 0
        )

        return {
            "bookmarks_count": BookmarkService.get_user_bookmarks(self.user).count(),
            "personal_files_count": PersonalResource.objects.filter(
                user=self.user
            ).count(),
            "uploads_count": Resource.objects.filter(uploaded_by=self.user).count(),
            "downloads_count": Download.objects.filter(user=self.user).count(),
            "storage_used_mb": round(storage_used_mb, 2),
            "storage_limit_mb": round(storage_limit_mb, 2),
            "storage_percent_used": round(storage_percent, 2),
        }
