"""
Comprehensive tests for core module.
Tests for TimeStampedModel, SlugifiedModel, SoftDeleteModel, AuditLog, EmailCampaign, and APIUsageLog.
"""

import pytest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connection, models
from django.utils import timezone

from apps.core.models import (
    TimeStampedModel,
    SlugifiedModel,
    SoftDeleteModel,
    AuditLog,
    EmailCampaign,
    APIUsageLog,
)
from apps.core.sms import (
    AfricasTalkingSMSProvider,
    SMSService,
    get_sms_configuration_status,
)
from apps.core.emails import (
    AdminEmailService,
    ResourceEmailService,
    UserEmailService,
    build_app_url,
    get_frontend_base_url,
)

User = get_user_model()


# Concrete test models for abstract base classes
class TimeStampedTestModel(TimeStampedModel):
    """Concrete implementation for testing TimeStampedModel."""
    name = models.CharField(max_length=100)
    
    class Meta:
        app_label = 'core'


class SlugifiedTestModel(SlugifiedModel):
    """Concrete implementation for testing SlugifiedModel."""
    title = models.CharField(max_length=100)
    
    class Meta:
        app_label = 'core'


class SoftDeleteTestModel(SoftDeleteModel):
    """Concrete implementation for testing SoftDeleteModel."""
    name = models.CharField(max_length=100)
    
    class Meta:
        app_label = 'core'

@pytest.fixture(scope="module", autouse=True)
def abstract_model_tables(django_db_setup, django_db_blocker):
    """Create database tables for local concrete test models."""
    models_to_manage = (
        TimeStampedTestModel,
        SlugifiedTestModel,
        SoftDeleteTestModel,
    )

    with django_db_blocker.unblock():
        existing_tables = set(connection.introspection.table_names())
        with connection.schema_editor() as schema_editor:
            for model_class in models_to_manage:
                if model_class._meta.db_table not in existing_tables:
                    schema_editor.create_model(model_class)

        try:
            yield
        finally:
            with connection.schema_editor() as schema_editor:
                for model_class in reversed(models_to_manage):
                    if model_class._meta.db_table in connection.introspection.table_names():
                        schema_editor.delete_model(model_class)


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
        obj = TimeStampedTestModel.objects.create(name='Test')
        
        assert obj.id is not None
        assert obj.created_at is not None
        assert obj.updated_at is not None
        assert obj.created_at <= timezone.now()

    def test_updated_at_changes(self):
        """Test that updated_at changes on save."""
        obj = TimeStampedTestModel.objects.create(name='Test')
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
        obj = SlugifiedTestModel.objects.create(title='Hello World')
        
        assert obj.slug == 'hello-world'

    def test_unique_slug(self):
        """Test that slugs are unique."""
        obj1 = SlugifiedTestModel.objects.create(title='Test Title')
        obj2 = SlugifiedTestModel.objects.create(title='Test Title')
        
        assert obj1.slug == 'test-title'
        assert obj2.slug == 'test-title-1'

    def test_manual_slug(self):
        """Test that manual slug is preserved."""
        obj = SlugifiedTestModel.objects.create(title='Test', slug='custom-slug')
        
        assert obj.slug == 'custom-slug'


# =========================
# SoftDeleteModel Tests
# =========================

@pytest.mark.django_db
class TestSoftDeleteModel:
    """Tests for SoftDeleteModel abstract base class."""

    def test_soft_delete(self):
        """Test soft delete functionality."""
        obj = SoftDeleteTestModel.objects.create(name='Test')
        obj_id = obj.id
        
        obj.delete()
        
        # Object should not appear in default queryset
        assert not SoftDeleteTestModel.objects.filter(id=obj_id).exists()
        
        # But should exist in all_objects
        assert SoftDeleteTestModel.all_objects.filter(id=obj_id).exists()
        
        # Check is_deleted flag
        deleted_obj = SoftDeleteTestModel.all_objects.get(id=obj_id)
        assert deleted_obj.is_deleted is True
        assert deleted_obj.deleted_at is not None

    def test_restore(self):
        """Test restoring a soft-deleted object."""
        obj = SoftDeleteTestModel.objects.create(name='Test')
        obj.delete()
        
        obj.restore()
        
        assert obj.is_deleted is False
        assert obj.deleted_at is None
        assert SoftDeleteTestModel.objects.filter(id=obj.id).exists()

    def test_hard_delete(self):
        """Test hard delete functionality."""
        obj = SoftDeleteTestModel.objects.create(name='Test')
        obj_id = obj.id
        
        obj.hard_delete()
        
        assert not SoftDeleteTestModel.all_objects.filter(id=obj_id).exists()


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


