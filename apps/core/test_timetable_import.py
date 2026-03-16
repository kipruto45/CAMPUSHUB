from __future__ import annotations

import pytest

from apps.core.services import timetable_import
from apps.core.services.timetable_import import (
    ParsedTimetableRow,
    cluster_timetable_rows,
    import_timetable_pdf,
    parse_course_label,
)
from apps.courses.models import Course, Unit
from apps.faculties.models import Department, Faculty


def test_parse_course_label_handles_timetable_variants():
    assert parse_course_label("BSc.AM 2.1") == ("BSc.AM", 2, "1")
    assert parse_course_label("BEEP YIS1") == ("BEEP", 1, "1")
    assert parse_course_label("BDRMY3S1") == ("BDRM", 3, "1")
    assert parse_course_label("BBIT Y2 S1(SSP)") == ("BBIT", 2, "1")


def test_cluster_timetable_rows_prefers_non_ssp_variant_on_name_conflict():
    rows = [
        ParsedTimetableRow(
            course_label="BCOM Y2 S1",
            course_code="BCOM",
            year_of_study=2,
            semester="1",
            unit_code="BACC 2106",
            unit_name="ACCOUNTING FOR ASSETS",
            source_line="regular",
            ssp_variant=False,
        ),
        ParsedTimetableRow(
            course_label="BCOM Y2 S1 (SSP)",
            course_code="BCOM",
            year_of_study=2,
            semester="1",
            unit_code="BACC 2106",
            unit_name="ACCOUNTING FOR CO-OPERATIVES",
            source_line="ssp",
            ssp_variant=True,
        ),
    ]

    clustered, warnings = cluster_timetable_rows(rows)

    assert len(clustered) == 1
    assert clustered[0].unit_name == "ACCOUNTING FOR ASSETS"
    assert warnings


@pytest.mark.django_db
def test_import_timetable_pdf_updates_alias_course_and_creates_units(monkeypatch):
    faculty = Faculty.objects.create(code="SOC", name="Legacy Faculty")
    department = Department.objects.create(
        faculty=faculty,
        code="CS",
        name="Legacy Department",
    )
    legacy_course = Course.objects.create(
        department=department,
        code="BCSC",
        name="Legacy Computer Science",
        duration_years=4,
    )

    parsed_rows = [
        ParsedTimetableRow(
            course_label="BCS Y1 S1",
            course_code="BCS",
            year_of_study=1,
            semester="1",
            unit_code="BCIT 1101",
            unit_name="FOUNDATIONS OF INFORMATION TECHNOLOGY",
            source_line="row-1",
        ),
        ParsedTimetableRow(
            course_label="BSc.Fin Y2 S1",
            course_code="BSc.Fin",
            year_of_study=2,
            semester="1",
            unit_code="BACC 2106",
            unit_name="ACCOUNTING FOR ASSETS",
            source_line="row-2",
        ),
    ]

    monkeypatch.setattr(
        timetable_import,
        "parse_timetable_pdf",
        lambda pdf_path: (parsed_rows, []),
    )

    report = import_timetable_pdf("/tmp/does-not-matter.pdf")

    legacy_course.refresh_from_db()
    assert legacy_course.code == "BCS"
    assert legacy_course.name == "Bachelor of Science in Computer Science"
    assert report.courses_created == 1
    assert report.courses_updated == 1
    assert Unit.objects.filter(course=legacy_course, code="BCIT 1101", semester="1").exists()
    assert Course.objects.filter(code="BSc.Fin").exists()
