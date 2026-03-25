"""
Calendar services for timetable management and scheduling.
"""

import logging
from datetime import date, datetime, time, timedelta
from typing import List, Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


class TimetableService:
    """Service for managing timetables and schedules."""

    @staticmethod
    def get_user_timetable(user, start_date: date = None, end_date: date = None):
        """Get user's timetable for a date range."""
        from apps.calendar.models import Timetable, TimetableOverride
        from apps.accounts.models import User

        # Determine user's year of study and courses
        year_of_study = user.year_of_study
        user_courses = []
        
        if hasattr(user, 'course'):
            user_courses = [user.course]
        elif hasattr(user, 'courses'):
            user_courses = list(user.courses.all())

        # Get timetables for user's courses and year
        timetables = Timetable.objects.filter(
            course__in=user_courses,
            year_of_study=year_of_study,
            academic_calendar__is_active=True,
        ).select_related('unit', 'course', 'instructor').order_by('day', 'start_time')

        if start_date:
            timetables = timetables.filter(academic_calendar__start_date__lte=start_date,
                                           academic_calendar__end_date__gte=start_date)

        # Apply overrides
        result = []
        for timetable in timetables:
            overrides = TimetableOverride.objects.filter(
                timetable=timetable,
                date__gte=start_date or date.today(),
                date__lte=end_date or (date.today() + timedelta(days=30))
            )
            
            # Check if there's an override for today or this week
            today = date.today()
            week_overrides = overrides.filter(date=today)
            
            if week_overrides:
                for override in week_overrides:
                    if override.override_type == 'cancelled':
                        continue  # Skip cancelled classes
                    # Apply rescheduled info
                    if override.new_start_time:
                        timetable = timetable
                        timetable.start_time = override.new_start_time
                        timetable.end_time = override.new_end_time
                    if override.new_room:
                        timetable.room = override.new_room
                        timetable.building = override.new_building
            
            result.append(timetable)

        return result

    @staticmethod
    def get_today_schedule(user) -> dict:
        """Get today's schedule for a user."""
        from apps.calendar.models import Timetable

        today = date.today()
        day_name = today.strftime('%A').lower()

        timetables = Timetable.objects.filter(
            unit__course__enrolled_students=user,
            day=day_name,
            academic_calendar__is_active=True,
            academic_calendar__start_date__lte=today,
            academic_calendar__end_date__gte=today,
        ).select_related('unit', 'course', 'instructor').order_by('start_time')

        # Get personal events for today
        from apps.calendar.models import PersonalSchedule
        personal_events = PersonalSchedule.objects.filter(
            user=user,
            date=today,
        ).order_by('start_time')

        return {
            "date": today.isoformat(),
            "day": today.strftime('%A'),
            "timetable": list(timetables),
            "personal_events": list(personal_events),
        }

    @staticmethod
    def get_week_schedule(user, week_start: date = None) -> dict:
        """Get schedule for a full week."""
        from apps.calendar.models import Timetable, PersonalSchedule

        if not week_start:
            # Get current week's Monday
            today = date.today()
            week_start = today - timedelta(days=today.weekday())

        week_end = week_start + timedelta(days=6)

        schedule = {}
        for i in range(7):
            day = week_start + timedelta(days=i)
            day_name = day.strftime('%A').lower()
            schedule[day_name] = {
                "date": day.isoformat(),
                "timetable": [],
                "personal_events": [],
            }

        # Get timetables for the week
        timetables = Timetable.objects.filter(
            unit__course__enrolled_students=user,
            academic_calendar__is_active=True,
            academic_calendar__start_date__lte=week_end,
            academic_calendar__end_date__gte=week_start,
        ).select_related('unit', 'course', 'instructor')

        for timetable in timetables:
            day_name = timetable.day
            if day_name in schedule:
                schedule[day_name]["timetable"].append(timetable)

        # Get personal events
        personal_events = PersonalSchedule.objects.filter(
            user=user,
            date__gte=week_start,
            date__lte=week_end,
        ).order_by('date', 'start_time')

        for event in personal_events:
            day_name = event.date.strftime('%A').lower()
            if day_name in schedule:
                schedule[day_name]["personal_events"].append(event)

        return schedule

    @staticmethod
    def get_upcoming_events(user, days: int = 7) -> List[dict]:
        """Get upcoming events for the next N days."""
        from apps.calendar.models import Timetable, PersonalSchedule

        today = date.today()
        end_date = today + timedelta(days=days)
        events = []

        # Get personal events
        personal_events = PersonalSchedule.objects.filter(
            user=user,
            date__gte=today,
            date__lte=end_date,
        ).order_by('date', 'start_time')

        for event in personal_events:
            events.append({
                "type": "personal",
                "title": event.title,
                "date": event.date.isoformat(),
                "start_time": event.start_time.isoformat() if event.start_time else None,
                "end_time": event.end_time.isoformat() if event.end_time else None,
                "category": event.category,
                "is_all_day": event.is_all_day,
            })

        # Get timetable events
        day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        
        for day_offset in range(days):
            current_date = today + timedelta(days=day_offset)
            day_name = current_date.strftime('%A').lower()
            
            day_timetables = Timetable.objects.filter(
                unit__course__enrolled_students=user,
                day=day_name,
                academic_calendar__is_active=True,
                academic_calendar__start_date__lte=current_date,
                academic_calendar__end_date__gte=current_date,
            ).select_related('unit', 'course')

            for timetable in day_timetables:
                # Check for overrides
                from apps.calendar.models import TimetableOverride
                override = TimetableOverride.objects.filter(
                    timetable=timetable,
                    date=current_date,
                    override_type='cancelled'
                ).first()

                if not override:
                    start_time = timetable.start_time
                    end_time = timetable.end_time
                    
                    # Check for reschedule override
                    reschedule = TimetableOverride.objects.filter(
                        timetable=timetable,
                        date=current_date,
                        override_type__in=['rescheduled', 'moved']
                    ).first()
                    
                    if reschedule:
                        if reschedule.new_start_time:
                            start_time = reschedule.new_start_time
                            end_time = reschedule.new_end_time

                    events.append({
                        "type": "class",
                        "title": f"{timetable.unit.code}: {timetable.get_type_display()}",
                        "date": current_date.isoformat(),
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "course": timetable.course.name,
                        "unit": timetable.unit.name,
                        "location": f"{timetable.building} {timetable.room}" if timetable.room else "TBA",
                        "is_virtual": timetable.is_virtual,
                    })

        return sorted(events, key=lambda x: (x['date'], x.get('start_time', '')))

    @staticmethod
    def check_conflicts(user, new_start: time, new_end: time, day: str, 
                       exclude_timetable_id: str = None) -> List[dict]:
        """Check for scheduling conflicts."""
        from apps.calendar.models import Timetable

        query = Timetable.objects.filter(
            unit__course__enrolled_students=user,
            day=day,
            academic_calendar__is_active=True,
        )

        if exclude_timetable_id:
            query = query.exclude(id=exclude_timetable_id)

        conflicts = []
        
        for timetable in query:
            # Check time overlap
            if (new_start <= timetable.start_time < new_end or
                new_start < timetable.end_time <= new_end or
                timetable.start_time <= new_start and new_end <= timetable.end_time):
                conflicts.append({
                    "type": "class",
                    "timetable_id": str(timetable.id),
                    "unit": timetable.unit.code,
                    "title": f"{timetable.unit.code} - {timetable.get_type_display()}",
                    "start_time": timetable.start_time.isoformat(),
                    "end_time": timetable.end_time.isoformat(),
                })

        # Also check personal events
        from apps.calendar.models import PersonalSchedule
        personal_events = PersonalSchedule.objects.filter(
            user=user,
            day=day,  # Note: this compares day names, need date
        )

        return conflicts


