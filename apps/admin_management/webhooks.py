"""
Webhook Configuration System
Manage webhooks for event notifications to external services.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import URLValidator, MinValueValidator
from django.core.exceptions import ValidationError
from uuid import uuid4
import secrets
import hashlib
import json


def validate_url(value):
    """Validate URL field."""
    validator = URLValidator()
    try:
        validator(value)
    except ValidationError:
        raise ValidationError('Invalid URL format')


class Webhook(models.Model):
    """
    Webhook endpoints for event notifications.
    """
    
    class WebhookEvent(models.TextChoices):
        # User events
        USER_REGISTERED = 'user.registered', 'User Registered'
        USER_UPDATED = 'user.updated', 'User Updated'
        USER_DELETED = 'user.deleted', 'User Deleted'
        
        # Resource events
        RESOURCE_CREATED = 'resource.created', 'Resource Created'
        RESOURCE_UPDATED = 'resource.updated', 'Resource Updated'
        RESOURCE_DELETED = 'resource.deleted', 'Resource Deleted'
        RESOURCE_DOWNLOADED = 'resource.downloaded', 'Resource Downloaded'
        
        # Announcement events
        ANNOUNCEMENT_CREATED = 'announcement.created', 'Announcement Created'
        ANNOUNCEMENT_PUBLISHED = 'announcement.published', 'Announcement Published'
        
        # Report events
        REPORT_SUBMITTED = 'report.submitted', 'Report Submitted'
        REPORT_RESOLVED = 'report.resolved', 'Report Resolved'
        
        # Moderation events
        CONTENT_FLAGGED = 'moderation.content_flagged', 'Content Flagged'
        CONTENT_APPROVED = 'moderation.content_approved', 'Content Approved'
        
        # Gamification events
        BADGE_EARNED = 'gamification.badge_earned', 'Badge Earned'
        POINTS_AWARDED = 'gamification.points_awarded', 'Points Awarded'
        
        # System events
        SYSTEM_ALERT = 'system.alert', 'System Alert'
        API_USAGE_THRESHOLD = 'system.api_limit', 'API Usage Threshold'
        
        # Custom events
        CUSTOM = 'custom', 'Custom Event'
    
    class WebhookStatus(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'
        FAILED = 'failed', 'Failed'
        SUSPENDED = 'suspended', 'Suspended'
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    
    # Identity
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=WebhookStatus.choices, default=WebhookStatus.ACTIVE)
    
    # Endpoint
    url = models.URLField(max_length=500)
    secret = models.CharField(max_length=128, blank=True)
    
    # Events to subscribe
    events = models.JSONField(default=list, help_text="List of event types to subscribe to")
    
    # Authentication
    auth_type = models.CharField(
        max_length=20,
        choices=[
            ('none', 'None'),
            ('basic', 'Basic Auth'),
            ('bearer', 'Bearer Token'),
            ('api_key', 'API Key'),
        ],
        default='none'
    )
    auth_credentials = models.JSONField(default=dict, blank=True)
    
    # Configuration
    is_active = models.BooleanField(default=True)
    retry_on_failure = models.BooleanField(default=True)
    max_retries = models.IntegerField(default=3)
    timeout_seconds = models.IntegerField(default=30)
    
    # Filtering
    event_filters = models.JSONField(default=dict, blank=True)  # Filter events by criteria
    
    # Headers
    custom_headers = models.JSONField(default=dict, blank=True)
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_webhooks'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Statistics
    total_deliveries = models.IntegerField(default=0)
    successful_deliveries = models.IntegerField(default=0)
    failed_deliveries = models.IntegerField(default=0)
    last_delivered_at = models.DateTimeField(null=True, blank=True)
    last_failed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_webhooks'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.url})"
    
    def generate_secret(self):
        """Generate a new webhook secret."""
        self.secret = secrets.token_hex(32)
        self.save()
        return self.secret
    
    def subscribe_event(self, event_type):
        """Subscribe to an event type."""
        if event_type not in self.events:
            self.events.append(event_type)
            self.save()
    
    def unsubscribe_event(self, event_type):
        """Unsubscribe from an event type."""
        if event_type in self.events:
            self.events.remove(event_type)
            self.save()
    
    def is_subscribed_to(self, event_type):
        """Check if subscribed to event type."""
        return event_type in self.events or '*' in self.events
    
    def trigger(self, event_type, payload):
        """Trigger webhook with event."""
        if self.status != self.WebhookStatus.ACTIVE:
            return None
        
        if not self.is_subscribed_to(event_type):
            return None
        
        delivery = WebhookDelivery.objects.create(
            webhook=self,
            event_type=event_type,
            payload=payload
        )
        
        delivery.send()
        return delivery
    
    @property
    def success_rate(self):
        """Calculate delivery success rate."""
        if self.total_deliveries == 0:
            return 100
        return round((self.successful_deliveries / self.total_deliveries) * 100, 2)


class WebhookDelivery(models.Model):
    """
    Individual webhook delivery attempts.
    """
    
    class DeliveryStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENDING = 'sending', 'Sending'
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'
        RETRYING = 'retrying', 'Retrying'
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    webhook = models.ForeignKey(Webhook, on_delete=models.CASCADE, related_name='deliveries')
    
    event_type = models.CharField(max_length=100)
    payload = models.JSONField(default=dict)
    
    status = models.CharField(max_length=20, choices=DeliveryStatus.choices, default=DeliveryStatus.PENDING)
    
    # Request
    request_headers = models.JSONField(default=dict)
    request_body = models.TextField(blank=True)
    
    # Response
    response_status_code = models.IntegerField(null=True, blank=True)
    response_headers = models.JSONField(default=dict)
    response_body = models.TextField(blank=True)
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    
    # Retry
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=3)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    
    # Error
    error_message = models.TextField(blank=True)
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_webhook_deliveries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['webhook', '-created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.status}"
    
    def send(self):
        """Send the webhook."""
        import requests
        
        self.status = self.DeliveryStatus.SENDING
        self.attempts += 1
        self.save()
        
        # Build request
        headers = {
            'Content-Type': 'application/json',
            'X-Webhook-Event': self.event_type,
            'X-Webhook-ID': str(self.webhook.id),
        }
        
        # Add signature
        if self.webhook.secret:
            import hmac
            signature = hmac.new(
                self.webhook.secret.encode(),
                json.dumps(self.payload).encode(),
                'sha256'
            ).hexdigest()
            headers['X-Webhook-Signature'] = f'sha256={signature}'
        
        # Add custom headers
        headers.update(self.webhook.custom_headers or {})
        
        # Add auth headers
        if self.webhook.auth_type == 'bearer':
            headers['Authorization'] = f"Bearer {self.webhook.auth_credentials.get('token', '')}"
        elif self.webhook.auth_type == 'api_key':
            headers['X-API-Key'] = self.webhook.auth_credentials.get('key', '')
        
        start_time = timezone.now()
        
        try:
            response = requests.post(
                self.webhook.url,
                json=self.payload,
                headers=headers,
                timeout=self.webhook.timeout_seconds
            )
            
            end_time = timezone.now()
            self.duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            self.response_status_code = response.status_code
            self.response_headers = dict(response.headers)
            self.response_body = response.text[:5000]  # Limit response size
            
            if 200 <= response.status_code < 300:
                self.status = self.DeliveryStatus.SUCCESS
                self.webhook.successful_deliveries += 1
                self.webhook.last_delivered_at = timezone.now()
            else:
                self.status = self.DeliveryStatus.FAILED
                self.error_message = f"HTTP {response.status_code}"
                self.webhook.failed_deliveries += 1
                self.webhook.last_failed_at = timezone.now()
            
            self.webhook.total_deliveries += 1
            self.webhook.save()
            self.save()
            
        except requests.Timeout:
            self.status = self.DeliveryStatus.FAILED
            self.error_message = "Request timeout"
            self.handle_retry()
        except requests.RequestException as e:
            self.status = self.DeliveryStatus.FAILED
            self.error_message = str(e)
            self.handle_retry()
        
        self.completed_at = timezone.now()
        self.save()
    
    def handle_retry(self):
        """Handle retry logic."""
        if self.webhook.retry_on_failure and self.attempts < self.max_attempts:
            self.status = self.DeliveryStatus.RETRYING
            self.next_retry_at = timezone.now() + timezone.timedelta(
                minutes=2 ** self.attempts  # Exponential backoff
            )
            self.save()
            # Schedule retry task (would use Celery in production)
    
    @property
    def is_successful(self):
        return self.status == self.DeliveryStatus.SUCCESS


class WebhookEventLog(models.Model):
    """
    Log of all webhook events.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    
    event_type = models.CharField(max_length=100)
    payload = models.JSONField(default=dict)
    timestamp = models.DateTimeField(default=timezone.now)
    
    delivered_to = models.JSONField(default=list)  # List of webhook IDs
    delivery_count = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_webhook_events'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['event_type', '-timestamp']),
        ]


