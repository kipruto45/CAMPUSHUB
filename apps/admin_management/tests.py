"""
Comprehensive tests for admin_management module.
Tests for Content Calendar, Invitation Roles, and Admin functionality.
"""

import pytest
from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.admin_management.models import (
    ContentCalendarEvent,
    CalendarCategory,
    CalendarTemplate,
    AdminInvitationRole,
    AdminInvitationBatch,
    AdminRoleInvitation,
    AdminRoleInvitationRole,
    AdminUserRoleAssignment,
)

User = get_user_model()


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
# ContentCalendarEvent Tests
# =========================

@pytest.mark.django_db
class TestContentCalendarEvent:
    """Tests for ContentCalendarEvent model."""

    def test_create_event(self, user):
        """Test creating a content calendar event."""
        event = ContentCalendarEvent.objects.create(
            title='Test Event',
            description='Test Description',
            event_type=ContentCalendarEvent.EventType.ANNOUNCEMENT,
            status=ContentCalendarEvent.EventStatus.DRAFT,
            start_datetime=timezone.now() + timedelta(days=1),
            created_by=user,
        )
        
        assert event.id is not None
        assert event.title == 'Test Event'
        assert event.event_type == 'announcement'
        assert event.status == 'draft'
        assert str(event) == 'Test Event (announcement)'

    def test_event_types(self, user):
        """Test all event type choices."""
        event_types = [
            ContentCalendarEvent.EventType.ANNOUNCEMENT,
            ContentCalendarEvent.EventType.POST,
            ContentCalendarEvent.EventType.EMAIL,
            ContentCalendarEvent.EventType.NOTIFICATION,
            ContentCalendarEvent.EventType.PROMOTION,
            ContentCalendarEvent.EventType.MAINTENANCE,
            ContentCalendarEvent.EventType.EVENT,
        ]
        
        for event_type in event_types:
            event = ContentCalendarEvent.objects.create(
                title=f'Test {event_type}',
                event_type=event_type,
                start_datetime=timezone.now(),
                created_by=user,
            )
            assert event.event_type == event_type

    def test_event_statuses(self, user):
        """Test all event status choices."""
        event_statuses = [
            ContentCalendarEvent.EventStatus.DRAFT,
            ContentCalendarEvent.EventStatus.SCHEDULED,
            ContentCalendarEvent.EventStatus.PUBLISHED,
            ContentCalendarEvent.EventStatus.CANCELLED,
            ContentCalendarEvent.EventStatus.COMPLETED,
        ]
        
        for status in event_statuses:
            event = ContentCalendarEvent.objects.create(
                title=f'Test {status}',
                event_type=ContentCalendarEvent.EventType.ANNOUNCEMENT,
                status=status,
                start_datetime=timezone.now(),
                created_by=user,
            )
            assert event.status == status

    def test_publish_event(self, user, admin_user):
        """Test publishing an event."""
        event = ContentCalendarEvent.objects.create(
            title='Test Event',
            event_type=ContentCalendarEvent.EventType.ANNOUNCEMENT,
            start_datetime=timezone.now(),
            created_by=user,
        )
        
        event.publish(admin_user)
        
        assert event.status == ContentCalendarEvent.EventStatus.PUBLISHED
        assert event.published_at is not None
        assert event.published_by == admin_user

    def test_cancel_event(self, user):
        """Test cancelling an event."""
        event = ContentCalendarEvent.objects.create(
            title='Test Event',
            event_type=ContentCalendarEvent.EventType.ANNOUNCEMENT,
            start_datetime=timezone.now(),
            created_by=user,
        )
        
        event.cancel()
        
        assert event.status == ContentCalendarEvent.EventStatus.CANCELLED

    def test_is_upcoming_property(self, user):
        """Test is_upcoming property."""
        future_event = ContentCalendarEvent.objects.create(
            title='Future Event',
            event_type=ContentCalendarEvent.EventType.ANNOUNCEMENT,
            start_datetime=timezone.now() + timedelta(days=1),
            created_by=user,
        )
        
        past_event = ContentCalendarEvent.objects.create(
            title='Past Event',
            event_type=ContentCalendarEvent.EventType.ANNOUNCEMENT,
            start_datetime=timezone.now() - timedelta(days=1),
            created_by=user,
        )
        
        assert future_event.is_upcoming is True
        assert past_event.is_upcoming is False


# =========================
# CalendarCategory Tests
# =========================

@pytest.mark.django_db
class TestCalendarCategory:
    """Tests for CalendarCategory model."""

    def test_create_category(self):
        """Test creating a calendar category."""
        category = CalendarCategory.objects.create(
            name='Test Category',
            color='#FF0000',
            icon='calendar',
            event_types=['announcement', 'event'],
        )
        
        assert category.id is not None
        assert category.name == 'Test Category'
        assert category.color == '#FF0000'
        assert category.is_active is True
        assert str(category) == 'Test Category'