class TestSMSService:
    def test_accepts_africas_talking_provider_alias_with_underscore(self, settings):
        settings.SMS_PROVIDER = "africas_talking"

        service = SMSService()

        assert isinstance(service.provider, AfricasTalkingSMSProvider)

    def test_sms_configuration_status_reports_missing_required_fields(self, settings):
        settings.SMS_PROVIDER = "africas_talking"
        settings.AFRICAS_TALKING_USERNAME = ""
        settings.AFRICAS_TALKING_API_KEY = ""
        settings.AFRICAS_TALKING_SHORT_CODE = ""

        status = get_sms_configuration_status()

        assert status["provider"] == "africastalking"
        assert status["configured"] is False
        assert "AFRICAS_TALKING_USERNAME" in status["missing"]
        assert "AFRICAS_TALKING_API_KEY" in status["missing"]
        assert "AFRICAS_TALKING_SHORT_CODE" in status["optional_missing"]

    def test_sms_configuration_status_accepts_africas_talking_without_shortcode(self, settings):
        settings.SMS_PROVIDER = "africas_talking"
        settings.AFRICAS_TALKING_USERNAME = "sandbox"
        settings.AFRICAS_TALKING_API_KEY = "key"
        settings.AFRICAS_TALKING_SHORT_CODE = ""

        status = get_sms_configuration_status()

        assert status["configured"] is True
        assert status["optional_missing"] == ["AFRICAS_TALKING_SHORT_CODE"]


