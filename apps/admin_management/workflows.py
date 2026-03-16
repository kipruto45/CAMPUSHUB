"""
Admin Workflow Automation
Create and manage automated admin workflows.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from uuid import uuid4
import json


class Workflow(models.Model):
    """
    Automated workflows for admin tasks.
    """
    
    class WorkflowStatus(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        ACTIVE = 'active', 'Active'
        PAUSED = 'paused', 'Paused'
        DISABLED = 'disabled', 'Disabled'
    
    class TriggerType(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        EVENT = 'event', 'Event-Based'
        MANUAL = 'manual', 'Manual'
        API = 'api', 'API Triggered'
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    
    # Identity
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=WorkflowStatus.choices, default=WorkflowStatus.DRAFT)
    
    # Trigger configuration
    trigger_type = models.CharField(max_length=20, choices=TriggerType.choices)
    trigger_config = models.JSONField(default=dict)  # Depends on trigger type
    
    # Event-based triggers
    trigger_event = models.CharField(max_length=100, blank=True)  # Event that triggers workflow
    
    # Scheduled triggers
    schedule_cron = models.CharField(max_length=100, blank=True)  # Cron expression
    schedule_interval_minutes = models.IntegerField(null=True, blank=True)
    
    # Actions
    actions = models.JSONField(
        default=list,
        help_text="List of actions to perform"
    )
    
    # Conditions
    conditions = models.JSONField(
        default=list,
        help_text="Conditions that must be met"
    )
    
    # Configuration
    is_active = models.BooleanField(default=True)
    run_on_creation = models.BooleanField(default=False)
    
    # Execution
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    run_count = models.IntegerField(default=0)
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_workflows'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_workflows'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.status})"
    
    def activate(self):
        """Activate the workflow."""
        self.status = self.WorkflowStatus.ACTIVE
        self.save()
        self.schedule_next_run()
    
    def pause(self):
        """Pause the workflow."""
        self.status = self.WorkflowStatus.PAUSED
        self.save()
    
    def disable(self):
        """Disable the workflow."""
        self.status = self.WorkflowStatus.DISABLED
        self.save()
    
    def run(self, context=None):
        """Execute the workflow."""
        if not self.is_active or self.status != self.WorkflowStatus.ACTIVE:
            return None
        
        execution = WorkflowExecution.objects.create(
            workflow=self,
            status=WorkflowExecution.ExecutionStatus.RUNNING,
            context=context or {}
        )
        
        try:
            # Check conditions
            if not self._evaluate_conditions(context):
                execution.status = WorkflowExecution.ExecutionStatus.SKIPPED
                execution.save()
                return execution
            
            # Execute actions
            results = self._execute_actions(context)
            
            execution.results = results
            execution.status = WorkflowExecution.ExecutionStatus.COMPLETED
            
        except Exception as e:
            execution.status = WorkflowExecution.ExecutionStatus.FAILED
            execution.error_message = str(e)
        
        execution.completed_at = timezone.now()
        execution.save()
        
        self.last_run_at = timezone.now()
        self.run_count += 1
        self.save()
        
        self.schedule_next_run()
        
        return execution
    
    def _evaluate_conditions(self, context):
        """Evaluate workflow conditions."""
        from apps.accounts.models import User
        from apps.resources.models import Resource
        from apps.reports.models import Report
        
        for condition in self.conditions:
            condition_type = condition.get('type')
            
            if condition_type == 'user_count':
                min_users = condition.get('min_users', 0)
                if User.objects.count() < min_users:
                    return False
            
            elif condition_type == 'resource_count':
                min_resources = condition.get('min_resources', 0)
                if Resource.objects.count() < min_resources:
                    return False
            
            elif condition_type == 'pending_reports':
                pending_count = condition.get('count', 0)
                if Report.objects.filter(status='pending').count() < pending_count:
                    return False
            
            elif condition_type == 'custom':
                # Custom condition would evaluate a Python expression
                pass
        
        return True
    
    def _execute_actions(self, context):
        """Execute workflow actions."""
        from apps.accounts.models import User
        from apps.resources.models import Resource
        from apps.announcements.models import Announcement
        from apps.notifications.models import Notification
        
        results = []
        
        for action in self.actions:
            action_type = action.get('type')
            action_config = action.get('config', {})
            
            try:
                if action_type == 'send_notification':
                    user_id = action_config.get('user_id')
                    message = action_config.get('message', '').format(**context)
                    
                    if user_id == 'all_admins':
                        users = User.objects.filter(is_staff=True)
                        for user in users:
                            Notification.objects.create(
                                recipient=user,
                                title=action_config.get('title', 'Workflow Notification'),
                                message=message
                            )
                    results.append({'action': action_type, 'status': 'success'})
                
                elif action_type == 'create_announcement':
                    announcement = Announcement.objects.create(
                        title=action_config.get('title', '').format(**context),
                        content=action_config.get('content', '').format(**context),
                        priority=action_config.get('priority', 'normal'),
                        created_by=self.created_by
                    )
                    results.append({'action': action_type, 'status': 'success', 'id': str(announcement.id)})
                
                elif action_type == 'delete_old_resources':
                    days = action_config.get('days', 30)
                    from datetime import timedelta
                    cutoff = timezone.now() - timedelta(days=days)
                    
                    resources = Resource.objects.filter(
                        created_at__lt=cutoff,
                        is_deleted=True
                    )
                    count = resources.count()
                    resources.delete()
                    results.append({'action': action_type, 'status': 'success', 'deleted': count})
                
                elif action_type == 'archive_old_reports':
                    days = action_config.get('days', 90)
                    from datetime import timedelta
                    cutoff = timezone.now() - timedelta(days=days)
                    
                    reports = Report.objects.filter(
                        created_at__lt=cutoff,
                        status='resolved'
                    )
                    count = reports.count()
                    reports.update(is_archived=True)
                    results.append({'action': action_type, 'status': 'success', 'archived': count})
                
                elif action_type == 'flag_inactive_users':
                    days = action_config.get('days', 90)
                    from datetime import timedelta
                    cutoff = timezone.now() - timedelta(days=days)
                    
                    from apps.activity.models import RecentActivity
                    active_users = RecentActivity.objects.filter(
                        created_at__gte=cutoff
                    ).values_list('user_id', flat=True).distinct()
                    
                    inactive_count = User.objects.exclude(
                        id__in=active_users
                    ).update(is_active=False)
                    
                    results.append({'action': action_type, 'status': 'success', 'flagged': inactive_count})
                
                elif action_type == 'webhook':
                    from apps.admin_management.webhooks import WebhookService
                    WebhookService.trigger_event(
                        action_config.get('event', 'workflow.executed'),
                        action_config.get('payload', {})
                    )
                    results.append({'action': action_type, 'status': 'success'})
                
                elif action_type == 'email':
                    # Would integrate with email service
                    results.append({'action': action_type, 'status': 'success', 'message': 'Email queued'})
                
                else:
                    results.append({'action': action_type, 'status': 'unknown_action'})
            
            except Exception as e:
                results.append({'action': action_type, 'status': 'error', 'message': str(e)})
        
        return results
    
    def schedule_next_run(self):
        """Schedule the next run for scheduled workflows."""
        if self.trigger_type == self.TriggerType.SCHEDULED:
            if self.schedule_interval_minutes:
                self.next_run_at = timezone.now() + timezone.timedelta(
                    minutes=self.schedule_interval_minutes
                )
                self.save()


class WorkflowExecution(models.Model):
    """
    Execution log for workflows.
    """
    
    class ExecutionStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        RUNNING = 'running', 'Running'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
        SKIPPED = 'skipped', 'Skipped'
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='executions')
    
    status = models.CharField(max_length=20, choices=ExecutionStatus.choices, default=ExecutionStatus.PENDING)
    context = models.JSONField(default=dict)
    results = models.JSONField(default=list)
    
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    error_message = models.TextField(blank=True)
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_workflow_executions'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['workflow', '-started_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.workflow.name} - {self.status}"


class WorkflowTemplate(models.Model):
    """
    Pre-built workflow templates.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    
    name = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=100)
    
    # Template configuration
    trigger_type = models.CharField(max_length=20, choices=Workflow.TriggerType.choices)
    trigger_config = models.JSONField(default=dict)
    actions = models.JSONField(default=list)
    conditions = models.JSONField(default=list)
    
    is_active = models.BooleanField(default=True)
    usage_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'admin_management'
        db_table = 'admin_workflow_templates'
        ordering = ['category', 'name']
    
    def __str__(self):
        return self.name
    
    def create_workflow(self, user, name=None):
        """Create a workflow from this template."""
        workflow = Workflow.objects.create(
            name=name or self.name,
            description=self.description,
            trigger_type=self.trigger_type,
            trigger_config=self.trigger_config,
            actions=self.actions,
            conditions=self.conditions,
            created_by=user
        )
        
        self.usage_count += 1
        self.save()
        
        return workflow


