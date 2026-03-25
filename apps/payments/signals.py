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
    from apps.payments.models import Subscription
    
    subscription = Subscription.objects.filter(
        user=user,
        status__in=["active", "trialing"]
    ).select_related("plan").first()
    
    if subscription:
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
    from apps.payments.models import Subscription, StorageUpgrade
    from django.utils import timezone
    
    # Get base limits from plan
    limits = {
        "storage_gb": 1,
        "max_upload_mb": 10,
        "downloads_monthly": 50,
        "unlimited_downloads": False,
        "has_ads": True,
        "priority_support": False,
        "analytics": False,
        "early_access": False,
    }
    
    # Get active subscription
    subscription = Subscription.objects.filter(
        user=user,
        status__in=["active", "trialing"]
    ).select_related("plan").first()
    
    if subscription and subscription.is_active:
        limits.update({
            "storage_gb": subscription.plan.storage_limit_gb,
            "max_upload_mb": subscription.plan.max_upload_size_mb,
            "downloads_monthly": subscription.plan.download_limit_monthly,
            "unlimited_downloads": subscription.plan.can_download_unlimited,
            "has_ads": subscription.plan.has_ads,
            "priority_support": subscription.plan.has_priority_support,
            "analytics": subscription.plan.has_analytics,
            "early_access": subscription.plan.has_early_access,
        })
    
    # Add storage upgrades
    active_upgrades = StorageUpgrade.objects.filter(
        user=user,
        status="active",
        ends_at__gt=timezone.now()
    ).aggregate(total=models.Sum("storage_gb"))
    
    if active_upgrades.get("total"):
        limits["storage_gb"] += active_upgrades["total"]
    
    return limits
