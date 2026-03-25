"""
Comprehensive tests for core module.
Tests for TimeStampedModel, SlugifiedModel, SoftDeleteModel, AuditLog, EmailCampaign, and APIUsageLog.
"""

import pytest
from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from apps.core.models import (
    TimeStampedModel,
    SlugifiedModel,
    SoftDeleteModel,
    AuditLog,
    EmailCampaign,
    APIUsageLog,
)

User = get_user_model()


# Concrete test models for abstract base classes
class TestTimeStampedModel(TimeStampedModel):
    """Concrete implementation for testing TimeStampedModel."""
    name = models.CharField(max_length=100)
    
    class Meta:
        app_label = 'core'


class TestSlugifiedModel(SlugifiedModel):
    """Concrete implementation for testing SlugifiedModel."""
    title = models.CharField(max_length=100)
    
    class Meta:
        app_label = 'core'


class TestSoftDeleteModel(SoftDeleteModel):
    """Concrete implementation for testing SoftDeleteModel."""
    name = models.CharField(max_length=100)
    
    class Meta:
        app_label = 'core'



from django.db import models


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email='test@example.com',
        password='testpass123',
        role='STUDENT'
    )


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_user(
        email='admin@example.com',
        password='adminpass123',
        role='ADMIN'
    )


# =========================
# TimeStampedModel Tests
# =========================

@pytest.mark.django_db
class TestTimeStampedModel:
    """Tests for TimeStampedModel abstract base class."""

    def test_creates_timestamps(self):
        """Test that created_at and updated_at are automatically set."""
        obj = TestTimeStampedModel.objects.create(name='Test')
        
        assert obj.id is not None
        assert obj.created_at is not None
        assert obj.updated_at is not None
        assert obj.created_at <= timezone.now()

    def test_updated_at_changes(self):
        """Test that updated_at changes on save."""
        obj = TestTimeStampedModel.objects.create(name='Test')
        original_updated = obj.updated_at
        
        # Wait a tiny bit and save
        obj.name = 'Updated'
        obj.save()
        
        assert obj.updated_at > original_updated


# =========================
# SlugifiedModel Tests
# =========================

@pytest.mark.django_db
class TestSlugifiedModel:
    """Tests for SlugifiedModel abstract base class."""

    def test_auto_slug_generation(self):
        """Test that slug is automatically generated from title."""
        obj = TestSlugifiedModel.objects.create(title='Hello World')
        
        assert obj.slug == 'hello-world'

    def test_unique_slug(self):
        """Test that slugs are unique."""
        obj1 = TestSlugifiedModel.objects.create(title='Test Title')
        obj2 = TestSlugifiedModel.objects.create(title='Test Title')
        
        assert obj1.slug == 'test-title'
        assert obj2.slug == 'test-title-1'

    def test_manual_slug(self):
        """Test that manual slug is preserved."""
        obj = TestSlugifiedModel.objects.create(title='Test', slug='custom-slug')
        
        assert obj.slug == 'custom-slug'


# =========================
# SoftDeleteModel Tests
# =========================

@pytest.mark.django_db
class TestSoftDeleteModel:
    """Tests for SoftDeleteModel abstract base class."""

    def test_soft_delete(self):
        """Test soft delete functionality."""
        obj = TestSoftDeleteModel.objects.create(name='Test')
        obj_id = obj.id
        
        obj.delete()
        
        # Object should not appear in default queryset
        assert not TestSoftDeleteModel.objects.filter(id=obj_id).exists()
        
        # But should exist in all_objects
        assert TestSoftDeleteModel.all_objects.filter(id=obj_id).exists()
        
        # Check is_deleted flag
        deleted_obj = TestSoftDeleteModel.all_objects.get(id=obj_id)
        assert deleted_obj.is_deleted is True
        assert deleted_obj.deleted_at is not None

    def test_restore(self):
        """Test restoring a soft-deleted object."""
        obj = TestSoftDeleteModel.objects.create(name='Test')
        obj.delete()
        
        obj.restore()
        
        assert obj.is_deleted is False
        assert obj.deleted_at is None
        assert TestSoftDeleteModel.objects.filter(id=obj.id).exists()

    def test_hard_delete(self):
        """Test hard delete functionality."""
        obj = TestSoftDeleteModel.objects.create(name='Test')
        obj_id = obj.id
        
        obj.hard_delete()
        
        assert not TestSoftDeleteModel.all_objects.filter(id=obj_id).exists()


# =========================
# AuditLog Tests
# =========================

