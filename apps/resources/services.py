"""
Services for resource details module.
"""

import math

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q, Sum, Value
from django.utils import timezone

from apps.accounts.models import Profile, UserActivity
from apps.activity.models import ActivityType, RecentActivity
from apps.bookmarks.models import Bookmark
from apps.downloads.models import Download
from apps.notifications.services import NotificationService
from apps.resources.models import CourseProgress, Resource, ResourceShareEvent

from .automations import suggest_tags
from .validators import (normalize_tags, normalize_title,
                         validate_academic_relationships,
                         validate_duplicate_upload, validate_upload_file)


def calculate_auto_rating(
    resource: Resource,
    ratings_count: int | None = None,
    likes_count: int | None = None,
    view_count: int | None = None,
    download_count: int | None = None,
) -> float:
    """
    Compute an automatic rating based on engagement signals.

    Signals used: views, downloads, likes, and average rating.
    Returns a value between 0 and 5 (rounded to 2 decimals).
    """

    def normalize_count(count: int, scale: int) -> float:
        if count <= 0:
            return 0.0
        # Log scaling keeps large counts from dominating.
        return min(1.0, math.log10(count + 1) / math.log10(scale + 1))

    avg_rating = float(getattr(resource, "average_rating", 0) or 0)
    ratings_count = ratings_count if ratings_count is not None else getattr(resource, "ratings_count", None)
    if ratings_count is None:
        try:
            ratings_count = resource.ratings.count()
        except Exception:
            ratings_count = 0
    ratings_count = int(ratings_count or 0)

    likes_count = likes_count if likes_count is not None else getattr(resource, "likes_count", None)
    if likes_count is None:
        try:
            likes_count = resource.favorites.count()
        except Exception:
            likes_count = 0
    likes_count = int(likes_count or 0)

    view_count = int(view_count if view_count is not None else getattr(resource, "view_count", 0) or 0)
    download_count = int(download_count if download_count is not None else getattr(resource, "download_count", 0) or 0)

    rating_strength = min(1.0, ratings_count / 10.0)
    rating_score = (avg_rating / 5.0) * (0.4 + 0.6 * rating_strength)

    view_score = normalize_count(view_count, 1500)
    download_score = normalize_count(download_count, 400)
    like_score = normalize_count(likes_count, 200)

    engagement_score = (0.45 * download_score) + (0.35 * view_score) + (0.20 * like_score)
    combined = (0.6 * rating_score) + (0.4 * engagement_score)

    return round(max(0.0, min(5.0, combined * 5.0)), 2)


