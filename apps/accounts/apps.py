"""App configuration for accounts."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Accounts app config."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    verbose_name = "Accounts"

    def ready(self):
        """Register signal handlers."""
        import apps.accounts.openapi  # noqa: F401
        import apps.accounts.signals  # noqa: F401