class CalendarExportService:
    """Service for exporting calendar to external formats."""

    @staticmethod
    def generate_ical(user, start_date: date = None, end_date: date = None) -> str:
        """Generate iCal format calendar."""
        from apps.calendar.models import Timetable, PersonalSchedule
        
        if not start_date:
            start_date = date.today()
        if not end_date:
            end_date = start_date + timedelta(days=30)

        ical_lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//CampusHub//Calendar//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
        ]

        # Add timetables
        day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        
        for day_offset in range((end_date - start_date).days + 1):
            current_date = start_date + timedelta(days=day_offset)
            day_name = current_date.strftime('%A').lower()

            timetables = Timetable.objects.filter(
                unit__course__enrolled_students=user,
                day=day_name,
                academic_calendar__is_active=True,
                academic_calendar__start_date__lte=current_date,
                academic_calendar__end_date__gte=current_date,
            )

            for timetable in timetables:
                dt_start = datetime.combine(current_date, timetable.start_time)
                dt_end = datetime.combine(current_date, timetable.end_time)

                ical_lines.extend([
                    "BEGIN:VEVENT",
                    f"UID:timetable-{timetable.id}@{current_date}",
                    f"DTSTART:{dt_start.strftime('%Y%m%dT%H%M%S')}",
                    f"DTEND:{dt_end.strftime('%Y%m%dT%H%M%S')}",
                    f"SUMMARY:{timetable.unit.code} - {timetable.get_type_display()}",
                    f"LOCATION:{timetable.building} {timetable.room}".strip() or "TBA",
                    "END:VEVENT",
                ])

        # Add personal events
        personal_events = PersonalSchedule.objects.filter(
            user=user,
            date__gte=start_date,
            date__lte=end_date,
        )

        for event in personal_events:
            dt_start = datetime.combine(event.date, event.start_time) if event.start_time else None
            dt_end = datetime.combine(event.date, event.end_time) if event.end_time else None

            ical_lines.extend([
                "BEGIN:VEVENT",
                f"UID:personal-{event.id}",
                f"DTSTART:{dt_start.strftime('%Y%m%dT%H%M%S') if dt_start else ''}",
                f"DTEND:{dt_end.strftime('%Y%m%dT%H%M%S') if dt_end else ''}",
                f"SUMMARY:{event.title}",
                "END:VEVENT",
            ])

        ical_lines.append("END:VCALENDAR")

        return "\r\n".join(ical_lines)

    @staticmethod
    def generate_csv(user, start_date: date = None, end_date: date = None) -> str:
        """Generate CSV format calendar."""
        from apps.calendar.models import Timetable, PersonalSchedule
        
        if not start_date:
            start_date = date.today()
        if not end_date:
            end_date = start_date + timedelta(days=30)

        csv_lines = ["Date,Day,Time,Type,Title,Location"]

        day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        
        for day_offset in range((end_date - start_date).days + 1):
            current_date = start_date + timedelta(days=day_offset)
            day_name = current_date.strftime('%A').lower()

            timetables = Timetable.objects.filter(
                unit__course__enrolled_students=user,
                day=day_name,
                academic_calendar__is_active=True,
            ).order_by('start_time')

            for timetable in timetables:
                location = f"{timetable.building} {timetable.room}".strip() or "TBA"
                csv_lines.append(
                    f'{current_date},{current_date.strftime("%A")},'
                    f'{timetable.start_time}-{timetable.end_time},'
                    f'{timetable.get_type_display()},'
                    f'{timetable.unit.code} - {timetable.unit.name},'
                    f'{location}'
                )

        return "\n".join(csv_lines)


