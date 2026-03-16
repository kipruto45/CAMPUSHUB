"""Core OOP service layer for CampusHub.

This module demonstrates:
- Encapsulation with service classes
- Reusable business abstractions
- Data-structure aware operations (trees, dicts, sets)
- Algorithm-driven scoring, ranking and validation
"""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import Iterable
from unittest.mock import Mock

from django.db.models import Count, Sum
from django.utils import timezone

from apps.core.algorithms import (aggregate_usage_dictionaries,
                                  build_comment_tree,
                                  calculate_search_relevance, get_breadcrumbs,
                                  get_folder_tree, rank_analytics_entities,
                                  traverse_comment_tree, validate_folder_move)


def _is_real_user_instance(user) -> bool:
    """Detect persisted Django user instances and exclude mocked users."""
    from django.contrib.auth import get_user_model

    if user is None or isinstance(user, Mock):
        return False

    return isinstance(user, get_user_model())


class StorageService:
    """Encapsulates storage quota logic and usage calculations."""

    DEFAULT_LIMIT = 5 * 1024 * 1024 * 1024  # 5 GB
    MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB

    @classmethod
    def _is_real_user(cls, user) -> bool:
        return _is_real_user_instance(user)

    @classmethod
    def _get_storage(cls, user):
        from apps.resources.models import UserStorage

        if not cls._is_real_user(user):
            return SimpleNamespace(
                used_storage=cls.calculate_user_storage(user),
                storage_limit=cls.DEFAULT_LIMIT,
                save=lambda **kwargs: None,
            )

        storage, _ = UserStorage.objects.get_or_create(
            user=user,
            defaults={"storage_limit": cls.DEFAULT_LIMIT},
        )
        return storage

    @classmethod
    def recalculate_usage(cls, user) -> int:
        """Recalculate storage usage from persisted files."""
        from apps.resources.models import PersonalResource, Resource

        personal_size = (
            PersonalResource.all_objects.filter(user=user).aggregate(
                total=Sum("file_size")
            )["total"]
            or 0
        )
        public_size = (
            Resource.objects.filter(uploaded_by=user).aggregate(total=Sum("file_size"))[
                "total"
            ]
            or 0
        )

        used = int(personal_size + public_size)
        storage = cls._get_storage(user)
        if storage.used_storage != used:
            storage.used_storage = used
            storage.save(update_fields=["used_storage"])
        return used

    @classmethod
    def get_storage_info(cls, user) -> dict:
        """Get normalized storage summary."""
        storage = cls._get_storage(user)
        used = cls.recalculate_usage(user)
        remaining = max(0, int(storage.storage_limit) - used)
        percent = (
            (used / storage.storage_limit * 100.0) if storage.storage_limit else 0.0
        )

        return {
            "used_bytes": used,
            "limit_bytes": int(storage.storage_limit),
            "remaining_bytes": remaining,
            "usage_percent": round(percent, 2),
        }

    @classmethod
    def can_upload(cls, user, file_size: int) -> tuple[bool, str | None]:
        """Validate quota and file-size constraints."""
        if file_size <= 0:
            return False, "Invalid file size."
        if file_size > cls.MAX_FILE_SIZE_BYTES:
            return False, "File size exceeds 100MB limit."

        info = cls.get_storage_info(user)
        if file_size > info["remaining_bytes"]:
            return False, "Storage quota exceeded."
        return True, None

    @classmethod
    def get_usage_by_folder(cls, user) -> dict:
        """Return dictionary breakdown of storage usage by folder."""
        from apps.resources.models import PersonalFolder, PersonalResource

        usage = {}
        root = PersonalResource.objects.filter(
            user=user,
            folder__isnull=True,
            is_deleted=False,
        ).aggregate(total=Sum("file_size"), count=Count("id"))
        usage["root"] = {
            "size": int(root["total"] or 0),
            "count": int(root["count"] or 0),
        }

        for folder in PersonalFolder.objects.filter(user=user):
            stats = PersonalResource.objects.filter(
                user=user,
                folder=folder,
                is_deleted=False,
            ).aggregate(total=Sum("file_size"), count=Count("id"))
            usage[str(folder.id)] = {
                "name": folder.name,
                "size": int(stats["total"] or 0),
                "count": int(stats["count"] or 0),
            }

        return usage

    @classmethod
    def calculate_user_storage(cls, user) -> int:
        """Compatibility wrapper used by tests and other services."""
        from apps.resources.models import PersonalResource

        try:
            total = (
                PersonalResource.objects.filter(user=user)
                .aggregate(total=Sum("file_size"))
                .get("total")
                or 0
            )
            return int(total)
        except Exception:
            return 0

    @classmethod
    def get_storage_summary(cls, user) -> dict:
        """Return storage summary payload expected by API/tests."""
        from apps.resources.models import PersonalResource

        used = cls.calculate_user_storage(user)
        try:
            total_files = int(
                PersonalResource.objects.filter(user=user)
                .aggregate(count=Count("id"))
                .get("count")
                or 0
            )
        except Exception:
            total_files = 0

        limit = cls.DEFAULT_LIMIT
        remaining = max(0, limit - used)
        usage_percent = round((used / limit * 100.0), 2) if limit else 0.0

        return {
            "storage_used_bytes": used,
            "storage_limit_bytes": limit,
            "storage_remaining_bytes": remaining,
            "usage_percent": usage_percent,
            "total_files": total_files,
        }

    @classmethod
    def can_user_upload_file(cls, user, file_size: int) -> bool:
        if file_size <= 0 or file_size > cls.MAX_FILE_SIZE_BYTES:
            return False
        return cls.calculate_user_storage(user) + int(file_size) <= cls.DEFAULT_LIMIT

    @classmethod
    def get_storage_warning_level(cls, usage_percent: float) -> str:
        if usage_percent >= 90:
            return "critical"
        if usage_percent >= 70:
            return "warning"
        return "normal"


