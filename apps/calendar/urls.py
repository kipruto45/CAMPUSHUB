"""
Calendar URL configuration.
"""

from django.urls import path

from . import views

app_name = "calendar"

urlpatterns = [
    # Schedule views
    path("today/", views.TodayScheduleView.as_view(), name="today-schedule"),
    path("week/", views.WeekScheduleView.as_view(), name="week-schedule"),
    path("upcoming/", views.UpcomingEventsView.as_view(), name="upcoming-events"),
    
    # Timetable
    path("timetable/", views.TimetableListView.as_view(), name="timetable"),
    
    # Personal schedules
    path("schedules/", views.PersonalScheduleListView.as_view(), name="personal-schedules"),
    path("schedules/<uuid:pk>/", views.PersonalScheduleDetailView.as_view(), name="personal-schedule-detail"),
    
    # Export
    path("export/", views.CalendarExportView.as_view(), name="calendar-export"),
]
