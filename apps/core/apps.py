from django.apps import AppConfig
import os


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        """Run migrations automatically on startup in production."""
        env = os.environ.get('ENVIRONMENT', '')
        
        # Only run in production
        if env == 'production':
            try:
                from django.core.management import call_command
                from django.db import connection
                
                # Check if we can connect to database
                connection.ensure_connection()
                
                # Run migrations
                print("Running migrations automatically...")
                call_command('migrate', '--noinput', verbosity=0)
                print("Migrations complete.")
            except Exception as e:
                print(f"Auto-migration: {e}")
                # Try without verbosity to avoid output issues
                try:
                    call_command('migrate', '--noinput')
                except:
                    pass