# =========================
# CalendarTemplate Tests
# =========================

@pytest.mark.django_db
class TestCalendarTemplate:
    """Tests for CalendarTemplate model."""

    def test_create_template(self, user):
        """Test creating a calendar template."""
        template = CalendarTemplate.objects.create(
            name='Weekly Announcement',
            description='Weekly announcement template',
            event_type=ContentCalendarEvent.EventType.ANNOUNCEMENT,
            default_duration_hours=2,
            default_color='#00FF00',
            title_template='Weekly Update',
            description_template='This week in campus...',
            recurrence_pattern='WEEKLY:MONDAY',
            created_by=user,
        )
        
        assert template.id is not None
        assert template.name == 'Weekly Announcement'
        assert str(template) == 'Weekly Announcement'

    def test_create_events_from_template(self, user):
        """Test creating events from a template."""
        template = CalendarTemplate.objects.create(
            name='Weekly Announcement',
            event_type=ContentCalendarEvent.EventType.ANNOUNCEMENT,
            default_duration_hours=1,
            title_template='Weekly Update',
            recurrence_pattern='WEEKLY:MONDAY',
            created_by=user,
        )
        
        start_date = timezone.now()
        end_date = start_date + timedelta(weeks=2)
        
        events = template.create_events(start_date, end_date, user)
        
        assert len(events) == 3  # 3 weeks


# =========================
# AdminInvitationRole Tests
# =========================

@pytest.mark.django_db
class TestAdminInvitationRole:
    """Tests for AdminInvitationRole model."""

    def test_create_role(self):
        """Test creating an admin invitation role."""
        role = AdminInvitationRole.objects.create(
            code='INSTRUCTOR',
            name='Instructor',
            description='Teaching staff member',
        )
        
        assert role.id is not None
        assert role.code == 'INSTRUCTOR'
        assert role.name == 'Instructor'
        assert role.is_active is True
        assert role.is_assignable is True
        assert str(role) == 'Instructor'

    def test_role_choices(self):
        """Test all role choices."""
        expected_codes = ['STUDENT', 'INSTRUCTOR', 'DEPARTMENT_HEAD', 'SUPPORT_STAFF', 'MODERATOR', 'ADMIN']
        
        for code in expected_codes:
            role = AdminInvitationRole.objects.create(
                code=code,
                name=code.replace('_', ' ').title(),
            )
            assert role.code == code

    def test_save_normalizes_code(self):
        """Test that save normalizes the code to uppercase."""
        role = AdminInvitationRole.objects.create(
            code='student',  # lowercase
            name='Student',
        )
        
        assert role.code == 'STUDENT'

    def test_save_invalid_code_defaults_to_student(self):
        """Test that invalid code defaults to STUDENT."""
        role = AdminInvitationRole.objects.create(
            code='INVALID_ROLE',
            name='Invalid Role',
        )
        
        assert role.code == 'STUDENT'


# =========================
# AdminInvitationBatch Tests
# =========================

@pytest.mark.django_db
class TestAdminInvitationBatch:
    """Tests for AdminInvitationBatch model."""

    def test_create_batch(self, user):
        """Test creating an invitation batch."""
        batch = AdminInvitationBatch.objects.create(
            name='Test Batch',
            source_file_name='test.csv',
            invited_by=user,
            total_rows=100,
            successful_rows=95,
            failed_rows=5,
        )
        
        assert batch.id is not None
        assert batch.name == 'Test Batch'
        assert str(batch) == 'Test Batch'

    def test_success_rate(self, user):
        """Test success_rate property."""
        batch = AdminInvitationBatch.objects.create(
            invited_by=user,
            total_rows=100,
            successful_rows=75,
            failed_rows=25,
        )
        
        assert batch.success_rate == 75.0

    def test_success_rate_zero_total(self, user):
        """Test success_rate when total_rows is 0."""
        batch = AdminInvitationBatch.objects.create(
            invited_by=user,
            total_rows=0,
            successful_rows=0,
            failed_rows=0,
        )
        
        assert batch.success_rate == 0.0


# =========================
# AdminRoleInvitation Tests
# =========================

