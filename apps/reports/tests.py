"""
Tests for reports app.
"""
import pytest
from django.contrib.auth import get_user_model

from apps.reports.models import Report

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def user2(db):
    """Create another test user."""
    return User.objects.create_user(
        email="test2@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestReportModel:
    """Tests for Report model."""

    def test_report_creation(self, user, user2):
        """Test report creation."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test",
            created_by=user2,
        )
        report = Report.objects.create(
            reporter=user,
            resource=resource,
            reason_type="inappropriate",
            message="This content is inappropriate",
        )
        assert report.id is not None
        assert report.status == "open"

    def test_report_str(self, user, user2):
        """Test report string representation."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test",
            created_by=user2,
        )
        report = Report.objects.create(
            reporter=user,
            resource=resource,
            reason_type="inappropriate",
        )
        assert "inappropriate" in str(report)

    def test_get_target_type_resource(self, user, user2):
        """Test get_target_type for resource."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test",
            created_by=user2,
        )
        report = Report.objects.create(
            reporter=user,
            resource=resource,
            reason_type="inappropriate",
        )
        assert report.get_target_type() == "resource"

    def test_get_target_title(self, user, user2):
        """Test get_target_title."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test",
            created_by=user2,
        )
        report = Report.objects.create(
            reporter=user,
            resource=resource,
            reason_type="inappropriate",
        )
        assert report.get_target_title() == "Test Resource"