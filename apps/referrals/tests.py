"""
Tests for referrals app.
"""
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from apps.referrals.models import ReferralCode, Referral, RewardTier, RewardHistory

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
class TestReferralCodeModel:
    """Tests for ReferralCode model."""

    def test_referral_code_creation(self, user):
        """Test referral code creation."""
        code = ReferralCode.objects.create(user=user)
        assert code.id is not None
        assert code.code is not None
        assert len(code.code) == 8

    def test_referral_code_str(self, user):
        """Test referral code string representation."""
        code = ReferralCode.objects.create(user=user)
        assert "Referral Code:" in str(code)

    def test_is_valid_property_active(self, user):
        """Test is_valid property when active."""
        code = ReferralCode.objects.create(user=user, is_active=True)
        assert code.is_valid is True


@pytest.mark.django_db
class TestReferralModel:
    """Tests for Referral model."""

    def test_referral_creation(self, user, user2):
        """Test referral creation."""
        code = ReferralCode.objects.create(user=user)
        referral = Referral.objects.create(
            referrer=user,
            referral_code=code,
            email="newuser@example.com",
        )
        assert referral.id is not None
        assert referral.status == "pending"

    def test_referral_str(self, user):
        """Test referral string representation."""
        code = ReferralCode.objects.create(user=user)
        referral = Referral.objects.create(
            referrer=user,
            referral_code=code,
            email="newuser@example.com",
        )
        assert "pending" in str(referral)


@pytest.mark.django_db
class TestRewardTierModel:
    """Tests for RewardTier model."""

    def test_reward_tier_creation(self):
        """Test reward tier creation."""
        tier = RewardTier.objects.create(
            name="Bronze",
            min_referrals=1,
            points=100,
        )
        assert tier.id is not None
        assert tier.name == "Bronze"


@pytest.mark.django_db
class TestRewardHistoryModel:
    """Tests for RewardHistory model."""

    def test_reward_history_creation(self, user):
        """Test reward history creation."""
        history = RewardHistory.objects.create(
            user=user,
            reward_type="points",
            reward_value=100,
            description="Referral bonus",
        )
        assert history.id is not None
        assert history.reward_type == "points"
