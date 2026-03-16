"""Tests for comments module."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from apps.comments.models import Comment
from apps.moderation.models import ModerationLog
from apps.notifications.models import Notification, NotificationType
from apps.resources.models import Resource

User = get_user_model()


@pytest.fixture
def comment_resource(db, admin_user):
    """Create an approved resource for commenting."""
    return Resource.objects.create(
        title="Commentable Resource",
        resource_type="notes",
        uploaded_by=admin_user,
        status="approved",
        is_public=True,
    )


@pytest.mark.django_db
class TestCommentsModule:
    """Comment CRUD, permissions, and moderation flow tests."""

    def test_authenticated_user_can_create_comment(
        self, authenticated_client, user, admin_user, comment_resource
    ):
        response = authenticated_client.post(
            reverse("comments:comment-list"),
            {
                "resource": str(comment_resource.id),
                "content": "Very helpful notes",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Comment.objects.filter(
            user=user, resource=comment_resource, content="Very helpful notes"
        ).exists()
        assert Notification.objects.filter(
            recipient=admin_user,
            notification_type=NotificationType.NEW_COMMENT,
            target_resource=comment_resource,
        ).exists()

    def test_unauthenticated_user_cannot_create_comment(
        self, api_client, comment_resource
    ):
        response = api_client.post(
            reverse("comments:comment-list"),
            {"resource": str(comment_resource.id), "content": "Blocked"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_reply_creates_reply_notification(
        self, authenticated_client, user, admin_user, comment_resource
    ):
        parent = Comment.objects.create(
            user=admin_user,
            resource=comment_resource,
            content="Original comment",
        )
        response = authenticated_client.post(
            reverse("comments:comment-list"),
            {
                "resource": str(comment_resource.id),
                "parent": str(parent.id),
                "content": "This is a reply",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Comment.objects.filter(parent=parent, user=user).exists()
        assert Notification.objects.filter(
            recipient=admin_user,
            notification_type=NotificationType.COMMENT_REPLY,
            target_comment__parent=parent,
        ).exists()

    def test_delete_is_soft_delete(
        self, authenticated_client, user, comment_resource
    ):
        comment = Comment.objects.create(
            user=user,
            resource=comment_resource,
            content="Temporary comment",
        )
        response = authenticated_client.delete(
            reverse("comments:comment-detail", kwargs={"pk": comment.id})
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        comment.refresh_from_db()
        assert comment.is_deleted is True
        assert comment.content == "[deleted]"

    def test_student_cannot_lock_comment(
        self, authenticated_client, user, comment_resource
    ):
        comment = Comment.objects.create(
            user=user,
            resource=comment_resource,
            content="Needs moderation check",
        )
        response = authenticated_client.post(
            reverse("comments:comment-lock", kwargs={"pk": comment.id}),
            {"reason": "spam", "hide_content": True},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_moderator_can_lock_and_unlock_comment(
        self, moderator_client, user, comment_resource
    ):
        original_content = "Potentially harmful comment"
        comment = Comment.objects.create(
            user=user,
            resource=comment_resource,
            content=original_content,
        )
        lock_response = moderator_client.post(
            reverse("comments:comment-lock", kwargs={"pk": comment.id}),
            {"reason": "moderation action", "hide_content": True},
            format="json",
        )
        assert lock_response.status_code == status.HTTP_200_OK
        comment.refresh_from_db()
        assert comment.is_locked is True
        assert comment.is_deleted is True
        assert comment.content == "[hidden by moderation]"
        assert ModerationLog.objects.filter(
            comment=comment, action="locked"
        ).exists()

        unlock_response = moderator_client.post(
            reverse("comments:comment-unlock", kwargs={"pk": comment.id}),
            {"reason": "resolved", "restore_content": True},
            format="json",
        )
        assert unlock_response.status_code == status.HTTP_200_OK
        comment.refresh_from_db()
        assert comment.is_locked is False
        assert comment.is_deleted is False
        assert comment.content == original_content
        assert ModerationLog.objects.filter(
            comment=comment, action="unlocked"
        ).exists()

    def test_non_owner_student_cannot_delete_comment(
        self, api_client, user, comment_resource
    ):
        owner = User.objects.create_user(
            email="owner-comments@test.com",
            password="testpass123",
            full_name="Owner",
            registration_number="OWNC001",
            role="student",
        )
        comment = Comment.objects.create(
            user=owner,
            resource=comment_resource,
            content="Owner comment",
        )
        api_client.force_authenticate(user=user)
        response = api_client.delete(
            reverse("comments:comment-detail", kwargs={"pk": comment.id})
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