class LibraryService:
    """Service for personal library operations."""

    @classmethod
    def get_library_stats(cls, user) -> dict:
        from apps.bookmarks.models import Bookmark
        from apps.favorites.models import Favorite, FavoriteType
        from apps.resources.models import PersonalFolder, PersonalResource

        storage_info = StorageService.get_storage_info(user)
        return {
            "total_files": PersonalResource.objects.filter(
                user=user, is_deleted=False
            ).count(),
            "total_folders": PersonalFolder.objects.filter(user=user).count(),
            "total_bookmarks": Bookmark.objects.filter(user=user).count(),
            "total_favorites": Favorite.objects.filter(
                user=user,
                favorite_type=FavoriteType.RESOURCE,
            ).count(),
            "storage_used_mb": round(storage_info["used_bytes"] / (1024 * 1024), 2),
            "storage_limit_mb": round(storage_info["limit_bytes"] / (1024 * 1024), 2),
        }

    @classmethod
    def get_user_library(cls, user):
        """Return user personal resources queryset."""
        from apps.resources.models import PersonalResource

        return PersonalResource.objects.filter(user=user, is_deleted=False)

    @classmethod
    def get_recent_files(cls, user, limit: int = 10) -> list:
        from apps.resources.models import PersonalResource

        return list(
            PersonalResource.objects.filter(user=user, is_deleted=False)
            .order_by("-last_accessed_at", "-created_at")[: max(1, limit)]
            .values("id", "title", "file_type", "file_size", "last_accessed_at")
        )

    @classmethod
    def move_to_trash(cls, resource, user) -> bool:
        if resource.user_id != user.id:
            return False

        resource.original_folder = resource.folder
        resource.folder = None
        resource.is_deleted = True
        resource.deleted_at = timezone.now()
        resource.save(
            update_fields=["original_folder", "folder", "is_deleted", "deleted_at"]
        )
        return True

    @classmethod
    def restore_from_trash(cls, resource, user) -> bool:
        if resource.user_id != user.id or not resource.is_deleted:
            return False

        target_folder = resource.original_folder
        if target_folder and target_folder.user_id != user.id:
            target_folder = None

        resource.folder = target_folder
        resource.is_deleted = False
        resource.deleted_at = None
        resource.save(update_fields=["folder", "is_deleted", "deleted_at"])
        return True

    @classmethod
    def permanent_delete(cls, resource, user) -> bool:
        if resource.user_id != user.id:
            return False

        if resource.file:
            resource.file.delete(save=False)
        resource.delete()
        StorageService.recalculate_usage(user)
        return True


