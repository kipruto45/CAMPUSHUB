"""
API Key Management System
Manage API keys for external integrations.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator
from uuid import uuid4
import secrets
import hashlib


class APIKey(models.Model):
    """
    API Keys for external integrations.
    """
    
    class KeyType(models.TextChoices):
        PERSONAL = 'personal', 'Personal'
        PROJECT = 'project', 'Project'
        SERVICE = 'service', 'Service'
        INTEGRATION = 'integration', 'Integration'
    
    class KeyStatus(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'
        EXPIRED = 'expired', 'Expired'
        REVOKED = 'revoked', 'Revoked'
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    
    # Key identity
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    key_type = models.CharField(max_length=20, choices=KeyType.choices, default=KeyType.PERSONAL)
    status = models.CharField(max_length=20, choices=KeyStatus.choices, default=KeyStatus.ACTIVE)
    
    # The key (hashed)
    key_hash = models.CharField(max_length=128, unique=True)
    key_prefix = models.CharField(max_length=16)  # First few chars for display
    
    # Key metadata
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    
    # Rate limiting
    rate_limit = models.IntegerField(
        default=1000,
        validators=[MinValueValidator(1)],
        help_text="Requests per hour"
    )
    rate_limit_remaining = models.IntegerField(default=1000)
    
    # Scopes/Permissions
    scopes = models.JSONField(
        default=list,
        help_text="List of allowed scopes/permissions"
    )
    
    # Constraints
    allowed_ips = models.JSONField(
        default=list,
        help_text="List of allowed IP addresses (empty = all)"
    )
    allowed_origins = models.JSONField(
        default=list,
        help_text="List of allowed CORS origins"
    )
    
    # Usage tracking
    total_requests = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    
    # Owner
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='api_keys'
    )
    
    # Metadata
    origin = models.CharField(max_length=100, blank=True)  # Web, Mobile, Server
    environment = models.CharField(max_length=50, default='production')  # development, staging, production
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_api_keys'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['key_hash']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.key_prefix}...)"
    
    @property
    def is_expired(self):
        """Check if key is expired."""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    @property
    def is_active(self):
        """Check if key is active."""
        return (self.status == self.KeyStatus.ACTIVE and 
                not self.is_expired)
    
    @classmethod
    def generate_key(cls):
        """Generate a new API key."""
        return secrets.token_urlsafe(32)
    
    @classmethod
    def create_key(cls, name, user, **kwargs):
        """Create a new API key."""
        raw_key = cls.generate_key()
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:8]
        
        api_key = cls.objects.create(
            name=name,
            user=user,
            key_hash=key_hash,
            key_prefix=key_prefix,
            **kwargs
        )
        
        # Return the raw key only once
        return api_key, raw_key
    
    def revoke(self):
        """Revoke this API key."""
        self.status = self.KeyStatus.REVOKED
        self.save()
    
    def deactivate(self):
        """Deactivate this API key."""
        self.status = self.KeyStatus.INACTIVE
        self.save()
    
    def activate(self):
        """Activate this API key."""
        if not self.is_expired:
            self.status = self.KeyStatus.ACTIVE
            self.save()
    
    def record_usage(self):
        """Record API key usage."""
        self.total_requests += 1
        self.rate_limit_remaining = max(0, self.rate_limit_remaining - 1)
        self.last_used_at = timezone.now()
        self.save(update_fields=['total_requests', 'rate_limit_remaining', 'last_used_at'])
    
    def record_error(self):
        """Record an error."""
        self.error_count += 1
        self.save(update_fields=['error_count'])
    
    def reset_rate_limit(self):
        """Reset rate limit counter."""
        self.rate_limit_remaining = self.rate_limit
        self.save(update_fields=['rate_limit_remaining'])
    
    @classmethod
    def verify_key(cls, raw_key):
        """Verify an API key."""
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        try:
            api_key = cls.objects.get(key_hash=key_hash)
            if api_key.is_active:
                return api_key
            return None
        except cls.DoesNotExist:
            return None


class APIKeyAccessLog(models.Model):
    """
    Log of API key access.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    api_key = models.ForeignKey(APIKey, on_delete=models.CASCADE, related_name='access_logs')
    
    timestamp = models.DateTimeField(default=timezone.now)
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=500)
    query_params = models.JSONField(default=dict)
    
    status_code = models.IntegerField()
    response_time_ms = models.IntegerField()
    
    ip_address = models.GenericIPAddressField(null=True)
    user_agent = models.CharField(max_length=500, blank=True)
    origin = models.CharField(max_length=100, blank=True)
    
    error_message = models.TextField(blank=True)
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_api_key_access_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['api_key', '-timestamp']),
            models.Index(fields=['-timestamp']),
        ]


class APIKeyService:
    """Service for API key management."""
    
    @staticmethod
    def get_user_keys(user):
        """Get all API keys for a user."""
        return APIKey.objects.filter(user=user)
    
    @staticmethod
    def create_project_key(name, user, project_id, scopes=None):
        """Create a project-level API key."""
        return APIKey.create_key(
            name=name,
            user=user,
            key_type=APIKey.KeyType.PROJECT,
            scopes=scopes or ['read'],
            origin='project',
            description=f"Project: {project_id}"
        )
    
    @staticmethod
    def create_service_key(name, user, service_name, scopes=None):
        """Create a service-level API key."""
        return APIKey.create_key(
            name=name,
            user=user,
            key_type=APIKey.KeyType.SERVICE,
            scopes=scopes or ['read', 'write'],
            origin='server',
            description=f"Service: {service_name}"
        )
    
    @staticmethod
    def get_usage_stats(api_key, days=30):
        """Get usage statistics for an API key."""
        from datetime import timedelta
        
        logs = APIKeyAccessLog.objects.filter(
            api_key=api_key,
            timestamp__gte=timezone.now() - timedelta(days=days)
        )
        
        total_requests = logs.count()
        error_requests = logs.filter(status_code__gte=400).count()
        
        # Group by day
        daily_stats = {}
        for log in logs:
            day = log.timestamp.date().isoformat()
            if day not in daily_stats:
                daily_stats[day] = {'requests': 0, 'errors': 0}
            daily_stats[day]['requests'] += 1
            if log.status_code >= 400:
                daily_stats[day]['errors'] += 1
        
        return {
            'total_requests': total_requests,
            'error_count': error_requests,
            'error_rate': round((error_requests / total_requests) * 100, 2) if total_requests > 0 else 0,
            'daily_stats': daily_stats,
            'rate_limit_remaining': api_key.rate_limit_remaining
        }
