#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    
    # Auto-add 0.0.0.0:8000 to runserver when the user didn't supply an addr/port.
    # This preserves explicit addrport usage like `127.0.0.1:8000` and avoids
    # accidentally passing multiple positional addrports.
    if len(sys.argv) > 1 and sys.argv[1] == 'runserver':
        has_addrport = any(arg and not str(arg).startswith('-') for arg in sys.argv[2:])
        if not has_addrport:
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
