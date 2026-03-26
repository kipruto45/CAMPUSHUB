"""Production readiness checks for backend deployment."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.migrations.executor import MigrationExecutor

from apps.core.sms import get_sms_configuration_status


def _is_weak_secret(secret_key: str) -> bool:
    """Basic secret-key strength checks aligned with deploy expectations."""
    if not secret_key:
        return True
    if len(secret_key) < 50:
        return True
    if len(set(secret_key)) < 5:
        return True
    return secret_key.startswith("django-insecure-")


class Command(BaseCommand):
    """Validate critical settings and services before production deployment."""

    help = "Run production readiness checks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--allow-sqlite",
            action="store_true",
            help="Allow sqlite in readiness checks (useful for CI/local dry runs).",
        )
        parser.add_argument(
            "--require-superuser",
            action="store_true",
            help="Fail when no active superuser exists.",
        )
        parser.add_argument(
            "--strict-push",
            action="store_true",
            help="Require at least one correctly configured push provider.",
        )

    def handle(self, *args, **options):
        allow_sqlite = bool(options.get("allow_sqlite"))
        require_superuser = bool(options.get("require_superuser"))
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

        self.stdout.write("Running production readiness checks...")

        self._check_environment(ok, fail)
        self._check_debug(ok, fail)
        self._check_secret_key(ok, fail)
        self._check_hosts(ok, fail)
        self._check_csrf_origins(ok, fail)
        self._check_secure_cookies(ok, fail)
        self._check_ssl_redirect(ok, fail)
        self._check_hsts(ok, fail)
        self._check_proxy_ssl_header(ok, warn)
        self._check_database_backend(ok, fail, allow_sqlite=allow_sqlite)
        database_ready = self._check_database_connectivity(ok, fail)
        migrations_ready = self._check_migrations(ok, fail, database_ready=database_ready)
        self._check_cache(ok, fail)
        self._check_channel_layer(ok, fail)
        self._check_celery(ok, fail)
        self._check_email_backend(ok, fail)
        self._check_sms_backend(ok, warn, fail)
        self._check_superuser(
            ok,
            warn,
            fail,
            require_superuser=require_superuser,
            database_ready=database_ready,
            migrations_ready=migrations_ready,
        )
        self._check_push(ok, warn, fail, strict_push=strict_push)

        self.stdout.write(
            f"Production readiness summary: failures={failures}, warnings={warnings}"
        )
        if failures:
            raise CommandError("Production readiness checks failed.")

    @staticmethod
    def _check_environment(ok, fail):
        env = str(getattr(settings, "ENVIRONMENT", "")).strip().lower()
        if env == "production":
            ok("environment", "production")
        else:
            fail("environment", f"expected production, got {env or 'unset'}")

    @staticmethod
    def _check_debug(ok, fail):
        if getattr(settings, "DEBUG", False):
            fail("debug", "DEBUG must be False")
        else:
            ok("debug", "False")

    @staticmethod
    def _check_secret_key(ok, fail):
        secret_key = str(getattr(settings, "SECRET_KEY", "") or "")
        if _is_weak_secret(secret_key):
            fail("secret_key", "weak SECRET_KEY")
        else:
            ok("secret_key", "strong")

    @staticmethod
    def _check_hosts(ok, fail):
        hosts = [str(host).strip() for host in getattr(settings, "ALLOWED_HOSTS", [])]
        if not hosts:
            fail("allowed_hosts", "ALLOWED_HOSTS is empty")
            return
        if "*" in hosts:
            fail("allowed_hosts", "wildcard '*' is not allowed in production")
            return
        ok("allowed_hosts", ", ".join(hosts))

    @staticmethod
    def _check_csrf_origins(ok, fail):
        origins = [
            str(origin).strip()
            for origin in getattr(settings, "CSRF_TRUSTED_ORIGINS", [])
        ]
        if origins:
            ok("csrf_trusted_origins", f"{len(origins)} configured")
        else:
            fail("csrf_trusted_origins", "CSRF_TRUSTED_ORIGINS is empty")

    @staticmethod
    def _check_secure_cookies(ok, fail):
        session_secure = bool(getattr(settings, "SESSION_COOKIE_SECURE", False))
        csrf_secure = bool(getattr(settings, "CSRF_COOKIE_SECURE", False))
        if session_secure and csrf_secure:
            ok("secure_cookies", "SESSION_COOKIE_SECURE and CSRF_COOKIE_SECURE enabled")
        else:
            fail(
                "secure_cookies",
                (
                    f"SESSION_COOKIE_SECURE={session_secure}, "
                    f"CSRF_COOKIE_SECURE={csrf_secure}"
                ),
            )

    @staticmethod
    def _check_ssl_redirect(ok, fail):
        if bool(getattr(settings, "SECURE_SSL_REDIRECT", False)):
            ok("ssl_redirect", "enabled")
        else:
            fail("ssl_redirect", "SECURE_SSL_REDIRECT must be True")

    @staticmethod
    def _check_hsts(ok, fail):
        seconds = int(getattr(settings, "SECURE_HSTS_SECONDS", 0) or 0)
        if seconds > 0:
            ok("hsts", f"{seconds} seconds")
        else:
            fail("hsts", "SECURE_HSTS_SECONDS must be greater than zero")

    @staticmethod
    def _check_proxy_ssl_header(ok, warn):
        header = getattr(settings, "SECURE_PROXY_SSL_HEADER", None)
        if (
            isinstance(header, tuple)
            and len(header) == 2
            and all(str(part).strip() for part in header)
        ):
            ok("proxy_ssl_header", f"{header[0]}={header[1]}")
        else:
            warn("proxy_ssl_header", "SECURE_PROXY_SSL_HEADER is not configured")

    @staticmethod
    def _check_database_backend(ok, fail, *, allow_sqlite: bool):
        engine = str(connections["default"].settings_dict.get("ENGINE", ""))
        if "sqlite3" in engine and not allow_sqlite:
            fail("database_backend", "sqlite is not allowed for production")
            return
        ok("database_backend", engine)

    @staticmethod
    def _check_database_connectivity(ok, fail):
        try:
            connection = connections["default"]
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            ok("database_connectivity", "connection succeeded")
            return True
        except Exception as exc:  # pragma: no cover - runtime dependent
            fail("database_connectivity", str(exc))
            return False

    @staticmethod
    def _check_migrations(ok, fail, *, database_ready: bool):
        if not database_ready:
            fail("migrations", "skipped because database connectivity failed")
            return False
        try:
            connection = connections["default"]
            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            if plan:
                fail("migrations", f"{len(plan)} unapplied migrations")
                return False
            ok("migrations", "all applied")
            return True
        except Exception as exc:  # pragma: no cover - runtime dependent
            fail("migrations", str(exc))
            return False

    @staticmethod
    def _check_cache(ok, fail):
        key = "prod:readiness:cache"
        try:
            cache.set(key, "ok", timeout=15)
            value = cache.get(key)
            cache.delete(key)
            if value == "ok":
                ok("cache", "read/write succeeded")
            else:
                fail("cache", f"unexpected value: {value!r}")
        except Exception as exc:  # pragma: no cover - runtime dependent
            fail("cache", str(exc))

    @staticmethod
    def _check_channel_layer(ok, fail):
        layers = getattr(settings, "CHANNEL_LAYERS", {}) or {}
        backend = str(layers.get("default", {}).get("BACKEND", "")).strip()
        if not backend:
            fail("channel_layer", "CHANNEL_LAYERS default backend missing")
            return
        if "InMemoryChannelLayer" in backend:
            fail("channel_layer", "in-memory backend is not allowed in production")
            return
        ok("channel_layer", backend)

    @staticmethod
    def _check_celery(ok, fail):
        broker = str(getattr(settings, "CELERY_BROKER_URL", "") or "").strip()
        backend = str(getattr(settings, "CELERY_RESULT_BACKEND", "") or "").strip()
        if not broker:
            fail("celery_broker", "CELERY_BROKER_URL is empty")
        else:
            ok("celery_broker", broker)
        if not backend:
            fail("celery_result_backend", "CELERY_RESULT_BACKEND is empty")
        else:
            ok("celery_result_backend", backend)

    @staticmethod
    def _check_email_backend(ok, fail):
        backend = str(getattr(settings, "EMAIL_BACKEND", "") or "").strip()
        disallowed = {
            "django.core.mail.backends.console.EmailBackend",
            "django.core.mail.backends.locmem.EmailBackend",
            "django.core.mail.backends.filebased.EmailBackend",
            "django.core.mail.backends.dummy.EmailBackend",
        }
        if not backend:
            fail("email_backend", "EMAIL_BACKEND is empty")
            return
        if backend in disallowed:
            fail("email_backend", f"{backend} is not suitable for production")
            return
        ok("email_backend", backend)

    @staticmethod
    def _check_sms_backend(ok, warn, fail):
        status = get_sms_configuration_status()
        if not status.get("supported", False):
            fail("sms_backend", status.get("message", "unsupported SMS provider"))
            return

        provider = status.get("provider", "unknown")
        optional_missing = list(status.get("optional_missing") or [])

        if status.get("configured", False):
            details = f"{provider} configured"
            if optional_missing:
                details += f" (optional missing: {', '.join(optional_missing)})"
            ok("sms_backend", details)
            return

        warn("sms_backend", status.get("message", f"{provider} not configured"))

    @staticmethod
    def _check_superuser(ok, warn, fail, *, require_superuser: bool, database_ready: bool, migrations_ready: bool):
        if not database_ready:
            message = "skipped because database connectivity failed"
            if require_superuser:
                fail("superuser", message)
            else:
                warn("superuser", message)
            return
        if not migrations_ready:
            message = "skipped because migrations are not fully applied"
            if require_superuser:
                fail("superuser", message)
            else:
                warn("superuser", message)
            return

        user_model = get_user_model()
        count = user_model.objects.filter(is_superuser=True, is_active=True).count()
        if count > 0:
            ok("superuser", f"{count} active superuser(s)")
            return
        if require_superuser:
            fail("superuser", "no active superuser found")
        else:
            warn("superuser", "no active superuser found")

    @staticmethod
    def _check_push(ok, warn, fail, *, strict_push: bool):
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

        configured_count = 0

        for provider, enabled, configured in (
            ("push_fcm", fcm_enabled, fcm_configured),
            ("push_apns", apns_enabled, apns_configured),
        ):
            if not enabled:
                warn(provider, "disabled")
                continue
            if configured:
                configured_count += 1
                ok(provider, "enabled and configured")
            else:
                fail(provider, "enabled but incomplete configuration")

        if strict_push and configured_count == 0:
            fail("push_strict", "no enabled+configured push provider")