class CourseProgressService:
    """Derive and sync course progress from real student usage."""

    IN_PROGRESS_PERCENTAGE = 50

    @staticmethod
    def _should_track(user) -> bool:
        return bool(
            user
            and getattr(user, "is_authenticated", False)
            and getattr(user, "is_student", False)
        )

    @classmethod
    def get_relevant_resources_queryset(cls, user, course):
        """Return course resources relevant to the student's profile."""
        queryset = Resource.objects.filter(course=course, status="approved", is_deleted=False)

        year_of_study = getattr(user, "year_of_study", None)
        if year_of_study not in (None, ""):
            queryset = queryset.filter(
                Q(year_of_study=year_of_study) | Q(year_of_study__isnull=True)
            )

        semester = getattr(user, "semester", None)
        if semester not in (None, "", 0):
            queryset = queryset.filter(Q(semester=str(semester)) | Q(semester=""))

        return queryset

    @classmethod
    def sync_resource_view(cls, user, resource):
        """Mark a resource as in progress when a student views it."""
        if not cls._should_track(user) or not getattr(resource, "course_id", None):
            return None

        progress, _ = CourseProgress.objects.get_or_create(
            user=user,
            course_id=resource.course_id,
            resource=resource,
            defaults={"status": "not_started"},
        )

        now = timezone.now()
        update_fields = ["last_accessed", "updated_at"]
        progress.last_accessed = now

        if progress.status != "completed":
            if progress.status != "in_progress":
                progress.status = "in_progress"
                update_fields.append("status")
            if progress.completion_percentage < cls.IN_PROGRESS_PERCENTAGE:
                progress.completion_percentage = cls.IN_PROGRESS_PERCENTAGE
                update_fields.append("completion_percentage")

        progress.save(update_fields=list(dict.fromkeys(update_fields)))
        return progress

    @classmethod
    def sync_resource_completion(cls, user, resource):
        """Mark a resource as completed when a student downloads it."""
        if not cls._should_track(user) or not getattr(resource, "course_id", None):
            return None

        progress, _ = CourseProgress.objects.get_or_create(
            user=user,
            course_id=resource.course_id,
            resource=resource,
            defaults={"status": "not_started"},
        )
        progress.mark_completed()
        return progress

    @classmethod
    def build_course_summary(cls, user, course) -> dict:
        """Build a progress summary using stored progress plus actual usage."""
        resources = list(
            cls.get_relevant_resources_queryset(user, course).only(
                "id", "course_id", "year_of_study", "semester"
            )
        )
        resource_ids = [resource.id for resource in resources]

        progress_records = {
            record.resource_id: record
            for record in CourseProgress.objects.filter(
                user=user,
                course=course,
                resource_id__in=resource_ids,
            )
        }
        downloaded_ids = set(
            Download.objects.filter(
                user=user,
                resource_id__in=resource_ids,
            ).values_list("resource_id", flat=True)
        )
        viewed_ids = set(
            RecentActivity.objects.filter(
                user=user,
                activity_type=ActivityType.VIEWED_RESOURCE,
                resource_id__in=resource_ids,
            ).values_list("resource_id", flat=True)
        )

        completed_resources = 0
        in_progress_resources = 0
        completion_points = 0

        for resource_id in resource_ids:
            progress = progress_records.get(resource_id)

            if resource_id in downloaded_ids or (
                progress and progress.status == "completed"
            ):
                completed_resources += 1
                completion_points += 100
                continue

            inferred_progress = 0
            if progress and progress.status == "in_progress":
                in_progress_resources += 1
                inferred_progress = max(
                    int(progress.completion_percentage or 0),
                    cls.IN_PROGRESS_PERCENTAGE,
                )
            elif progress and int(progress.completion_percentage or 0) > 0:
                in_progress_resources += 1
                inferred_progress = max(
                    int(progress.completion_percentage or 0),
                    cls.IN_PROGRESS_PERCENTAGE,
                )
            elif resource_id in viewed_ids:
                in_progress_resources += 1
                inferred_progress = cls.IN_PROGRESS_PERCENTAGE

            completion_points += min(max(inferred_progress, 0), 100)

        total_resources = len(resource_ids)
        overall_percentage = (
            round(completion_points / total_resources, 1) if total_resources > 0 else 0
        )

        return {
            "course_id": str(course.id),
            "course_name": course.name,
            "total_resources": total_resources,
            "completed_resources": completed_resources,
            "in_progress_resources": in_progress_resources,
            "not_started_resources": max(
                total_resources - completed_resources - in_progress_resources, 0
            ),
            "overall_percentage": overall_percentage,
            "time_spent_minutes": sum(
                int(record.time_spent_minutes or 0)
                for record in progress_records.values()
            ),
        }


