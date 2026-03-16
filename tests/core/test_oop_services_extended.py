"""Extended tests for core OOP services."""

from unittest.mock import Mock, patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.comments.models import Comment
from apps.core.oop_services import (AnalyticsService, CommentTreeService,
                                    DashboardService, FolderService,
                                    LibraryService, NotificationService,
                                    ReportService, SearchService,
                                    StorageService)
from apps.downloads.models import Download
from apps.favorites.models import Favorite, FavoriteType
from apps.notifications.models import Notification
from apps.reports.models import Report
from apps.resources.models import PersonalFolder, PersonalResource, Resource


@pytest.mark.django_db
class TestStorageAndLibraryServices:
    """Coverage for storage and library service operations."""

    def test_storage_recalculate_info_breakdown_and_limits(
        self, user, faculty, department, course, unit
    ):
        folder = PersonalFolder.objects.create(user=user, name="Week 1")
        root_file = PersonalResource.objects.create(
            user=user,
            title="Root",
            file=SimpleUploadedFile("root.pdf", b"root-bytes"),
        )
        folder_file = PersonalResource.objects.create(
            user=user,
            folder=folder,
            title="Folder File",
            file=SimpleUploadedFile("folder.pdf", b"folder-bytes"),
        )
        public_resource = Resource.objects.create(
            title="Uploaded Public",
            resource_type="notes",
            uploaded_by=user,
            status="approved",
            is_public=True,
            faculty=faculty,
            department=department,
            course=course,
            unit=unit,
            file=SimpleUploadedFile("public.pdf", b"public-bytes"),
        )

        expected_used = (
            int(root_file.file_size)
            + int(folder_file.file_size)
            + int(public_resource.file_size)
        )
        assert StorageService.recalculate_usage(user) == expected_used

        info = StorageService.get_storage_info(user)
        assert info["used_bytes"] == expected_used
        assert info["remaining_bytes"] == info["limit_bytes"] - expected_used
        assert info["usage_percent"] >= 0

        breakdown = StorageService.get_usage_by_folder(user)
        assert breakdown["root"]["count"] >= 1
        assert breakdown[str(folder.id)]["name"] == "Week 1"

        assert StorageService.can_upload(user, 0)[0] is False
        assert StorageService.can_upload(
            user, StorageService.MAX_FILE_SIZE_BYTES + 1
        )[0] is False
        with patch.object(
            StorageService,
            "get_storage_info",
            return_value={"remaining_bytes": 5},
        ):
            assert StorageService.can_upload(user, 10)[0] is False

        with patch.object(StorageService, "calculate_user_storage", return_value=0):
            assert StorageService.can_user_upload_file(user, 1024) is True
            assert StorageService.can_user_upload_file(user, -1) is False

    def test_library_trash_restore_and_permanent_delete(self, user, admin_user):
        folder = PersonalFolder.objects.create(user=user, name="My Folder")
        resource = PersonalResource.objects.create(
            user=user,
            folder=folder,
            title="Trash Me",
            file=SimpleUploadedFile("trash.pdf", b"trash-bytes"),
        )

        assert LibraryService.move_to_trash(resource, admin_user) is False
        assert LibraryService.move_to_trash(resource, user) is True
        resource.refresh_from_db()
        assert resource.is_deleted is True
        assert resource.original_folder == folder

        assert LibraryService.restore_from_trash(resource, admin_user) is False
        assert LibraryService.restore_from_trash(resource, user) is True
        resource.refresh_from_db()
        assert resource.is_deleted is False
        assert resource.folder == folder

        assert LibraryService.permanent_delete(resource, user) is True
        assert not PersonalResource.all_objects.filter(id=resource.id).exists()


@pytest.mark.django_db
class TestFolderCommentAndSearchServices:
    """Coverage for folder/comment/search service methods."""

    def test_folder_service_create_move_tree_and_breadcrumbs(self, user, admin_user):
        root = FolderService.create_folder(user=user, name="Root")
        child = FolderService.create_folder(user=user, name="Child", parent=root)

        failed, reason = FolderService.move_folder(root, child, user)
        assert failed is False
        assert "descendant" in reason.lower()

        with pytest.raises(ValueError):
            FolderService.create_folder(
                user=user,
                name="Denied",
                parent=PersonalFolder.objects.create(user=admin_user, name="Other"),
            )

        success, error = FolderService.move_folder(child, None, user)
        assert success is True
        assert error is None

        breadcrumbs = FolderService.get_breadcrumbs(child)
        assert breadcrumbs[0]["name"] == "Child"

        tree = FolderService.get_folder_tree(user)
        assert any(node["name"] == "Root" for node in tree)

    def test_comment_tree_service_and_search_facade(
        self, user, faculty, department, course, unit
    ):
        resource = Resource.objects.create(
            title="Searchable Resource",
            description="linked list stack queue",
            resource_type="notes",
            uploaded_by=user,
            status="approved",
            is_public=True,
            faculty=faculty,
            department=department,
            course=course,
            unit=unit,
            tags="stack,queue,list",
        )
        root_comment = Comment.objects.create(
            user=user, resource=resource, content="Root comment"
        )
        Comment.objects.create(
            user=user, resource=resource, parent=root_comment, content="Reply comment"
        )

        tree = CommentTreeService.get_resource_comment_tree(resource)
        flat = CommentTreeService.get_flat_thread(resource)
        assert len(tree) == 1
        assert [row["depth"] for row in flat] == [0, 1]

        ranked = SearchService.search_ranked_preview("searchable", limit=5)
        assert ranked
        assert ranked[0].id == resource.id

        with patch("apps.search.services.SearchService.search_resources") as search_mock:
            SearchService.search_resources("queue")
            assert search_mock.called
        with patch("apps.search.services.SearchService.save_recent_search") as save_mock:
            SearchService.save_recent_search(user, "queue")
            assert save_mock.called
        with patch("apps.search.services.SearchService.get_recent_searches") as recent_mock:
            SearchService.get_recent_searches(user)
            assert recent_mock.called


