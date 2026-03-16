"""SMTP delivery verification command."""

from __future__ import annotations

from django.conf import settings
from django.core.mail import get_connection
from django.core.management.base import BaseCommand, CommandError

from apps.core.emails import EmailService


class Command(BaseCommand):
    """Validate email backend configuration and send a test message."""

    help = "Check email backend readiness and send a test email."

    NON_SMTP_BACKENDS = {
        "django.core.mail.backends.console.EmailBackend",
        "django.core.mail.backends.filebased.EmailBackend",
        "django.core.mail.backends.locmem.EmailBackend",
        "django.core.mail.backends.dummy.EmailBackend",
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            type=str,
            help="Recipient email for the test message (defaults to EMAIL_HOST_USER).",
        )
        parser.add_argument(
            "--strict-backend",
            action="store_true",
            help="Fail if backend is not SMTP.",
        )

    def handle(self, *args, **options):
        backend = str(getattr(settings, "EMAIL_BACKEND", "") or "")
        strict_backend = bool(options.get("strict_backend"))

        self.stdout.write(f"EMAIL_BACKEND: {backend}")
        if backend in self.NON_SMTP_BACKENDS:
            message = (
                "Email backend is non-SMTP, so real inbox delivery is disabled."
            )
            if strict_backend:
                raise CommandError(message)
            self.stdout.write(self.style.WARNING(f"[WARN] {message}"))
            return

        missing = []
        if not str(getattr(settings, "EMAIL_HOST", "") or "").strip():
            missing.append("EMAIL_HOST")
        if not int(getattr(settings, "EMAIL_PORT", 0) or 0):
            missing.append("EMAIL_PORT")
        if not str(getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip():
            missing.append("DEFAULT_FROM_EMAIL")
        if not str(getattr(settings, "EMAIL_HOST_USER", "") or "").strip():
            missing.append("EMAIL_HOST_USER")
        if not str(getattr(settings, "EMAIL_HOST_PASSWORD", "") or "").strip():
            missing.append("EMAIL_HOST_PASSWORD")

        if missing:
            raise CommandError(
                "Missing required SMTP settings: " + ", ".join(missing)
            )

        recipient = (
            (options.get("to") or "").strip()
            or str(getattr(settings, "EMAIL_HOST_USER", "") or "").strip()
        )
        if not recipient:
            raise CommandError("Provide --to or set EMAIL_HOST_USER in environment.")

        try:
            connection = get_connection(fail_silently=False)
            connection.open()
            connection.close()
        except Exception as exc:  # pragma: no cover - environment dependent
            raise CommandError(f"SMTP connection check failed: {exc}") from exc

        try:
            EmailService.send_email(
                subject="CampusHub email delivery check",
                message=(
                    "This is a test email from CampusHub.\n\n"
                    "If you received this, SMTP delivery is working."
                ),
                recipient_list=[recipient],
                fail_silently=False,
            )
        except Exception as exc:  # pragma: no cover - environment dependent
            raise CommandError(f"SMTP send failed: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(f"[OK] Test email sent successfully to {recipient}")
        )
