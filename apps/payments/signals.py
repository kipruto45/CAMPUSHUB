"""
Payment signals for handling subscription lifecycle events.
"""

import logging
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


def _update_user_payment_flags(user, is_premium=None, premium_plan=None, storage_limit_gb=None):
    """Persist payment-related user flags only when the model actually supports them."""
    update_fields = []

    if is_premium is not None and hasattr(user, "is_premium"):
        user.is_premium = is_premium
        update_fields.append("is_premium")
    if premium_plan is not None and hasattr(user, "premium_plan"):
        user.premium_plan = premium_plan
        update_fields.append("premium_plan")
    if storage_limit_gb is not None and hasattr(user, "storage_limit_gb"):
        user.storage_limit_gb = storage_limit_gb
        update_fields.append("storage_limit_gb")

    if update_fields:
        user.save(update_fields=update_fields)


@receiver(post_save, sender="payments.Subscription")
def subscription_post_save(sender, instance, created, **kwargs):
    """Handle subscription creation and updates."""
    from django.conf import settings
    from django.contrib.auth import get_user_model

    User = get_user_model()

    if created:
        logger.info(
            "New subscription created for user %s: %s",
            instance.user.id,
            getattr(instance.plan, "name", "Plan"),
        )

    # Keep user flags in sync even when Stripe/IAP updates the same subscription later.
    try:
        plan_tier = getattr(getattr(instance, "plan", None), "tier", None)
        is_paid_tier = bool(plan_tier and str(plan_tier).lower() != "free")
        if instance.is_active and is_paid_tier:
            _update_user_payment_flags(
                instance.user,
                is_premium=True,
                premium_plan=plan_tier,
            )

            # If this user was referred, mark the referral as subscribed and award rewards.
            try:
                from apps.referrals.models import Referral
                from apps.referrals.services import ReferralService

                referral = (
                    Referral.objects.filter(
                        models.Q(referee=instance.user)
                        | models.Q(email__iexact=getattr(instance.user, "email", "")),
                    )
                    .exclude(status="subscribed")
                    .first()
                )
                if referral:
                    ReferralService.mark_referral_as_subscribed(referral)
            except Exception:
                logger.exception(
                    "Failed to mark referral subscribed for user_id=%s",
                    instance.user.id,
                )

            # Record premium subscription achievement progress (best effort).
            try:
                from apps.gamification.services import AchievementService

                AchievementService.set_achievement_progress(
                    instance.user,
                    target_type="premium_subscription",
                    value=1,
                )
            except Exception:
                pass
    except Exception:
        logger.exception(
            "Failed to sync user premium flags for subscription_id=%s",
            getattr(instance, "id", None),
        )
    
    # Handle status changes
    if instance.status == "canceled" and not instance.cancel_at_period_end:
        logger.info(f"Subscription canceled for user {instance.user.id}")
        _update_user_payment_flags(
            instance.user,
            is_premium=False,
            premium_plan="free",
        )


@receiver(post_save, sender="payments.Payment")
def payment_post_save(sender, instance, created, **kwargs):
    """Handle payment events."""
    if created:
        logger.info(f"Payment {instance.id} created for user {instance.user.id}: ${instance.amount}")
        
        # Create notification for successful payment
        if instance.status == "succeeded":
            from apps.notifications.models import Notification
            from django.utils import timezone
            
            Notification.objects.create(
                recipient=instance.user,
                title="Payment Successful",
                message=f"Your payment of ${instance.amount} was successful.",
                notification_type="payment",
                link="/settings/billing/",
            )


@receiver(post_save, sender="payments.StorageUpgrade")
def storage_upgrade_post_save(sender, instance, created, **kwargs):
    """Handle storage upgrade events."""
    if created:
        logger.info(f"Storage upgrade created for user {instance.user.id}: {instance.storage_gb}GB")


def sync_user_storage_from_subscription(user):
    """Sync user's storage limit from their active subscription."""
    from apps.payments.freemium import get_active_subscription

    subscription = get_active_subscription(user)
    
    if subscription and subscription.plan:
        # Calculate total storage (base + upgrades)
        base_storage = subscription.plan.storage_limit_gb
        
        from apps.payments.models import StorageUpgrade
        active_upgrades = StorageUpgrade.objects.filter(
            user=user,
            status="active",
            ends_at__gt=timezone.now()
        ).aggregate(total=models.Sum("storage_gb"))
        
        total_storage = base_storage + (active_upgrades.get("total") or 0)
        
        # Update user's storage limit if supported by the user model.
        _update_user_payment_flags(user, storage_limit_gb=total_storage)


