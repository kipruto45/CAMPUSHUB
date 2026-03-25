"""
Tests for forums app.
"""
import pytest
from django.contrib.auth import get_user_model

from apps.forums.models import (
    Forum,
    ForumThread,
    ForumPost,
    ForumVote,
    ForumBookmark,
    ForumNotification,
)

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestForumModel:
    """Tests for Forum model."""

    def test_forum_creation(self):
        """Test forum creation."""
        forum = Forum.objects.create(
            name="Test Forum",
            slug="test-forum",
            description="A test forum",
        )
        assert forum.id is not None
        assert forum.name == "Test Forum"
        assert forum.slug == "test-forum"

    def test_forum_str(self):
        """Test forum string representation."""
        forum = Forum.objects.create(
            name="Test Forum",
            slug="test-forum",
            description="Test",
        )
        assert str(forum) == "Test Forum"

    def test_forum_thread_count_property(self):
        """Test thread_count property."""
        forum = Forum.objects.create(
            name="Test Forum",
            slug="test-forum",
            description="Test",
        )
        assert forum.thread_count == 0


@pytest.mark.django_db
class TestForumThreadModel:
    """Tests for ForumThread model."""

    def test_thread_creation(self, user):
        """Test thread creation."""
        forum = Forum.objects.create(
            name="Test Forum",
            slug="test-forum",
            description="Test",
        )
        thread = ForumThread.objects.create(
            forum=forum,
            author=user,
            title="Test Thread",
            content="Test content",
        )
        assert thread.id is not None
        assert thread.title == "Test Thread"

    def test_thread_str(self, user):
        """Test thread string representation."""
        forum = Forum.objects.create(
            name="Test Forum",
            slug="test-forum",
            description="Test",
        )
        thread = ForumThread.objects.create(
            forum=forum,
            author=user,
            title="Test Thread",
            content="Test",
        )
        assert str(thread) == "Test Thread"

    def test_thread_reply_count_property(self, user):
        """Test reply_count property."""
        forum = Forum.objects.create(
            name="Test Forum",
            slug="test-forum",
            description="Test",
        )
        thread = ForumThread.objects.create(
            forum=forum,
            author=user,
            title="Test Thread",
            content="Test",
        )
        assert thread.reply_count == 0


@pytest.mark.django_db
class TestForumPostModel:
    """Tests for ForumPost model."""

    def test_post_creation(self, user):
        """Test post creation."""
        forum = Forum.objects.create(
            name="Test Forum",
            slug="test-forum",
            description="Test",
        )
        thread = ForumThread.objects.create(
            forum=forum,
            author=user,
            title="Test Thread",
            content="Test",
        )
        post = ForumPost.objects.create(
            thread=thread,
            author=user,
            content="Test post content",
        )
        assert post.id is not None
        assert post.content == "Test post content"

    def test_post_str(self, user):
        """Test post string representation."""
        forum = Forum.objects.create(
            name="Test Forum",
            slug="test-forum",
            description="Test",
        )
        thread = ForumThread.objects.create(
            forum=forum,
            author=user,
            title="Test Thread",
            content="Test",
        )
        post = ForumPost.objects.create(
            thread=thread,
            author=user,
            content="Test",
        )
        assert user.email in str(post)

    def test_post_score_property(self, user):
        """Test score property."""
        forum = Forum.objects.create(
            name="Test Forum",
            slug="test-forum",
            description="Test",
        )
        thread = ForumThread.objects.create(
            forum=forum,
            author=user,
            title="Test Thread",
            content="Test",
        )
        post = ForumPost.objects.create(
            thread=thread,
            author=user,
            content="Test",
            upvotes=10,
            downvotes=3,
        )
        assert post.score == 7


@pytest.mark.django_db
class TestForumVoteModel:
    """Tests for ForumVote model."""

    def test_vote_creation(self, user):
        """Test vote creation."""
        forum = Forum.objects.create(
            name="Test Forum",
            slug="test-forum",
            description="Test",
        )
        thread = ForumThread.objects.create(
            forum=forum,
            author=user,
            title="Test Thread",
            content="Test",
        )
        post = ForumPost.objects.create(
            thread=thread,
            author=user,
            content="Test",
        )
        vote = ForumVote.objects.create(
            user=user,
            post=post,
            vote=1,
        )
        assert vote.id is not None
        assert vote.vote == 1


@pytest.mark.django_db
class TestForumBookmarkModel:
    """Tests for ForumBookmark model."""

    def test_bookmark_creation(self, user):
        """Test bookmark creation."""
        forum = Forum.objects.create(
            name="Test Forum",
            slug="test-forum",
            description="Test",
        )
        thread = ForumThread.objects.create(
            forum=forum,
            author=user,
            title="Test Thread",
            content="Test",
        )
        bookmark = ForumBookmark.objects.create(
            user=user,
            thread=thread,
        )
        assert bookmark.id is not None


@pytest.mark.django_db
class TestForumNotificationModel:
    """Tests for ForumNotification model."""

    def test_notification_creation(self, user):
        """Test notification creation."""
        forum = Forum.objects.create(
            name="Test Forum",
            slug="test-forum",
            description="Test",
        )
        thread = ForumThread.objects.create(
            forum=forum,
            author=user,
            title="Test Thread",
            content="Test",
        )
        notification = ForumNotification.objects.create(
            user=user,
            notification_type="reply",
            thread=thread,
            message="New reply",
        )
        assert notification.id is not None
        assert notification.notification_type == "reply"

    def test_notification_str(self, user):
        """Test notification string representation."""
        notification = ForumNotification.objects.create(
            user=user,
            notification_type="reply",
            message="Test",
        )
        assert user.email in str(notification)