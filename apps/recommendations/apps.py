from django.apps import AppConfig


class RecommendationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.recommendations"
    verbose_name = "Recommendations"

    def ready(self):
        """Register recommendation signal handlers."""
        import apps.recommendations.signals  # noqa: F401
