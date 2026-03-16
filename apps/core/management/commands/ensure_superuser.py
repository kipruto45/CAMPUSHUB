"""Ensure a superuser exists using CLI args or environment variables."""

from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


def _as_bool(value) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


class Command(BaseCommand):
    """Create or update a superuser non-interactively."""

    help = "Create/update a superuser from args/env (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--email", type=str, help="Superuser email")
        parser.add_argument("--password", type=str, help="Superuser password")
        parser.add_argument("--full-name", type=str, default="", help="Display name")
        parser.add_argument(
            "--update-password",
            action="store_true",
            help="Update password when user already exists.",
        )

    def handle(self, *args, **options):
        email = (options.get("email") or os.getenv("DJANGO_SUPERUSER_EMAIL") or "").strip()
        password = (
            options.get("password") or os.getenv("DJANGO_SUPERUSER_PASSWORD") or ""
        ).strip()
        full_name = (
            options.get("full_name")
            or os.getenv("DJANGO_SUPERUSER_FULL_NAME")
            or "CampusHub Admin"
        ).strip()
        update_password = bool(options.get("update_password")) or _as_bool(
            os.getenv("DJANGO_SUPERUSER_UPDATE_PASSWORD")
        )

        if not email:
            raise CommandError("Superuser email is required.")
        if not password:
            raise CommandError("Superuser password is required.")

        user_model = get_user_model()
        user = user_model.objects.filter(email=email).first()
        if user is None:
            created = user_model.objects.create_superuser(
                email=email,
                password=password,
                full_name=full_name,
                role="ADMIN",
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Superuser created: {created.email}"
                )
            )
            return

        changed = False
        if not user.is_staff:
            user.is_staff = True
            changed = True
        if not user.is_superuser:
            user.is_superuser = True
            changed = True
        if not user.is_active:
            user.is_active = True
            changed = True
        if str(getattr(user, "role", "")).upper() != "ADMIN":
            user.role = "ADMIN"
            changed = True
        if full_name and getattr(user, "full_name", "") != full_name:
            user.full_name = full_name
            changed = True
        if update_password or not user.has_usable_password():
            user.set_password(password)
            changed = True

        if changed:
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Superuser updated: {user.email}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Superuser already ready: {user.email}"))
