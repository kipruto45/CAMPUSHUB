"""
Custom managers for accounts app.
"""

from django.contrib.auth.models import BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Custom user manager with email as username."""

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user."""
        if not email:
            raise ValueError("Email address is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", "ADMIN")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class ActiveUserManager(models.Manager):
    """Manager for active users."""

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class VerifiedUserManager(models.Manager):
    """Manager for verified users."""

    def get_queryset(self):
        return super().get_queryset().filter(is_verified=True)


class UserRoleManager(models.Manager):
    """Manager for filtering users by role."""

    def admins(self):
        return self.get_queryset().filter(role="ADMIN")

    def moderators(self):
        return self.get_queryset().filter(role="MODERATOR")

    def students(self):
        return self.get_queryset().filter(role="STUDENT")
