"""
Management command to delete all faculties, departments, courses, and units.
"""

from django.core.management.base import BaseCommand
from apps.faculties.models import Faculty, Department
from apps.courses.models import Course, Unit


class Command(BaseCommand):
    help = "Delete all faculties, departments, courses, and units"

    def handle(self, *args, **options):
        # Delete in reverse order to ensure clean deletion
        # Due to CASCADE, we could just delete Faculty, but let's be explicit
        
        # Delete all Units
        unit_count = Unit.objects.count()
        Unit.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {unit_count} units"))
        
        # Delete all Courses
        course_count = Course.objects.count()
        Course.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {course_count} courses"))
        
        # Delete all Departments
        dept_count = Department.objects.count()
        Department.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {dept_count} departments"))
        
        # Delete all Faculties
        faculty_count = Faculty.objects.count()
        Faculty.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {faculty_count} faculties"))
        
        self.stdout.write(self.style.SUCCESS("All faculties, departments, courses, and units have been deleted!"))
