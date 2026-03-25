import io
from pathlib import Path

import pytest
from django.core.management import call_command

from apps.calendar.models import PersonalSchedule
from apps.accounts.models import User


@pytest.mark.django_db
def test_import_calendar_csv(tmp_path):
    user = User.objects.create_user(username="caluser", password="pass")
    csv_content = "title,date,start_time,end_time,category,is_all_day\nClass,2026-03-25,09:00,10:00,lecture,false\n"
    file_path = tmp_path / "events.csv"
    file_path.write_text(csv_content)

    call_command("import_calendar", str(file_path), "--user-id", str(user.id))

    event = PersonalSchedule.objects.get(user=user)
    assert event.title == "Class"
    assert event.start_time.hour == 9


@pytest.mark.django_db
def test_import_calendar_ics(tmp_path):
    user = User.objects.create_user(username="caluser2", password="pass")
    ics = "\n".join(
        [
            "BEGIN:VCALENDAR",
            "BEGIN:VEVENT",
            "SUMMARY:Exam",
            "DTSTART;VALUE=DATE:20260326",
            "DTEND;VALUE=DATE:20260327",
            "END:VEVENT",
            "END:VCALENDAR",
        ]
    )
    file_path = tmp_path / "events.ics"
    file_path.write_text(ics)

    call_command("import_calendar", str(file_path), "--user-id", str(user.id))

    event = PersonalSchedule.objects.get(user=user)
    assert event.title == "Exam"
    assert event.is_all_day is True
