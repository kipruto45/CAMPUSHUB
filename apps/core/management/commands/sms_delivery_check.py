"""SMS delivery readiness verification command."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.core.sms import get_sms_configuration_status, sms_service


class Command(BaseCommand):
    """Validate SMS backend configuration and optionally send a live test."""

    help = "Check SMS provider readiness and optionally send a test SMS."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            type=str,
            help="Recipient phone number in E.164 format for a live test send.",
        )
        parser.add_argument(
            "--message",
            type=str,
            default="CampusHub SMS delivery check. If you received this, SMS delivery is working.",
            help="Custom message body for --send.",
        )
        parser.add_argument(
            "--send",
            action="store_true",
            help="Send a live test SMS after configuration passes.",
        )
        parser.add_argument(
            "--strict-config",
            action="store_true",
            help="Fail if SMS configuration is incomplete.",
        )

    def handle(self, *args, **options):
        status = get_sms_configuration_status()
        strict_config = bool(options.get("strict_config"))
        send_live = bool(options.get("send"))

        self.stdout.write(f"SMS_PROVIDER: {status['raw_provider'] or status['provider']}")

        if not status["supported"]:
            raise CommandError(status["message"])

        if not status["configured"]:
            message = status["message"]
            if strict_config or send_live:
                raise CommandError(message)
            self.stdout.write(self.style.WARNING(f"[WARN] {message}"))
            return

        if status["optional_missing"]:
            self.stdout.write(
                self.style.WARNING(
                    "[WARN] Optional SMS settings not configured: "
                    + ", ".join(status["optional_missing"])
                )
            )

        self.stdout.write(self.style.SUCCESS(f"[OK] {status['message']}"))

        if not send_live:
            return

        recipient = str(options.get("to") or "").strip()
        if not recipient:
            raise CommandError("Provide --to when using --send.")

        result = sms_service.send(phone=recipient, message=options["message"])
        if not result.get("success"):
            raise CommandError(
                "SMS send failed: " + str(result.get("error") or "unknown error")
            )

        self.stdout.write(
            self.style.SUCCESS(f"[OK] Test SMS sent successfully to {recipient}")
        )
