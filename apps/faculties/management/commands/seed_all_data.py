"""
Compatibility wrapper for seeding the academic catalog.

Render and local workflows still invoke ``seed_all_data``. Delegate to the
comprehensive catalog importer so every environment loads the same structure.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed faculties, departments, courses, and units from the comprehensive catalog."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and report catalog changes without committing them.",
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                "seed_all_data now delegates to import_catalog_data to keep local and Render aligned."
            )
        )
        call_command("import_catalog_data", dry_run=options["dry_run"])
