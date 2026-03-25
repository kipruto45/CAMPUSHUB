"""
Tests for moderation app.
"""
import pytest
from django.contrib.auth import get_user_model

from apps.moderation.models import ModerationLog, AdminActivityLog

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_user(
        email="admin@example.com",
        password="adminpass123",
        is_staff=True,
    )


@pytest.mark.django_db
class TestModerationLogModel:
    """Tests for ModerationLog model."""

    def test_moderation_log_creation(self, user, admin_user):
        """Test moderation log creation."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test",
            created_by=user,
        )
        log = ModerationLog.objects.create(
            resource=resource,
            reviewed_by=admin_user,
            action="approved",
        )
        assert log.id is not None
        assert log.action == "approved"

    def test_moderation_log_str(self, user, admin_user):
        """Test moderation log string representation."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test",
            created_by=user,
        )
        log = ModerationLog.objects.create(
            resource=resource,
            reviewed_by=admin_user,
            action="approved",
        )
        assert "approved" in str(log)


@pytest.mark.django_db
class TestAdminActivityLogModel:
    """Tests for AdminActivityLog model."""

    def test_admin_activity_log_creation(self, admin_user):
        """Test admin activity log creation."""
        log = AdminActivityLog.objects.create(
            admin=admin_user,
            action="resource_approved",
            target_type="resource",
            target_id="1",
            target_title="Test Resource",
        )
        assert log.id is not None
        assert log.action == "resource_approved"

    def test_admin_activity_log_str(self, admin_user):
        """Test admin activity log string representation."""
        log = AdminActivityLog.objects.create(
            admin=admin_user,
            action="resource_approved",
            target_type="resource",
            target_id="1",
        )
        assert "resource_approved" in str(log)