class ReminderService:
    """Service for sending calendar reminders."""

    @staticmethod
    def send_reminders():
        """Send reminders for upcoming events."""
        from apps.calendar.models import PersonalSchedule
        from apps.notifications.models import Notification

        now = timezone.now()
        
        # Get events with upcoming reminders
        events = PersonalSchedule.objects.filter(
            reminder_sent=False,
            reminder_minutes__gt=0,
        )

        for event in events:
            event_datetime = datetime.combine(event.date, event.start_time) if event.start_time else None
            
            if event_datetime:
                reminder_time = event_datetime - timedelta(minutes=event.reminder_minutes)
                
                if now >= reminder_time:
                    # Send reminder notification
                    Notification.objects.create(
                        recipient=event.user,
                        title=f"Reminder: {event.title}",
                        message=f"Starting at {event.start_time.strftime('%H:%M')}" if event.start_time else "All day event",
                        notification_type="reminder",
                        link=f"/calendar/event/{event.id}/",
                    )
                    
                    event.reminder_sent = True
                    event.save()

        # Check timetable classes
        from apps.calendar.models import Timetable
        
        # This would check for class reminders
        logger.info("Calendar reminders processed")


class TimetableImportService:
    """Service for importing timetable data from CSV/ICS."""

    @staticmethod
    def import_timetable(file_content: str, import_type: str, user) -> dict:
        """Import timetable from file content."""
        from apps.calendar.models import Timetable, AcademicCalendar
        import csv
        import io

        # Get active academic calendar
        calendar = AcademicCalendar.objects.filter(is_active=True).first()
        if not calendar:
            return {
                "success": False,
                "message": "No active academic calendar found. Please contact admin.",
                "imported_count": 0
            }

        imported_count = 0
        errors = []

        if import_type == "csv":
            try:
                reader = csv.DictReader(io.StringIO(file_content))
                
                for row in reader:
                    try:
                        # Parse day
                        day = row.get('day', '').lower()
                        if day not in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
                            errors.append(f"Invalid day: {day}")
                            continue

                        # Parse times
                        start_time = datetime.strptime(row.get('start_time', '00:00'), '%H:%M').time()
                        end_time = datetime.strptime(row.get('end_time', '00:00'), '%H:%M').time()

                        # Get unit
                        from apps.courses.models import Unit
                        unit_code = row.get('unit_code', '').upper()
                        unit = Unit.objects.filter(code=unit_code).first()

                        if not unit:
                            errors.append(f"Unit not found: {unit_code}")
                            continue

                        # Create timetable
                        Timetable.objects.create(
                            academic_calendar=calendar,
                            course=unit.course,
                            unit=unit,
                            day=day,
                            start_time=start_time,
                            end_time=end_time,
                            type=row.get('type', 'lecture'),
                            building=row.get('building', ''),
                            room=row.get('room', ''),
                            group_name=row.get('group', ''),
                            year_of_study=int(row.get('year_of_study', user.year_of_study or 1)),
                        )
                        imported_count += 1

                    except Exception as e:
                        errors.append(f"Error parsing row: {str(e)}")

            except Exception as e:
                return {
                    "success": False,
                    "message": f"Error parsing CSV: {str(e)}",
                    "imported_count": 0
                }

        elif import_type == "ics":
            # Minimal iCal parsing into PersonalSchedule events
            try:
                from apps.calendar.models import PersonalSchedule

                def parse_dt(val):
                    if "T" in val:
                        dt = datetime.strptime(val, "%Y%m%dT%H%M%S")
                        return dt.date(), dt.time(), False
                    dt = datetime.strptime(val, "%Y%m%d")
                    return dt.date(), None, True

                events = file_content.split("BEGIN:VEVENT")
                for event in events[1:]:
                    try:
                        fields = {}
                        for raw in event.splitlines():
                            raw = raw.strip()
                            if ":" in raw:
                                k, v = raw.split(":", 1)
                                fields[k.split(";")[0]] = v

                        dtstart = fields.get("DTSTART")
                        if not dtstart:
                            continue
                        dtend = fields.get("DTEND")
                        date_val, start_t, all_day = parse_dt(dtstart)
                        _, end_t, _ = parse_dt(dtend) if dtend else (None, None, all_day)

                        PersonalSchedule.objects.create(
                            user=user,
                            title=fields.get("SUMMARY", "Event"),
                            description=fields.get("DESCRIPTION", ""),
                            category="personal",
                            date=date_val,
                            start_time=start_t,
                            end_time=end_t,
                            is_all_day=all_day,
                        )
                        imported_count += 1
                    except Exception as e:  # noqa: BLE001
                        errors.append(f"Error parsing event: {str(e)}")

            except Exception as e:
                return {
                    "success": False,
                    "message": f"Error parsing ICS: {str(e)}",
                    "imported_count": 0
                }

        return {
            "success": imported_count > 0,
            "message": f"Imported {imported_count} entries. Errors: {len(errors)}" if errors else f"Successfully imported {imported_count} entries.",
            "imported_count": imported_count,
            "errors": errors,
        }
