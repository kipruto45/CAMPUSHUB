"""
Content Calendar - Schedule and manage content publishing.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from uuid import uuid4


class ContentCalendarEvent(models.Model):
    """
    Events for content calendar - schedule announcements, posts, and content.
    """
    
    class EventType(models.TextChoices):
        ANNOUNCEMENT = 'announcement', 'Announcement'
        POST = 'post', 'Social Post'
        EMAIL = 'email', 'Email Campaign'
        NOTIFICATION = 'notification', 'Push Notification'
        PROMOTION = 'promotion', 'Promotion'
        MAINTENANCE = 'maintenance', 'Maintenance'
        EVENT = 'event', 'Event'
    
    class EventStatus(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SCHEDULED = 'scheduled', 'Scheduled'
        PUBLISHED = 'published', 'Published'
        CANCELLED = 'cancelled', 'Cancelled'
        COMPLETED = 'completed', 'Completed'
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    status = models.CharField(max_length=20, choices=EventStatus.choices, default=EventStatus.DRAFT)
    
    # Scheduling
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField(null=True, blank=True)
    timezone = models.CharField(max_length=50, default='UTC')
    is_all_day = models.BooleanField(default=False)
    
    # Content reference
    related_object_type = models.CharField(max_length=50, blank=True)  # announcement, resource, etc.
    related_object_id = models.UUIDField(null=True, blank=True)
    
    # Target audience
    target_faculty_id = models.UUIDField(null=True, blank=True)
    target_department_id = models.UUIDField(null=True, blank=True)
    target_year_level = models.IntegerField(null=True, blank=True)
    is_global = models.BooleanField(default=True)
    
    # Recurrence
    recurrence_rule = models.CharField(max_length=255, blank=True)  # RRULE format
    
    # Visual
    color = models.CharField(max_length=7, default='#3B82F6')  # Hex color
    icon = models.CharField(max_length=50, blank=True)
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='calendar_events_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Publishing
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='calendar_events_published'
    )
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_content_calendar'
        ordering = ['start_datetime']
        indexes = [
            models.Index(fields=['start_datetime']),
            models.Index(fields=['event_type']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.event_type})"
    
    def publish(self, user):
        """Publish the event."""
        self.status = self.EventStatus.PUBLISHED
        self.published_at = timezone.now()
        self.published_by = user
        self.save()
    
    def cancel(self):
        """Cancel the event."""
        self.status = self.EventStatus.CANCELLED
        self.save()
    
    @property
    def is_upcoming(self):
        """Check if event is upcoming."""
        return self.start_datetime > timezone.now() and self.status in [self.EventStatus.DRAFT, self.EventStatus.SCHEDULED]
    
    @property
    def is_past(self):
        """Check if event is in the past."""
        return self.end_datetime and self.end_datetime < timezone.now()


class CalendarCategory(models.Model):
    """Custom categories for calendar events."""
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7)
    icon = models.CharField(max_length=50, blank=True)
    event_types = models.JSONField(default=list)  # List of event types
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_calendar_categories'
        verbose_name_plural = 'Calendar Categories'
    
    def __str__(self):
        return self.name


class CalendarTemplate(models.Model):
    """Templates for recurring calendar events."""
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    event_type = models.CharField(max_length=20, choices=ContentCalendarEvent.EventType.choices)
    
    # Default values
    default_duration_hours = models.IntegerField(default=1)
    default_color = models.CharField(max_length=7, default='#3B82F6')
    default_target = models.JSONField(default=dict)
    
    # Template content
    title_template = models.CharField(max_length=255)
    description_template = models.TextField(blank=True)
    
    recurrence_pattern = models.CharField(max_length=255)  # e.g., "WEEKLY:MONDAY"
    
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_calendar_templates'
    
    def __str__(self):
        return self.name
    
    def create_events(self, start_date, end_date, user):
        """Generate events from template."""
        from datetime import timedelta
        
        events = []
        current_date = start_date
        
        while current_date <= end_date:
            event = ContentCalendarEvent(
                title=self.title_template,
                description=self.description_template,
                event_type=self.event_type,
                start_datetime=current_date,
                end_datetime=current_date + timedelta(hours=self.default_duration_hours),
                color=self.default_color,
                created_by=user,
                related_object_type='template',
                related_object_id=self.id
            )
            events.append(event)
            
            # Move to next occurrence based on recurrence
            if 'WEEKLY' in self.recurrence_pattern:
                current_date += timedelta(weeks=1)
            elif 'DAILY' in self.recurrence_pattern:
                current_date += timedelta(days=1)
            elif 'MONTHLY' in self.recurrence_pattern:
                current_date += timedelta(days=30)
            else:
                break
        
        return ContentCalendarEvent.objects.bulk_create(events)
