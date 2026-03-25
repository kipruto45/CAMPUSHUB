"""
Seed default subscription plans.

Idempotent command that ensures exactly one active plan per tier:
free, basic, premium, enterprise.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.payments.models import Plan


DEFAULT_PLANS = [
    {
        "tier": "free",
        "name": "Free",
        "description": "Starter access with basic limits.",
        "price_monthly": Decimal("0.00"),
        "price_yearly": Decimal("0.00"),
        "billing_period": "monthly",
        "storage_limit_gb": 1,
        "max_upload_size_mb": 10,
        "download_limit_monthly": 50,
        "can_download_unlimited": False,
        "has_ads": True,
        "has_priority_support": False,
        "has_analytics": False,
        "has_early_access": False,
        "is_featured": False,
        "display_order": 0,
    },
    {
        "tier": "basic",
        "name": "Basic",
        "description": "Affordable plan for regular learners.",
        "price_monthly": Decimal("5.99"),
        "price_yearly": Decimal("59.99"),
        "billing_period": "monthly",
        "storage_limit_gb": 10,
        "max_upload_size_mb": 50,
        "download_limit_monthly": 500,
        "can_download_unlimited": False,
        "has_ads": False,
        "has_priority_support": False,
        "has_analytics": True,
        "has_early_access": False,
        "is_featured": False,
        "display_order": 1,
    },
    {
        "tier": "premium",
        "name": "Premium",
        "description": "Best value with advanced features and generous limits.",
        "price_monthly": Decimal("12.00"),
        "price_yearly": Decimal("120.00"),
        "billing_period": "monthly",
        "storage_limit_gb": 100,
        "max_upload_size_mb": 250,
        "download_limit_monthly": 0,
        "can_download_unlimited": True,
        "has_ads": False,
        "has_priority_support": True,
        "has_analytics": True,
        "has_early_access": True,
        "is_featured": True,
        "display_order": 2,
    },
    {
        "tier": "enterprise",
        "name": "Enterprise",
        "description": "Institution-grade plan for teams and advanced workloads.",
        "price_monthly": Decimal("49.00"),
        "price_yearly": Decimal("490.00"),
        "billing_period": "monthly",
        "storage_limit_gb": 1000,
        "max_upload_size_mb": 1024,
        "download_limit_monthly": 0,
        "can_download_unlimited": True,
        "has_ads": False,
        "has_priority_support": True,
        "has_analytics": True,
        "has_early_access": True,
        "is_featured": False,
        "display_order": 3,
    },
]


class Command(BaseCommand):
    help = "Ensure default payment plans exist and keep one active plan per tier."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        deactivated = 0

        for plan_data in DEFAULT_PLANS:
            tier = plan_data["tier"]
            existing = list(Plan.objects.filter(tier=tier).order_by("created_at", "id"))

            if not existing:
                Plan.objects.create(is_active=True, **plan_data)
                created += 1
                self.stdout.write(self.style.SUCCESS(f"Created {tier} plan"))
                continue

            primary = existing[0]
            changed = False
            for field, value in plan_data.items():
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
