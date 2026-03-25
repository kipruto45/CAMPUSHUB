"""
Tests for downloads app.
"""
import pytest
from django.contrib.auth import get_user_model

from apps.downloads.models import Download

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestDownloadModel:
    """Tests for Download model."""

    def test_download_creation(self, user):
        """Test download creation for resource."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test description",
            created_by=user,
        )
        download = Download.objects.create(
            user=user,
            resource=resource,
            ip_address="127.0.0.1",
            user_agent="Test Agent",
        )
        assert download.id is not None
        assert download.resource == resource
        assert download.user == user

    def test_download_str_with_resource(self, user):
        """Test download string with resource."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test description",
            created_by=user,
        )
        download = Download.objects.create(
            user=user,
            resource=resource,
        )
        assert str(download) == f"{user.email} - {resource.title}"

    def test_download_title_property(self, user):
        """Test download_title property."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test description",
            created_by=user,
        )
        download = Download.objects.create(
            user=user,
            resource=resource,
        )
        assert download.download_title == "Test Resource"

    def test_download_type_property(self, user):
        """Test download_type property."""
        from apps.resources.models import Resource
        
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test description",
            created_by=user,
        )
        download = Download.objects.create(
            user=user,
            resource=resource,
        )
        assert download.download_type == "resource"
