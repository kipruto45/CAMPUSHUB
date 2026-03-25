"""
Cloud Storage Models for CampusHub
Google Drive and OneDrive integration models
"""

import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class CloudStorageAccount(models.Model):
    """Model to store user's cloud storage connections"""
    
    class Provider(models.TextChoices):
        GOOGLE_DRIVE = 'google_drive', 'Google Drive'
        ONEDRIVE = 'onedrive', 'OneDrive'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cloud_storage_accounts'
    )
    provider = models.CharField(max_length=20, choices=Provider.choices)
    provider_user_id = models.CharField(max_length=255)  # ID from the cloud provider
    email = models.EmailField()
    display_name = models.CharField(max_length=255)
    avatar_url = models.URLField(null=True, blank=True)
    access_token = models.TextField()
    refresh_token = models.TextField(null=True, blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    storage_used = models.BigIntegerField(default=0)  # in bytes
    storage_total = models.BigIntegerField(default=0)  # in bytes
    last_sync = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cloud_storage_accounts'
        unique_together = [['user', 'provider']]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.provider}"
    
    @property
    def is_token_expired(self):
        if not self.token_expires_at:
            return False
        return timezone.now() >= self.token_expires_at
    
    def get_storage_used_display(self):
        """Return human readable storage used"""
        return self.storage_used
    
    def get_storage_total_display(self):
        """Return human readable storage total"""
        return self.storage_total


class CloudFile(models.Model):
    """Model to cache cloud file metadata"""
    
    class Provider(models.TextChoices):
        GOOGLE_DRIVE = 'google_drive', 'Google Drive'
        ONEDRIVE = 'onedrive', 'OneDrive'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        CloudStorageAccount,
        on_delete=models.CASCADE,
        related_name='files'
    )
    provider_file_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=255)
    size = models.BigIntegerField(default=0)
    modified_time = models.DateTimeField(null=True, blank=True)
    web_url = models.URLField(null=True, blank=True)
    download_url = models.URLField(null=True, blank=True)
    is_folder = models.BooleanField(default=False)
    parent_folder_id = models.CharField(max_length=255, null=True, blank=True)
    cached_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cloud_files'
        unique_together = [['account', 'provider_file_id']]
        ordering = ['-cached_at']
    
    def __str__(self):
        return f"{self.name} ({self.provider})"


class CloudImportHistory(models.Model):
    """Track imports from cloud storage to CampusHub"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cloud_imports'
    )
    account = models.ForeignKey(
        CloudStorageAccount,
        on_delete=models.CASCADE,
        related_name='imports'
    )
    cloud_file = models.ForeignKey(
        CloudFile,
        on_delete=models.CASCADE,
        related_name='imports'
    )
    resource = models.ForeignKey(
        'resources.Resource',
        on_delete=models.CASCADE,
        related_name='cloud_imports',
        null=True,
        blank=True
    )
    imported_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'cloud_import_history'
        ordering = ['-imported_at']


class CloudExportHistory(models.Model):
    """Track exports from CampusHub to cloud storage"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cloud_exports'
    )
    account = models.ForeignKey(
        CloudStorageAccount,
        on_delete=models.CASCADE,
        related_name='exports'
    )
    resource = models.ForeignKey(
        'resources.Resource',
        on_delete=models.CASCADE,
        related_name='cloud_exports'
    )
    cloud_file_id = models.CharField(max_length=255)
    cloud_file_name = models.CharField(max_length=255)
    exported_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'cloud_export_history'
        ordering = ['-exported_at']
