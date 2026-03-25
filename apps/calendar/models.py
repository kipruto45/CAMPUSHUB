"""
Calendar and timetable models for CampusHub.
Provides integration with university academic schedules.
"""

import uuid
from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class AcademicCalendar(TimeStampedModel):
    """Academic calendar for a faculty/department."""

    SEMESTER_CHOICES = [
        ("1", "Semester 1"),
        ("2", "Semester 2"),
        ("3", "Semester 3 (Summer)"),
    ]

    YEAR_CHOICES = [(str(y), str(y)) for y in range(2020, 2030)]

    name = models.CharField(max_length=100)
    faculty = models.ForeignKey(
        "faculties.Faculty",
        on_delete=models.CASCADE,
        related_name="academic_calendars",
        null=True,
        blank=True,
    )
    department = models.ForeignKey(
        "faculties.Department",
        on_delete=models.CASCADE,
        related_name="academic_calendars",
        null=True,
        blank=True,
    )
    year = models.CharField(max_length=4, choices=YEAR_CHOICES)
    semester = models.CharField(max_length=2, choices=SEMESTER_CHOICES)

    # Semester dates
    start_date = models.DateField()
    end_date = models.DateField()
    mid_semester_start = models.DateField(null=True, blank=True)
    mid_semester_end = models.DateField(null=True, blank=True)
    exam_start_date = models.DateField(null=True, blank=True)
    exam_end_date = models.DateField(null=True, blank=True)

    # Recess dates
    break_start_date = models.DateField(null=True, blank=True)
    break_end_date = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = "calendar"
        unique_together = ["faculty", "year", "semester"]
        ordering = ["-year", "-semester"]
        verbose_name = "Academic Calendar"
        verbose_name_plural = "Academic Calendars"

    def __str__(self):
        return f"{self.year} - {self.get_semester_display()}"


class Timetable(TimeStampedModel):
    """Course timetable with scheduled classes."""

    DAY_CHOICES = [
        ("monday", "Monday"),
        ("tuesday", "Tuesday"),
        ("wednesday", "Wednesday"),
        ("thursday", "Thursday"),
        ("friday", "Friday"),
        ("saturday", "Saturday"),
        ("sunday", "Sunday"),
    ]

    TYPE_CHOICES = [
        ("lecture", "Lecture"),
        ("tutorial", "Tutorial"),
        ("lab", "Laboratory"),
        ("seminar", "Seminar"),
        ("fieldwork", "Field Work"),
        ("exam", "Exam"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Academic calendar reference
    academic_calendar = models.ForeignKey(
        AcademicCalendar,
        on_delete=models.CASCADE,
        related_name="timetables",
    )

    # Course info
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="timetables",
    )
    unit = models.ForeignKey(
        "courses.Unit",
        on_delete=models.CASCADE,
        related_name="timetables",
        null=True,
        blank=True,
    )

    # Schedule
    day = models.CharField(max_length=20, choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="lecture")

    # Location
    building = models.CharField(max_length=100, blank=True)
    room = models.CharField(max_length=50, blank=True)
    is_virtual = models.BooleanField(default=False)
    virtual_link = models.URLField(blank=True)

    # Instructor
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teaching_timetables",
    )

    # Year of study
    year_of_study = models.PositiveIntegerField(null=True, blank=True)

    # Recurring
    is_recurring = models.BooleanField(default=True)
    weeks = models.JSONField(default=list, blank=True)  # List of week numbers

    # Group (for different student groups)
    group_name = models.CharField(max_length=50, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = "calendar"
        ordering = ["day", "start_time"]
        verbose_name = "Timetable"
        verbose_name_plural = "Timetables"
        indexes = [
            models.Index(fields=["academic_calendar", "day", "start_time"]),
            models.Index(fields=["unit", "day"]),
            models.Index(fields=["instructor", "day"]),
        ]

    def __str__(self):
        return f"{self.unit.code} - {self.get_day_display()} {self.start_time}"


class TimetableOverride(TimeStampedModel):
    """Special timetable events (cancelled classes, extra sessions)."""

    TYPE_CHOICES = [
        ("cancelled", "Cancelled"),
        ("rescheduled", "Rescheduled"),
        ("extra", "Extra Session"),
        ("moved", "Moved to New Location"),
    ]

    timetable = models.ForeignKey(
        Timetable,
        on_delete=models.CASCADE,
        related_name="overrides",
    )

    date = models.DateField()
    override_type = models.CharField(max_length=20, choices=TYPE_CHOICES)

    # New time/location (for rescheduled/moved)
    new_start_time = models.TimeField(null=True, blank=True)
    new_end_time = models.TimeField(null=True, blank=True)
    new_building = models.CharField(max_length=100, blank=True)
    new_room = models.CharField(max_length=50, blank=True)
    new_virtual_link = models.URLField(blank=True)

    # Reason
    reason = models.TextField(blank=True)

    # Notify students
    notify_students = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_timetable_overrides",
    )

    class Meta:
        app_label = "calendar"
        ordering = ["-date"]
        verbose_name = "Timetable Override"
        verbose_name_plural = "Timetable Overrides"

    def __str__(self):
        return f"{self.timetable} - {self.date} ({self.get_override_type_display()})"


class PersonalSchedule(TimeStampedModel):
    """User's personal schedule/events (not from official timetable)."""

    CATEGORY_CHOICES = [
        ("study", "Study Session"),
        ("assignment", "Assignment Due"),
        ("exam", "Exam"),
        ("club", "Club Activity"),
        ("personal", "Personal"),
        ("reminder", "Reminder"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="personal_schedules",
    )

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)

    # Date/time
    date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    is_all_day = models.BooleanField(default=False)

    # Related to course/unit
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="personal_schedules",
    )
    unit = models.ForeignKey(
        "courses.Unit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="personal_schedules",
    )

    # Reminder
    reminder_minutes = models.PositiveIntegerField(
        default=30,
        help_text="Minutes before event to send reminder"
    )
    reminder_sent = models.BooleanField(default=False)

    # Recurrence
    is_recurring = models.BooleanField(default=False)
    recurrence_pattern = models.JSONField(default=dict, blank=True)

    # Visibility
    is_private = models.BooleanField(default=True)

    class Meta:
        app_label = "calendar"
        ordering = ["date", "start_time"]
        verbose_name = "Personal Schedule"
        verbose_name_plural = "Personal Schedules"
        indexes = [
            models.Index(fields=["user", "date"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.date}"


class ScheduleExport(TimeStampedModel):
    """Export calendar to external systems (Google Calendar, etc)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="schedule_exports",
    )

    export_type = models.CharField(max_length=50)  # google, ical, csv

    # OAuth tokens for external services
    external_tokens = models.JSONField(default=dict, blank=True)

    # Last sync
    last_sync = models.DateTimeField(null=True, blank=True)
    sync_enabled = models.BooleanField(default=True)

    # What to sync
    sync_official_timetable = models.BooleanField(default=True)
    sync_personal_events = models.BooleanField(default=True)
    sync_exams = models.BooleanField(default=True)
    sync_announcements = models.BooleanField(default=False)

    class Meta:
        app_label = "calendar"
        verbose_name = "Schedule Export"
        verbose_name_plural = "Schedule Exports"

    def __str__(self):
        return f"{self.user.username} - {self.export_type}"