class ResourceDetailService:
    """Service for resource detail operations."""

    def __init__(self, resource: Resource, user=None, request=None):
        self.resource = resource
        self.user = user
        self.request = request

    def get_user_specific_data(self) -> dict:
        """Get user-specific data for the resource."""
        data = {
            "is_bookmarked": False,
            "is_favorited": False,
            "is_in_my_library": False,
            "user_rating": None,
            "can_edit": False,
            "can_delete": False,
            "can_download": False,
        }

        if not self.user or not self.user.is_authenticated:
            # Anonymous users can only download approved public resources
            data["can_download"] = (
                self.resource.status == "approved" and self.resource.is_public
            )
            return data

        # Check bookmark status
        data["is_bookmarked"] = Bookmark.objects.filter(
            user=self.user, resource=self.resource
        ).exists()

        from apps.favorites.models import Favorite, FavoriteType

        data["is_favorited"] = Favorite.objects.filter(
            user=self.user,
            favorite_type=FavoriteType.RESOURCE,
            resource=self.resource,
        ).exists()

        # Check if already saved to personal library
        from apps.resources.models import FolderItem, PersonalResource

        data["is_in_my_library"] = (
            PersonalResource.objects.filter(
                user=self.user,
                linked_public_resource=self.resource,
            ).exists()
            or FolderItem.objects.filter(
                folder__user=self.user,
                resource=self.resource,
            ).exists()
        )

        # Check user rating
        from apps.ratings.models import Rating

        rating = Rating.objects.filter(user=self.user, resource=self.resource).first()
        if rating:
            data["user_rating"] = rating.value

        # Check edit/delete permissions
        data["can_edit"] = (
            self.resource.uploaded_by == self.user
            or self.user.is_admin
            or self.user.is_moderator
        )
        data["can_delete"] = data["can_edit"]

        # Check download permission
        data["can_download"] = (
            self.resource.status == "approved"
            or self.resource.uploaded_by == self.user
            or self.user.is_admin
            or self.user.is_moderator
        )

        return data

    def track_view(self):
        """Track resource view."""
        self.resource.increment_view_count()

        # Track recent view if user is authenticated
        if self.user and self.user.is_authenticated:
            from apps.activity.services import ActivityService

            ActivityService.log_resource_view(
                user=self.user,
                resource=self.resource,
                request=self.request,
            )
            CourseProgressService.sync_resource_view(self.user, self.resource)

    def get_related_resources(self, limit: int = 10) -> list:
        """Get related resources based on course, unit, tags, and type."""
        queryset = Resource.objects.filter(status="approved", is_deleted=False).exclude(
            id=self.resource.id
        )

        # Start with base scoring
        related = []

        # Get resources from same course
        if self.resource.course:
            course_resources = list(
                queryset.filter(course=self.resource.course).annotate(
                    relevance_score=Value(3)  # High score for same course
                )[:20]
            )
            related.extend(course_resources)

        # Get resources from same unit
        if self.resource.unit:
            unit_resources = list(
                queryset.filter(unit=self.resource.unit).annotate(
                    relevance_score=Value(4)  # Higher score for same unit
                )[:20]
            )
            related.extend(unit_resources)

        # Get resources with overlapping tags
        if self.resource.tags:
            resource_tags = set(self.resource.get_tags_list())
            if resource_tags:
                for res in queryset.exclude(tags=""):
                    res_tags = set(res.get_tags_list())
                    if res_tags & resource_tags:  # Has common tags
                        common_count = len(res_tags & resource_tags)
                        res.relevance_score = common_count * 2
                        related.append(res)

        # Get resources of same type
        type_resources = list(
            queryset.filter(resource_type=self.resource.resource_type).annotate(
                relevance_score=Value(1)
            )[:20]
        )
        related.extend(type_resources)

        # Remove duplicates and sort by relevance
        seen = set()
        unique_related = []
        for res in related:
            if res.id not in seen:
                seen.add(res.id)
                # Add fallback score if not set
                if not hasattr(res, "relevance_score"):
                    res.relevance_score = 0
                unique_related.append(res)

        # Sort by relevance score, then by popularity
        unique_related.sort(
            key=lambda x: (x.relevance_score, x.download_count, x.view_count),
            reverse=True,
        )

        return unique_related[:limit]


