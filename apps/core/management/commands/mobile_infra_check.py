"""Infrastructure readiness checks for mobile backend integration."""

from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.urls import NoReverseMatch, reverse

try:
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer
except Exception:  # pragma: no cover - channels import may be unavailable in lean envs
    async_to_sync = None
    get_channel_layer = None


class Command(BaseCommand):
    """Validate core infra dependencies required by mobile clients."""

    help = "Run mobile backend infrastructure checks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict-push",
            action="store_true",
            help="Fail when an enabled push provider is not fully configured.",
        )

    def handle(self, *args, **options):
        strict_push = bool(options.get("strict_push"))
        failures = 0
        warnings = 0

        def ok(label: str, details: str = ""):
            suffix = f" - {details}" if details else ""
            self.stdout.write(self.style.SUCCESS(f"[OK] {label}{suffix}"))

        def warn(label: str, details: str = ""):
            nonlocal warnings
            warnings += 1
            suffix = f" - {details}" if details else ""
            self.stdout.write(self.style.WARNING(f"[WARN] {label}{suffix}"))

        def fail(label: str, details: str = ""):
            nonlocal failures
            failures += 1
            suffix = f" - {details}" if details else ""
            self.stdout.write(self.style.ERROR(f"[FAIL] {label}{suffix}"))

        self.stdout.write("Running mobile infrastructure checks...")

        self._check_database(ok, fail)
        self._check_cache(ok, fail)
        self._check_mobile_api_version(ok, fail)
        self._check_middleware(ok, fail)
        self._check_mobile_throttle_rates(ok, warn, fail)
        self._check_mobile_urls(ok, fail)
        self._check_channel_layer(ok, warn, fail)
        self._check_push_settings(ok, warn, fail, strict_push=strict_push)

        self.stdout.write(
            f"Mobile infra check summary: failures={failures}, warnings={warnings}"
        )
        if failures:
            raise CommandError(
                "Mobile backend infrastructure checks failed. Resolve failures above."
            )

    @staticmethod
    def _check_database(ok, fail):
        """Verify DB connectivity with a trivial query."""
        try:
            connection = connections["default"]
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            ok("database", "connection succeeded")
        except Exception as exc:  # pragma: no cover - runtime environment dependent
            fail("database", str(exc))

    @staticmethod
    def _check_cache(ok, fail):
        """Verify cache read/write behavior."""
        key = "mobile:infra:check"
        try:
            cache.set(key, "ok", timeout=30)
            value = cache.get(key)
            cache.delete(key)
            if value == "ok":
                ok("cache", "read/write succeeded")
            else:
                fail("cache", f"unexpected cache value: {value!r}")
        except Exception as exc:  # pragma: no cover - runtime environment dependent
            fail("cache", str(exc))

    @staticmethod
    def _check_mobile_api_version(ok, fail):
        version = str(getattr(settings, "MOBILE_API_VERSION", "")).strip()
        if version:
            ok("mobile_api_version", version)
        else:
            fail("mobile_api_version", "MOBILE_API_VERSION is empty")

    @staticmethod
    def _check_middleware(ok, fail):
        middleware = list(getattr(settings, "MIDDLEWARE", []))
        required = "apps.core.middleware.RequestContextMiddleware"
        if required in middleware:
            ok("request_context_middleware", "installed")
        else:
            fail("request_context_middleware", f"missing {required}")

    @staticmethod
    def _check_mobile_throttle_rates(ok, warn, fail):
        if str(getattr(settings, "ENVIRONMENT", "")).strip().lower() == "testing":
            warn(
                "mobile_throttle_rates",
                "skipped in testing (throttles intentionally disabled)",
            )
            return

        rates = (
            getattr(settings, "REST_FRAMEWORK", {}).get("DEFAULT_THROTTLE_RATES", {})
            or {}
        )
        required_keys = {
            "mobile_anon",
            "mobile_auth",
            "mobile_upload",
            "mobile_download",
        }
        missing = sorted(required_keys.difference(rates.keys()))
        if missing:
            fail("mobile_throttle_rates", f"missing keys: {', '.join(missing)}")
        else:
            ok("mobile_throttle_rates", "configured")

    @staticmethod
    def _check_mobile_urls(ok, fail):
        names = [
            "api:api_info",
            "api:mobile_login",
            "api:mobile_refresh_token",
            "api:mobile_resources",
            "api:mobile_resource_detail",
            "api:mobile_dashboard",
            "api:mobile_notifications",
            "api:mobile_bookmarks",
            "api:mobile_favorites",
            "api:mobile_library_summary",
        ]
        unresolved: list[str] = []

        for name in names:
            kwargs = {}
            if name == "api:mobile_resource_detail":
                kwargs = {"resource_id": "00000000-0000-0000-0000-000000000001"}
            try:
                reverse(name, kwargs=kwargs)
            except NoReverseMatch:
                unresolved.append(name)

        if unresolved:
            fail("mobile_urls", f"missing routes: {', '.join(unresolved)}")
        else:
            ok("mobile_urls", "core routes resolved")

    @staticmethod
    def _check_channel_layer(ok, warn, fail):
        channel_layers = getattr(settings, "CHANNEL_LAYERS", None) or {}
        if not channel_layers:
            warn("channel_layer", "CHANNEL_LAYERS not configured")
            return

        if get_channel_layer is None or async_to_sync is None:
            warn("channel_layer", "channels libraries unavailable")
            return

        backend = str(channel_layers.get("default", {}).get("BACKEND", ""))
        channel_layer = get_channel_layer()
        if channel_layer is None:
            fail("channel_layer", "get_channel_layer() returned None")
            return

        if "InMemoryChannelLayer" not in backend:
            # For networked backends, avoid blocking connection checks here.
            ok("channel_layer", f"configured ({backend})")
            return

        try:
            channel_name = async_to_sync(channel_layer.new_channel)(
                "mobile_infra_check."
            )
            async_to_sync(channel_layer.send)(
                channel_name, {"type": "infra.check", "value": "ok"}
            )
            message = async_to_sync(channel_layer.receive)(channel_name)
            if message.get("value") == "ok":
                ok("channel_layer", "send/receive succeeded")
            else:
                fail("channel_layer", f"unexpected message: {message!r}")
        except Exception as exc:  # pragma: no cover - runtime environment dependent
            fail("channel_layer", str(exc))

    @staticmethod
    def _check_push_settings(ok, warn, fail, *, strict_push: bool):
        fcm_enabled = bool(getattr(settings, "FCM_ENABLED", False))
        fcm_configured = bool(
            getattr(settings, "FCM_SERVER_KEY", "")
            and getattr(settings, "FCM_PROJECT_ID", "")
        )

        apns_enabled = bool(getattr(settings, "APNS_ENABLED", False))
        apns_configured = bool(
            getattr(settings, "APNS_TEAM_ID", "")
            and getattr(settings, "APNS_KEY_ID", "")
            and (
                getattr(settings, "APNS_AUTH_KEY", "")
                or getattr(settings, "APNS_AUTH_KEY_PATH", "")
            )
        )

        for provider, enabled, configured in (
            ("fcm", fcm_enabled, fcm_configured),
            ("apns", apns_enabled, apns_configured),
        ):
            if not enabled:
                warn(f"push_{provider}", "disabled")
                continue

            if configured:
                ok(f"push_{provider}", "enabled and configured")
                continue

            if strict_push:
                fail(f"push_{provider}", "enabled but incomplete configuration")
            else:
                warn(f"push_{provider}", "enabled but incomplete configuration")
