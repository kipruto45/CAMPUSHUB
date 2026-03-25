"""
Calendar API views for timetable and schedule management.
"""

import logging
from datetime import date, timedelta

from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import HttpResponse

from .models import (
    AcademicCalendar,
    PersonalSchedule,
    ScheduleExport,
    Timetable,
    TimetableOverride,
)
from .serializers import (
    AcademicCalendarSerializer,
    PersonalScheduleSerializer,
    TimetableOverrideSerializer,
    TimetableSerializer,
)
from .services import CalendarExportService, ReminderService, TimetableService

logger = logging.getLogger(__name__)


class TodayScheduleView(APIView):
    """Get today's schedule."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Today's Schedule",
        description="Get today's classes and personal events"
    )
    def get(self, request):
        schedule = TimetableService.get_today_schedule(request.user)
        
        return Response({
            "date": schedule["date"],
            "day": schedule["day"],
            "timetable": [{
                "id": str(t.id),
                "unit_code": t.unit.code if t.unit else None,
                "unit_name": t.unit.name if t.unit else None,
                "type": t.type,
                "start_time": t.start_time.isoformat(),
                "end_time": t.end_time.isoformat(),
                "building": t.building,
                "room": t.room,
                "is_virtual": t.is_virtual,
                "instructor": t.instructor.username if t.instructor else None,
            } for t in schedule["timetable"]],
            "personal_events": [{
                "id": str(e.id),
                "title": e.title,
                "category": e.category,
                "start_time": e.start_time.isoformat() if e.start_time else None,
                "end_time": e.end_time.isoformat() if e.end_time else None,
                "is_all_day": e.is_all_day,
            } for e in schedule["personal_events"]],
        })


class WeekScheduleView(APIView):
    """Get week's schedule."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Week Schedule",
        description="Get schedule for a full week"
    )
    def get(self, request):
        week_start = request.query_params.get("week_start")
        
        if week_start:
            from datetime import datetime
            week_start = datetime.strptime(week_start, "%Y-%m-%d").date()
        
        schedule = TimetableService.get_week_schedule(request.user, week_start)
        
        result = {}
        for day_name, day_data in schedule.items():
            result[day_name] = {
                "date": day_data["date"],
                "timetable": [{
                    "id": str(t.id),
                    "unit_code": t.unit.code if t.unit else None,
                    "type": t.type,
                    "start_time": t.start_time.isoformat(),
                    "end_time": t.end_time.isoformat(),
                } for t in day_data["timetable"]],
                "personal_events": [{
                    "id": str(e.id),
                    "title": e.title,
                } for e in day_data["personal_events"]],
            }
        
        return Response(result)


