import pytest
from datetime import date

from apps.calendar.services import TimetableImportService
from apps.calendar.models import AcademicCalendar, PersonalSchedule
from apps.accounts.models import User


@pytest.mark.django_db
def test_import_ics_creates_personal_schedule():
    user = User.objects.create_user(username="ics_user", password="pass")
    AcademicCalendar.objects.create(
        name="Test Cal",
        faculty=None,
        year=2026,
        semester="Fall",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        is_active=True,
    )

    ics_content = "\n".join(
        [
            "BEGIN:VCALENDAR",
            "BEGIN:VEVENT",
            "SUMMARY:Exam Prep",
            "DTSTART;VALUE=DATE:20260401",
            "DTEND;VALUE=DATE:20260402",
            "DESCRIPTION:Study for finals",
            "END:VEVENT",
            "END:VCALENDAR",
        ]
    )

    result = TimetableImportService.import_timetable(
        file_content=ics_content,
        import_type="ics",
        user=user,
    )

    assert result["success"] is True
    assert result["imported_count"] == 1
    event = PersonalSchedule.objects.get(user=user)
    assert event.title == "Exam Prep"
    assert event.is_all_day is True
