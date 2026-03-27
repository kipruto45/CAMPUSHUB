"""
Helpers for loading the bundled academic catalog exports.

The mobile app depends on faculties, departments, courses, and units being
available even on fresh environments. These helpers seed the database from the
checked-in CSV exports when the catalog is empty or incomplete.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from django.db import transaction

from apps.courses.models import Course, Unit
from apps.faculties.models import Department, Faculty


ROOT_DIR = Path(__file__).resolve().parents[2]
EXPORTS_DIR = ROOT_DIR / "exports"


@dataclass(frozen=True)
class CatalogImportResult:
    seeded: bool
    faculties: int
    departments: int
    courses: int
    units: int


def _clean(value: object) -> str:
    return str(value or "").strip()


def _read_rows(filename: str) -> list[dict[str, str]]:
    path = EXPORTS_DIR / filename
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def ensure_catalog_seeded_from_exports(*, force: bool = False) -> CatalogImportResult:
    """
    Idempotently import the checked-in academic catalog into the database.

    When `force` is false, the import only runs when the core catalog tables are
    empty or incomplete. Existing rows are updated in place so the app can
    recover from partial seed data without manual intervention.
    """

    has_catalog = (
        Faculty.objects.exists()
        and Department.objects.exists()
        and Course.objects.exists()
        and Unit.objects.exists()
    )
    if has_catalog and not force:
        return CatalogImportResult(
            seeded=False,
            faculties=Faculty.objects.count(),
            departments=Department.objects.count(),
            courses=Course.objects.count(),
            units=Unit.objects.count(),
        )

    faculty_rows = _read_rows("faculties.csv")
    department_rows = _read_rows("departments.csv")
    course_rows = _read_rows("courses.csv")
    unit_rows = _read_rows("units.csv")

    if not faculty_rows or not department_rows or not course_rows or not unit_rows:
        return CatalogImportResult(
            seeded=False,
            faculties=Faculty.objects.count(),
            departments=Department.objects.count(),
            courses=Course.objects.count(),
            units=Unit.objects.count(),
        )

    with transaction.atomic():
        faculties_by_code: dict[str, Faculty] = {}
        for row in faculty_rows:
            code = _clean(row.get("code"))
            name = _clean(row.get("name"))
            if not code or not name:
                continue
            faculty, _created = Faculty.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "description": "",
                    "is_active": True,
                },
            )
            faculties_by_code[code] = faculty

        departments_by_code: dict[str, Department] = {}
        for row in department_rows:
            faculty_code = _clean(row.get("faculty"))
            code = _clean(row.get("code"))
            name = _clean(row.get("name"))
            faculty = faculties_by_code.get(faculty_code)
            if not faculty or not code or not name:
                continue
            department, _created = Department.objects.update_or_create(
                faculty=faculty,
                code=code,
                defaults={
                    "name": name,
                    "description": "",
                    "is_active": True,
                },
            )
            departments_by_code[code] = department

        courses_by_code: dict[str, Course] = {}
        for row in course_rows:
            department_code = _clean(row.get("department"))
            code = _clean(row.get("code"))
            name = _clean(row.get("name"))
            years_raw = _clean(row.get("years"))
            department = departments_by_code.get(department_code)
            if not department or not code or not name:
                continue
            try:
                duration_years = max(1, int(years_raw or "4"))
            except (TypeError, ValueError):
                duration_years = 4
            course, _created = Course.objects.update_or_create(
                department=department,
                code=code,
                defaults={
                    "name": name,
                    "description": "",
                    "duration_years": duration_years,
                    "is_active": True,
                },
            )
            courses_by_code[code] = course

        for row in unit_rows:
            course_code = _clean(row.get("course"))
            semester = _clean(row.get("semester"))
            code = _clean(row.get("code"))
            name = _clean(row.get("name"))
            year_raw = _clean(row.get("year"))
            course = courses_by_code.get(course_code)
            if not course or not code or not name or semester not in {"1", "2"}:
                continue
            try:
                year_of_study = max(1, int(year_raw or "1"))
            except (TypeError, ValueError):
                year_of_study = 1
            Unit.objects.update_or_create(
                course=course,
                code=code,
                semester=semester,
                defaults={
                    "name": name,
                    "description": "",
                    "year_of_study": year_of_study,
                    "is_active": True,
                },
            )

    return CatalogImportResult(
        seeded=True,
        faculties=Faculty.objects.count(),
        departments=Department.objects.count(),
        courses=Course.objects.count(),
        units=Unit.objects.count(),
    )
