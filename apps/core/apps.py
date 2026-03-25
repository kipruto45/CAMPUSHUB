from django.apps import AppConfig
import os


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        """Optionally run migrations on startup for non-Render workflows.

        Render already runs `manage.py migrate` in `render.yaml` buildCommand.
        Keeping migrations inside app startup can stall/loop worker boot.
        """
        env = os.environ.get("ENVIRONMENT", "").strip().lower()
        auto_migrate = os.environ.get("AUTO_MIGRATE_ON_STARTUP", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        # Disabled by default: explicit opt-in only.
        if env != "production" or not auto_migrate:
            return

        try:
            from django.core.management import call_command
            from django.db import connection

            connection.ensure_connection()
            print("Running startup auto-migrations...")
            call_command("migrate", "--noinput", verbosity=0)
            print("Startup auto-migrations complete.")
        except Exception as exc:
            print(f"Startup auto-migrations skipped due to error: {exc}")
