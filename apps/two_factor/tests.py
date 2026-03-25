"""
Tests for two_factor app.
"""
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from apps.two_factor.models import TwoFactorSetting, TwoFactorVerification

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestTwoFactorSettingModel:
    """Tests for TwoFactorSetting model."""

    def test_two_factor_setting_creation(self, user):
        """Test 2FA setting creation."""
        setting = TwoFactorSetting.objects.create(
            user=user,
            enabled=True,
            method="totp",
        )
        assert setting.id is not None
        assert setting.enabled is True
        assert setting.method == "totp"

    def test_two_factor_setting_str(self, user):
        """Test 2FA setting string representation."""
        setting = TwoFactorSetting.objects.create(user=user)
        assert "2FA" in str(setting)

    def test_generate_totp_secret(self, user):
        """Test TOTP secret generation."""
        setting = TwoFactorSetting.objects.create(user=user)
        secret = setting.generate_totp_secret()
        assert secret is not None
        assert len(secret) > 0


@pytest.mark.django_db
class TestTwoFactorVerificationModel:
    """Tests for TwoFactorVerification model."""

    def test_two_factor_verification_creation(self, user):
        """Test 2FA verification creation."""
        verification = TwoFactorVerification.objects.create(
            user=user,
            code="123456",
            method="totp",
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        assert verification.id is not None
        assert verification.status == "pending"

    def test_is_expired_property(self, user):
        """Test is_expired property."""
        verification = TwoFactorVerification.objects.create(
            user=user,
            code="123456",
            method="totp",
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        assert verification.is_expired is True