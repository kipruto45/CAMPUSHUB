"""Tests for announcements module."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework import status

from apps.announcements.models import Announcement, AnnouncementStatus
from apps.notifications.models import Notification, NotificationType


@pytest.fixture
def published_announcement(db, admin_user):
    """Create a published announcement."""
    return Announcement.objects.create(
        title="Published Notice",
        content="Classes resume on Monday.",
        announcement_type="general",
        status=AnnouncementStatus.PUBLISHED,
        is_pinned=False,
        published_at=timezone.now(),
        created_by=admin_user,
    )


@pytest.fixture
def pinned_announcement(db, admin_user):
    """Create a pinned published announcement."""
    return Announcement.objects.create(
        title="Pinned Notice",
        content="Urgent registration update.",
        announcement_type="urgent",
        status=AnnouncementStatus.PUBLISHED,
        is_pinned=True,
        published_at=timezone.now(),
        created_by=admin_user,
    )


@pytest.mark.django_db
class TestAnnouncementsModule:
    """Student and admin announcement behaviors."""

    def test_student_list_shows_only_published(
        self, authenticated_client, published_announcement, admin_user
    ):
        Announcement.objects.create(
            title="Draft Notice",
            content="This should not be visible to students.",
            announcement_type="general",
            status=AnnouncementStatus.DRAFT,
            created_by=admin_user,
        )
        response = authenticated_client.get("/api/announcements/")
        assert response.status_code == status.HTTP_200_OK
        titles = [item["title"] for item in response.data["results"]]
        assert "Published Notice" in titles
        assert "Draft Notice" not in titles
        published_item = next(
            item
            for item in response.data["results"]
            if item["title"] == "Published Notice"
        )
        assert published_item["content"] == "Classes resume on Monday."

    def test_pinned_endpoint_returns_only_pinned(
        self, authenticated_client, pinned_announcement
    ):
        response = authenticated_client.get("/api/announcements/pinned/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
        assert all(item["is_pinned"] for item in response.data)

    def test_admin_can_create_and_publish_announcement(
        self, admin_client, user
    ):
        create_payload = {
            "title": "System Maintenance",
            "content": "Maintenance tonight at 10 PM.",
            "announcement_type": "maintenance",
            "status": AnnouncementStatus.DRAFT,
            "is_pinned": False,
        }
        create_response = admin_client.post(
            "/api/announcements/admin/", create_payload, format="json"
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        created = (
            Announcement.objects.filter(title="System Maintenance")
            .order_by("-created_at")
            .first()
        )
        assert created is not None
        slug = created.slug

        publish_response = admin_client.post(
            f"/api/announcements/admin/{slug}/publish/", {}, format="json"
        )
        assert publish_response.status_code == status.HTTP_200_OK

        announcement = Announcement.objects.get(slug=slug)
        assert announcement.status == AnnouncementStatus.PUBLISHED
        assert announcement.published_at is not None
        assert Notification.objects.filter(
            recipient=user,
            notification_type=NotificationType.ANNOUNCEMENT,
            title=announcement.title,
        ).exists()

    def test_admin_can_create_announcement_with_attachments(self, admin_client):
        attachment = SimpleUploadedFile(
            "maintenance-plan.pdf",
            b"maintenance plan",
            content_type="application/pdf",
        )
        create_response = admin_client.post(
            "/api/announcements/admin/",
            {
                "title": "Attachment Notice",
                "content": "Maintenance attachment included.",
                "announcement_type": "maintenance",
                "status": AnnouncementStatus.DRAFT,
                "attachment_files": [attachment],
            },
            format="multipart",
        )

        assert create_response.status_code == status.HTTP_201_CREATED
        assert create_response.data["attachment_count"] == 1
        assert len(create_response.data["attachments"]) == 1
        assert create_response.data["attachments"][0]["filename"].endswith(".pdf")

        announcement = Announcement.objects.get(title="Attachment Notice")
        assert announcement.attachments.count() == 1
        saved_attachment = announcement.attachments.first()
        assert saved_attachment is not None
        assert saved_attachment.filename.endswith(".pdf")
        assert saved_attachment.file_type == "pdf"

    def test_admin_can_remove_existing_attachment(self, admin_client, admin_user):
        announcement = Announcement.objects.create(
            title="Attachment Cleanup",
            content="Draft with attachment.",
            announcement_type="general",
            status=AnnouncementStatus.DRAFT,
            created_by=admin_user,
        )
        attachment = announcement.attachments.create(
            file=SimpleUploadedFile(
                "old-file.txt",
                b"stale attachment",
                content_type="text/plain",
            )
        )

        update_response = admin_client.patch(
            f"/api/announcements/admin/{announcement.slug}/",
            {
                "remove_attachment_ids": [str(attachment.id)],
            },
            format="multipart",
        )

        assert update_response.status_code == status.HTTP_200_OK
        announcement.refresh_from_db()
        assert announcement.attachments.count() == 0

    def test_non_admin_cannot_create_announcement(self, authenticated_client):
        response = authenticated_client.post(
            "/api/announcements/admin/",
            {
                "title": "Unauthorized",
                "content": "Should not be created",
                "announcement_type": "general",
                "status": AnnouncementStatus.DRAFT,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_dashboard_announcements_requires_authentication(self, api_client):
        response = api_client.get("/api/announcements/dashboard/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_dashboard_announcements_returns_visible_items(
        self, authenticated_client, published_announcement
    ):
        response = authenticated_client.get("/api/announcements/dashboard/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 1
