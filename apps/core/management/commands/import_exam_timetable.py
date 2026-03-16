"""Import academic structure from a timetable PDF."""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.services.timetable_import import import_timetable_pdf, preview_timetable_pdf


class Command(BaseCommand):
    """Import courses and units from a timetable PDF."""

    help = "Parse a timetable PDF and upsert faculties, departments, courses, and units."

    def add_arguments(self, parser):
        parser.add_argument(
            "pdf_path",
            type=str,
            help="Absolute or relative path to the timetable PDF.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and summarize the timetable without committing database changes.",
        )

    def handle(self, *args, **options):
        pdf_path = Path(options["pdf_path"]).expanduser().resolve()
        if not pdf_path.exists():
            raise CommandError(f"File not found: {pdf_path}")

        dry_run = bool(options.get("dry_run"))
        try:
            report = (
                preview_timetable_pdf(pdf_path)
                if dry_run
                else import_timetable_pdf(pdf_path)
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        mode = "Dry run" if dry_run else "Import"
        self.stdout.write(self.style.SUCCESS(f"{mode} completed for {pdf_path}"))
        self.stdout.write(f"Clustered units: {report.clustered_units}")
        if not dry_run:
            self.stdout.write(
                "Faculties created/updated: "
                f"{report.faculties_created}/{report.faculties_updated}"
            )
            self.stdout.write(
                "Departments created/updated: "
                f"{report.departments_created}/{report.departments_updated}"
            )
            self.stdout.write(
                "Courses created/updated: "
                f"{report.courses_created}/{report.courses_updated}"
            )
            self.stdout.write(
                "Units created/updated: "
                f"{report.units_created}/{report.units_updated}"
            )

        if report.warnings:
            self.stdout.write(self.style.WARNING("Warnings:"))
            for warning in report.warnings:
                self.stdout.write(f" - {warning}")
