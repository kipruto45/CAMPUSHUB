from django.core.management.base import BaseCommand
from django.utils.text import slugify

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
    "FSSD": {
        "name": "Faculty of Social Sciences and Development Studies",
        "departments": {
            "DSOC": {
                "name": "Department of Community Development",
                "courses": {
                    "BCCD": ("Bachelor of Co-operatives and Community Development", 4),
                    "BCD": ("Bachelor of Community Development", 4),
                },
            },
            "DDRM": {
                "name": "Department of Disaster Risk Management",
                "courses": {
                    "BDRM": ("Bachelor of Disaster Risk Management", 4),
                },
            },
            "DENV": {
                "name": "Department of Environmental Studies",
                "courses": {
                    "BSET": ("Bachelor of Environmental Studies", 4),
                    "BEEP": ("Bachelor of Environmental Economics and Policy", 4),
                    "BELSI": ("Bachelor of Environmental Land and Spatial Informatics", 4),
                    "BAEM": ("Bachelor of Agricultural Economics and Management", 4),
                },
            },
        },
    },
    "FHTM": {
        "name": "Faculty of Hospitality and Tourism Management",
        "departments": {
            "DHTM": {
                "name": "Department of Hospitality Management",
                "courses": {
                    "BCHM": ("Bachelor of Catering and Hospitality Management", 4),
                },
            },
            "DTRM": {
                "name": "Department of Tourism and Travel Management",
                "courses": {
                    "BTM": ("Bachelor of Tourism Management", 4),
                },
            },
        },
    },
    "FASC": {
        "name": "Faculty of Arts and Social Communication",
        "departments": {
            "DAPR": {
                "name": "Department of Media and Public Relations",
                "courses": {
                    "BPRA": ("Bachelor of Public Relations and Advertising", 4),
                },
            },
        },
    },
    "FBE2": {
        "name": "Faculty of Business and Economics (Additional Programs)",
        "departments": {
            "DBUS": {
                "name": "Department of Business Programs",
                "courses": {
                    "BSA": ("Bachelor of Accounting", 4),
                    "BBF": ("Bachelor of Banking and Finance", 4),
                    "BCOM": ("Bachelor of Commerce", 4),
                    "BBM": ("Bachelor of Business Management", 4),
                    "BHRM": ("Bachelor of Human Resource Management", 4),
                    "BPSM": ("Bachelor of Purchasing and Supplies Management", 4),
                    "BECO": ("Bachelor of Economics", 4),
                    "BSCFIN": ("Bachelor of Science in Finance", 4),
                    "BSAS": ("Bachelor of Science in Actuarial Science", 4),
                    "BASD": ("Bachelor of Applied Statistics and Data Science", 4),
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
                    # Ensure there is a single course per (department, code)
                    dupes = list(
                        Course.objects.filter(department=dept, code=course_code).order_by("created_at", "id")
                    )

                    if dupes:
                        primary = dupes[0]
                        # Remove extra duplicates to avoid unique constraint collisions.
                        if len(dupes) > 1:
                            Course.objects.filter(id__in=[c.id for c in dupes[1:]]).delete()
                        primary.name = course_name
                        primary.duration_years = years
                        primary.description = course_name
                        primary.slug = slugify(f"{dept.faculty.code}-{course_code}")
                        primary.save(
                            update_fields=["name", "duration_years", "description", "slug", "updated_at"]
                        )
                        continue

                    # If a course with this code exists in another department, re-use the oldest one.
                    stray = Course.objects.filter(code=course_code).order_by("created_at", "id").first()
                    if stray:
                        stray.department = dept
                        stray.name = course_name
                        stray.duration_years = years
                        stray.description = course_name
                        stray.slug = slugify(f"{dept.faculty.code}-{course_code}")
                        stray.save(
                            update_fields=[
                                "department",
                                "name",
                                "duration_years",
                                "description",
                                "slug",
                                "updated_at",
                            ]
                        )
                        # Clean up any remaining duplicates of that code now that it moved
                        Course.objects.filter(code=course_code).exclude(id=stray.id).filter(
                            department=dept
                        ).delete()
                        continue

                    Course.objects.create(
                        code=course_code,
                        department=dept,
                        name=course_name,
                        duration_years=years,
                        description=course_name,
                        slug=slugify(f"{dept.faculty.code}-{course_code}"),
                    )
        self.stdout.write(self.style.SUCCESS("Minimal faculties/departments/courses ensured."))
