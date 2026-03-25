"""
Comprehensive tests for social module.
Tests for Follow, Message, Conversation, UserBlock, FriendRequest, Friendship, StudyGroup, and related models.
"""

import pytest
from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.social.models import (
    Follow,
    Message,
    Conversation,
    ConversationMessage,
    UserBlock,
    FriendRequest,
    Friendship,
    StudyGroup,
    StudyGroupMember,
    StudyGroupPost,
    StudyGroupPostLike,
    StudyGroupPostComment,
    StudyGroupResource,
    StudyGroupInviteLink,
)

User = get_user_model()


@pytest.fixture
def user1(db):
    """Create first test user."""
    return User.objects.create_user(
        email='user1@example.com',
        password='testpass123',
        role='STUDENT'
    )


@pytest.fixture
def user2(db):
    """Create second test user."""
    return User.objects.create_user(
        email='user2@example.com',
        password='testpass123',
        role='STUDENT'
    )


@pytest.fixture
def user3(db):
    """Create third test user."""
    return User.objects.create_user(
        email='user3@example.com',
        password='testpass123',
        role='INSTRUCTOR'
    )


# =========================
# Follow Tests
# =========================

@pytest.mark.django_db
class TestFollow:
    """Tests for Follow model."""

    def test_create_follow(self, user1, user2):
        """Test creating a follow relationship."""
        follow = Follow.objects.create(
            follower=user1,
            following=user2,
        )
        
        assert follow.id is not None
        assert follow.follower == user1
        assert follow.following == user2
        assert str(follow) == f"{user1.username} follows {user2.username}"

    def test_unique_follow(self, user1, user2):
        """Test that duplicate follows are prevented."""
        Follow.objects.create(follower=user1, following=user2)
        
        with pytest.raises(Exception):
            Follow.objects.create(follower=user1, following=user2)


# =========================
# Message Tests
# =========================

@pytest.mark.django_db
class TestMessage:
    """Tests for Message model."""

    def test_create_message(self, user1, user2):
        """Test creating a message."""
        message = Message.objects.create(
            sender=user1,
            recipient=user2,
            subject='Hello',
            body='Test message content',
        )
        
        assert message.id is not None
        assert message.sender == user1
        assert message.recipient == user2
        assert message.is_read is False
        assert str(message) == f"Message from {user1.username} to {user2.username}"

    def test_mark_as_read(self, user1, user2):
        """Test marking message as read."""
        message = Message.objects.create(
            sender=user1,
            recipient=user2,
            body='Test',
        )
        
        message.is_read = True
        message.read_at = timezone.now()
        message.save()
        
        assert message.is_read is True
        assert message.read_at is not None


# =========================
# Conversation Tests
# =========================

@pytest.mark.django_db
class TestConversation:
    """Tests for Conversation model."""

    def test_create_conversation(self, user1, user2):
        """Test creating a conversation."""
        conversation = Conversation.objects.create(
            name='Test Conversation',
            created_by=user1,
            is_group=False,
        )
        conversation.members.add(user1, user2)
        
        assert conversation.id is not None
        assert conversation.name == 'Test Conversation'
        assert str(conversation) == 'Test Conversation'

    def test_create_group_conversation(self, user1, user2, user3):
        """Test creating a group conversation."""
        conversation = Conversation.objects.create(
            name='Study Group Chat',
            description='Chat for study group',
            created_by=user1,
            is_group=True,
        )
        conversation.members.add(user1, user2, user3)
        
        assert conversation.is_group is True
        assert conversation.members.count() == 3


@pytest.mark.django_db
class TestConversationMessage:
    """Tests for ConversationMessage model."""

    def test_create_conversation_message(self, user1, user2):
        """Test creating a conversation message."""
        conversation = Conversation.objects.create(
            name='Test',
            created_by=user1,
        )
        conversation.members.add(user1, user2)
        
        message = ConversationMessage.objects.create(
            conversation=conversation,
            sender=user1,
            body='Hello everyone!',
        )
        
        assert message.id is not None
        assert message.body == 'Hello everyone!'
        assert message.is_read is False


# =========================
# UserBlock Tests
# =========================

@pytest.mark.django_db
class TestUserBlock:
    """Tests for UserBlock model."""

    def test_create_block(self, user1, user2):
        """Test blocking a user."""
        block = UserBlock.objects.create(
            blocker=user1,
            blocked=user2,
            reason='Inappropriate behavior',
        )
        
        assert block.id is not None
        assert block.blocker == user1
        assert block.blocked == user2
        assert str(block) == f"{user1.username} blocked {user2.username}"


