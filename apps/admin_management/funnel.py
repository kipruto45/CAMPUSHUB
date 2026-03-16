"""
User Journey and Funnel Analytics
Track user behavior through conversion funnels and analyze user paths.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from uuid import uuid4
from django.core.validators import MinValueValidator, MaxValueValidator


class Funnel(models.Model):
    """
    Define conversion funnels to track user journeys.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Funnel steps
    steps = models.JSONField(
        default=list,
        help_text="List of funnel steps with name, event, and target"
    )
    
    # Time window
    time_window_days = models.IntegerField(
        default=7,
        validators=[MinValueValidator(1), MaxValueValidator(90)]
    )
    
    # Filters
    user_segment = models.JSONField(default=dict, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_funnels'
    
    def __str__(self):
        return self.name
    
    @property
    def step_count(self):
        return len(self.steps)
    
    def calculate_conversion(self, start_date=None, end_date=None):
        """Calculate funnel conversion rates."""
        from apps.activity.models import RecentActivity
        
        if not start_date:
            start_date = timezone.now() - timezone.timedelta(days=self.time_window_days)
        if not end_date:
            end_date = timezone.now()
        
        results = []
        previous_count = None
        
        for i, step in enumerate(self.steps):
            event_type = step.get('event')
            
            # Count users who completed this step
            count = RecentActivity.objects.filter(
                activity_type=event_type,
                created_at__gte=start_date,
                created_at__lte=end_date
            ).values('user').distinct().count()
            
            conversion_rate = None
            if previous_count and previous_count > 0:
                conversion_rate = round((count / previous_count) * 100, 2)
            
            results.append({
                'step': i + 1,
                'name': step.get('name'),
                'event': event_type,
                'count': count,
                'conversion_rate': conversion_rate
            })
            
            previous_count = count
        
        # Calculate overall conversion
        if results:
            first_count = results[0]['count'] if results else 0
            last_count = results[-1]['count'] if results else 0
            overall_conversion = None
            if first_count > 0:
                overall_conversion = round((last_count / first_count) * 100, 2)
            
            results.append({
                'overall_conversion': overall_conversion,
                'total_users': first_count
            })
        
        return results


class FunnelAnalysis(models.Model):
    """Stored funnel analysis results."""
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    funnel = models.ForeignKey(Funnel, on_delete=models.CASCADE, related_name='analyses')
    
    # Analysis period
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    
    # Results
    results = models.JSONField()
    total_users = models.IntegerField()
    overall_conversion = models.FloatField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_funnel_analyses'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.funnel.name} - {self.created_at}"


class UserJourney(models.Model):
    """
    Track individual user journeys through the app.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='journeys'
    )
    
    # Journey details
    session_id = models.CharField(max_length=255)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    
    # Entry and exit
    entry_point = models.CharField(max_length=255)  # e.g., '/home', 'notification'
    exit_point = models.CharField(max_length=255, blank=True)
    
    # Path taken
    path = models.JSONField(default=list)  # List of screens/pages visited
    
    # Outcome
    completed_goal = models.CharField(max_length=255, blank=True)
    goal_completed = models.BooleanField(default=False)
    
    # Events
    events_count = models.IntegerField(default=0)
    interactions = models.JSONField(default=list)
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_user_journeys'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['user', '-started_at']),
            models.Index(fields=['session_id']),
            models.Index(fields=['goal_completed']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.started_at}"
    
    def record_event(self, event_type, properties=None):
        """Record an event in this journey."""
        event = {
            'type': event_type,
            'timestamp': timezone.now().isoformat(),
            'properties': properties or {}
        }
        self.events_count += 1
        self.path.append(event)
        self.save()
    
    def complete_goal(self, goal_name):
        """Mark goal as completed."""
        self.goal_completed = True
        self.completed_goal = goal_name
        self.save()


class JourneyPattern(models.Model):
    """
    Common journey patterns identified through analysis.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Pattern definition
    pattern = models.JSONField(
        default=list,
        help_text="Sequence of events that define this pattern"
    )
    
    # Statistics
    frequency = models.IntegerField(default=0)  # How often this pattern occurs
    completion_rate = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    avg_duration_seconds = models.IntegerField(default=0)
    
    # Insights
    insights = models.TextField(blank=True)
    recommendations = models.JSONField(default=list)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_journey_patterns'
    
    def __str__(self):
        return self.name


class UserSegmentFunnel(models.Model):
    """
    Compare funnels across different user segments.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    funnel = models.ForeignKey(Funnel, on_delete=models.CASCADE)
    
    # Segment definition
    segment_name = models.CharField(max_length=255)
    segment_criteria = models.JSONField()
    
    # Comparison results
    results = models.JSONField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_segment_funnels'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.funnel.name} - {self.segment_name}"


class FunnelAnalyticsService:
    """Service for funnel analytics operations."""
    
    @staticmethod
    def get_default_funnels():
        """Return default funnel templates."""
        return [
            {
                'name': 'User Registration',
                'description': 'Track user signup flow',
                'steps': [
                    {'name': 'App Open', 'event': 'app_open'},
                    {'name': 'View Signup', 'event': 'view_signup'},
                    {'name': 'Start Signup', 'event': 'start_signup'},
                    {'name': 'Complete Signup', 'event': 'complete_signup'},
                    {'name': 'Verify Email', 'event': 'verify_email'}
                ],
                'time_window_days': 7
            },
            {
                'name': 'Resource Upload',
                'description': 'Track resource sharing flow',
                'steps': [
                    {'name': 'Browse Resources', 'event': 'browse_resources'},
                    {'name': 'View Resource', 'event': 'view_resource'},
                    {'name': 'Start Upload', 'event': 'start_upload'},
                    {'name': 'Complete Upload', 'event': 'complete_upload'},
                    {'name': 'Resource Published', 'event': 'resource_published'}
                ],
                'time_window_days': 14
            },
            {
                'name': 'Search to Download',
                'description': 'Track search and download behavior',
                'steps': [
                    {'name': 'Search', 'event': 'search'},
                    {'name': 'View Results', 'event': 'view_results'},
                    {'name': 'View Resource', 'event': 'view_resource'},
                    {'name': 'Download', 'event': 'download'},
                    {'name': 'Rate Resource', 'event': 'rate_resource'}
                ],
                'time_window_days': 7
            }
        ]
    
    @staticmethod
    def analyze_user_drop_off(funnel_id):
        """Analyze where users drop off in the funnel."""
        from apps.activity.models import RecentActivity
        
        try:
            funnel = Funnel.objects.get(id=funnel_id)
        except Funnel.DoesNotExist:
            return None
        
        results = []
        for i, step in enumerate(funnel.steps):
            event_type = step.get('event')
            
            # Get users at this step
            users = RecentActivity.objects.filter(
                activity_type=event_type
            ).values_list('user_id', flat=True).distinct()
            
            # Get users who were at previous step but not this one
            if i > 0:
                prev_event = funnel.steps[i-1].get('event')
                prev_users = set(RecentActivity.objects.filter(
                    activity_type=prev_event
                ).values_list('user_id', flat=True).distinct())
                
                current_users = set(users)
                dropped_users = prev_users - current_users
                
                results.append({
                    'step': i + 1,
                    'step_name': step.get('name'),
                    'at_step': len(prev_users),
                    'dropped': len(dropped_users),
                    'drop_rate': round((len(dropped_users) / len(prev_users)) * 100, 2) if prev_users else 0
                })
        
        return results
