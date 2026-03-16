from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        """Run migrations automatically on startup."""
        # Only run in production/with database
        import os
        import django
        
        # Check if we should run migrations
        env = os.environ.get('ENVIRONMENT', 'development')
        
        if env == 'production':
            from django.core.management import call_command
            from django.db import connection
            
            # Check if tables exist
            try:
                with connection.schema_editor() as schema_editor:
                    # Try to get the user table
                    from django.apps import apps
                    try:
                        apps.get_model('accounts', 'User')
                    except:
                        # Run migrations
                        print("Running migrations automatically...")
                        call_command('migrate', '--noinput')
                        print("Migrations complete.")
            except Exception as e:
                print(f"Auto-migration check: {e}")