# =========================
# FriendRequest Tests
# =========================

@pytest.mark.django_db
class TestFriendRequest:
    """Tests for FriendRequest model."""

    def test_create_friend_request(self, user1, user2):
        """Test creating a friend request."""
        request = FriendRequest.objects.create(
            from_user=user1,
            to_user=user2,
        )
        
        assert request.id is not None
        assert request.from_user == user1
        assert request.to_user == user2
        assert request.status == 'pending'
        assert str(user1.username) in str(request)

    def test_accept_friend_request(self, user1, user2):
        """Test accepting a friend request."""
        request = FriendRequest.objects.create(
            from_user=user1,
            to_user=user2,
        )
        
        request.status = 'accepted'
        request.save()
        
        assert request.status == 'accepted'

    def test_reject_friend_request(self, user1, user2):
        """Test rejecting a friend request."""
        request = FriendRequest.objects.create(
            from_user=user1,
            to_user=user2,
        )
        
        request.status = 'rejected'
        request.save()
        
        assert request.status == 'rejected'


# =========================
# Friendship Tests
# =========================

@pytest.mark.django_db
class TestFriendship:
    """Tests for Friendship model."""

    def test_create_friendship(self, user1, user2):
        """Test creating a friendship."""
        friendship = Friendship.objects.create(
            user1=user1,
            user2=user2,
        )
        
        assert friendship.id is not None
        assert str(friendship) == f"{user1.username} and {user2.username} are friends"


# =========================
# StudyGroup Tests
# =========================

@pytest.mark.django_db
class TestStudyGroup:
    """Tests for StudyGroup model."""

    def test_create_study_group(self, user1):
        """Test creating a study group."""
        group = StudyGroup.objects.create(
            name='Python Study Group',
            description='Learn Python together',
            creator=user1,
            privacy='public',
        )
        
        assert group.id is not None
        assert group.name == 'Python Study Group'
        assert group.status == 'active'
        assert str(group) == 'Python Study Group'

    def test_study_group_privacy_choices(self, user1):
        """Test all privacy choices."""
        privacy_choices = ['public', 'private', 'invite_only']
        
        for privacy in privacy_choices:
            group = StudyGroup.objects.create(
                name=f'Test {privacy}',
                description='Test',
                creator=user1,
                privacy=privacy,
            )
            assert group.privacy == privacy

    def test_study_group_status_choices(self, user1):
        """Test all status choices."""
        status_choices = ['active', 'archived', 'completed']
        
        for status in status_choices:
            group = StudyGroup.objects.create(
                name=f'Test {status}',
                description='Test',
                creator=user1,
                status=status,
            )
            assert group.status == status

    def test_member_count_property(self, user1, user2):
        """Test member_count property."""
        group = StudyGroup.objects.create(
            name='Test Group',
            description='Test',
            creator=user1,
        )
        group.members.add(user1, user2)
        
        assert group.member_count == 2

    def test_is_member(self, user1, user2):
        """Test is_member method."""
        group = StudyGroup.objects.create(
            name='Test Group',
            description='Test',
            creator=user1,
        )
        group.members.add(user1)
        
        assert group.is_member(user1) is True
        assert group.is_member(user2) is False

    def test_is_creator(self, user1, user2):
        """Test is_creator method."""
        group = StudyGroup.objects.create(
            name='Test Group',
            description='Test',
            creator=user1,
        )
        
        assert group.is_creator(user1) is True
        assert group.is_creator(user2) is False


@pytest.mark.django_db
class TestStudyGroupMember:
    """Tests for StudyGroupMember model."""

    def test_create_member(self, user1, user2):
        """Test adding a member to a study group."""
        group = StudyGroup.objects.create(
            name='Test Group',
            description='Test',
            creator=user1,
        )
        
        member = StudyGroupMember.objects.create(
            user=user2,
            group=group,
            role='member',
            status='active',
        )
        
        assert member.id is not None
        assert member.role == 'member'
        assert member.status == 'active'
        assert str(member) == f"{user2.username} in {group.name}"

    def test_member_roles(self, user1, user2):
        """Test all member role choices."""
        roles = ['admin', 'moderator', 'member']
        
        group = StudyGroup.objects.create(
            name='Test Group',
            description='Test',
            creator=user1,
        )
        
        for role in roles:
            member = StudyGroupMember.objects.create(
                user=user2,
                group=group,
                role=role,
            )
            assert member.role == role