@pytest.mark.django_db
class TestAuditLog:
    """Tests for AuditLog model."""

    def test_create_audit_log(self, user):
        """Test creating an audit log entry."""
        log = AuditLog.objects.create(
            action='user_login',
            user=user,
            description='User logged in',
            target_type='User',
            target_id=user.id,
            ip_address='192.168.1.1',
        )
        
        assert log.id is not None
        assert log.action == 'user_login'
        assert log.user == user
        assert str(log) == f"user_login by {user.email} at {log.created_at}"

    def test_action_choices(self, user):
        """Test all action choices."""
        actions = [
            'user_login', 'user_logout', 'user_created', 'user_updated',
            'user_deleted', 'resource_created', 'resource_updated',
            'resource_deleted', 'faculty_created', 'department_created',
            'course_created', 'unit_created', 'report_created',
            'announcement_created', 'settings_updated', 'backup_created',
        ]
        
        for action in actions:
            log = AuditLog.objects.create(
                action=action,
                user=user,
            )
            assert log.action == action

    def test_audit_log_with_changes(self, user):
        """Test audit log with changes JSON."""
        changes = {'old': 'value', 'new': 'updated_value'}
        
        log = AuditLog.objects.create(
            action='user_updated',
            user=user,
            changes=changes,
        )
        
        assert log.changes == changes


# =========================
# EmailCampaign Tests
# =========================

@pytest.mark.django_db
class TestEmailCampaign:
    """Tests for EmailCampaign model."""

    def test_create_campaign(self, user):
        """Test creating an email campaign."""
        campaign = EmailCampaign.objects.create(
            name='Test Campaign',
            subject='Test Subject',
            body='Test body content',
            created_by=user,
        )
        
        assert campaign.id is not None
        assert campaign.name == 'Test Campaign'
        assert campaign.status == 'draft'
        assert str(campaign) == 'Test Campaign (draft)'

    def test_campaign_types(self, user):
        """Test all campaign type choices."""
        campaign_types = ['general', 'announcement', 'welcome', 'notification', 'promotional', 'digest']
        
        for campaign_type in campaign_types:
            campaign = EmailCampaign.objects.create(
                name=f'Test {campaign_type}',
                subject='Subject',
                body='Body',
                campaign_type=campaign_type,
                created_by=user,
            )
            assert campaign.campaign_type == campaign_type

    def test_campaign_statuses(self, user):
        """Test all campaign status choices."""
        statuses = ['draft', 'scheduled', 'sending', 'sent', 'cancelled', 'failed']
        
        for status in statuses:
            campaign = EmailCampaign.objects.create(
                name=f'Test {status}',
                subject='Subject',
                body='Body',
                status=status,
                created_by=user,
            )
            assert campaign.status == status

    def test_campaign_statistics(self, user):
        """Test campaign statistics fields."""
        campaign = EmailCampaign.objects.create(
            name='Test Campaign',
            subject='Subject',
            body='Body',
            recipient_count=1000,
            sent_count=950,
            opened_count=500,
            clicked_count=200,
            failed_count=50,
            created_by=user,
        )
        
        assert campaign.recipient_count == 1000
        assert campaign.sent_count == 950
        assert campaign.opened_count == 500
        assert campaign.clicked_count == 200
        assert campaign.failed_count == 50

    def test_campaign_scheduling(self, user):
        """Test campaign scheduling."""
        scheduled_at = timezone.now() + timedelta(days=1)
        
        campaign = EmailCampaign.objects.create(
            name='Test Campaign',
            subject='Subject',
            body='Body',
            scheduled_at=scheduled_at,
            status='scheduled',
            created_by=user,
        )
        
        assert campaign.scheduled_at == scheduled_at
        assert campaign.status == 'scheduled'


# =========================
# APIUsageLog Tests
# =========================

@pytest.mark.django_db
class TestAPIUsageLog:
    """Tests for APIUsageLog model."""

    def test_create_api_log(self, user):
        """Test creating an API usage log entry."""
        log = APIUsageLog.objects.create(
            user=user,
            endpoint='/api/v1/users',
            method='GET',
            status_code=200,
            response_time_ms=150,
            ip_address='192.168.1.1',
        )
        
        assert log.id is not None
        assert log.endpoint == '/api/v1/users'
        assert log.method == 'GET'
        assert log.status_code == 200
        assert str(log) == 'GET /api/v1/users - 200'

    def test_api_log_methods(self, user):
        """Test different HTTP methods."""
        methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
        
        for method in methods:
            log = APIUsageLog.objects.create(
                user=user,
                endpoint='/api/test',
                method=method,
                status_code=200,
            )
            assert log.method == method

    def test_api_log_status_codes(self, user):
        """Test different status codes."""
        status_codes = [200, 201, 400, 401, 403, 404, 500]
        
        for status_code in status_codes:
            log = APIUsageLog.objects.create(
                user=user,
                endpoint='/api/test',
                method='GET',
                status_code=status_code,
            )
            assert log.status_code == status_code

    def test_api_log_response_time(self, user):
        """Test response time tracking."""
        log = APIUsageLog.objects.create(
            user=user,
            endpoint='/api/slow',
            method='GET',
            status_code=200,
            response_time_ms=5000,
        )
        
        assert log.response_time_ms == 5000

    def test_api_log_request_data(self, user):
        """Test request data tracking."""
        request_data = {'query': 'test', 'page': 1}
        
        log = APIUsageLog.objects.create(
            user=user,
            endpoint='/api/search',
            method='GET',
            status_code=200,
            request_data=request_data,
        )
        
        assert log.request_data == request_data
