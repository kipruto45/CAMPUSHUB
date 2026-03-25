"""
Referral system models.
"""

import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string


def generate_unique_referral_code():
    """Generate a unique referral code."""
    while True:
        code = get_random_string(8, allowed_chars="ABCDEFGHJKLMNPQRSTUVWXYZ23456789")
        if not ReferralCode.objects.filter(code=code).exists():
            return code


class ReferralCode(models.Model):
    """
    Stores unique referral codes for each user.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referral_code",
    )
    code = models.CharField(
        max_length=20,
        unique=True,
        default=generate_unique_referral_code,
        db_index=True,
    )
    is_active = models.BooleanField(default=True)
    max_uses = models.IntegerField(
        default=100,
        help_text="Maximum number of times this code can be used",
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the referral code expires",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "referral_codes"
        verbose_name = "Referral Code"
        verbose_name_plural = "Referral Codes"

    def __str__(self):
        return f"Referral Code: {self.code} (User: {self.user.email})"

    @property
    def is_valid(self):
        """Check if the referral code is valid."""
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        if self.usage_count >= self.max_uses:
            return False
        return True

    @property
    def usage_count(self):
        """Get the number of times this code has been used."""
        return self.referrals.count()


class Referral(models.Model):
    """
    Tracks referrals - who referred whom.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("registered", "Registered"),
        ("subscribed", "Subscribed"),
        ("expired", "Expired"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referrals_made",
    )
    referee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referrals_received",
        null=True,
        blank=True,
    )
    referral_code = models.ForeignKey(
        ReferralCode,
        on_delete=models.CASCADE,
        related_name="referrals",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )
    email = models.EmailField(
        help_text="Email of the referred user (before registration)",
    )
    rewards_claimed = models.BooleanField(default=False)
    subscribed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the referee subscribed to premium",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "referrals"
        verbose_name = "Referral"
        verbose_name_plural = "Referrals"
        ordering = ["-created_at"]
        unique_together = ["referrer", "email"]

    def __str__(self):
        return f"Referral: {self.referrer.email} -> {self.email} ({self.status})"


class RewardTier(models.Model):
    """
    Defines reward tiers based on referral count.
    """

    name = models.CharField(max_length=100)
    min_referrals = models.IntegerField(
        help_text="Minimum number of referrals required for this tier",
    )
    points = models.IntegerField(default=0)
    premium_days = models.IntegerField(default=0)
    badge = models.CharField(
        max_length=100,
        blank=True,
        help_text="Badge identifier to grant",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reward_tiers"
        verbose_name = "Reward Tier"
        verbose_name_plural = "Reward Tiers"
        ordering = ["min_referrals"]

    def __str__(self):
        return f"{self.name} ({self.min_referrals}+ referrals)"


class RewardHistory(models.Model):
    """
    Tracks reward history for users.
    """

    REWARD_TYPES = [
        ("points", "Points"),
        ("premium_days", "Premium Days"),
        ("badge", "Badge"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reward_history",
    )
    referral = models.ForeignKey(
        Referral,
        on_delete=models.CASCADE,
        related_name="rewards",
        null=True,
        blank=True,
    )
    reward_type = models.CharField(max_length=20, choices=REWARD_TYPES)
    reward_value = models.IntegerField()
    description = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reward_history"
        verbose_name = "Reward History"
        verbose_name_plural = "Reward History"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} - {self.reward_type}: {self.reward_value}"


# Default reward tiers
DEFAULT_REWARD_TIERS = [
    {
        "name": "Bronze",
        "min_referrals": 1,
        "points": 100,
        "premium_days": 7,
        "badge": "",
    },
    {
        "name": "Silver",
        "min_referrals": 5,
        "points": 500,
        "premium_days": 30,
        "badge": "",
    },
    {
        "name": "Gold",
        "min_referrals": 10,
        "points": 1000,
        "premium_days": 90,
        "badge": "gold_referrer",
    },
]


def create_default_reward_tiers():
    """Create default reward tiers if they don't exist."""
    for tier_data in DEFAULT_REWARD_TIERS:
        RewardTier.objects.get_or_create(
            min_referrals=tier_data["min_referrals"],
            defaults=tier_data,
        )