class ResourceShareService:
    """Service for resource sharing workflows."""

    DEFAULT_SHARE_BASE_URL = "https://campushub.app"

    def __init__(self, resource: Resource, user=None, request=None):
        self.resource = resource
        self.user = user
        self.request = request

    @staticmethod
    def can_share(resource: Resource, user=None) -> tuple[bool, str | None]:
        """Check if a resource can be shared publicly."""
        if not resource:
            return False, "Resource not found."
        if resource.status != "approved":
            return False, "Only approved resources can be shared."
        if not resource.is_public:
            return False, "Private resources cannot be shared."
        if bool(getattr(resource, "is_deleted", False)):
            return False, "Deleted resources cannot be shared."
        if getattr(resource, "deleted_at", None):
            return False, "Deleted resources cannot be shared."
        if bool(getattr(resource, "is_hidden", False)):
            return False, "Hidden resources cannot be shared."
        return True, None

    def _get_share_base_url(self) -> str:
        if self.request is not None:
            try:
                return self.request.build_absolute_uri("/").rstrip("/")
            except Exception:
                # Fall back to settings-based resolution.
                pass
        configured = (
            getattr(settings, "RESOURCE_SHARE_BASE_URL", "")
            or getattr(settings, "FRONTEND_BASE_URL", "")
            or getattr(settings, "WEB_APP_URL", "")
            or self.DEFAULT_SHARE_BASE_URL
        )
        return str(configured).rstrip("/")

    def build_share_url(self, resource: Resource | None = None) -> str:
        """Build public web URL for a resource."""
        target = resource or self.resource
        return f"{self._get_share_base_url()}/resources/{target.slug}"

    def build_deep_link(self, resource: Resource | None = None) -> str:
        """Build deep link URL used by the mobile app router."""
        target = resource or self.resource
        scheme = str(getattr(settings, "MOBILE_DEEPLINK_SCHEME", "campushub")).strip()
        if not scheme:
            scheme = "campushub"
        # Mobile expects paths like campushub://resource/<slug>
        return f"{scheme}://resource/{target.slug}"

    @staticmethod
    def _build_metadata_summary(resource: Resource) -> str:
        parts: list[str] = []
        unit_code = getattr(resource.unit, "code", None)
        course_code = getattr(resource.course, "code", None)
        if unit_code:
            parts.append(str(unit_code))
        elif course_code:
            parts.append(str(course_code))
        parts.append(resource.get_resource_type_display())
        return " | ".join([part for part in parts if part])

    def build_share_message(self, resource: Resource | None = None) -> str:
        """Build polished share message payload."""
        target = resource or self.resource
        share_url = self.build_share_url(target)
        summary = self._build_metadata_summary(target)
        lines = [
            "Check out this resource on CampusHub:",
            "",
            target.title,
        ]
        if summary:
            lines.append(summary)
        lines.extend(["", "Open here:", share_url])
        return "\n".join(lines)

    def get_share_payload(self) -> dict:
        """Return full share payload consumed by API clients."""
        can_share, error = self.can_share(self.resource, self.user)
        if not can_share:
            return {
                "resource_id": self.resource.id,
                "title": self.resource.title,
                "slug": self.resource.slug,
                "share_url": "",
                "deep_link_url": self.build_deep_link(self.resource),
                "share_message": "",
                "metadata_summary": self._build_metadata_summary(self.resource),
                "can_share": False,
                "reason": error,
            }

        share_url = self.build_share_url(self.resource)
        return {
            "resource_id": self.resource.id,
            "title": self.resource.title,
            "slug": self.resource.slug,
            "share_url": share_url,
            "deep_link_url": self.build_deep_link(self.resource),
            "share_message": self.build_share_message(self.resource),
            "metadata_summary": self._build_metadata_summary(self.resource),
            "can_share": True,
        }

    @transaction.atomic
    def record_share(self, method: str = ResourceShareEvent.ShareMethod.OTHER, request=None):
        """Record share analytics and increment aggregate share count."""
        can_share, error = self.can_share(self.resource, self.user)
        if not can_share:
            raise ValidationError({"detail": error})

        resolved_method = method or ResourceShareEvent.ShareMethod.OTHER
        valid_methods = {choice[0] for choice in ResourceShareEvent.ShareMethod.choices}
        if resolved_method not in valid_methods:
            resolved_method = ResourceShareEvent.ShareMethod.OTHER

        Resource.objects.filter(id=self.resource.id).update(share_count=F("share_count") + 1)
        self.resource.refresh_from_db(fields=["share_count"])

        event_user = (
            self.user
            if self.user is not None and getattr(self.user, "is_authenticated", False)
            else None
        )
        ResourceShareEvent.objects.create(
            resource=self.resource,
            user=event_user,
            share_method=resolved_method,
            ip_address=self._get_client_ip(request) if request else None,
            device_info=(request.META.get("HTTP_USER_AGENT", "")[:500] if request else ""),
        )

        return {
            "success": True,
            "message": "Resource share recorded successfully.",
            "share_count": self.resource.share_count,
        }

    @staticmethod
    def _get_client_ip(request) -> str | None:
        """Get best-effort client IP from request headers."""
        if not request:
            return None
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")