@pytest.mark.django_db
class TestStudyGroupPost:
    """Tests for StudyGroupPost model."""

    def test_create_post(self, user1):
        """Test creating a study group post."""
        group = StudyGroup.objects.create(
            name='Test Group',
            description='Test',
            creator=user1,
        )
        
        post = StudyGroupPost.objects.create(
            group=group,
            author=user1,
            title='Welcome Post',
            content='Welcome to the study group!',
        )
        
        assert post.id is not None
        assert post.title == 'Welcome Post'
        assert post.is_pinned is False
        assert post.likes_count == 0

    def test_pinned_post(self, user1):
        """Test creating a pinned post."""
        group = StudyGroup.objects.create(
            name='Test Group',
            description='Test',
            creator=user1,
        )
        
        post = StudyGroupPost.objects.create(
            group=group,
            author=user1,
            title='Important',
            content='Important announcement',
            is_pinned=True,
        )
        
        assert post.is_pinned is True


@pytest.mark.django_db
class TestStudyGroupPostLike:
    """Tests for StudyGroupPostLike model."""

    def test_create_like(self, user1, user2):
        """Test liking a post."""
        group = StudyGroup.objects.create(
            name='Test Group',
            description='Test',
            creator=user1,
        )
        
        post = StudyGroupPost.objects.create(
            group=group,
            author=user1,
            title='Test',
            content='Test',
        )
        
        like = StudyGroupPostLike.objects.create(
            post=post,
            user=user2,
        )
        
        assert like.id is not None
        assert str(like) == f"{user2} liked post {post.id}"


@pytest.mark.django_db
class TestStudyGroupPostComment:
    """Tests for StudyGroupPostComment model."""

    def test_create_comment(self, user1, user2):
        """Test commenting on a post."""
        group = StudyGroup.objects.create(
            name='Test Group',
            description='Test',
            creator=user1,
        )
        
        post = StudyGroupPost.objects.create(
            group=group,
            author=user1,
            title='Test',
            content='Test',
        )
        
        comment = StudyGroupPostComment.objects.create(
            post=post,
            author=user2,
            content='Great post!',
        )
        
        assert comment.id is not None
        assert comment.content == 'Great post!'


@pytest.mark.django_db
class TestStudyGroupInviteLink:
    """Tests for StudyGroupInviteLink model."""

    def test_create_invite_link(self, user1):
        """Test creating an invite link."""
        group = StudyGroup.objects.create(
            name='Test Group',
            description='Test',
            creator=user1,
        )
        
        invite_link = StudyGroupInviteLink.objects.create(
            group=group,
            created_by=user1,
            token='test-token-123',
        )
        
        assert invite_link.id is not None
        assert invite_link.token == 'test-token-123'
        assert invite_link.is_active is True
        assert str(invite_link) == f"Invite link for {group.name}"

    def test_is_valid(self, user1):
        """Test is_valid method."""
        group = StudyGroup.objects.create(
            name='Test Group',
            description='Test',
            creator=user1,
        )
        
        # Active, not expired, not at max uses
        valid_link = StudyGroupInviteLink.objects.create(
            group=group,
            created_by=user1,
            token='valid-token',
            is_active=True,
        )
        assert valid_link.is_valid() is True
        
        # Inactive
        invalid_link = StudyGroupInviteLink.objects.create(
            group=group,
            created_by=user1,
            token='inactive-token',
            is_active=False,
        )
        assert invalid_link.is_valid() is False

    def test_is_expired_property(self, user1):
        """Test is_expired property."""
        group = StudyGroup.objects.create(
            name='Test Group',
            description='Test',
            creator=user1,
        )
        
        # Not expired
        link = StudyGroupInviteLink.objects.create(
            group=group,
            created_by=user1,
            token='token1',
            expires_at=timezone.now() + timedelta(days=1),
        )
        assert link.is_expired is False
        
        # Expired
        expired_link = StudyGroupInviteLink.objects.create(
            group=group,
            created_by=user1,
            token='token2',
            expires_at=timezone.now() - timedelta(days=1),
        )
        assert expired_link.is_expired is True
