"""
Social features models for CampusHub.
Includes messaging and user following.
"""

import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel

User = get_user_model()


class Follow(TimeStampedModel):
    """
    Model for user following relationships.
    """

    follower = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="following"
    )
    following = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="followers"
    )

    class Meta:
        app_label = "social"
        unique_together = ["follower", "following"]
        indexes = [
            models.Index(fields=["follower", "created_at"]),
            models.Index(fields=["following", "created_at"]),
        ]

    def __str__(self):
        return f"{self.follower.username} follows {self.following.username}"


class Message(TimeStampedModel):
    """
    Model for direct messages between users.
    """

    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sent_messages"
    )
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="received_messages"
    )
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "social"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
            models.Index(fields=["sender", "created_at"]),
        ]

    def __str__(self):
        return f"Message from {self.sender.username} to {self.recipient.username}"


class Conversation(TimeStampedModel):
    """
    Model for group conversations.
    """

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    members = models.ManyToManyField(User, related_name="conversations")
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_conversations"
    )
    is_group = models.BooleanField(default=False)

    class Meta:
        app_label = "social"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class ConversationMessage(TimeStampedModel):
    """
    Model for messages within conversations.
    """

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="conversation_messages"
    )
    body = models.TextField()
    is_read = models.BooleanField(default=False)

    class Meta:
        app_label = "social"
        ordering = ["created_at"]

    def __str__(self):
        return f"Message in {self.conversation.name}"


class UserBlock(TimeStampedModel):
    """
    Model for blocking users.
    """

    blocker = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="blocked_users"
    )
    blocked = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="blocked_by"
    )
    reason = models.TextField(blank=True)

    class Meta:
        app_label = "social"
        unique_together = ["blocker", "blocked"]

    def __str__(self):
        return f"{self.blocker.username} blocked {self.blocked.username}"


class FriendRequest(TimeStampedModel):
    """
    Model for friend requests.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
    ]

    from_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="friend_requests_sent"
    )
    to_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="friend_requests_received"
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")

    class Meta:
        app_label = "social"
        unique_together = ["from_user", "to_user"]
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"Friend request from {self.from_user.username} to {self.to_user.username}"
        )


class Friendship(TimeStampedModel):
    """
    Model for accepted friendships.
    """

    user1 = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="friendships1"
    )
    user2 = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="friendships2"
    )

    class Meta:
        app_label = "social"
        unique_together = ["user1", "user2"]

    def __str__(self):
        return f"{self.user1.username} and {self.user2.username} are friends"



class StudyGroup(TimeStampedModel):
    """
    Model for study groups where students can collaborate.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    STATUS_CHOICES = [
        ("active", "Active"),
        ("archived", "Archived"),
        ("completed", "Completed"),
    ]

    PRIVACY_CHOICES = [
        ("public", "Public"),
        ("private", "Private"),
        ("invite_only", "Invite Only"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField()
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="study_groups",
    )
    faculty = models.ForeignKey(
        "faculties.Faculty",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="study_groups",
    )
    department = models.ForeignKey(
        "faculties.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="study_groups",
    )
    year_of_study = models.PositiveIntegerField(null=True, blank=True)
    privacy = models.CharField(max_length=20, choices=PRIVACY_CHOICES, default="public")
    is_public = models.BooleanField(default=True)
    allow_member_invites = models.BooleanField(default=True)
    max_members = models.PositiveIntegerField(default=10)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_study_groups",
    )
    members = models.ManyToManyField(
        User,
        related_name="study_groups",
        through="StudyGroupMember",
    )
    cover_image = models.ImageField(upload_to="study_groups/covers/", null=True, blank=True)

    class Meta:
        app_label = "social"
        verbose_name = "Study Group"
        verbose_name_plural = "Study Groups"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["course", "status"]),
        ]

    def __str__(self):
        return self.name

    @property
    def member_count(self):
        return self.members.count()

    def is_member(self, user):
        return self.members.filter(id=user.id).exists()

    def is_creator(self, user):
        return self.creator_id == user.id


class StudyGroupMember(TimeStampedModel):
    """
    Through model for study group members with roles.
    """

    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("moderator", "Moderator"),
        ("member", "Member"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("pending", "Pending"),
        ("banned", "Banned"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="study_group_memberships")
    group = models.ForeignKey(StudyGroup, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "social"
        unique_together = ["user", "group"]
        indexes = [
            models.Index(fields=["group", "status"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"{self.user.username} in {self.group.name}"


class StudyGroupPost(TimeStampedModel):
    """
    Posts/discussions within a study group.
    """

    group = models.ForeignKey(StudyGroup, on_delete=models.CASCADE, related_name="posts")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="study_group_posts")
    title = models.CharField(max_length=255)
    content = models.TextField()
    is_pinned = models.BooleanField(default=False)
    is_announcement = models.BooleanField(default=False)
    likes_count = models.PositiveIntegerField(default=0)
    comments_count = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "social"
        verbose_name = "Study Group Post"
        verbose_name_plural = "Study Group Posts"
        ordering = ["-is_pinned", "-created_at"]
        indexes = [
            models.Index(fields=["group", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.title} in {self.group.name}"


class StudyGroupPostLike(TimeStampedModel):
    """
    Likes for study group posts.
    """

    post = models.ForeignKey(
        StudyGroupPost, 
        on_delete=models.CASCADE, 
        related_name="likes"
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name="study_group_post_likes"
    )

    class Meta:
        app_label = "social"
        unique_together = ["post", "user"]

    def __str__(self):
        return f"{self.user} liked post {self.post.id}"


class StudyGroupPostComment(TimeStampedModel):
    """
    Comments on study group posts.
    """

    post = models.ForeignKey(
        StudyGroupPost, 
        on_delete=models.CASCADE, 
        related_name="comments"
    )
    author = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name="study_group_post_comments"
    )
    content = models.TextField()

    class Meta:
        app_label = "social"
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author} on post {self.post.id}"


class StudyGroupResource(TimeStampedModel):
    """
    Shared resources within a study group.
    """

    group = models.ForeignKey(StudyGroup, on_delete=models.CASCADE, related_name="resources")
    resource = models.ForeignKey(
        "resources.Resource",
        on_delete=models.CASCADE,
        related_name="shared_in_groups",
    )
    shared_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="shared_in_groups")
    description = models.TextField(blank=True)

    class Meta:
        app_label = "social"
        unique_together = ["group", "resource"]
        verbose_name = "Study Group Resource"
        verbose_name_plural = "Study Group Resources"

    def __str__(self):
        return f"{self.resource.title} shared in {self.group.name}"


class StudyGroupInviteLink(TimeStampedModel):
    """
    Model for study group invite links.
    """

    group = models.ForeignKey(
        StudyGroup,
        on_delete=models.CASCADE,
        related_name="invite_links",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_invite_links",
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    use_count = models.PositiveIntegerField(default=0)
    allow_auto_join = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "social"
        verbose_name = "Study Group Invite Link"
        verbose_name_plural = "Study Group Invite Links"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["group", "is_active"]),
            models.Index(fields=["token", "is_active"]),
        ]

    def __str__(self):
        return f"Invite link for {self.group.name}"

    def is_valid(self):
        """Check if the invite link is still valid."""
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        if self.max_uses and self.use_count >= self.max_uses:
            return False
        return True

    @property
    def is_expired(self):
        return self.expires_at and self.expires_at < timezone.now()
