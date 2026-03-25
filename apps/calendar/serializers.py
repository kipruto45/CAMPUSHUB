"""Serializers for calendar and timetable APIs."""

from rest_framework import serializers

from .models import (
    AcademicCalendar,
    PersonalSchedule,
    Timetable,
    TimetableOverride,
)


class AcademicCalendarSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicCalendar
        fields = [
            "id",
            "name",
            "faculty",
            "department",
            "year",
            "semester",
            "start_date",
            "end_date",
            "mid_semester_start",
            "mid_semester_end",
            "exam_start_date",
            "exam_end_date",
            "break_start_date",
            "break_end_date",
            "is_active",
            "metadata",
            "created_at",
            "updated_at",
        ]


class TimetableSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source="course.name", read_only=True)
    unit_name = serializers.CharField(source="unit.name", read_only=True)
    instructor_name = serializers.SerializerMethodField()

    class Meta:
        model = Timetable
        fields = [
            "id",
            "academic_calendar",
            "course",
            "course_name",
            "unit",
            "unit_name",
            "day",
            "start_time",
            "end_time",
            "type",
            "building",
            "room",
            "is_virtual",
            "virtual_link",
            "instructor",
            "instructor_name",
            "year_of_study",
            "is_recurring",
            "weeks",
            "group_name",
            "metadata",
            "created_at",
            "updated_at",
        ]

    def get_instructor_name(self, obj):
        if obj.instructor:
            return obj.instructor.get_full_name() or obj.instructor.email
        return None


class TimetableOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimetableOverride
        fields = [
            "id",
            "timetable",
            "date",
            "override_type",
            "new_start_time",
            "new_end_time",
            "new_building",
            "new_room",
            "new_virtual_link",
            "reason",
            "notify_students",
            "created_by",
            "created_at",
            "updated_at",
        ]


class PersonalScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonalSchedule
        fields = [
            "id",
            "title",
            "description",
            "category",
            "date",
            "start_time",
            "end_time",
            "is_all_day",
            "course",
            "unit",
            "reminder_minutes",
            "is_recurring",
            "recurrence_pattern",
            "is_private",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
