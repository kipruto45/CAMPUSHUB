"""
Seed default subscription plans.

Idempotent command that ensures exactly one active plan per tier:
free, basic, premium, enterprise.
"""

import os
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.payments.models import Plan


DEFAULT_PLANS = [
    {
        "tier": "free",
        "name": "Free",
        "description": "Starter access with tighter daily and monthly caps.",
        "price_monthly": Decimal("0.00"),
        "price_yearly": Decimal("0.00"),
        "billing_period": "monthly",
        "storage_limit_gb": 1,
        "max_upload_size_mb": 8,
        "download_limit_monthly": 25,
        "upload_limit_monthly": 4,
        "message_limit_daily": 8,
        "group_limit": 2,
        "bookmark_limit": 15,
        "event_limit_monthly": 6,
        "points_limit_monthly": 250,
        "badge_limit": 3,
        "search_results_limit": 6,
        "notification_delay_hours": 6,
        "support_response_hours": 72,
        "can_download_unlimited": False,
        "has_ads": True,
        "has_priority_support": False,
        "has_analytics": False,
        "has_early_access": False,
        "is_featured": False,
        "display_order": 0,
        "metadata": {
            "plan_type": "Starter",
            "ideal_for": "Light browsing and occasional downloads.",
            "highlights": [
                "Core study tools",
                "Basic library access",
                "Announcements and calendar",
            ],
        },
    },
    {
        "tier": "basic",
        "name": "Basic",
        "description": "Focused student plan with AI support and stronger caps.",
        "price_monthly": Decimal("5.99"),
        "price_yearly": Decimal("59.99"),
        "billing_period": "monthly",
        "storage_limit_gb": 8,
        "max_upload_size_mb": 40,
        "download_limit_monthly": 250,
        "upload_limit_monthly": 40,
        "message_limit_daily": 120,
        "group_limit": 8,
        "bookmark_limit": 120,
        "event_limit_monthly": 40,
        "points_limit_monthly": 5000,
        "badge_limit": 20,
        "search_results_limit": 30,
        "notification_delay_hours": 1,
        "support_response_hours": 24,
        "can_download_unlimited": False,
        "has_ads": False,
        "has_priority_support": False,
        "has_analytics": True,
        "has_early_access": False,
        "is_featured": False,
        "display_order": 1,
        "metadata": {
            "plan_type": "Focus",
            "ideal_for": "Active students who need AI help and better daily limits.",
            "highlights": [
                "AI chat and summaries",
                "Analytics and folders",
                "Moderate creator limits",
            ],
        },
    },
    {
        "tier": "premium",
        "name": "Premium",
        "description": "Power-user plan with larger limits, certificates, and premium perks.",
        "price_monthly": Decimal("12.00"),
        "price_yearly": Decimal("120.00"),
        "billing_period": "monthly",
        "storage_limit_gb": 40,
        "max_upload_size_mb": 150,
        "download_limit_monthly": 1500,
        "upload_limit_monthly": 180,
        "message_limit_daily": 500,
        "group_limit": 30,
        "bookmark_limit": 500,
        "event_limit_monthly": 200,
        "points_limit_monthly": 25000,
        "badge_limit": 100,
        "search_results_limit": 100,
        "notification_delay_hours": 0,
        "support_response_hours": 8,
        "can_download_unlimited": False,
        "has_ads": False,
        "has_priority_support": True,
        "has_analytics": True,
        "has_early_access": True,
        "is_featured": True,
        "display_order": 2,
        "metadata": {
            "plan_type": "Power",
            "ideal_for": "Heavy contributors, study leaders, and serious daily use.",
            "highlights": [
                "Large upload and download caps",
                "Advanced search and certificates",
                "Priority perks and early access",
            ],
        },
    },
    {
        "tier": "enterprise",
        "name": "Enterprise",
        "description": "Institution-grade plan for teams and advanced workloads.",
        "price_monthly": Decimal("49.00"),
        "price_yearly": Decimal("490.00"),
        "billing_period": "monthly",
        "storage_limit_gb": 500,
        "max_upload_size_mb": 512,
        "download_limit_monthly": 0,
        "upload_limit_monthly": -1,
        "message_limit_daily": -1,
        "group_limit": -1,
        "bookmark_limit": -1,
        "event_limit_monthly": -1,
        "points_limit_monthly": -1,
        "badge_limit": -1,
        "search_results_limit": -1,
        "notification_delay_hours": 0,
        "support_response_hours": 1,
        "can_download_unlimited": True,
        "has_ads": False,
        "has_priority_support": True,
        "has_analytics": True,
        "has_early_access": True,
        "is_featured": False,
        "display_order": 3,
        "metadata": {
            "plan_type": "Campus",
            "ideal_for": "Departments, teams, and institution-scale collaboration.",
            "highlights": [
                "Enterprise controls",
                "Unlimited collaboration workflows",
                "Dedicated operational support",
            ],
        },
    },
]


STRIPE_ENV_FIELDS = (
    "stripe_monthly_price_id",
    "stripe_yearly_price_id",
    "stripe_product_id",
)


def _stripe_config_for_tier(tier: str) -> dict:
    prefix = f"STRIPE_{str(tier).upper()}_"
    env_mapping = {
        "stripe_monthly_price_id": "MONTHLY_PRICE_ID",
        "stripe_yearly_price_id": "YEARLY_PRICE_ID",
        "stripe_product_id": "PRODUCT_ID",
    }
    values = {}
    for field_name, env_suffix in env_mapping.items():
        value = str(os.getenv(f"{prefix}{env_suffix}", "")).strip()
        if value:
            values[field_name] = value
    return values


class Command(BaseCommand):
    help = "Ensure default payment plans exist and keep one active plan per tier."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        deactivated = 0

        for plan_data in DEFAULT_PLANS:
            tier = plan_data["tier"]
            stripe_config = _stripe_config_for_tier(tier)
            create_data = {**plan_data, **stripe_config}
            existing = list(Plan.objects.filter(tier=tier).order_by("created_at", "id"))

            if not existing:
                Plan.objects.create(is_active=True, **create_data)
                created += 1
                self.stdout.write(self.style.SUCCESS(f"Created {tier} plan"))
                continue

            primary = existing[0]
            changed = False
            for field, value in plan_data.items():
                if getattr(primary, field) != value:
                    setattr(primary, field, value)
                    changed = True
            for field, value in stripe_config.items():
                if getattr(primary, field) != value:
                    setattr(primary, field, value)
                    changed = True
            if not primary.is_active:
                primary.is_active = True
                changed = True
            if changed:
                primary.save()
                updated += 1
                self.stdout.write(self.style.SUCCESS(f"Updated {tier} plan"))

            for duplicate in existing[1:]:
                if duplicate.is_active:
                    duplicate.is_active = False
                    duplicate.save(update_fields=["is_active", "updated_at"])
                    deactivated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Plans seeding complete. Created: {created}, Updated: {updated}, Deactivated extras: {deactivated}"
            )
        )
