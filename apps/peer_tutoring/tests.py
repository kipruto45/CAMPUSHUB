"""
Tests for peer_tutoring app.
"""
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from apps.peer_tutoring.models import (
    TutoringProfile,
    TutoringSession,
    TutoringRequest,
    TutoringReview,
    TutoringSubject,
)

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
class TestTutoringProfileModel:
    """Tests for TutoringProfile model."""

    def test_tutoring_profile_creation(self, user):
        """Test tutoring profile creation."""
        profile = TutoringProfile.objects.create(
            user=user,
            is_available=True,
            hourly_rate=20.00,
        )
        assert profile.id is not None
        assert profile.is_available is True

    def test_tutoring_profile_str(self, user):
        """Test tutoring profile string representation."""
        profile = TutoringProfile.objects.create(user=user)
        assert str(profile) == f"Tutoring profile: {user.email}"


@pytest.mark.django_db
class TestTutoringSessionModel:
    """Tests for TutoringSession model."""

    def test_tutoring_session_creation(self, user, user2):
        """Test tutoring session creation."""
        profile = TutoringProfile.objects.create(user=user)
        session = TutoringSession.objects.create(
            tutor=profile,
            student=user2,
            subject="Mathematics",
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2),
        )
        assert session.id is not None
        assert session.subject == "Mathematics"


@pytest.mark.django_db
class TestTutoringRequestModel:
    """Tests for TutoringRequest model."""

    def test_tutoring_request_creation(self, user):
        """Test tutoring request creation."""
        request = TutoringRequest.objects.create(
            student=user,
            subject="Physics",
            description="Need help with mechanics",
            expires_at=timezone.now() + timedelta(days=7),
        )
        assert request.id is not None
        assert request.subject == "Physics"


@pytest.mark.django_db
class TestTutoringSubjectModel:
    """Tests for TutoringSubject model."""

    def test_tutoring_subject_creation(self):
        """Test tutoring subject creation."""
        subject = TutoringSubject.objects.create(
            name="Mathematics",
            code="MATH",
        )
        assert subject.id is not None
        assert subject.name == "Mathematics"

    def test_tutoring_subject_str(self):
        """Test tutoring subject string representation."""
        subject = TutoringSubject.objects.create(
            name="Mathematics",
            code="MATH",
        )
        assert "Mathematics" in str(subject)