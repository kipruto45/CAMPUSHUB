"""
Referral app configuration.
"""

from django.apps import AppConfig


class ReferralsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.referrals"
    verbose_name = "Referral System"

    def ready(self):
        # Import signals when app is ready
        try:
            import apps.referrals.signals  # noqa: F401
        except ImportError:
            pass