class WebhookService:
    """Service for webhook management."""
    
    @staticmethod
    def trigger_event(event_type, payload, filters=None):
        """Trigger all webhooks subscribed to an event."""
        webhooks = Webhook.objects.filter(
            status=Webhook.WebhookStatus.ACTIVE,
            is_active=True
        )
        
        # Filter webhooks
        if filters:
            webhooks = webhooks.filter(event_filters__contains=filters)
        
        event_log = WebhookEventLog.objects.create(
            event_type=event_type,
            payload=payload
        )
        
        delivered_to = []
        
        for webhook in webhooks:
            if webhook.is_subscribed_to(event_type):
                delivery = webhook.trigger(event_type, payload)
                if delivery:
                    delivered_to.append(str(webhook.id))
        
        event_log.delivered_to = delivered_to
        event_log.delivery_count = len(delivered_to)
        event_log.save()
        
        return event_log
    
    @staticmethod
    def test_webhook(webhook_id):
        """Test a webhook endpoint."""
        webhook = Webhook.objects.get(id=webhook_id)
        
        test_payload = {
            'event': 'test',
            'timestamp': timezone.now().isoformat(),
            'message': 'This is a test webhook delivery'
        }
        
        delivery = webhook.trigger('test', test_payload)
        return delivery
    
    @staticmethod
    def get_available_events():
        """Get list of available webhook events."""
        return [
            {'value': event.value, 'label': event.label}
            for event in Webhook.WebhookEvent
        ]
