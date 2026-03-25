"""
Tests for certificates app.
"""
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.certificates.models import Certificate, CertificateTemplate, CertificateType

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def certificate_type(db):
    """Create a certificate type."""
    return CertificateType.objects.create(
        name="Course Completion",
        type="course_completion",
    )


@pytest.fixture
def certificate_template(db, certificate_type):
    """Create a certificate template."""
    return CertificateTemplate.objects.create(
        name="Default Template",
        certificate_type=certificate_type,
        title="Certificate of Completion",
    )


@pytest.mark.django_db
class TestCertificateTypeModel:
    """Tests for CertificateType model."""

    def test_certificate_type_creation(self):
        """Test certificate type creation."""
        cert_type = CertificateType.objects.create(
            name="Test Type",
            type="custom",
        )
        assert cert_type.id is not None
        assert cert_type.name == "Test Type"
        assert cert_type.slug == "test-type"

    def test_certificate_type_str(self):
        """Test certificate type string representation."""
        cert_type = CertificateType.objects.create(name="Test Type")
        assert str(cert_type) == "Test Type"


@pytest.mark.django_db
class TestCertificateTemplateModel:
    """Tests for CertificateTemplate model."""

    def test_certificate_template_creation(self, certificate_type):
        """Test certificate template creation."""
        template = CertificateTemplate.objects.create(
            name="Test Template",
            certificate_type=certificate_type,
            title="Test Certificate",
        )
        assert template.id is not None
        assert template.slug == "test-template"

    def test_certificate_template_str(self, certificate_type):
        """Test certificate template string representation."""
        template = CertificateTemplate.objects.create(
            name="Test Template",
            certificate_type=certificate_type,
            title="Test Certificate",
        )
        assert "Test Template" in str(template)


@pytest.mark.django_db
class TestCertificateModel:
    """Tests for Certificate model."""

    def test_certificate_creation(self, user, certificate_type):
        """Test certificate creation."""
        certificate = Certificate.objects.create(
            user=user,
            certificate_type=certificate_type,
            title="Test Certificate",
            recipient_name="John Doe",
        )
        assert certificate.id is not None
        assert certificate.unique_id is not None
        assert certificate.unique_id.startswith("CERT-")

    def test_certificate_str(self, user, certificate_type):
        """Test certificate string representation."""
        certificate = Certificate.objects.create(
            user=user,
            certificate_type=certificate_type,
            title="Test Certificate",
            recipient_name="John Doe",
        )
        assert "Test Certificate" in str(certificate)
        assert "John Doe" in str(certificate)

    def test_certificate_verification_url(self, user, certificate_type):
        """Test certificate verification URL is generated."""
        certificate = Certificate.objects.create(
            user=user,
            certificate_type=certificate_type,
            title="Test Certificate",
            recipient_name="John Doe",
        )
        assert certificate.verification_url is not None

    def test_certificate_is_valid_issued(self, user, certificate_type):
        """Test valid certificate returns True."""
        certificate = Certificate.objects.create(
            user=user,
            certificate_type=certificate_type,
            title="Test Certificate",
            recipient_name="John Doe",
            status="issued",
        )
        assert certificate.is_valid() is True

    def test_certificate_is_valid_revoked(self, user, certificate_type):
        """Test revoked certificate returns False."""
        certificate = Certificate.objects.create(
            user=user,
            certificate_type=certificate_type,
            title="Test Certificate",
            recipient_name="John Doe",
            status="revoked",
        )
        assert certificate.is_valid() is False

    def test_certificate_is_valid_expired(self, user, certificate_type):
        """Test expired certificate returns False."""
        certificate = Certificate.objects.create(
            user=user,
            certificate_type=certificate_type,
            title="Test Certificate",
            recipient_name="John Doe",
            status="issued",
            expiry_date=timezone.now() - timezone.timedelta(days=1),
        )
        assert certificate.is_valid() is False

    def test_certificate_revoke(self, user, certificate_type):
        """Test revoking a certificate."""
        certificate = Certificate.objects.create(
            user=user,
            certificate_type=certificate_type,
            title="Test Certificate",
            recipient_name="John Doe",
            status="issued",
        )
        certificate.revoke()
        assert certificate.status == "revoked"

    def test_certificate_get_verification_data(self, user, certificate_type):
        """Test getting verification data."""
        certificate = Certificate.objects.create(
            user=user,
            certificate_type=certificate_type,
            title="Test Certificate",
            recipient_name="John Doe",
        )
        data = certificate.get_verification_data()
        assert "unique_id" in data
        assert "title" in data
        assert "recipient_name" in data
        assert "verification_url" in data