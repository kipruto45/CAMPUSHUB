"""
Incident Management System
Track, manage, and resolve system incidents.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from uuid import uuid4


class Incident(models.Model):
    """
    System incidents tracking.
    """
    
    class Severity(models.TextChoices):
        CRITICAL = 'critical', 'Critical'
        HIGH = 'high', 'High'
        MEDIUM = 'medium', 'Medium'
        LOW = 'low', 'Low'
        INFO = 'info', 'Info'
    
    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        INVESTIGATING = 'investigating', 'Investigating'
        IDENTIFIED = 'identified', 'Identified'
        MONITORING = 'monitoring', 'Monitoring'
        RESOLVED = 'resolved', 'Resolved'
        CLOSED = 'closed', 'Closed'
    
    class IncidentType(models.TextChoices):
        BUG = 'bug', 'Bug'
        PERFORMANCE = 'performance', 'Performance Issue'
        SECURITY = 'security', 'Security'
        OUTAGE = 'outage', 'Service Outage'
        DATA = 'data', 'Data Issue'
        INFRASTRUCTURE = 'infrastructure', 'Infrastructure'
        USER_REPORT = 'user_report', 'User Report'
        AUTOMATED = 'automated', 'Automated Alert'
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField()
    
    # Classification
    incident_type = models.CharField(max_length=20, choices=IncidentType.choices)
    severity = models.CharField(max_length=20, choices=Severity.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    
    # Timeline
    started_at = models.DateTimeField(default=timezone.now)
    identified_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    # Related systems
    affected_systems = models.JSONField(default=list)  # List of affected components
    related_resources = models.JSONField(default=list)  # Related resource IDs
    
    # Impact
    affected_users_count = models.IntegerField(default=0)
    impact_summary = models.TextField(blank=True)
    
    # Root cause
    root_cause = models.TextField(blank=True)
    resolution = models.TextField(blank=True)
    
    # Assignment
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_incidents'
    )
    watchers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='watched_incidents'
    )
    
    # Metadata
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='reported_incidents'
    )
    source = models.CharField(max_length=50, default='manual')  # manual, automated, user
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # External references
    jira_ticket = models.CharField(max_length=100, blank=True)
    slack_channel = models.CharField(max_length=100, blank=True)
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_incidents'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['severity']),
            models.Index(fields=['incident_type']),
        ]
    
    def __str__(self):
        return f"[{self.severity}] {self.title}"
    
    @property
    def duration(self):
        """Calculate incident duration in minutes."""
        end_time = self.resolved_at or self.closed_at or timezone.now()
        duration = end_time - self.started_at
        return int(duration.total_seconds() / 60)
    
    @property
    def is_active(self):
        """Check if incident is still active."""
        return self.status not in [self.Status.RESOLVED, self.Status.CLOSED]
    
    def mark_identifying(self):
        """Mark incident as identified."""
        self.identified_at = timezone.now()
        self.status = self.Status.IDENTIFIED
        self.save()
    
    def mark_monitoring(self):
        """Mark incident as monitoring."""
        self.status = self.Status.MONITORING
        self.save()
    
    def resolve(self, resolution_text):
        """Resolve the incident."""
        self.resolved_at = timezone.now()
        self.resolution = resolution_text
        self.status = self.Status.RESOLVED
        self.save()
    
    def close(self):
        """Close the incident."""
        self.closed_at = timezone.now()
        self.status = self.Status.CLOSED
        self.save()


class IncidentUpdate(models.Model):
    """
    Updates/timeline entries for incidents.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name='updates')
    
    content = models.TextField()
    status = models.CharField(max_length=20, choices=Incident.Status.choices, null=True)
    severity = models.CharField(max_length=20, choices=Incident.Severity.choices, null=True)
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    is_internal = models.BooleanField(default=False)
    attachments = models.JSONField(default=list)
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_incident_updates'
        ordering = ['created_at']
    
    def __str__(self):
        return f"Update on {self.incident.title}"


