"""
Referral services for handling referral logic.
"""

from django.db import models, transaction
from django.utils import timezone

from apps.gamification.services import GamificationService, ReferralIntegration

from .models import (
    Referral,
    ReferralCode,
    RewardHistory,
    RewardTier,
    create_default_reward_tiers,
)


class ReferralService:
    """Service for handling referral operations."""

    @staticmethod
    def get_or_create_referral_code(user):
        """Get or create a referral code for a user."""
        referral_code, created = ReferralCode.objects.get_or_create(
            user=user,
            defaults={
                "is_active": True,
                "max_uses": 100,
            },
        )
        return referral_code

    @staticmethod
    def get_referral_code(user):
        """Get the referral code for a user."""
        try:
            return user.referral_code
        except ReferralCode.DoesNotExist:
            return None

    @staticmethod
    def validate_referral_code(code):
        """Validate a referral code."""
        try:
            referral_code = ReferralCode.objects.get(code=code, is_active=True)
            if not referral_code.is_valid:
                return None
            return referral_code
        except ReferralCode.DoesNotExist:
            return None

    @staticmethod
    @transaction.atomic
    def use_referral_code(code, user):
        """
        Use a referral code for a user.
        Returns a tuple (success, message, referral).
        """
        # Validate the code
        referral_code = ReferralService.validate_referral_code(code)
        if not referral_code:
            return (False, "Invalid or expired referral code", None)

        # Check if user is trying to use their own code
        if referral_code.user == user:
            return (False, "You cannot use your own referral code", None)

        # Check if user was already referred
        if Referral.objects.filter(referee=user).exists():
            return (False, "You have already used a referral code", None)

        # Check if user was already referred by email
        if Referral.objects.filter(email=user.email).exists():
            return (False, "This email has already been referred", None)

        # Create the referral
        referral = Referral.objects.create(
            referrer=referral_code.user,
            referee=user,
            referral_code=referral_code,
            status="registered",
            email=user.email,
        )

        return (True, "Referral code applied successfully", referral)

    @staticmethod
    @transaction.atomic
    def mark_referral_as_subscribed(referral):
        """
        Mark a referral as subscribed and award rewards.
        """
        if referral.status == "subscribed":
            return False

        referral.status = "subscribed"
        referral.subscribed_at = timezone.now()
        referral.save()

        # Award rewards to the referrer
        RewardService.award_referral_rewards(referral)

        return True

    @staticmethod
    def get_user_referrals(user):
        """Get all referrals made by a user."""
        return Referral.objects.filter(referrer=user).select_related("referee")

    @staticmethod
    def get_user_referral_stats(user):
        """Get referral statistics for a user."""
        referrals = Referral.objects.filter(referrer=user)

        total_referrals = referrals.count()
        registered_count = referrals.filter(status="registered").count()
        subscribed_count = referrals.filter(status="subscribed").count()
        pending_count = referrals.filter(status="pending").count()

        # Get current tier
        current_tier = RewardService.get_current_tier(subscribed_count)

        # Calculate next tier
        next_tier = None
        if current_tier:
            next_tiers = RewardTier.objects.filter(
                min_referrals__gt=subscribed_count,
                is_active=True,
            ).order_by("min_referrals").first()
            next_tier = next_tiers

        return {
            "total_referrals": total_referrals,
            "registered_count": registered_count,
            "subscribed_count": subscribed_count,
            "pending_count": pending_count,
            "current_tier": {
                "name": current_tier.name if current_tier else None,
                "min_referrals": current_tier.min_referrals if current_tier else None,
                "points": current_tier.points if current_tier else 0,
                "premium_days": current_tier.premium_days if current_tier else 0,
                "badge": current_tier.badge if current_tier else None,
            } if current_tier else None,
            "next_tier": {
                "name": next_tier.name if next_tier else None,
                "min_referrals": next_tier.min_referrals if next_tier else None,
                "points": next_tier.points if next_tier else 0,
                "premium_days": next_tier.premium_days if next_tier else 0,
                "badge": next_tier.badge if next_tier else None,
            } if next_tier else None,
            "referrals_to_next_tier": (
                next_tier.min_referrals - subscribed_count
                if next_tier else 0
            ),
        }


class RewardService:
    """Service for handling reward operations."""

    @staticmethod
    def initialize_default_tiers():
        """Initialize default reward tiers."""
        create_default_reward_tiers()

    @staticmethod
    def get_current_tier(referral_count):
        """Get the current reward tier based on referral count."""
        return (
            RewardTier.objects.filter(
                min_referrals__lte=referral_count,
                is_active=True,
            )
            .order_by("-min_referrals")
            .first()
        )

    @staticmethod
    @transaction.atomic
    def award_referral_rewards(referral):
        """
        Award rewards to the referrer when their referral subscribes.
        Also syncs points to the gamification system.
        """
        referrer = referral.referrer
        referral_count = Referral.objects.filter(
            referrer=referrer,
            status="subscribed",
        ).count()

        # Get the current tier
        current_tier = RewardService.get_current_tier(referral_count)

        if not current_tier:
            return []

        rewards_awarded = []

        # Award points
        if current_tier.points > 0:
            points_reward = RewardHistory.objects.create(
                user=referrer,
                referral=referral,
                reward_type="points",
                reward_value=current_tier.points,
                description=f"Points earned from referral ({referral.email})",
            )
            rewards_awarded.append(points_reward)

            # Sync to gamification system
            ReferralIntegration.sync_referral_subscription(
                referrer, current_tier.points, referral.email
            )

        # Award premium days
        if current_tier.premium_days > 0:
            premium_reward = RewardHistory.objects.create(
                user=referrer,
                referral=referral,
                reward_type="premium_days",
                reward_value=current_tier.premium_days,
                description=f"Premium days earned from referral ({referral.email})",
            )
            rewards_awarded.append(premium_reward)

        # Award badge
        if current_tier.badge:
            badge_reward = RewardHistory.objects.create(
                user=referrer,
                referral=referral,
                reward_type="badge",
                reward_value=1,
                description=f"Badge '{current_tier.badge}' earned from referral ({referral.email})",
            )
            rewards_awarded.append(badge_reward)

        # Mark referral as rewards claimed
        referral.rewards_claimed = True
        referral.save()

        return rewards_awarded

    @staticmethod
    def get_user_reward_history(user):
        """Get reward history for a user."""
        return RewardHistory.objects.filter(user=user).order_by("-created_at")

    @staticmethod
    def get_user_total_points(user):
        """Get total points earned by a user."""
        return (
            RewardHistory.objects.filter(
                user=user,
                reward_type="points",
                is_active=True,
            )
            .aggregate(total=models.Sum("reward_value"))
            .get("total", 0) or 0
        )

    @staticmethod
    def get_user_total_premium_days(user):
        """Get total premium days earned by a user."""
        return (
            RewardHistory.objects.filter(
                user=user,
                reward_type="premium_days",
                is_active=True,
            )
            .aggregate(total=models.Sum("reward_value"))
            .get("total", 0) or 0
        )

    @staticmethod
    def get_user_badges(user):
        """Get all badges earned by a user."""
        return RewardHistory.objects.filter(
            user=user,
            reward_type="badge",
            is_active=True,
        ).values_list("description", flat=True)
