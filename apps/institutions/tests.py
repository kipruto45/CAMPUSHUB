"""
Tests for institutions app.
"""
import pytest
from django.contrib.auth import get_user_model

from apps.institutions.models import (
    Institution,
    InstitutionAdmin,
    Department,
    InstitutionInvitation,
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
class TestInstitutionModel:
    """Tests for Institution model."""

    def test_institution_creation(self):
        """Test institution creation."""
        institution = Institution.objects.create(
            name="Test University",
            slug="test-university",
            email_domain="@test.edu",
        )
        assert institution.id is not None
        assert institution.name == "Test University"
        assert institution.slug == "test-university"

    def test_institution_str(self):
        """Test institution string representation."""
        institution = Institution.objects.create(
            name="Test University",
            slug="test-university",
        )
        assert str(institution) == "Test University"

    def test_is_subscription_active_property_free(self):
        """Test subscription active property for free tier."""
        institution = Institution.objects.create(
            name="Test University",
            slug="test-university",
            subscription_tier="free",
            subscription_expires=None,
        )
        assert institution.is_subscription_active is True


@pytest.mark.django_db
class TestInstitutionAdminModel:
    """Tests for InstitutionAdmin model."""

    def test_institution_admin_creation(self, user):
        """Test institution admin creation."""
        institution = Institution.objects.create(
            name="Test University",
            slug="test-university",
        )
        admin = InstitutionAdmin.objects.create(
            user=user,
            institution=institution,
            role="admin",
        )
        assert admin.id is not None
        assert admin.role == "admin"

    def test_institution_admin_str(self, user):
        """Test institution admin string representation."""
        institution = Institution.objects.create(
            name="Test University",
            slug="test-university",
        )
        admin = InstitutionAdmin.objects.create(
            user=user,
            institution=institution,
        )
        assert str(admin) != ""


@pytest.mark.django_db
class TestDepartmentModel:
    """Tests for Department model."""

    def test_department_creation(self):
        """Test department creation."""
        institution = Institution.objects.create(
            name="Test University",
            slug="test-university",
        )
        department = Department.objects.create(
            institution=institution,
            name="Computer Science",
            code="CS",
        )
        assert department.id is not None
        assert department.name == "Computer Science"

    def test_department_str(self):
        """Test department string representation."""
        institution = Institution.objects.create(
            name="Test University",
            short_name="TU",
            slug="test-university",
        )
        department = Department.objects.create(
            institution=institution,
            name="Computer Science",
            code="CS",
        )
        assert "Computer Science" in str(department)


@pytest.mark.django_db
class TestInstitutionInvitationModel:
    """Tests for InstitutionInvitation model."""

    def test_invitation_creation(self, user):
        """Test invitation creation."""
        from django.utils import timezone
        from datetime import timedelta
        
        institution = Institution.objects.create(
            name="Test University",
            slug="test-university",
        )
        invitation = InstitutionInvitation.objects.create(
            institution=institution,
            email="newuser@example.com",
            role="student",
            invited_by=user,
            token="testtoken123",
            expires_at=timezone.now() + timedelta(days=7),
        )
        assert invitation.id is not None
        assert invitation.email == "newuser@example.com"

    def test_invitation_is_valid(self, user):
        """Test invitation is_valid method."""
        from django.utils import timezone
        from datetime import timedelta
        
        institution = Institution.objects.create(
            name="Test University",
            slug="test-university",
        )
        invitation = InstitutionInvitation.objects.create(
            institution=institution,
            email="newuser@example.com",
            role="student",
            invited_by=user,
            token="testtoken123",
            expires_at=timezone.now() + timedelta(days=7),
        )
        assert invitation.is_valid() is True