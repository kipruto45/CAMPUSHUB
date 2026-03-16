#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    
    # Auto-add 0.0.0.0 to runserver for network access
    if len(sys.argv) > 1 and sys.argv[1] == 'runserver':
        if '0.0.0.0' not in sys.argv[2] if len(sys.argv) > 2 else True:
            # Insert 0.0.0.0:8000 after runserver
            sys.argv.insert(2, '0.0.0.0:8000')
    
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
