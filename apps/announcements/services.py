"""
Business logic services for announcements app.
"""

from django.utils import timezone

from apps.accounts.models import User
from apps.notifications.services import NotificationService

from .models import Announcement, AnnouncementStatus


class AnnouncementService:
    """Service for managing announcements."""

    @staticmethod
    def get_visible_announcements(user, limit=None):
        """
        Get announcements visible to a specific user.

        Args:
            user: The user to get announcements for
            limit: Optional limit

        Returns:
            QuerySet: Visible announcements
        """
        queryset = Announcement.objects.filter(status=AnnouncementStatus.PUBLISHED)

        # Filter by targeting using user academic attributes.
        from django.db.models import Q

        q = Q(
            target_faculty__isnull=True,
            target_department__isnull=True,
            target_course__isnull=True,
            target_year_of_study__isnull=True,
        )
        faculty_id = getattr(user, "faculty_id", None)
        department_id = getattr(user, "department_id", None)
        course_id = getattr(user, "course_id", None)
        year_of_study = getattr(user, "year_of_study", None)

        if faculty_id:
            q |= Q(target_faculty_id=faculty_id)
        if department_id:
            q |= Q(target_department_id=department_id)
        if course_id:
            q |= Q(target_course_id=course_id)
        if year_of_study:
            q |= Q(target_year_of_study=year_of_study)
        queryset = queryset.filter(q)

        # Order by pinned first, then by published date
        queryset = queryset.order_by("-is_pinned", "-published_at")

        if limit:
            return queryset[:limit]
        return queryset

    @staticmethod
    def get_pinned_announcements(limit=5):
        """Get pinned announcements."""
        return Announcement.objects.filter(
            status=AnnouncementStatus.PUBLISHED, is_pinned=True
        ).order_by("-published_at")[:limit]

    @staticmethod
    def get_dashboard_announcements(user, limit=5):
        """Get announcements for dashboard preview."""
        return AnnouncementService.get_visible_announcements(user, limit=limit)

    @staticmethod
    def publish_announcement(announcement):
        """Publish an announcement."""
        announcement.status = AnnouncementStatus.PUBLISHED
        if not announcement.published_at:
            announcement.published_at = timezone.now()
        announcement.save()
        recipients = AnnouncementService.get_target_recipients(announcement)
        NotificationService.notify_announcement(
            recipients=recipients,
            title=announcement.title,
            message=announcement.content,
            link=f"/announcements/{announcement.slug}/",
        )
        return announcement

    @staticmethod
    def archive_announcement(announcement):
        """Archive an announcement."""
        announcement.status = AnnouncementStatus.ARCHIVED
        announcement.save()
        return announcement

    @staticmethod
    def unpublish_announcement(announcement):
        """Unpublish an announcement (set to draft)."""
        announcement.status = AnnouncementStatus.DRAFT
        announcement.published_at = None
        announcement.save()
        return announcement

    @staticmethod
    def get_target_recipients(announcement):
        """Resolve recipients for targeted announcement delivery."""
        recipients = User.objects.filter(is_active=True, role__iexact="student")
        if announcement.target_faculty_id:
            recipients = recipients.filter(faculty_id=announcement.target_faculty_id)
        if announcement.target_department_id:
            recipients = recipients.filter(
                department_id=announcement.target_department_id
            )
        if announcement.target_course_id:
            recipients = recipients.filter(course_id=announcement.target_course_id)
        if announcement.target_year_of_study:
            recipients = recipients.filter(
                year_of_study=announcement.target_year_of_study
            )
        return recipients.distinct()