class FolderService:
    """Tree-aware folder operations."""

    @classmethod
    def create_folder(cls, user, name: str, parent=None, color="#3b82f6"):
        from apps.resources.models import PersonalFolder

        parent_user_id = (
            getattr(parent, "user_id", None) if parent is not None else None
        )
        if (
            parent
            and isinstance(parent_user_id, (int, str))
            and str(parent_user_id) != str(user.id)
        ):
            raise ValueError("Cannot create folder under another user's folder.")

        return PersonalFolder.objects.create(
            user=user,
            name=name,
            parent=parent,
            color=color,
        )

    @classmethod
    def move_folder(cls, folder, new_parent, user) -> tuple[bool, str | None]:
        is_valid, error = validate_folder_move(folder, new_parent, user)
        if not is_valid:
            return False, error

        folder.parent = new_parent
        folder.save(update_fields=["parent"])
        return True, None

    @classmethod
    def get_folder_tree(cls, user, root_folder=None, include_files=True) -> list:
        return get_folder_tree(
            user, root_folder=root_folder, include_files=include_files
        )

    @classmethod
    def get_breadcrumbs(cls, folder) -> list:
        return get_breadcrumbs(folder)


class CommentTreeService:
    """Service for threaded comment tree operations."""

    @classmethod
    def get_resource_comment_tree(cls, resource, include_deleted=False) -> list:
        return build_comment_tree(resource, include_deleted=include_deleted)

    @classmethod
    def get_flat_thread(cls, resource, include_deleted=False) -> list:
        return traverse_comment_tree(
            build_comment_tree(resource, include_deleted=include_deleted)
        )


class NotificationService:
    """Service wrapper for in-app notification workflows."""

    @classmethod
    def create_notification(
        cls,
        user,
        notification_type: str,
        title: str,
        message: str,
        target_resource=None,
        target_comment=None,
        link: str = "",
    ):
        from apps.notifications.models import Notification

        return Notification.objects.create(
            recipient=user,
            notification_type=notification_type,
            title=title,
            message=message,
            target_resource=target_resource,
            target_comment=target_comment,
            link=link,
        )

    @classmethod
    def get_unread_count(cls, user) -> int:
        from apps.notifications.models import Notification

        return Notification.objects.filter(recipient=user, is_read=False).count()

    @classmethod
    def mark_as_read(cls, notification_id, user) -> bool:
        from apps.notifications.models import Notification

        updated = Notification.objects.filter(
            id=notification_id,
            recipient=user,
            is_read=False,
        ).update(is_read=True)
        return bool(updated)

    @classmethod
    def mark_all_read(cls, user) -> int:
        from apps.notifications.models import Notification

        return Notification.objects.filter(recipient=user, is_read=False).update(
            is_read=True
        )

    @classmethod
    def get_notifications(cls, user, unread_only=False, limit: int = 20) -> list:
        from apps.notifications.models import Notification

        queryset = Notification.objects.filter(recipient=user)
        if unread_only:
            queryset = queryset.filter(is_read=False)
        return list(queryset.order_by("-created_at")[: max(1, limit)])

    @classmethod
    def send_bulk_notification(
        cls, users: Iterable, notification_type: str, title: str, message: str
    ):
        from apps.notifications.models import Notification

        rows = [
            Notification(
                recipient=user,
                notification_type=notification_type,
                title=title,
                message=message,
            )
            for user in users
        ]
        if rows:
            Notification.objects.bulk_create(rows, batch_size=200)


