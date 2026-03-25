"""
Signals for referral system.
"""

from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .models import create_default_reward_tiers


@receiver(post_migrate)
def create_referral_tiers(sender, **kwargs):
    """
    Create default reward tiers after migration.
    """
    if sender.name == "apps.referrals":
        create_default_reward_tiers()
