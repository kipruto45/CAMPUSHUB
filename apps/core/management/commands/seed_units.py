"""
Management command to seed academic units for CampusHub.
"""

from django.core.management.base import BaseCommand
from apps.faculties.models import Faculty, Department
from apps.courses.models import Course, Unit


class Command(BaseCommand):
    help = 'Seed academic units (BDSC, BCIT, BSTA, BCSC, etc.)'

    def handle(self, *args, **options):
        self.stdout.write('Seeding academic structure...')
        
        # Create Faculty
        faculty, created = Faculty.objects.get_or_create(
            code='SOC',
            defaults={
                'name': 'School of Computing',
                'description': 'School of Computing and Information Technology'
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created faculty: {faculty.name}'))
        
        # Create Department
        department, created = Department.objects.get_or_create(
            code='CS',
            faculty=faculty,
            defaults={
                'name': 'Computer Science',
                'description': 'Department of Computer Science'
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created department: {department.name}'))
        
        # Create Course - Bachelor of Science in Computer Science
        course, created = Course.objects.get_or_create(
            code='BCSC',
            department=department,
            defaults={
                'name': 'Bachelor of Science in Computer Science',
                'duration_years': 4
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created course: {course.name}'))
        
        # Define units to create
        units_data = [
            # BCSC Units
            {'code': 'BCSC 2207', 'name': 'Scientific Computing', 'year': 2, 'semester': '2'},
            
            # BCIT Units (Note: BCTT for Internet Application Programming)
            {'code': 'BCIT 2214', 'name': 'Software Engineering', 'year': 2, 'semester': '2'},
            {'code': 'BCTT 2218', 'name': 'Internet Application Programming', 'year': 2, 'semester': '2'},
            
            # BSTA Units
            {'code': 'BSTA 2206', 'name': 'Probability and Statistics III', 'year': 2, 'semester': '2'},
            {'code': 'BSTA 2134', 'name': 'Linear Models II', 'year': 2, 'semester': '1'},
            
            # BDSC Units
            {'code': 'BDSC 2203', 'name': 'Data Communication', 'year': 2, 'semester': '1'},
            {'code': 'BDSC 2203', 'name': 'Data Preparation', 'year': 2, 'semester': '2'},
        ]
        
        # Create units
        units_created = 0
        for unit_data in units_data:
            code = unit_data['code']
            # Extract prefix for course matching
            prefix = code.split()[0]
            
            # Find matching course or use default BCSC
            course_obj = Course.objects.filter(code__startswith=prefix).first()
            if not course_obj:
                course_obj = course  # Use default BCSC course
            
            unit, created = Unit.objects.get_or_create(
                code=code,
                course=course_obj,
                semester=unit_data['semester'],
                defaults={
                    'name': unit_data['name'],
                    'year_of_study': unit_data['year']
                }
            )
            if created:
                units_created += 1
                self.stdout.write(f'Created unit: {unit.code} - {unit.name}')
        
        self.stdout.write(self.style.SUCCESS(
            f'Successfully seeded {units_created} units!'
        ))
        
        # Display all units
        self.stdout.write('\nAll Units:')
        for unit in Unit.objects.all().order_by('code'):
            self.stdout.write(f'  {unit.code} - {unit.name} ({unit.course.name})')