class IncidentTimeline(models.Model):
    """
    Detailed timeline events for incidents.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name='timeline')
    
    timestamp = models.DateTimeField(default=timezone.now)
    event_type = models.CharField(max_length=50)  # created, updated, status_change, etc.
    description = models.TextField()
    
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    
    metadata = models.JSONField(default=dict)
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_incident_timeline'
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.event_type} - {self.incident.title}"


class IncidentTemplate(models.Model):
    """
    Templates for common incident types.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Template values
    default_incident_type = models.CharField(max_length=20, choices=Incident.IncidentType.choices)
    default_severity = models.CharField(max_length=20, choices=Incident.Severity.choices)
    default_affected_systems = models.JSONField(default=list)
    
    # Runbook
    runbook_steps = models.JSONField(default=list)
    escalation_procedure = models.TextField(blank=True)
    
    # Notifications
    notify_channels = models.JSONField(default=list)  # Slack, Email, etc.
    auto_assign = models.BooleanField(default=False)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_incident_templates'
    
    def __str__(self):
        return self.name
    
    def create_incident(self, title, description, reporter):
        """Create an incident from this template."""
        return Incident.objects.create(
            title=title,
            description=description,
            incident_type=self.default_incident_type,
            severity=self.default_severity,
            affected_systems=self.default_affected_systems,
            reported_by=reporter,
            source='template',
            assigned_to=self.get_auto_assignee() if self.auto_assign else None
        )
    
    def get_auto_assignee(self):
        """Get auto-assigned user."""
        # Implementation would check on-call schedule
        return None


class OnCallSchedule(models.Model):
    """
    On-call rotation schedules.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Schedule
    timezone = models.CharField(max_length=50, default='UTC')
    rotation_type = models.CharField(max_length=20)  # daily, weekly, custom
    rotation_interval_hours = models.IntegerField(default=24)
    
    # Escalation
    escalation_levels = models.JSONField(default=list)
    
    # Members
    members = models.JSONField(default=list)  # List of user IDs in rotation
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_oncall_schedules'
    
    def __str__(self):
        return self.name
    
    def get_current_oncall(self):
        """Get current on-call person."""
        # Implementation would calculate based on rotation
        return None
    
    def get_escalation_contact(self, level):
        """Get escalation contact for level."""
        if level <= len(self.escalation_levels):
            return self.escalation_levels[level - 1]
        return None


class IncidentService:
    """Service for incident management."""
    
    @staticmethod
    def create_incident(title, description, incident_type, severity, reporter, source='manual'):
        """Create a new incident."""
        return Incident.objects.create(
            title=title,
            description=description,
            incident_type=incident_type,
            severity=severity,
            reported_by=reporter,
            source=source
        )
    
    @staticmethod
    def get_active_incidents():
        """Get all active incidents."""
        return Incident.objects.filter(
            status__in=[Incident.Status.OPEN, Incident.Status.INVESTIGATING, 
                       Incident.Status.IDENTIFIED, Incident.Status.MONITORING]
        ).order_by('-severity', '-started_at')
    
    @staticmethod
    def get_incident_stats(days=30):
        """Get incident statistics."""
        from datetime import timedelta
        start_date = timezone.now() - timedelta(days=days)
        
        total = Incident.objects.filter(started_at__gte=start_date).count()
        by_severity = {}
        for severity in Incident.Severity:
            count = Incident.objects.filter(
                started_at__gte=start_date,
                severity=severity
            ).count()
            by_severity[severity] = count
        
        by_status = {}
        for status in Incident.Status:
            count = Incident.objects.filter(
                started_at__gte=start_date,
                status=status
            ).count()
            by_status[status] = count
        
        return {
            'total': total,
            'by_severity': by_severity,
            'by_status': by_status,
            'avg_resolution_time': Incident.objects.filter(
                resolved_at__isnull=False,
                started_at__gte=start_date
            ).average_duration()
        }
    
    @staticmethod
    def add_update(incident, content, user, status=None, severity=None):
        """Add an update to an incident."""
        return IncidentUpdate.objects.create(
            incident=incident,
            content=content,
            created_by=user,
            status=status,
            severity=severity
        )