class ResourceDownloadService:
    """Service for resource download operations."""

    def __init__(self, resource: Resource, user=None):
        self.resource = resource
        self.user = user

    def can_download(self) -> tuple:
        """
        Check if user can download the resource.

        Returns:
            tuple: (can_download: bool, error_message: str or None)
        """
        if not self.user or not self.user.is_authenticated:
            if self.resource.status != "approved":
                return False, "Resource is not available for download."
            if not self.resource.is_public:
                return False, "Resource is not public."
            return True, None

        # Authenticated user
        if self.resource.status == "approved":
            return True, None

        # Owner or staff can download
        if self.resource.uploaded_by == self.user:
            return True, None

        if self.user.is_admin or self.user.is_moderator:
            return True, None

        return False, "Resource is not available for download."

    def record_download(self, request) -> bool:
        """Record a download action."""
        can_download, error = self.can_download()
        if not can_download:
            return False

        # Increment download count
        self.resource.increment_download_count()

        # Record download in downloads table
        if self.user and self.user.is_authenticated:
            Download.objects.create(
                user=self.user,
                resource=self.resource,
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
            )

        return True

    def _get_client_ip(self, request) -> str:
        """Get client IP from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")


class ResourceBookmarkService:
    """Service for resource bookmark operations."""

    def __init__(self, resource: Resource, user):
        self.resource = resource
        self.user = user

    def toggle_bookmark(self) -> dict:
        """
        Toggle bookmark status for the resource.

        Returns:
            dict: {'is_bookmarked': bool, 'message': str}
        """
        from apps.bookmarks.services import BookmarkService

        return BookmarkService.toggle_bookmark(self.user, self.resource)

    def add_to_library(self, folder_id=None) -> dict:
        """
        Add resource to user's library.

        Returns:
            dict: {'success': bool, 'message': str}
        """
        from apps.resources.models import Folder, FolderItem

        # Get or create default library folder
        if folder_id:
            try:
                folder = Folder.objects.get(id=folder_id, user=self.user)
            except Folder.DoesNotExist:
                return {"success": False, "message": "Folder not found."}
        else:
            folder, created = Folder.objects.get_or_create(
                user=self.user, name="My Library", defaults={"color": "#10b981"}
            )

        # Add to folder
        item, item_created = FolderItem.objects.get_or_create(
            folder=folder, resource=self.resource
        )

        if not item_created:
            return {"success": False, "message": "Resource already in library."}

        return {
            "success": True,
            "message": "Resource added to library.",
            "folder_id": str(folder.id),
        }


class ResourceRatingService:
    """Service for resource rating operations."""

    def __init__(self, resource: Resource, user):
        self.resource = resource
        self.user = user

    def rate(self, value: int) -> dict:
        """
        Rate the resource.

        Args:
            value: Rating value (1-5)

        Returns:
            dict: {'success': bool, 'message': str, 'user_rating': int or None}
        """
        from apps.ratings.models import Rating

        if self.resource.uploaded_by_id == getattr(self.user, "id", None):
            return {
                "success": False,
                "message": "You cannot rate your own resource.",
                "user_rating": None,
            }

        if not 1 <= value <= 5:
            return {
                "success": False,
                "message": "Rating must be between 1 and 5.",
                "user_rating": None,
            }

        rating, created = Rating.objects.update_or_create(
            user=self.user, resource=self.resource, defaults={"value": value}
        )

        # Recalculate average rating
        self._update_average_rating()

        return {"success": True, "message": "Rating saved.", "user_rating": value}

    def remove_rating(self) -> dict:
        """Remove user's rating from the resource."""
        from apps.ratings.models import Rating

        deleted, _ = Rating.objects.filter(
            user=self.user, resource=self.resource
        ).delete()

        if deleted:
            self._update_average_rating()
            return {"success": True, "message": "Rating removed.", "user_rating": None}

        return {
            "success": False,
            "message": "No rating to remove.",
            "user_rating": None,
        }

    def _update_average_rating(self):
        """Update the resource's average rating."""
        from django.db.models import Avg

        from apps.ratings.models import Rating

        result = Rating.objects.filter(resource=self.resource).aggregate(
            avg_rating=Avg("value")
        )

        avg = result["avg_rating"] or 0
        self.resource.average_rating = round(avg, 2)
        self.resource.save(update_fields=["average_rating"])