def get_user_plan_limits(user):
    """Get effective plan limits for a user."""
    from apps.payments.freemium import (
        TRIAL_LIMIT_OVERRIDES,
        TIER_BOOKMARK_LIMITS,
        TIER_DOWNLOAD_LIMITS,
        TIER_EVENT_LIMITS,
        TIER_GROUP_LIMITS,
        TIER_MAX_UPLOAD_SIZE_MB,
        TIER_MESSAGE_LIMITS,
        TIER_NOTIFICATION_DELAY_HOURS,
        TIER_POINTS_LIMITS,
        TIER_SEARCH_RESULTS_LIMITS,
        TIER_STORAGE_LIMITS,
        TIER_SUPPORT_RESPONSE_HOURS,
        TIER_UPLOAD_LIMITS,
        TIER_BADGE_LIMITS,
        Tier,
        get_active_subscription,
        get_tier_from_string,
        get_trial_feature_exclusions,
    )
    from apps.payments.models import StorageUpgrade
    from django.utils import timezone
    
    # Get base limits from plan
    limits = {
        "storage_gb": TIER_STORAGE_LIMITS[Tier.FREE],
        "max_upload_mb": TIER_MAX_UPLOAD_SIZE_MB[Tier.FREE],
        "downloads_monthly": TIER_DOWNLOAD_LIMITS[Tier.FREE],
        "upload_limit_monthly": TIER_UPLOAD_LIMITS[Tier.FREE],
        "message_limit_daily": TIER_MESSAGE_LIMITS[Tier.FREE],
        "group_limit": TIER_GROUP_LIMITS[Tier.FREE],
        "bookmark_limit": TIER_BOOKMARK_LIMITS[Tier.FREE],
        "event_limit_monthly": TIER_EVENT_LIMITS[Tier.FREE],
        "points_limit_monthly": TIER_POINTS_LIMITS[Tier.FREE],
        "badge_limit": TIER_BADGE_LIMITS[Tier.FREE],
        "search_results_limit": TIER_SEARCH_RESULTS_LIMITS[Tier.FREE],
        "notification_delay_hours": TIER_NOTIFICATION_DELAY_HOURS[Tier.FREE],
        "support_response_hours": TIER_SUPPORT_RESPONSE_HOURS[Tier.FREE],
        "unlimited_downloads": False,
        "has_ads": True,
        "priority_support": False,
        "analytics": False,
        "early_access": False,
        "is_trial_limited": False,
        "trial_locked_features": [],
    }
    
    # Get active subscription
    subscription = get_active_subscription(user)
    
    if subscription and subscription.plan:
        limits.update({
            "storage_gb": subscription.plan.storage_limit_gb,
            "max_upload_mb": subscription.plan.max_upload_size_mb,
            "downloads_monthly": subscription.plan.download_limit_monthly,
            "upload_limit_monthly": subscription.plan.upload_limit_monthly,
            "message_limit_daily": subscription.plan.message_limit_daily,
            "group_limit": subscription.plan.group_limit,
            "bookmark_limit": subscription.plan.bookmark_limit,
            "event_limit_monthly": subscription.plan.event_limit_monthly,
            "points_limit_monthly": subscription.plan.points_limit_monthly,
            "badge_limit": subscription.plan.badge_limit,
            "search_results_limit": subscription.plan.search_results_limit,
            "notification_delay_hours": subscription.plan.notification_delay_hours,
            "support_response_hours": subscription.plan.support_response_hours,
            "unlimited_downloads": subscription.plan.can_download_unlimited,
            "has_ads": subscription.plan.has_ads,
            "priority_support": subscription.plan.has_priority_support,
            "analytics": subscription.plan.has_analytics,
            "early_access": subscription.plan.has_early_access,
        })

        if subscription.status == "trialing":
            tier = get_tier_from_string(subscription.plan.tier)
            limits.update(TRIAL_LIMIT_OVERRIDES.get(tier, {}))
            limits["is_trial_limited"] = True
            limits["trial_locked_features"] = sorted(
                feature.value
                for feature in get_trial_feature_exclusions(user, subscription=subscription)
            )
    
    # Add storage upgrades
    active_upgrades = StorageUpgrade.objects.filter(
        user=user,
        status="active",
        ends_at__gt=timezone.now()
    ).aggregate(total=models.Sum("storage_gb"))
    
    if active_upgrades.get("total"):
        limits["storage_gb"] += active_upgrades["total"]
    
    return limits
