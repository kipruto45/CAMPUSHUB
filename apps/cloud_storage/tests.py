"""
Tests for cloud_storage app.
"""
import pytest
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.cloud_storage.models import (
    CloudStorageAccount,
    CloudFile,
    CloudImportHistory,
    CloudExportHistory,
)

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestCloudStorageAccountModel:
    """Tests for CloudStorageAccount model."""

    def test_cloud_storage_account_creation(self, user):
        """Test cloud storage account creation."""
        account = CloudStorageAccount.objects.create(
            user=user,
            provider=CloudStorageAccount.Provider.GOOGLE_DRIVE,
            provider_user_id="user123",
            email="test@example.com",
            display_name="Test User",
            access_token="test_token",
        )
        assert account.id is not None
        assert account.provider == "google_drive"
        assert account.email == "test@example.com"

    def test_cloud_storage_account_str(self, user):
        """Test cloud storage account string representation."""
        account = CloudStorageAccount.objects.create(
            user=user,
            provider=CloudStorageAccount.Provider.GOOGLE_DRIVE,
            provider_user_id="user123",
            email="test@example.com",
            display_name="Test User",
            access_token="test_token",
        )
        assert str(account) == f"{user.email} - google_drive"

    def test_is_token_expired_true(self, user):
        """Test token expired when past expiration."""
        account = CloudStorageAccount.objects.create(
            user=user,
            provider=CloudStorageAccount.Provider.GOOGLE_DRIVE,
            provider_user_id="user123",
            email="test@example.com",
            display_name="Test User",
            access_token="test_token",
            token_expires_at=timezone.now() - timedelta(hours=1),
        )
        assert account.is_token_expired is True

    def test_is_token_expired_false(self, user):
        """Test token not expired when in future."""
        account = CloudStorageAccount.objects.create(
            user=user,
            provider=CloudStorageAccount.Provider.GOOGLE_DRIVE,
            provider_user_id="user123",
            email="test@example.com",
            display_name="Test User",
            access_token="test_token",
            token_expires_at=timezone.now() + timedelta(hours=1),
        )
        assert account.is_token_expired is False

    def test_is_token_expired_none(self, user):
        """Test token not expired when no expiration set."""
        account = CloudStorageAccount.objects.create(
            user=user,
            provider=CloudStorageAccount.Provider.GOOGLE_DRIVE,
            provider_user_id="user123",
            email="test@example.com",
            display_name="Test User",
            access_token="test_token",
            token_expires_at=None,
        )
        assert account.is_token_expired is False


@pytest.mark.django_db
class TestCloudFileModel:
    """Tests for CloudFile model."""

    def test_cloud_file_creation(self, user):
        """Test cloud file creation."""
        account = CloudStorageAccount.objects.create(
            user=user,
            provider=CloudStorageAccount.Provider.GOOGLE_DRIVE,
            provider_user_id="user123",
            email="test@example.com",
            display_name="Test User",
            access_token="test_token",
        )
        cloud_file = CloudFile.objects.create(
            account=account,
            provider_file_id="file123",
            name="test.txt",
            mime_type="text/plain",
            size=1024,
        )
        assert cloud_file.id is not None
        assert cloud_file.name == "test.txt"

    def test_cloud_file_str(self, user):
        """Test cloud file string representation."""
        account = CloudStorageAccount.objects.create(
            user=user,
            provider=CloudStorageAccount.Provider.GOOGLE_DRIVE,
            provider_user_id="user123",
            email="test@example.com",
            display_name="Test User",
            access_token="test_token",
        )
        cloud_file = CloudFile.objects.create(
            account=account,
            provider_file_id="file123",
            name="test.txt",
            mime_type="text/plain",
        )
        assert "test.txt" in str(cloud_file)


@pytest.mark.django_db
class TestCloudImportHistoryModel:
    """Tests for CloudImportHistory model."""

    def test_cloud_import_history_creation(self, user):
        """Test cloud import history creation."""
        account = CloudStorageAccount.objects.create(
            user=user,
            provider=CloudStorageAccount.Provider.GOOGLE_DRIVE,
            provider_user_id="user123",
            email="test@example.com",
            display_name="Test User",
            access_token="test_token",
        )
        cloud_file = CloudFile.objects.create(
            account=account,
            provider_file_id="file123",
            name="test.txt",
            mime_type="text/plain",
        )
        history = CloudImportHistory.objects.create(
            user=user,
            account=account,
            cloud_file=cloud_file,
        )
        assert history.id is not None
        assert history.imported_at is not None


@pytest.mark.django_db
class TestCloudExportHistoryModel:
    """Tests for CloudExportHistory model."""

    def test_cloud_export_history_creation(self, user):
        """Test cloud export history creation."""
        account = CloudStorageAccount.objects.create(
            user=user,
            provider=CloudStorageAccount.Provider.GOOGLE_DRIVE,
            provider_user_id="user123",
            email="test@example.com",
            display_name="Test User",
            access_token="test_token",
        )
        from apps.resources.models import Resource
        resource = Resource.objects.create(
            title="Test Resource",
            description="Test",
            created_by=user,
        )
        history = CloudExportHistory.objects.create(
            user=user,
            account=account,
            resource=resource,
            cloud_file_id="file123",
            cloud_file_name="test.txt",
        )
        assert history.id is not None
        assert history.exported_at is not None