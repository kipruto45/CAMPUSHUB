from django.core.management.base import BaseCommand
from apps.faculties.models import Faculty, Department
from apps.courses.models import Course


# Minimal structure covering courses referenced in curated units
STRUCTURE = {
    "CIT": {
        "name": "Faculty of Computing and Information Technology",
        "departments": {
            "DCS": {
                "name": "Department of Computer Science",
                "courses": {
                    "BCS": ("BSc. Computer Science", 4),
                    "DCS": ("Diploma in Computer Science", 3),
                },
            },
            "DIT": {
                "name": "Department of Information Technology",
                "courses": {
                    "BIT": ("Bachelor of Information Technology", 4),
                    "BBIT": ("Bachelor of Business Information Technology", 4),
                    "DIT": ("Diploma in Information Technology", 3),
                    "DCY": ("Diploma in Cyber Security", 3),
                },
            },
            "DSE": {
                "name": "Department of Software Engineering",
                "courses": {
                    "BSEN": ("Bachelor of Software Engineering", 4),
                },
            },
            "DDS": {
                "name": "Department of Data Science",
                "courses": {
                    "BDAT": ("Bachelor of Data Science", 4),
                    "BSCAS": ("BSc. Applied Statistics", 4),
                    "BSIT": ("BSc. Statistics and Information Technology", 4),
                },
            },
        },
    },
    "FBE": {
        "name": "Faculty of Business and Economics",
        "departments": {
            "DAF": {
                "name": "Department of Accounting and Finance",
                "courses": {
                    "BASE": ("Bachelor of Applied Statistics and Economics", 4),
                    "BSACC": ("Bachelor of Accounting", 4),
                    "BBFI": ("Bachelor of Banking and Finance", 4),
                    "BSCFIN": ("Bachelor of Science in Finance", 4),
                },
            },
        },
    },
}


class Command(BaseCommand):
    help = "Seed minimal faculties, departments, and courses required by curated unit seeder."

    def handle(self, *args, **options):
        for fac_code, fac_data in STRUCTURE.items():
            faculty, _ = Faculty.objects.get_or_create(
                code=fac_code,
                defaults={
                    "name": fac_data["name"],
                    "description": fac_data["name"],
                },
            )
            for dept_code, dept_data in fac_data["departments"].items():
                dept, _ = Department.objects.get_or_create(
                    code=dept_code,
                    faculty=faculty,
                    defaults={"name": dept_data["name"]},
                )
                for course_code, (course_name, years) in dept_data["courses"].items():
                    Course.objects.get_or_create(
                        code=course_code,
                        department=dept,
                        defaults={
                            "name": course_name,
                            "duration_years": years,
                            "description": course_name,
                        },
                    )
        self.stdout.write(self.style.SUCCESS("Minimal faculties/departments/courses ensured."))