@pytest.mark.django_db
class TestNotificationAnalyticsReportAndDashboard:
    """Coverage for notification, analytics, report, and dashboard services."""

    def test_notification_service_methods(self, user, admin_user):
        baseline_unread = Notification.objects.filter(
            recipient=user, is_read=False
        ).count()
        created = NotificationService.create_notification(
            user=user,
            notification_type="system",
            title="Hello",
            message="World",
        )
        assert created.recipient == user
        assert NotificationService.get_unread_count(user) == baseline_unread + 1

        notifications = NotificationService.get_notifications(user, unread_only=True)
        assert any(item.id == created.id for item in notifications)

        assert NotificationService.mark_as_read(created.id, user) is True
        assert NotificationService.mark_as_read(created.id, user) is False
        marked_count = NotificationService.mark_all_read(user)
        assert marked_count >= 0
        assert NotificationService.get_unread_count(user) == 0

        NotificationService.send_bulk_notification(
            [user, admin_user], "system", "Bulk", "Bulk message"
        )
        assert Notification.objects.filter(title="Bulk").count() == 2

    def test_analytics_and_report_services(
        self, user, admin_user, faculty, department, course, unit
    ):
        resource = Resource.objects.create(
            title="Analytics Resource",
            resource_type="notes",
            uploaded_by=user,
            status="approved",
            is_public=True,
            faculty=faculty,
            department=department,
            course=course,
            unit=unit,
            download_count=12,
            view_count=15,
            average_rating=4.3,
        )
        Favorite.objects.create(
            user=user, favorite_type=FavoriteType.RESOURCE, resource=resource
        )
        Download.objects.create(user=user, resource=resource)

        assert AnalyticsService.get_top_resources(metric="downloads")
        assert AnalyticsService.get_top_resources(metric="views")
        assert AnalyticsService.get_top_resources(metric="favorites")
        assert AnalyticsService.get_top_resources(metric="rating")
        assert AnalyticsService.get_top_resources(metric="other")
        assert "top_downloaded_courses" in AnalyticsService.get_ranked_analytics(limit=3)

        with patch.object(
            AnalyticsService, "get_resource_analytics", side_effect=RuntimeError("Database access not allowed")
        ):
            assert AnalyticsService.get_platform_stats() == {
                "total_resources": 0,
                "total_downloads": 0,
                "total_views": 0,
            }
        with patch.object(
            AnalyticsService, "get_platform_stats", return_value={"total_resources": 1}
        ), patch.object(
            AnalyticsService, "get_top_resources", side_effect=RuntimeError("Database access not allowed")
        ):
            assert AnalyticsService.get_resource_metrics()["top_resources"] == []

        report = ReportService.create_report(
            reporter=user,
            resource=resource,
            reason_type="broken_file",
            message="Broken",
        )
        assert report.status == "open"

        with pytest.raises(ValueError):
            ReportService.create_report(
                reporter=user, reason_type="spam", message="No target"
            )

        Report.objects.create(
            reporter=user,
            resource=resource,
            reason_type="duplicate",
            message="Dup 1",
        )
        with pytest.raises(ValueError):
            ReportService.create_report(
                reporter=user,
                resource=resource,
                reason_type="duplicate",
                message="Dup 2",
            )

        assert ReportService.resolve_report(report, user) is False
        assert ReportService.resolve_report(report, admin_user, "Fixed") is True
        report.refresh_from_db()
        assert report.status == "resolved"

        assert ReportService.dismiss_report(report, admin_user, "No issue") is True
        report.refresh_from_db()
        assert report.status == "dismissed"
        stats = ReportService.get_report_stats()
        assert stats["total"] >= 2

    def test_dashboard_service_paths(self, user):
        mock_user = Mock()
        minimal = DashboardService.get_user_dashboard(mock_user)
        assert minimal["notifications"]["unread_count"] == 0

        with patch(
            "apps.activity.services.ActivityService.get_recent_activities",
            return_value=[{"id": "a"}],
        ), patch(
            "apps.recommendations.oop_services.RecommendationService.get_recommendations_for_dashboard",
            return_value=[{"id": "r"}],
        ):
            payload = DashboardService.get_user_dashboard(user, recommendation_limit=3)
            assert payload["recent_activity_count"] == 1
            assert payload["recommendations"] == [{"id": "r"}]

        admin_payload = DashboardService.get_admin_dashboard()
        assert "users" in admin_payload
        assert "resources" in admin_payload