@pytest.mark.django_db
class TestAdminRoleInvitation:
    """Tests for AdminRoleInvitation model."""

    def test_create_invitation(self, user):
        """Test creating a role invitation."""
        invitation = AdminRoleInvitation.objects.create(
            email='invitee@example.com',
            role='INSTRUCTOR',
            expires_at=timezone.now() + timedelta(days=7),
            invited_by=user,
        )
        
        assert invitation.id is not None
        assert invitation.email == 'invitee@example.com'
        assert invitation.role == 'INSTRUCTOR'
        assert invitation.token is not None
        assert invitation.status == 'pending'

    def test_email_normalization(self, user):
        """Test that email is normalized to lowercase."""
        invitation = AdminRoleInvitation.objects.create(
            email='UPPERCASE@EXAMPLE.COM',
            role='STUDENT',
            expires_at=timezone.now() + timedelta(days=7),
            invited_by=user,
        )
        
        assert invitation.email == 'uppercase@example.com'

    def test_status_pending(self, user):
        """Test status is pending for valid invitation."""
        invitation = AdminRoleInvitation.objects.create(
            email='test@example.com',
            role='STUDENT',
            expires_at=timezone.now() + timedelta(days=7),
            invited_by=user,
        )
        
        assert invitation.status == 'pending'
        assert invitation.is_active is True

    def test_status_expired(self, user):
        """Test status is expired when past expiration."""
        invitation = AdminRoleInvitation.objects.create(
            email='test@example.com',
            role='STUDENT',
            expires_at=timezone.now() - timedelta(days=1),
            invited_by=user,
        )
        
        assert invitation.status == 'expired'
        assert invitation.is_active is False

    def test_status_accepted(self, user, admin_user):
        """Test status is accepted when accepted."""
        invitation = AdminRoleInvitation.objects.create(
            email='test@example.com',
            role='STUDENT',
            expires_at=timezone.now() + timedelta(days=7),
            invited_by=user,
        )
        invitation.accepted_by = admin_user
        invitation.accepted_at = timezone.now()
        invitation.save()
        
        assert invitation.status == 'accepted'
        assert invitation.is_active is False

    def test_status_revoked(self, user, admin_user):
        """Test status is revoked when revoked."""
        invitation = AdminRoleInvitation.objects.create(
            email='test@example.com',
            role='STUDENT',
            expires_at=timezone.now() + timedelta(days=7),
            invited_by=user,
        )
        invitation.revoked_by = admin_user
        invitation.revoked_at = timezone.now()
        invitation.save()
        
        assert invitation.status == 'revoked'
        assert invitation.is_active is False

    def test_get_role_codes(self, user):
        """Test get_role_codes method."""
        invitation = AdminRoleInvitation.objects.create(
            email='test@example.com',
            role='INSTRUCTOR',
            expires_at=timezone.now() + timedelta(days=7),
            invited_by=user,
        )
        
        codes = invitation.get_role_codes()
        assert 'INSTRUCTOR' in codes

    def test_is_valid(self, user):
        """Test is_valid property."""
        valid_invitation = AdminRoleInvitation.objects.create(
            email='test@example.com',
            role='STUDENT',
            expires_at=timezone.now() + timedelta(days=7),
            invited_by=user,
        )
        
        expired_invitation = AdminRoleInvitation.objects.create(
            email='expired@example.com',
            role='STUDENT',
            expires_at=timezone.now() - timedelta(days=1),
            invited_by=user,
        )
        
        assert valid_invitation.is_valid() is True
        assert expired_invitation.is_valid() is False


# =========================
# AdminRoleInvitationRole Tests
# =========================

@pytest.mark.django_db
class TestAdminRoleInvitationRole:
    """Tests for AdminRoleInvitationRole model."""

    def test_create_invitation_role(self, user):
        """Test creating an invitation role assignment."""
        invitation = AdminRoleInvitation.objects.create(
            email='test@example.com',
            role='INSTRUCTOR',
            expires_at=timezone.now() + timedelta(days=7),
            invited_by=user,
        )
        
        role_definition = AdminInvitationRole.objects.create(
            code='INSTRUCTOR',
            name='Instructor',
        )
        
        invitation_role = AdminRoleInvitationRole.objects.create(
            invitation=invitation,
            role_definition=role_definition,
            is_primary=True,
        )
        
        assert invitation_role.id is not None
        assert invitation_role.is_primary is True
        assert str(invitation_role) == 'test@example.com -> INSTRUCTOR'


# =========================
# AdminUserRoleAssignment Tests
# =========================

@pytest.mark.django_db
class TestAdminUserRoleAssignment:
    """Tests for AdminUserRoleAssignment model."""

    def test_create_role_assignment(self, user, admin_user):
        """Test creating a user role assignment."""
        role_definition = AdminInvitationRole.objects.create(
            code='INSTRUCTOR',
            name='Instructor',
        )
        
        assignment = AdminUserRoleAssignment.objects.create(
            user=user,
            role_definition=role_definition,
            assigned_by=admin_user,
            is_primary=True,
        )
        
        assert assignment.id is not None
        assert assignment.user == user
        assert assignment.role_definition == role_definition
        assert assignment.is_primary is True
        assert assignment.is_active is True
