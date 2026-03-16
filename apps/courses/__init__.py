"""Courses app configuration."""

from django.apps import AppConfig


class CoursesConfig(AppConfig):
    """Courses app configuration."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.courses"
    verbose_name = "Courses"
