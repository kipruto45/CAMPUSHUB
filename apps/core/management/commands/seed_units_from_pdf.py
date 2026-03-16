"""
Management command to seed Units (courses' units/subjects) by parsing the
official timetable PDF. It groups each unit under the correct course, year,
and semester.
"""

import re
import subprocess
from collections import defaultdict

from django.core.management.base import BaseCommand

from apps.courses.models import Course, Unit


class Command(BaseCommand):
    help = "Seed units from timetable PDF into the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default="/home/kipruto/Downloads/FINAL TEACHING TIMETABLE FOR UNDERGRADUATE, DIPLOMA &  CERTIFICATE FEBRUARY-MAY 2026 Final.pdf",
            help="Absolute path to the timetable PDF",
        )

    def handle(self, *args, **options):
        pdf_path = options["path"]
        self.stdout.write(f"Parsing timetable: {pdf_path}")

        try:
            text = subprocess.check_output(["pdftotext", pdf_path, "-"]).decode(
                "utf-8", errors="ignore"
            )
        except FileNotFoundError:
            self.stderr.write("pdftotext is required but not available.")
            return
        except subprocess.CalledProcessError as exc:
            self.stderr.write(f"Failed to read PDF: {exc}")
            return

        lines = [line.strip() for line in text.splitlines()]

        course_re = re.compile(r"^([A-Z]{2,}[A-Z0-9]*)\\s*Y(\\d)\\s*S(\\d)")
        unit_code_re = re.compile(r"^[A-Z]{3,}[A-Z0-9]*\\s*\\d{3,4}[A-Z]?$")

        entries = []
        seen = set()

        i = 0
        while i < len(lines):
            line = lines[i]
            course_match = course_re.match(line)
            if not course_match:
                i += 1
                continue

            course_code, year, sem = (
                course_match.group(1),
                int(course_match.group(2)),
                int(course_match.group(3)),
            )

            # find unit code
            j = i + 1
            unit_code = None
            while j < len(lines):
                if unit_code_re.match(lines[j]):
                    unit_code = lines[j]
                    j += 1
                    break
                j += 1

            if not unit_code:
                i += 1
                continue

            # find unit name (first non-empty line that is not another course or unit code)
            unit_name = None
            while j < len(lines):
                candidate = lines[j]
                if candidate and not course_re.match(candidate) and not unit_code_re.match(
                    candidate
                ):
                    unit_name = candidate
                    break
                j += 1

            if not unit_name:
                i = j
                continue

            key = (course_code, unit_code)
            if key in seen:
                i = j
                continue
            seen.add(key)

            entries.append(
                {
                    "course_code": course_code,
                    "unit_code": unit_code,
                    "unit_name": unit_name,
                    "year": year,
                    "semester": sem,
                }
            )

            i = j

        # group by course and create
        created = 0
        missing_courses = defaultdict(list)
        for entry in entries:
            try:
                course = Course.objects.get(code=entry["course_code"])
            except Course.DoesNotExist:
                missing_courses[entry["course_code"]].append(entry["unit_code"])
                continue

            unit, was_created = Unit.objects.get_or_create(
                code=entry["unit_code"],
                course=course,
                defaults={
                    "name": entry["unit_name"],
                    "year_of_study": entry["year"],
                    "semester": str(entry["semester"]),
                },
            )
            if was_created:
                created += 1

        self.stdout.write(self.style.SUCCESS(f"Created {created} units"))
        if missing_courses:
            self.stdout.write("Courses missing in DB (units skipped):")
            for course_code, unit_codes in missing_courses.items():
                self.stdout.write(
                    f"  {course_code}: {', '.join(sorted(set(unit_codes)))}"
                )