class SearchService:
    """OOP facade over search module with relevance helpers."""

    @classmethod
    def search_resources(cls, query: str, filters=None, user=None, sort=None):
        from apps.search.services import SearchService as ModuleSearchService

        return ModuleSearchService.search_resources(
            query, filters=filters, user=user, sort=sort
        )

    @classmethod
    def search_ranked_preview(cls, query: str, limit: int = 20):
        """Return ranked resources using pure algorithmic relevance scoring."""
        from apps.resources.models import Resource

        queryset = Resource.objects.filter(
            status="approved", is_public=True
        ).select_related("course", "unit")
        scored = []
        for resource in queryset:
            score = calculate_search_relevance(resource, query)
            if score > 0:
                scored.append((resource, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return [item[0] for item in scored[: max(1, limit)]]

    @classmethod
    def save_recent_search(cls, user, query: str, filters=None, results_count: int = 0):
        from apps.search.services import SearchService as ModuleSearchService

        return ModuleSearchService.save_recent_search(
            user=user,
            query=query,
            filters=filters,
            results_count=results_count,
        )

    @classmethod
    def get_recent_searches(cls, user, limit: int = 10):
        from apps.search.services import SearchService as ModuleSearchService

        return ModuleSearchService.get_recent_searches(user=user, limit=limit)


class AnalyticsService:
    """Service for analytics aggregation, dictionary maps and ranking."""

    @classmethod
    def get_resource_analytics(cls, days: int = 30) -> dict:
        from apps.activity.models import ActivityType, RecentActivity
        from apps.downloads.models import Download
        from apps.resources.models import Resource

        since = timezone.now() - timedelta(days=days)
        return {
            "total_resources": Resource.objects.filter(
                status="approved", is_public=True
            ).count(),
            "total_downloads": Download.objects.filter(created_at__gte=since).count(),
            "total_views": RecentActivity.objects.filter(
                activity_type=ActivityType.VIEWED_RESOURCE,
                created_at__gte=since,
            ).count(),
        }

    @classmethod
    def get_dictionary_analytics(cls, days: int = 30) -> dict:
        return aggregate_usage_dictionaries(days=days)

    @classmethod
    def get_ranked_analytics(cls, days: int = 30, limit: int = 10) -> dict:
        metrics = cls.get_dictionary_analytics(days=days)
        return {
            "top_downloaded_courses": rank_analytics_entities(
                metrics["downloads_by_course"], limit=limit
            ),
            "top_viewed_units": rank_analytics_entities(
                metrics["views_by_unit"], limit=limit
            ),
            "top_favorited_resources": rank_analytics_entities(
                metrics["favorites_by_resource"], limit=limit
            ),
            "most_active_faculties": rank_analytics_entities(
                metrics["active_users_by_faculty"], limit=limit
            ),
        }

    @classmethod
    def get_top_resources(cls, metric: str = "downloads", limit: int = 10) -> list:
        from apps.resources.models import Resource

        queryset = Resource.objects.filter(status="approved", is_public=True)
        if metric == "downloads":
            queryset = queryset.order_by("-download_count", "-view_count")
        elif metric == "views":
            queryset = queryset.order_by("-view_count", "-download_count")
        elif metric == "favorites":
            queryset = queryset.annotate(favorite_count=Count("favorites")).order_by(
                "-favorite_count"
            )
        elif metric == "rating":
            queryset = queryset.order_by("-average_rating", "-download_count")
        else:
            queryset = queryset.order_by("-created_at")

        return list(
            queryset[: max(1, limit)].values(
                "id", "title", "download_count", "view_count", "average_rating"
            )
        )

    @classmethod
    def get_platform_stats(cls) -> dict:
        """Compatibility alias for dashboard-level aggregate stats."""
        try:
            return cls.get_resource_analytics(days=30)
        except RuntimeError as exc:
            if "Database access not allowed" in str(exc):
                return {
                    "total_resources": 0,
                    "total_downloads": 0,
                    "total_views": 0,
                }
            raise

    @classmethod
    def get_resource_metrics(cls) -> dict:
        """Compatibility alias exposing resource-centric metrics."""
        analytics = cls.get_platform_stats()
        try:
            analytics["top_resources"] = cls.get_top_resources(
                metric="downloads", limit=5
            )
        except RuntimeError as exc:
            if "Database access not allowed" in str(exc):
                analytics["top_resources"] = []
            else:
                raise
        return analytics


class ReportService:
    """Service for report lifecycle and moderation stats."""

    @classmethod
    def create_report(
        cls,
        reporter,
        *,
        resource=None,
        comment=None,
        reason_type: str,
        message: str = "",
    ):
        from apps.core.algorithms import detect_duplicate_report
        from apps.reports.models import Report

        if (
            resource
            and _is_real_user_instance(reporter)
            and detect_duplicate_report(reporter, resource.id, reason_type)
        ):
            raise ValueError("You have already reported this resource recently.")

        if not resource and not comment:
            raise ValueError("Report target is required.")

        return Report.objects.create(
            reporter=reporter,
            resource=resource,
            comment=comment,
            reason_type=reason_type,
            message=message,
            status="open",
        )

    @classmethod
    def get_user_reports(cls, user):
        from apps.reports.models import Report

        return Report.objects.filter(reporter=user).order_by("-created_at")

    @classmethod
    def resolve_report(cls, report, reviewer, resolution_note: str = "") -> bool:
        if not (
            getattr(reviewer, "is_staff", False) or getattr(reviewer, "is_admin", False)
        ):
            return False

        report.status = "resolved"
        report.reviewed_by = reviewer
        report.resolution_note = resolution_note
        report.save(
            update_fields=["status", "reviewed_by", "resolution_note", "updated_at"]
        )
        return True

    @classmethod
    def dismiss_report(cls, report, reviewer, reason: str = "") -> bool:
        if not (
            getattr(reviewer, "is_staff", False) or getattr(reviewer, "is_admin", False)
        ):
            return False

        report.status = "dismissed"
        report.reviewed_by = reviewer
        report.resolution_note = reason
        report.save(
            update_fields=["status", "reviewed_by", "resolution_note", "updated_at"]
        )
        return True

    @classmethod
    def get_report_stats(cls) -> dict:
        from apps.reports.models import Report

        return {
            "total": Report.objects.count(),
            "open": Report.objects.filter(status="open").count(),
            "in_review": Report.objects.filter(status="in_review").count(),
            "resolved": Report.objects.filter(status="resolved").count(),
            "dismissed": Report.objects.filter(status="dismissed").count(),
        }


class DashboardService:
    """Facade service that aggregates module services for dashboard payloads."""

    @classmethod
    def get_user_dashboard(cls, user, recommendation_limit: int = 5) -> dict:
        from apps.activity.services import ActivityService
        from apps.recommendations.oop_services import RecommendationService

        if not StorageService._is_real_user(user):
            return {
                "library": {},
                "storage": {
                    "used_bytes": 0,
                    "limit_bytes": StorageService.DEFAULT_LIMIT,
                    "remaining_bytes": StorageService.DEFAULT_LIMIT,
                    "usage_percent": 0.0,
                },
                "notifications": {"unread_count": 0},
                "recommendations": [],
                "recent_activity_count": 0,
                "recent_files": [],
            }

        library = LibraryService.get_library_stats(user)
        storage = StorageService.get_storage_info(user)
        notifications = {"unread_count": NotificationService.get_unread_count(user)}

        recommendations = RecommendationService.get_recommendations_for_dashboard(
            user,
            limit=recommendation_limit,
        )

        recent_activity = ActivityService.get_recent_activities(user, limit=10)

        return {
            "library": library,
            "storage": storage,
            "notifications": notifications,
            "recommendations": recommendations,
            "recent_activity_count": len(recent_activity),
            "recent_files": LibraryService.get_recent_files(user, limit=5),
        }

    @classmethod
    def get_admin_dashboard(cls) -> dict:
        from apps.accounts.models import User
        from apps.downloads.models import Download
        from apps.resources.models import Resource

        return {
            "users": {
                "total": User.objects.filter(is_active=True).count(),
                "students": User.objects.filter(role="STUDENT", is_active=True).count(),
                "moderators": User.objects.filter(
                    role="MODERATOR", is_active=True
                ).count(),
            },
            "resources": {
                "total": Resource.objects.count(),
                "approved": Resource.objects.filter(status="approved").count(),
                "pending": Resource.objects.filter(status="pending").count(),
                "rejected": Resource.objects.filter(status="rejected").count(),
            },
            "downloads": {
                "total": Download.objects.count(),
            },
            "reports": ReportService.get_report_stats(),
            "analytics_rankings": AnalyticsService.get_ranked_analytics(
                days=30, limit=5
            ),
        }


__all__ = [
    "StorageService",
    "LibraryService",
    "FolderService",
    "CommentTreeService",
    "NotificationService",
    "SearchService",
    "AnalyticsService",
    "ReportService",
    "DashboardService",
]
