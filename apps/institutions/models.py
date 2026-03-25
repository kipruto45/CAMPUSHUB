"""
Models for Institutions (Multi-Tenant Support)
University and institution management
"""

import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class Institution(models.Model):
    """University or Institution"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Basic info
    name = models.CharField(max_length=255)
    short_name = models.CharField(max_length=50, blank=True)  # e.g., "MIT"
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    
    # Contact
    email_domain = models.CharField(max_length=255, help_text="e.g., @mit.edu")
    website = models.URLField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    
    # Branding
    logo = models.ImageField(upload_to='institutions/logos/', null=True, blank=True)
    primary_color = models.CharField(max_length=7, default='#007bff')  # Hex color
    secondary_color = models.CharField(max_length=7, default='#6c757d')
    
    # Type
    TYPE_CHOICES = [
        ('university', 'University'),
        ('college', 'College'),
        ('high_school', 'High School'),
        ('bootcamp', 'Bootcamp'),
        ('online', 'Online Learning Platform'),
        ('other', 'Other'),
    ]
    institution_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='university')
    
    # Settings
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    
    # Features
    require_email_verification = models.BooleanField(default=True)
    allow_registration = models.BooleanField(default=True)
    max_users = models.IntegerField(null=True, blank=True)
    
    # Limits
    max_storage_gb = models.IntegerField(default=10)
    max_file_size_mb = models.IntegerField(default=100)
    
    # Subscription
    subscription_tier = models.CharField(
        max_length=20,
        choices=[
            ('free', 'Free'),
            ('basic', 'Basic'),
            ('premium', 'Premium'),
            ('enterprise', 'Enterprise'),
        ],
        default='free'
    )
    subscription_expires = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Institutions'
    
    def __str__(self):
        return self.name
    
    @property
    def is_subscription_active(self):
        if not self.subscription_expires:
            return self.subscription_tier == 'free'
        return timezone.now() < self.subscription_expires
    
    @property
    def user_count(self):
        return self.users.count()


class InstitutionAdmin(models.Model):
    """Admin users for an institution"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='institution_admin_roles'
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name='admins'
    )
    
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('admin', 'Admin'),
        ('moderator', 'Moderator'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='admin')
    
    can_manage_users = models.BooleanField(default=False)
    can_manage_content = models.BooleanField(default=False)
    can_manage_settings = models.BooleanField(default=False)
    can_view_analytics = models.BooleanField(default=False)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'institution']
        verbose_name_plural = 'Institution Admins'
    
    def __str__(self):
        return f"{self.user.email} - {self.institution.name} ({self.role})"


class Department(models.Model):
    """Department within an institution"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name='departments'
    )
    
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20)  # e.g., "CS" for Computer Science
    description = models.TextField(blank=True)
    
    head = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headed_departments'
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['institution', 'code']
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - {self.institution.short_name}"


class InstitutionInvitation(models.Model):
    """Invitation to join an institution"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name='invitations'
    )
    
    email = models.EmailField()
    role = models.CharField(
        max_length=20,
        choices=[
            ('student', 'Student'),
            ('teacher', 'Teacher'),
            ('staff', 'Staff'),
        ]
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invitations'
    )
    
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_invitations'
    )
    
    token = models.CharField(max_length=64, unique=True)
    accepted = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Invitation for {self.email} to {self.institution.name}"
    
    def is_valid(self):
        return not self.accepted and timezone.now() < self.expires_at