class ResourceReportService:
    """Service for reporting resources."""

    def __init__(self, resource: Resource, user):
        self.resource = resource
        self.user = user

    def report(self, reason: str, message: str) -> dict:
        """
        Report the resource.

        Args:
            reason: Reason for reporting
            message: Additional details

        Returns:
            dict: {'success': bool, 'message': str}
        """
        from apps.reports.models import Report

        # Check if user already reported this resource
        existing = Report.objects.filter(
            reporter=self.user, resource=self.resource
        ).exists()

        if existing:
            return {
                "success": False,
                "message": "You have already reported this resource.",
            }

        # Create report
        Report.objects.create(
            reporter=self.user,
            resource=self.resource,
            reason_type=reason,
            message=message,
            status="open",
        )

        return {
            "success": True,
            "message": "Report submitted. Thank you for helping keep our community safe.",
        }

class ResourceUploadService:
    """Service for upload validation and lifecycle operations."""

    @staticmethod
    def _notify_pending_moderation_reviewers(resource: Resource):
        """Notify admin/moderator users that a resource is waiting for review."""
        from django.contrib.auth import get_user_model

        from apps.notifications.models import NotificationType

        User = get_user_model()
        candidates = User.objects.filter(is_active=True).exclude(id=resource.uploaded_by_id)
        reviewers = [
            candidate
            for candidate in candidates
            if getattr(candidate, "is_admin", False) or getattr(candidate, "is_moderator", False)
        ]

        for reviewer in reviewers:
            NotificationService.create_notification(
                recipient=reviewer,
                title="New Resource Pending Review",
                message=f"Resource '{resource.title}' requires moderation review.",
                notification_type=NotificationType.ADMIN_RESOURCE_PENDING_MODERATION,
                link=f"/admin/resources/{resource.slug}/change/",
                target_resource=resource,
            )

    @staticmethod
    def _auto_publish_defaults() -> dict:
        """Return the normalized fields for resources awaiting moderation."""
        return {
            "status": "pending",
            "is_public": False,
            "approved_by": None,
            "approved_at": None,
            "rejection_reason": "",
        }

    @staticmethod
    def _resolve_mobile_academic_metadata(*, user, data):
        """Fill mobile upload gaps from the selected unit, course and user profile."""
        resolved = dict(data)

        unit = resolved.get("unit")
        if unit is not None:
            if not resolved.get("course"):
                course_from_unit = getattr(unit, "course", None)
                if course_from_unit is not None:
                    resolved["course"] = course_from_unit
            if not resolved.get("semester"):
                semester = getattr(unit, "semester", None)
                if semester not in (None, ""):
                    resolved["semester"] = semester
            if not resolved.get("year_of_study"):
                year_of_study = getattr(unit, "year_of_study", None)
                if year_of_study is not None:
                    resolved["year_of_study"] = year_of_study

        course = resolved.get("course") or getattr(user, "course", None)
        if course is not None and not resolved.get("course"):
            resolved["course"] = course

        department = resolved.get("department")
        if department is None and course is not None:
            department = getattr(course, "department", None)
            if department is not None:
                resolved["department"] = department
        elif department is None and getattr(user, "department", None) is not None:
            department = user.department
            resolved["department"] = department

        if resolved.get("faculty") is None:
            faculty = None
            if department is not None:
                faculty = getattr(department, "faculty", None)
            if faculty is None:
                faculty = getattr(user, "faculty", None)
            if faculty is not None:
                resolved["faculty"] = faculty

        if not resolved.get("year_of_study") and getattr(user, "year_of_study", None):
            resolved["year_of_study"] = user.year_of_study

        return resolved

    @staticmethod
    def validate_resource_upload(*, user, data, file_obj, instance=None, is_mobile=False):
        """Validate metadata, file payload and ownership constraints."""
        effective_data = (
            ResourceUploadService._resolve_mobile_academic_metadata(user=user, data=data)
            if is_mobile
            else data
        )

        title = normalize_title(effective_data.get("title") or "")
        if not title:
            raise ValidationError({"title": "Title is required."})
        if instance is None and not file_obj:
            raise ValidationError({"file": "File is required."})
        
        if is_mobile:
            required_fields = [
                "faculty",
                "department",
                "course",
                "unit",
                "semester",
                "year_of_study",
            ]
        else:
            # Web/desktop uploads require full academic info
            required_fields = [
                "faculty",
                "department",
                "course",
                "unit",
                "semester",
                "year_of_study",
            ]
            
        source_data = data if is_mobile else effective_data
        missing = {
            field: "This field is required."
            for field in required_fields
            if not source_data.get(field)
        }
        if is_mobile:
            if not effective_data.get("semester"):
                missing["semester"] = "Semester could not be derived from the selected unit."
            if not effective_data.get("year_of_study"):
                missing["year_of_study"] = (
                    "Year of study could not be derived from the selected unit."
                )
        if missing:
            raise ValidationError(missing)

        if is_mobile:
            selected_unit = effective_data.get("unit")
            selected_semester = source_data.get("semester")
            selected_year_of_study = source_data.get("year_of_study")

            if (
                selected_unit is not None
                and selected_semester not in (None, "")
                and str(selected_semester) != str(getattr(selected_unit, "semester", ""))
            ):
                raise ValidationError(
                    {
                        "semester": (
                            "Selected semester does not match the selected unit."
                        )
                    }
                )

            if (
                selected_unit is not None
                and selected_year_of_study not in (None, "")
                and int(selected_year_of_study)
                != int(getattr(selected_unit, "year_of_study", 0) or 0)
            ):
                raise ValidationError(
                    {
                        "year_of_study": (
                            "Selected year of study does not match the selected unit."
                        )
                    }
                )

        if file_obj is not None:
            file_meta = validate_upload_file(file_obj)
        else:
            file_meta = {
                "extension": instance.file_type if instance else "",
                "mime_type": "",
                "size": instance.file_size if instance else 0,
                "normalized_filename": instance.normalized_filename if instance else "",
            }

        faculty = effective_data.get("faculty") or (instance.faculty if instance else None)
        department = effective_data.get("department") or (
            instance.department if instance else None
        )
        course = effective_data.get("course") or (instance.course if instance else None)
        unit = effective_data.get("unit") or (instance.unit if instance else None)
        validate_academic_relationships(
            faculty=faculty,
            department=department,
            course=course,
            unit=unit,
        )

        validate_duplicate_upload(
            user=user,
            title=title,
            normalized_filename=file_meta["normalized_filename"],
            file_size=file_meta["size"],
            exclude_resource_id=instance.id if instance else None,
        )

        return {
            "title": title,
            "tags": normalize_tags(effective_data.get("tags", "")),
            "file_size": file_meta["size"],
            "file_type": file_meta["extension"],
            "normalized_filename": file_meta["normalized_filename"],
            "effective_data": effective_data,
        }

    @staticmethod
    @transaction.atomic
    def create_resource_upload(*, user, validated_data, is_mobile=False):
        """Create a new resource upload in pending moderation state."""
        file_obj = validated_data.get("file")
        computed = ResourceUploadService.validate_resource_upload(
            user=user,
            data=validated_data,
            file_obj=file_obj,
            is_mobile=is_mobile,
        )
        if is_mobile:
            for field in ("faculty", "department", "course", "unit", "semester", "year_of_study"):
                value = computed["effective_data"].get(field)
                if value not in (None, ""):
                    validated_data[field] = value
        validated_data["uploaded_by"] = user
        validated_data["title"] = computed["title"]
        if computed["tags"]:
            validated_data["tags"] = computed["tags"]
        else:
            generated_tags = suggest_tags(
                title=validated_data["title"],
                description=validated_data.get("description", ""),
                resource_type=validated_data.get("resource_type", ""),
            )
            validated_data["tags"] = ", ".join(generated_tags)
        validated_data["file_size"] = computed["file_size"]
        validated_data["file_type"] = computed["file_type"]
        validated_data["normalized_filename"] = computed["normalized_filename"]
        validated_data.update(ResourceUploadService._auto_publish_defaults())

        resource = Resource.objects.create(**validated_data)

        try:
            ResourceUploadService._notify_pending_moderation_reviewers(resource)
        except Exception:
            pass
        UserActivity.objects.create(
            user=user,
            action="upload",
            description=f'Uploaded resource "{resource.title}"',
        )
        ResourceUploadService.recalculate_user_upload_counts(user)

        return resource

    @staticmethod
    @transaction.atomic
    def update_resource_upload(*, instance: Resource, user, validated_data):
        """Update an upload and route it to pending moderation when required."""
        computed = ResourceUploadService.validate_resource_upload(
            user=user,
            data={
                **{
                    "title": instance.title,
                    "tags": instance.tags,
                    "faculty": instance.faculty,
                    "department": instance.department,
                    "course": instance.course,
                    "unit": instance.unit,
                    "semester": instance.semester,
                    "year_of_study": instance.year_of_study,
                },
                **validated_data,
            },
            file_obj=validated_data.get("file"),
            instance=instance,
        )
        previous_status = instance.status
        previously_public = bool(instance.is_public)
        updated_fields = set(validated_data.keys())

        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.title = computed["title"]
        instance.tags = computed["tags"]
        instance.file_size = computed["file_size"]
        instance.file_type = computed["file_type"]
        instance.normalized_filename = computed["normalized_filename"]
        updated_fields.update(
            ["title", "tags", "file_size", "file_type", "normalized_filename"]
        )

        if previous_status != "approved" or not previously_public:
            auto_publish_fields = ResourceUploadService._auto_publish_defaults()
            for field, value in auto_publish_fields.items():
                setattr(instance, field, value)
            updated_fields.update(auto_publish_fields.keys())

        instance.save(update_fields=sorted(updated_fields | {"updated_at"}))
        ResourceUploadService.recalculate_user_upload_counts(user)

        try:
            NotificationService.notify_resource_updated(instance, list(validated_data.keys()))
        except Exception:
            pass

        if previous_status != "approved" or not previously_public:
            try:
                ResourceUploadService._notify_pending_moderation_reviewers(instance)
            except Exception:
                pass

        return instance

    @staticmethod
    def get_user_uploads(user):
        """Return current user's uploads."""
        # Include trashed/archived resources so owners can restore them.
        return Resource.all_objects.filter(uploaded_by=user).order_by("-created_at")

    @staticmethod
    def recalculate_user_upload_counts(user):
        """Recalculate profile upload count and owned-resource storage usage."""
        total_uploads = Resource.objects.filter(uploaded_by=user).count()
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.total_uploads = total_uploads
        profile.save(update_fields=["total_uploads"])

    @staticmethod
    def recalculate_user_storage_usage(user):
        """Recalculate user storage based on public and personal resources."""
        from apps.resources.models import PersonalResource, UserStorage

        public_size = (
            Resource.objects.filter(uploaded_by=user).aggregate(total=Sum("file_size"))[
                "total"
            ]
            or 0
        )
        personal_size = (
            PersonalResource.objects.filter(user=user).aggregate(
                total=Sum("file_size")
            )["total"]
            or 0
        )
        storage, _ = UserStorage.objects.get_or_create(user=user)
        storage.used_storage = public_size + personal_size
        storage.save(update_fields=["used_storage"])
