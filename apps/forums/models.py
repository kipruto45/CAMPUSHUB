"""
Models for Discussion Forums
Threaded discussions with voting and best answers
"""

import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class Forum(models.Model):
    """Discussion forum/category"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    
    # Course association (optional)
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='forums'
    )
    
    # Settings
    is_public = models.BooleanField(default=True)
    require_moderation = models.BooleanField(default=False)
    allow_anonymous = models.BooleanField(default=False)
    
    # Moderators
    moderators = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='moderated_forums',
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Forums'
    
    def __str__(self):
        return self.name
    
    @property
    def thread_count(self):
        return self.threads.count()
    
    @property
    def post_count(self):
        return ForumPost.objects.filter(thread__forum=self).count()


class ForumThread(models.Model):
    """Discussion thread within a forum"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    forum = models.ForeignKey(
        Forum,
        on_delete=models.CASCADE,
        related_name='threads'
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='forum_threads'
    )
    
    title = models.CharField(max_length=255)
    content = models.TextField()
    
    # Status
    is_pinned = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    is_answered = models.BooleanField(default=False)
    
    # Best answer
    best_answer = models.ForeignKey(
        'ForumPost',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='best_for'
    )
    
    # Counts
    view_count = models.IntegerField(default=0)
    vote_count = models.IntegerField(default=0)
    
    # Tags
    tags = models.JSONField(default=list)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_pinned', '-created_at']
        indexes = [
            models.Index(fields=['forum', '-created_at']),
        ]
    
    def __str__(self):
        return self.title
    
    @property
    def reply_count(self):
        return self.posts.count()


class ForumPost(models.Model):
    """Post/reply in a thread"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    thread = models.ForeignKey(
        ForumThread,
        on_delete=models.CASCADE,
        related_name='posts'
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='forum_posts'
    )
    
    # Reply to (for nested replies)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies'
    )
    
    content = models.TextField()
    
    # Voting
    upvotes = models.IntegerField(default=0)
    downvotes = models.IntegerField(default=0)
    
    # Status
    is_accepted = models.BooleanField(default=False)  # Best answer
    is_edited = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Post by {self.author.email} in {self.thread.title}"
    
    @property
    def score(self):
        return self.upvotes - self.downvotes


class ForumVote(models.Model):
    """Vote on a post"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='forum_votes'
    )
    post = models.ForeignKey(
        ForumPost,
        on_delete=models.CASCADE,
        related_name='votes'
    )
    
    VOTE_CHOICES = [
        (1, 'Upvote'),
        (-1, 'Downvote'),
    ]
    vote = models.IntegerField(choices=VOTE_CHOICES)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'post']


class ForumBookmark(models.Model):
    """User bookmarked threads"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='forum_bookmarks'
    )
    thread = models.ForeignKey(
        ForumThread,
        on_delete=models.CASCADE,
        related_name='bookmarks'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'thread']


class ForumNotification(models.Model):
    """Notification for forum activity"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='forum_notifications'
    )
    
    NOTIFICATION_TYPES = [
        ('reply', 'New Reply'),
        ('mention', 'Mention'),
        ('vote', 'Vote'),
        ('best_answer', 'Best Answer'),
    ]
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    
    thread = models.ForeignKey(
        ForumThread,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    post = models.ForeignKey(
        ForumPost,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.notification_type} for {self.user.email}"
    
    def __str__(self):
        return f"{self.notification_type} for {self.user.email}"
