"""
Tests for comments app.
"""
import pytest
from django.contrib.auth import get_user_model

from apps.comments.models import Comment

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestCommentModel:
    """Tests for Comment model."""

    def test_comment_creation(self, user):
        """Test comment creation."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test description",
            created_by=user,
        )
        comment = Comment.objects.create(
            user=user,
            resource=resource,
            content="This is a test comment.",
        )
        assert comment.id is not None
        assert comment.content == "This is a test comment."
        assert comment.is_edited is False
        assert comment.is_deleted is False

    def test_comment_str(self, user):
        """Test comment string representation."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test description",
            created_by=user,
        )
        comment = Comment.objects.create(
            user=user,
            resource=resource,
            content="Test comment",
        )
        assert str(comment) == f"Comment by {user.email} on {resource.title}"

    def test_comment_reply(self, user):
        """Test comment reply creation."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test description",
            created_by=user,
        )
        parent_comment = Comment.objects.create(
            user=user,
            resource=resource,
            content="Parent comment",
        )
        reply = Comment.objects.create(
            user=user,
            resource=resource,
            content="Reply comment",
            parent=parent_comment,
        )
        assert reply.parent == parent_comment
        assert parent_comment.replies.count() == 1

    def test_comment_soft_delete(self, user):
        """Test soft delete of comment."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test description",
            created_by=user,
        )
        comment = Comment.objects.create(
            user=user,
            resource=resource,
            content="Test comment",
        )
        comment.is_deleted = True
        comment.save()
        assert comment.is_deleted is True