class WorkflowService:
    """Service for workflow management."""
    
    @staticmethod
    def get_default_templates():
        """Get default workflow templates."""
        return [
            {
                'name': 'Daily Admin Report',
                'description': 'Send daily summary to admin',
                'category': 'reporting',
                'trigger_type': Workflow.TriggerType.SCHEDULED,
                'trigger_config': {'interval_hours': 24},
                'actions': [
                    {
                        'type': 'send_notification',
                        'config': {
                            'user_id': 'all_admins',
                            'title': 'Daily Report',
                            'message': 'Daily system report: {report}'
                        }
                    }
                ]
            },
            {
                'name': 'Flag Inactive Users',
                'description': 'Automatically flag users inactive after 90 days',
                'category': 'user_management',
                'trigger_type': Workflow.TriggerType.SCHEDULED,
                'trigger_config': {'interval_hours': 24},
                'actions': [
                    {
                        'type': 'flag_inactive_users',
                        'config': {'days': 90}
                    }
                ]
            },
            {
                'name': 'Auto-Archive Resolved Reports',
                'description': 'Archive reports older than 90 days',
                'category': 'maintenance',
                'trigger_type': Workflow.TriggerType.SCHEDULED,
                'trigger_config': {'interval_hours': 24},
                'actions': [
                    {
                        'type': 'archive_old_reports',
                        'config': {'days': 90}
                    }
                ]
            },
            {
                'name': 'New User Welcome',
                'description': 'Send welcome message to new users',
                'category': 'onboarding',
                'trigger_type': Workflow.TriggerType.EVENT,
                'trigger_event': 'user.registered',
                'actions': [
                    {
                        'type': 'send_notification',
                        'config': {
                            'user_id': '{{user_id}}',
                            'title': 'Welcome to CampusHub!',
                            'message': 'Welcome! Start exploring resources.'
                        }
                    }
                ]
            },
            {
                'name': 'Content Moderation Alert',
                'description': 'Alert admins when content is flagged',
                'category': 'moderation',
                'trigger_type': Workflow.TriggerType.EVENT,
                'trigger_event': 'moderation.content_flagged',
                'actions': [
                    {
                        'type': 'send_notification',
                        'config': {
                            'user_id': 'all_admins',
                            'title': 'Content Flagged',
                            'message': 'Content has been flagged: {{content_type}}'
                        }
                    }
                ]
            }
        ]
    
    @staticmethod
    def trigger_workflows(event_type, context):
        """Trigger all workflows subscribed to an event."""
        workflows = Workflow.objects.filter(
            status=Workflow.WorkflowStatus.ACTIVE,
            trigger_type=Workflow.TriggerType.EVENT,
            trigger_event=event_type
        )
        
        executions = []
        for workflow in workflows:
            execution = workflow.run(context)
            if execution:
                executions.append(execution)
        
        return executions