class TestEmailLinks:
    def test_get_frontend_base_url_falls_back_to_base_url(self, settings):
        settings.FRONTEND_BASE_URL = ""
        settings.FRONTEND_URL = ""
        settings.RESOURCE_SHARE_BASE_URL = ""
        settings.WEB_APP_URL = ""
        settings.BASE_URL = "https://api.example.com"

        assert get_frontend_base_url() == "https://api.example.com"

    def test_build_app_url_prefers_mobile_deeplink_when_frontend_missing(self, settings):
        settings.FRONTEND_BASE_URL = ""
        settings.FRONTEND_URL = ""
        settings.RESOURCE_SHARE_BASE_URL = ""
        settings.WEB_APP_URL = ""
        settings.BASE_URL = "https://api.example.com"
        settings.MOBILE_DEEPLINK_SCHEME = "campushub"

        url = build_app_url(
            web_path="/billing",
            mobile_path="billing",
            fallback_path="/fallback/",
        )

        assert url == "campushub://billing"

    def test_build_app_url_falls_back_to_backend_when_frontend_and_deeplink_missing(self, settings):
        settings.FRONTEND_BASE_URL = ""
        settings.FRONTEND_URL = ""
        settings.RESOURCE_SHARE_BASE_URL = ""
        settings.WEB_APP_URL = ""
        settings.MOBILE_DEEPLINK_SCHEME = ""
        settings.BASE_URL = "https://api.example.com"

        url = build_app_url(
            web_path="/billing/plans",
            mobile_path="billing/plans",
            fallback_path="/api/payments/plans/",
        )

        assert url == "https://api.example.com/api/payments/plans/"

    @patch("apps.core.emails.EmailService.send_template_email", return_value=True)
    def test_password_reset_email_uses_current_reset_route(self, mock_send_template_email, settings, user):
        settings.FRONTEND_BASE_URL = "https://campushub.example"
        settings.FRONTEND_URL = "https://campushub.example"
        settings.RESOURCE_SHARE_BASE_URL = "https://campushub.example"
        settings.WEB_APP_URL = ""
        settings.MOBILE_DEEPLINK_SCHEME = "campushub"

        UserEmailService.send_password_reset_email(user, "reset-token-123")

        context = mock_send_template_email.call_args.kwargs["context"]
        assert context["reset_url"] == "https://campushub.example/password-reset/reset-token-123"

    @patch("apps.core.emails.EmailService.send_template_email", return_value=True)
    def test_welcome_email_support_links_have_real_fallback_urls(
        self,
        mock_send_template_email,
        settings,
        user,
    ):
        settings.FRONTEND_BASE_URL = ""
        settings.FRONTEND_URL = ""
        settings.RESOURCE_SHARE_BASE_URL = ""
        settings.WEB_APP_URL = ""
        settings.MOBILE_DEEPLINK_SCHEME = ""
        settings.BASE_URL = "https://api.campushub.example"
        settings.SUPPORT_EMAIL = "support@campushub.example"

        UserEmailService.send_welcome_email(user, verification_token="verify-token-123")

        context = mock_send_template_email.call_args.kwargs["context"]
        assert context["website_url"] == "https://api.campushub.example"
        assert context["help_center_url"] == "https://api.campushub.example/api/docs/"
        assert context["contact_url"] == "mailto:support@campushub.example"

    @patch("apps.core.emails.EmailService.send_template_email", return_value=True)
    def test_resource_approved_email_uses_public_resource_slug_url(self, mock_send_template_email, settings, user):
        settings.RESOURCE_SHARE_BASE_URL = "https://share.campushub.example"
        settings.FRONTEND_BASE_URL = ""
        settings.FRONTEND_URL = ""
        resource = SimpleNamespace(
            id=uuid4(),
            slug="intro-to-economics",
            title="Intro to Economics",
        )

        ResourceEmailService.send_resource_approved_email(user, resource)

        context = mock_send_template_email.call_args.kwargs["context"]
        assert context["resource_url"] == "https://share.campushub.example/resources/intro-to-economics"

    @patch("apps.core.emails.EmailService.send_template_email", return_value=True)
    def test_resource_rejected_email_uses_docs_fallback_when_app_route_unavailable(
        self,
        mock_send_template_email,
        settings,
        user,
    ):
        settings.FRONTEND_BASE_URL = ""
        settings.FRONTEND_URL = ""
        settings.RESOURCE_SHARE_BASE_URL = ""
        settings.WEB_APP_URL = ""
        settings.MOBILE_DEEPLINK_SCHEME = ""
        settings.BASE_URL = "https://api.campushub.example"
        resource = SimpleNamespace(title="Intro to Economics")

        ResourceEmailService.send_resource_rejected_email(user, resource, "Needs revision")

        context = mock_send_template_email.call_args.kwargs["context"]
        assert context["upload_url"] == "https://api.campushub.example/api/docs/"

    @patch("apps.core.emails.EmailService.send_template_email", return_value=True)
    def test_email_verification_email_falls_back_to_backend_when_no_frontend_or_scheme(
        self,
        mock_send_template_email,
        settings,
        user,
    ):
        settings.FRONTEND_BASE_URL = ""
        settings.FRONTEND_URL = ""
        settings.RESOURCE_SHARE_BASE_URL = ""
        settings.WEB_APP_URL = ""
        settings.MOBILE_DEEPLINK_SCHEME = ""
        settings.BASE_URL = "https://api.campushub.example"

        UserEmailService.send_email_verification_email(user, verification_token="verify-token-123")

        context = mock_send_template_email.call_args.kwargs["context"]
        assert context["verify_url"] == "https://api.campushub.example/api/auth/verify-email/verify-token-123/"

    @patch("apps.core.emails.EmailService.send_template_email", return_value=True)
    def test_admin_registration_email_uses_backend_admin_change_url(self, mock_send_template_email, settings, user):
        settings.BASE_URL = "https://api.campushub.example"

        AdminEmailService.send_new_user_registration_email("admin@example.com", user)

        context = mock_send_template_email.call_args.kwargs["context"]
        assert context["profile_url"] == f"https://api.campushub.example/admin/accounts/user/{user.id}/change/"


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