class UpcomingEventsView(APIView):
    """Get upcoming events."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Upcoming Events",
        description="Get upcoming events for the next N days"
    )
    def get(self, request):
        days = int(request.query_params.get("days", 7))
        events = TimetableService.get_upcoming_events(request.user, days)
        
        return Response({"events": events})


class PersonalScheduleListView(APIView):
    """Manage personal schedules."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List Personal Schedules",
        description="Get user's personal schedule events"
    )
    def get(self, request):
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        
        query = PersonalSchedule.objects.filter(user=request.user)
        
        if start_date:
            query = query.filter(date__gte=start_date)
        if end_date:
            query = query.filter(date__lte=end_date)
        
        schedules = query.order_by("date", "start_time")
        
        return Response({
            "schedules": [{
                "id": str(s.id),
                "title": s.title,
                "description": s.description,
                "category": s.category,
                "date": s.date.isoformat(),
                "start_time": s.start_time.isoformat() if s.start_time else None,
                "end_time": s.end_time.isoformat() if s.end_time else None,
                "is_all_day": s.is_all_day,
                "unit_code": s.unit.code if s.unit else None,
            } for s in schedules]
        })

    @extend_schema(
        summary="Create Personal Schedule",
        description="Add a personal schedule event"
    )
    def post(self, request):
        serializer = PersonalScheduleSerializer(data=request.data)
        
        if serializer.is_valid():
            schedule = serializer.save(user=request.user)
            return Response({
                "id": str(schedule.id),
                "message": "Schedule created successfully"
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PersonalScheduleDetailView(APIView):
    """Individual personal schedule."""

    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Get Schedule")
    def get(self, request, pk):
        try:
            schedule = PersonalSchedule.objects.get(pk=pk, user=request.user)
        except PersonalSchedule.DoesNotExist:
            return Response(
                {"error": "Schedule not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response({
            "id": str(schedule.id),
            "title": schedule.title,
            "description": schedule.description,
            "category": schedule.category,
            "date": schedule.date.isoformat(),
            "start_time": schedule.start_time.isoformat() if schedule.start_time else None,
            "end_time": schedule.end_time.isoformat() if schedule.end_time else None,
            "is_all_day": schedule.is_all_day,
        })

    @extend_schema(summary="Update Schedule")
    def put(self, request, pk):
        try:
            schedule = PersonalSchedule.objects.get(pk=pk, user=request.user)
        except PersonalSchedule.DoesNotExist:
            return Response(
                {"error": "Schedule not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = PersonalScheduleSerializer(schedule, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Schedule updated"})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="Delete Schedule")
    def delete(self, request, pk):
        try:
            schedule = PersonalSchedule.objects.get(pk=pk, user=request.user)
            schedule.delete()
            return Response({"message": "Schedule deleted"})
        except PersonalSchedule.DoesNotExist:
            return Response(
                {"error": "Schedule not found"},
                status=status.HTTP_404_NOT_FOUND
            )


class TimetableListView(APIView):
    """List timetable entries."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="My Timetable",
        description="Get user's course timetable"
    )
    def get(self, request):
        # Get active academic calendar
        calendar = AcademicCalendar.objects.filter(is_active=True).first()
        
        if not calendar:
            return Response({
                "message": "No active academic calendar",
                "timetable": []
            })
        
        timetables = TimetableService.get_user_timetable(
            request.user,
            start_date=calendar.start_date,
            end_date=calendar.end_date
        )
        
        return Response({
            "calendar": {
                "year": calendar.year,
                "semester": calendar.semester,
                "start_date": calendar.start_date.isoformat(),
                "end_date": calendar.end_date.isoformat(),
            },
            "timetable": [{
                "id": str(t.id),
                "day": t.day,
                "unit_code": t.unit.code if t.unit else None,
                "unit_name": t.unit.name if t.unit else None,
                "type": t.type,
                "start_time": t.start_time.isoformat(),
                "end_time": t.end_time.isoformat(),
                "building": t.building,
                "room": t.room,
                "group_name": t.group_name,
            } for t in timetables]
        })


class CalendarExportView(APIView):
    """Export calendar."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Export Calendar",
        description="Export calendar to iCal or CSV format"
    )
    def get(self, request):
        export_type = request.query_params.get("type", "ical")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        
        if start_date:
            from datetime import datetime
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        if end_date:
            from datetime import datetime
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        if export_type == "ical":
            content = CalendarExportService.generate_ical(
                request.user, start_date, end_date
            )
            content_type = "text/calendar"
            filename = "campushub-calendar.ics"
        elif export_type == "csv":
            content = CalendarExportService.generate_csv(
                request.user, start_date, end_date
            )
            content_type = "text/csv"
            filename = "campushub-calendar.csv"
        else:
            return Response(
                {"error": "Invalid export type"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from django.http import HttpResponse
        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        
        return response


# ---------------------------------------------------------------------------
# Public calendar discovery & ICS export
# ---------------------------------------------------------------------------


class AcademicCalendarListView(generics.ListAPIView):
    """List academic calendars with optional filtering."""

    serializer_class = AcademicCalendarSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = AcademicCalendar.objects.filter(is_active=True)
        faculty_id = self.request.query_params.get("faculty_id")
        department_id = self.request.query_params.get("department_id")
        year = self.request.query_params.get("year")
        semester = self.request.query_params.get("semester")

        if faculty_id:
            qs = qs.filter(faculty_id=faculty_id)
        if department_id:
            qs = qs.filter(department_id=department_id)
        if year:
            qs = qs.filter(year=str(year))
        if semester:
            qs = qs.filter(semester=str(semester))
        return qs.order_by("-year", "-semester", "-created_at")


class TimetableListView(generics.ListAPIView):
    """List timetables with filters for calendar, course, unit, and day."""

    serializer_class = TimetableSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = Timetable.objects.select_related("course", "unit", "instructor", "academic_calendar")

        calendar_id = self.request.query_params.get("calendar_id")
        course_id = self.request.query_params.get("course_id")
        unit_id = self.request.query_params.get("unit_id")
        day = self.request.query_params.get("day")
        year_of_study = self.request.query_params.get("year_of_study")

        if calendar_id:
            qs = qs.filter(academic_calendar_id=calendar_id)
        if course_id:
            qs = qs.filter(course_id=course_id)
        if unit_id:
            qs = qs.filter(unit_id=unit_id)
        if day:
            qs = qs.filter(day=day.lower())
        if year_of_study:
            qs = qs.filter(year_of_study=year_of_study)

        return qs.order_by("day", "start_time")


class TimetableDetailView(generics.RetrieveAPIView):
    """Retrieve a single timetable entry."""

    queryset = Timetable.objects.select_related("course", "unit", "instructor", "academic_calendar")
    serializer_class = TimetableSerializer
    permission_classes = [AllowAny]
    lookup_field = "id"


class TimetableOverrideListView(generics.ListAPIView):
    """List overrides for a timetable."""

    serializer_class = TimetableOverrideSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = TimetableOverride.objects.select_related("timetable")
        timetable_id = self.request.query_params.get("timetable_id")
        if timetable_id:
            qs = qs.filter(timetable_id=timetable_id)
        return qs.order_by("-date")


class TimetableICSView(APIView):
    """Export timetables as a basic ICS feed."""

    permission_classes = [AllowAny]

    def get(self, request):
        calendar_id = request.query_params.get("calendar_id")
        course_id = request.query_params.get("course_id")

        qs = Timetable.objects.select_related("course", "unit", "academic_calendar")
        if calendar_id:
            qs = qs.filter(academic_calendar_id=calendar_id)
        if course_id:
            qs = qs.filter(course_id=course_id)

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//CampusHub//Timetable//EN",
        ]

        for item in qs:
            dt_start = item.start_time.strftime("%H%M%S")
            dt_end = item.end_time.strftime("%H%M%S")
            today = date.today().strftime("%Y%m%d")
            summary = f"{item.unit.name if item.unit else item.course.name} ({item.get_type_display()})"
            location = item.room or item.building or ("Online" if item.is_virtual else "")
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:{item.id}@campushub",
                    f"SUMMARY:{summary}",
                    f"DTSTART;TZID=UTC:{today}T{dt_start}Z",
                    f"DTEND;TZID=UTC:{today}T{dt_end}Z",
                    f"DESCRIPTION:Group {item.group_name or ''}",
                    f"LOCATION:{location}",
                    "END:VEVENT",
                ]
            )

        lines.append("END:VCALENDAR")
        ics_body = "\\r\\n".join(lines)

        response = HttpResponse(ics_body, content_type="text/calendar")
        response["Content-Disposition"] = "attachment; filename=campus-timetable.ics"
        return response
