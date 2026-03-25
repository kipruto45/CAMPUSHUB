"""
Calendar admin configuration.
"""

from django.contrib import admin
from django import forms
from django.shortcuts import render
from django.http import HttpResponseRedirect

from .models import (AcademicCalendar, PersonalSchedule, ScheduleExport,
                    Timetable, TimetableOverride)


@admin.register(AcademicCalendar)
class AcademicCalendarAdmin(admin.ModelAdmin):
    list_display = ["name", "faculty", "year", "semester", "start_date", "end_date", "is_active"]
    list_filter = ["year", "semester", "is_active", "faculty"]
    search_fields = ["name", "faculty__name"]
    date_hierarchy = "start_date"
    actions = ["activate_calendars", "deactivate_calendars"]
    
    fieldsets = [
        ("Basic Info", {
            "fields": ["name", "faculty", "department"]
        }),
        ("Academic Period", {
            "fields": ["year", "semester", "start_date", "end_date"]
        }),
        ("Semester Breaks", {
            "fields": ["mid_semester_start", "mid_semester_end", "break_start_date", "break_end_date"]
        }),
        ("Exam Period", {
            "fields": ["exam_start_date", "exam_end_date"]
        }),
        ("Settings", {
            "fields": ["is_active", "metadata"]
        }),
    ]

    @admin.action(description="Activate selected calendars")
    def activate_calendars(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Deactivate selected calendars")
    def deactivate_calendars(self, request, queryset):
        queryset.update(is_active=False)


class TimetableInline(admin.TabularInline):
    model = Timetable
    extra = 0
    fields = ["day", "start_time", "end_time", "type", "building", "room"]


@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ["unit", "day", "start_time", "end_time", "type", "building", "room"]
    list_filter = ["day", "type", "academic_calendar"]
    search_fields = ["unit__code", "unit__name", "building", "room"]
    date_hierarchy = "created_at"
    
    actions = ["import_from_csv", "export_to_ical"]
    
    @admin.action(description="Import timetable from CSV")
    def import_from_csv(self, request, queryset):
        """Admin action to import timetable."""
        if "import_file" in request.POST:
            import_csv_form = ImportCSVForm(request.POST, request.FILES)
            if import_csv_form.is_valid():
                file_content = request.FILES["file"].read().decode("utf-8")
                from apps.calendar.services import TimetableImportService
                
                result = TimetableImportService.import_timetable(
                    file_content=file_content,
                    import_type="csv",
                    user=request.user
                )
                
                self.message_user(request, result["message"])
                return HttpResponseRedirect(request.get_full_path())
        else:
            import_csv_form = ImportCSVForm()
        
        return render(request, "admin/calendar/timetable/import.html", {
            "import_form": import_csv_form,
            "title": "Import Timetable"
        })
    
    @admin.action(description="Export to iCal")
    def export_to_ical(self, request, queryset):
        """Admin action to export timetable to iCal."""
        from apps.calendar.services import CalendarExportService
        from django.http import HttpResponse
        
        # Get all timetables for the query
        content = CalendarExportService.generate_ical(None)  # No user context
        
        response = HttpResponse(content, content_type="text/calendar")
        response["Content-Disposition"] = "attachment; filename=timetable.ics"
        return response


@admin.register(TimetableOverride)
class TimetableOverrideAdmin(admin.ModelAdmin):
    list_display = ["timetable", "date", "override_type", "reason"]
    list_filter = ["override_type", "date"]
    search_fields = ["timetable__unit__code", "reason"]


@admin.register(PersonalSchedule)
class PersonalScheduleAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "date", "category", "is_all_day"]
    list_filter = ["category", "is_all_day", "date"]
    search_fields = ["title", "user__username"]
    date_hierarchy = "date"


@admin.register(ScheduleExport)
class ScheduleExportAdmin(admin.ModelAdmin):
    list_display = ["user", "export_type", "last_sync", "sync_enabled"]
    list_filter = ["export_type", "sync_enabled"]
    search_fields = ["user__username"]


# Import form for admin action
class ImportCSVForm(forms.Form):
    file = forms.FileField(
        label="CSV File",
        help_text="Upload a CSV file with columns: day, start_time, end_time, unit_code, type, building, room"
    )
