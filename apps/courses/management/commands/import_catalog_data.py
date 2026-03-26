import re
from copy import deepcopy

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.courses.models import Course, Unit
from apps.faculties.models import Department, Faculty
from seed_comprehensive_data import DATA as CORE_DATA


HOSPITALITY_DATA = {
    "HOSPITALITY AND TOURISM PROGRAMS": {
        "code": "HTP",
        "departments": {
            "Hospitality and Tourism Programs": {
                "code": "HTP",
                "courses": {
                    "BCHM": {
                        "name": "Bachelor of Catering and Hospitality Management",
                        "duration_years": 4,
                        "units": {
                            "Year 1 Semester 2": [
                                ("BCHM 1204", "FOOD HYGIENE AND SAFETY"),
                                ("BCHM 1205", "FOOD AND BEVERAGE PRODUCTION PRACTICAL"),
                                ("BCHM 1206", "FOOD AND BEVERAGE SERVICE PRACTICAL"),
                                ("BENT 1207", "ENTREPRENEURSHIP SKILLS"),
                                ("BLAN 1204", "FRENCH 2"),
                                ("BMAT 1203", "FUNDAMENTALS OF MATHEMATICS"),
                            ],
                            "Year 2 Semester 2": [
                                ("BCHM 2213", "FOOD & BEVERAGE MANAGEMENT I"),
                                ("BCHM 2214", "HOUSE KEEPING OPERATIONS THEORY & PRACTICAL"),
                                ("BCHM 2215", "FRONT OFFICE OPERATIONS"),
                                ("BECO 1206", "GENERAL ECONOMICS"),
                                ("BMGT 1201", "PRINCIPLES AND PRACTICE OF MANAGEMENT"),
                                ("BLAN 2207", "FRENCH 3"),
                                ("BCHM 2134", "CONFECTIONERY THEORY AND PRACTICAL"),
                            ],
                            "Year 3 Semester 2": [
                                ("BCHM 3223", "FOOD & BEVERAGE MANAGEMENT III"),
                                ("BCHM 3224", "MICE MANAGEMENT"),
                                ("BCHM 3225", "FRONT OFFICE MANAGEMENT"),
                                ("BCHM 3226", "CROSS-CULTURAL MANAGEMENT"),
                                ("BCHM 3227", "ROOMS DIVISION MANAGEMENT"),
                                ("BHRM 2124", "HUMAN RESOURCE MANAGEMENT"),
                                ("BPSY 2209", "ORGANIZATIONAL BEHAVIOUR"),
                            ],
                            "Year 4 Semester 2": [
                                ("BCHM 4231", "PROJECT I"),
                                ("BCHM 4232", "PROJECT II"),
                                ("BENT 3205", "BUSINESS PLANNING"),
                            ],
                        },
                    },
                    "BTM": {
                        "name": "Bachelor of Tourism Management",
                        "duration_years": 4,
                        "units": {
                            "Year 1 Semester 2": [
                                ("BENT 1207", "ENTREPRENEURSHIP SKILLS"),
                                ("BMGT 1201", "PRINCIPLES OF MANAGEMENT"),
                                ("BTRM 1202", "INTRODUCTION TO HOSPITALITY SERVICES"),
                                ("BTRM 1203", "LEISURE, RECREATION AND PLAY"),
                                ("BTRM 1204", "TOURISM GEOGRAPHY"),
                                ("BTRM 1224", "GLOBAL TOURISM"),
                                ("BLAN 1204", "FRENCH 2"),
                            ],
                            "Year 2 Semester 2": [
                                ("BLAN 2207", "FRENCH 3"),
                                ("BTRM 2211", "FIELD COURSE TRIP I"),
                                ("BTRM 2214", "WILDLIFE CONSERVATION AND TOURISM"),
                                ("BTRM 2225", "NATURAL HISTORY OF FAUNA IN EAST AFRICA"),
                                ("BMGT 1201", "PRINCIPLES OF MANAGEMENT"),
                                ("BHRM 2105", "HUMAN RESOURCE PLANNING"),
                                ("BTRM 2202", "MICE MANAGEMENT"),
                            ],
                            "Year 3 Semester 2": [
                                ("BECO 3202", "TOURISM ECONOMICS"),
                                ("BLAN 3206", "FRENCH 3B"),
                                ("BMGT 1213", "STRATEGIC MANAGEMENT"),
                                ("BTRM 3219", "SUSTAINABLE TOURISM"),
                                ("BMGT 1201", "PRINCIPLES OF MANAGEMENT"),
                                ("BECO 1206", "GENERAL ECONOMICS"),
                                ("BHRM 2105", "HUMAN RESOURCE PLANNING"),
                            ],
                            "Year 4 Semester 2": [
                                ("BBCU 4103", "RESEARCH PROJECT"),
                                ("BUCU 4312", "INDUSTRIAL ATTACHMENT II"),
                            ],
                        },
                    },
                },
            }
        },
    }
}


DIPLOMA_CERTIFICATE_PROGRAMS = {
    "DCS": {
        "name": "Diploma in Computer Science",
        "duration_years": 2,
        "units": {
            "Year 1 Sem 2": [
                "Apply Business Maths and Statistics",
                "Cooperative Practices",
                "Apply Mathematics for Computer Science",
                "Networking and Distributed Systems",
                "Graphics Design",
            ],
        },
    },
    "DCY": {
        "name": "Diploma in Cybersecurity",
        "duration_years": 2,
        "units": {
            "Year 2 Sem 2": [
                "Security Assessment and Testing",
                "Security Operations management",
            ],
        },
    },
    "DCAM": {
        "name": "Diploma in Catering and Accommodation Management",
        "duration_years": 2,
        "units": {
            "Year 1 Sem 2": [
                "Housekeeping Interior Decorations",
                "Starters And Starter Accompaniments",
                "Desserts And Bakery Products",
                "Cooperative Practices",
                "Food And Beverage Service",
                "Catering And Accommodation Cost and Control",
            ],
        },
    },
    "DCHM": {
        "name": "Diploma in Catering and Hospitality Management",
        "duration_years": 2,
        "units": {
            "Year 2 Sem 2": [
                "FRONT OFFICE OPERATIONS",
                "FOOD AND BEVERAGE CONTROL",
                "FACILITIES MANAGEMENT",
                "FOOD AND BEVERAGE MANAGEMENT",
                "NUTRITION",
                "HOSPITALITY AND TOURISM LAW",
                "FUNDAMENTALS OF TOURISM",
                "FRENCH II",
            ],
        },
    },
    "DIT": {
        "name": "Diploma in Information Technology",
        "duration_years": 2,
        "units": {
            "Year 1 Sem 2": [
                "Cooperative Practices",
                "Computer Software",
                "Network Design and Management",
                "Computer Programming Principles",
                "Computerized Database System",
                "Discrete Mathematical Concepts",
            ],
            "Year 2 Sem 2": [
                "WEB ENGINEERING(CLOUD AND MOBILE)",
                "NETWORK DESIGN AND SETUP",
                "PROJECT WORK (DOCUMENTATION AND SYSTEM IMPLEMENTATION)",
                "EVENT DRIVEN PROGRAMMING",
                "DIGITAL ELECTRONICS CONSTRUCTION",
            ],
        },
    },
    "DTM": {
        "name": "Diploma in Tourism Management",
        "duration_years": 2,
        "units": {
            "Year 1 Sem 2": [
                "Cooperatives Practices",
                "Work Ethics and Practices",
                "Research Study",
                "Foreign Language Skills",
                "Tour Guide Operations",
            ],
        },
    },
    "DBF": {
        "name": "Diploma in Banking and Finance",
        "duration_years": 2,
        "units": {
            "Year 1 Sem 2": [
                "Management Skills",
                "Research Study",
                "Business Mathematics and Statistics",
                "Customer Relationship",
                "Electronic banking",
            ],
            "Year 2 Sem 1": [
                "RESEARCH PROJECT I",
                "DEVELOPMENT STUDIES AND ETHICS",
                "ISLAMIC FINANCE",
                "INVESTMENT BANKING AND BROKERAGE",
                "GENERAL ECONOMICS",
                "TAXATION",
            ],
        },
    },
    "DBA": {
        "name": "Diploma in Business Administration",
        "duration_years": 2,
        "units": {
            "Year 1 Sem 1": [
                "PRINCIPLES OF ACCOUNTING",
                "PRINCIPLES OF MARKETING",
                "COMMUNICATION SKILLS",
                "CO-OPERATIVE PHILOSOPHY",
                "COMPUTER APPLICATIONS",
                "FOUNDATIONS OF MATHEMATICS",
            ],
            "Year 2 Sem 2": [
                "RESEARCH PROJECT II",
                "GENERAL ECONOMICS",
                "BUSINESS PLANNING",
                "BUSINESS ETHICS",
                "BUSINESS LAW",
                "PURCHASING AND SUPPLIES MANAGEMENT",
            ],
        },
    },
    "DAF": {
        "name": "Diploma in Accounting and Finance",
        "duration_years": 2,
        "units": {
            "Year 1 Sem 2": [
                "Information Communication Technology",
                "Management Practices",
                "Financial Accounting Skills",
                "Research Study",
                "Business Mathematics and Statistics",
                "Financial Audit",
            ],
        },
    },
    "DHRM": {
        "name": "Diploma in Human Resource Management",
        "duration_years": 2,
        "units": {
            "Year 1 Sem 2": [
                "Apply Co-operative practices",
                "Apply Management Practices",
                "Apply Principles Research Methods",
                "Conduct employee resourcing",
                "Organizational Behaviour",
                "Coordinate employee training and Development",
            ],
        },
    },
    "DSCM": {
        "name": "Diploma in Supply Chain Management",
        "duration_years": 2,
        "units": {
            "Year 1 Sem 2": [
                "Co-operative Practices",
                "Management Skills",
                "Research Methods",
                "Basic Mathematics and Statistics",
                "Manage Organizational Materials",
                "Issuance and Dispatch of Goods",
            ],
        },
    },
    "CBM": {
        "name": "Certificate in Business Management",
        "duration_years": 1,
        "units": {
            "Year 1 Sem 1": [
                "Co-operative Practices",
                "Business Communication",
                "Financial Accounting Skills",
                "Digital Literacy",
                "Management Skills",
            ],
        },
    },
}


class Command(BaseCommand):
    help = "Import the supplied academic catalog data into the local database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and report changes without committing them.",
        )

    def handle(self, *args, **options):
        standard_data = deepcopy(CORE_DATA)
        standard_data.update(HOSPITALITY_DATA)
        dry_run = options["dry_run"]

        summary = {
            "faculties_created": 0,
            "departments_created": 0,
            "courses_created": 0,
            "courses_updated": 0,
            "units_created": 0,
            "units_updated": 0,
            "units_variant_codes": 0,
        }

        with transaction.atomic():
            self._seed_standard_catalog(standard_data, summary)
            self._seed_diploma_catalog(summary)

            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Catalog import complete."))
            for key, value in summary.items():
                self.stdout.write(f"{key}: {value}")
            self.stdout.write(f"faculties_total: {Faculty.objects.count()}")
            self.stdout.write(f"departments_total: {Department.objects.count()}")
            self.stdout.write(f"courses_total: {Course.objects.count()}")
            self.stdout.write(f"units_total: {Unit.objects.count()}")

            if dry_run:
                self.stdout.write(self.style.WARNING("Dry run requested; rolling back changes."))
                transaction.set_rollback(True)

    def _seed_standard_catalog(self, catalog, summary):
        for faculty_name, faculty_data in catalog.items():
            faculty, created = Faculty.objects.update_or_create(
                code=faculty_data["code"],
                defaults={
                    "name": faculty_name,
                    "description": faculty_data.get("description", faculty_name),
                    "is_active": True,
                },
            )
            if created:
                summary["faculties_created"] += 1

            for dept_name, dept_data in faculty_data.get("departments", {}).items():
                department, created = Department.objects.update_or_create(
                    faculty=faculty,
                    code=dept_data["code"],
                    defaults={
                        "name": dept_name,
                        "description": dept_data.get("description", dept_name),
                        "is_active": True,
                    },
                )
                if created:
                    summary["departments_created"] += 1

                for course_code, course_data in dept_data.get("courses", {}).items():
                    course, created = self._upsert_course(
                        department=department,
                        course_code=course_code,
                        course_data=course_data,
                    )
                    if created:
                        summary["courses_created"] += 1
                    else:
                        summary["courses_updated"] += 1

                    for year_sem_key, units in course_data.get("units", {}).items():
                        year, semester, label = self._parse_year_semester(year_sem_key)
                        for unit_code, unit_name in units:
                            self._upsert_unit(
                                course=course,
                                raw_code=unit_code,
                                unit_name=unit_name,
                                year=year,
                                semester=semester,
                                label=label,
                                summary=summary,
                            )

    def _seed_diploma_catalog(self, summary):
        faculty, created = Faculty.objects.update_or_create(
            code="DCP",
            defaults={
                "name": "DIPLOMA & CERTIFICATE PROGRAMS",
                "description": "Diploma and certificate programs imported from the supplied catalog.",
                "is_active": True,
            },
        )
        if created:
            summary["faculties_created"] += 1

        department, created = Department.objects.update_or_create(
            faculty=faculty,
            code="DCP",
            defaults={
                "name": "Diploma and Certificate Programs",
                "description": "General department for diploma and certificate programs.",
                "is_active": True,
            },
        )
        if created:
            summary["departments_created"] += 1

        for course_code, course_data in DIPLOMA_CERTIFICATE_PROGRAMS.items():
            course, created = self._upsert_course(
                department=department,
                course_code=course_code,
                course_data=course_data,
            )
            if created:
                summary["courses_created"] += 1
            else:
                summary["courses_updated"] += 1

            for year_sem_key, unit_names in course_data.get("units", {}).items():
                year, semester, label = self._parse_year_semester(year_sem_key)
                for index, unit_name in enumerate(unit_names, start=1):
                    generated_code = f"{course.code} Y{year} S{semester} {index:02d}"
                    self._upsert_unit(
                        course=course,
                        raw_code=generated_code,
                        unit_name=unit_name,
                        year=year,
                        semester=semester,
                        label=label or "No source unit code provided",
                        summary=summary,
                    )

    def _upsert_unit(self, *, course, raw_code, unit_name, year, semester, label, summary):
        code = self._normalize_code(raw_code)
        unit_name = re.sub(r"\s+", " ", unit_name.strip())
        existing = Unit.objects.filter(
            course=course, code__iexact=code, semester=semester
        ).order_by("-is_active", "created_at").first()

        if existing and self._unit_matches(existing, unit_name, year, label):
            if existing.code != code:
                existing.code = code
            existing.name = unit_name
            existing.year_of_study = year
            existing.description = self._build_description(unit_name, raw_code, label)
            existing.is_active = True
            existing.save(
                update_fields=["code", "name", "year_of_study", "description", "is_active", "updated_at"]
            )
            summary["units_updated"] += 1
            return existing

        resolved_code = code
        if existing:
            resolved_code = self._resolve_variant_code(course, code, semester, year, label)
            summary["units_variant_codes"] += 1

        _, created = Unit.objects.update_or_create(
            course=course,
            code=resolved_code,
            semester=semester,
            defaults={
                "name": unit_name,
                "year_of_study": year,
                "description": self._build_description(unit_name, raw_code, label),
                "slug": self._build_unique_unit_slug(course.code, resolved_code, semester),
                "is_active": True,
            },
        )
        if created:
            summary["units_created"] += 1
        else:
            summary["units_updated"] += 1

    @staticmethod
    def _normalize_code(code):
        return re.sub(r"\s+", " ", str(code).strip()).upper()

    @staticmethod
    def _build_description(unit_name, raw_code, label):
        details = [f"{unit_name} ({str(raw_code).strip()})"]
        if label:
            details.append(str(label).strip())
        return " - ".join(part for part in details if part)

    @staticmethod
    def _unit_matches(unit, incoming_name, incoming_year, label):
        if unit.name.strip() != incoming_name:
            return False
        if int(unit.year_of_study or 0) != int(incoming_year):
            return False
        if label and label not in (unit.description or ""):
            return False
        return True

    def _resolve_variant_code(self, course, base_code, semester, year, label):
        candidates = []
        if label:
            label_token = self._tokenize_label(label)
            if label_token:
                candidates.append(label_token)
        candidates.append(f"Y{year}")
        candidates.append(f"Y{year}S{semester}")

        seen = set()
        for token in candidates:
            variant = self._append_code_suffix(base_code, token)
            if variant not in seen and not Unit.objects.filter(
                course=course, code=variant, semester=semester
            ).exists():
                return variant
            seen.add(variant)

        for index in range(2, 100):
            variant = self._append_code_suffix(base_code, str(index))
            if variant not in seen and not Unit.objects.filter(
                course=course, code=variant, semester=semester
            ).exists():
                return variant
            seen.add(variant)

        raise RuntimeError(
            f"Could not generate a unique variant unit code for {course.code} {base_code} semester {semester}"
        )

    def _upsert_course(self, *, department, course_code, course_data):
        course = Course.objects.filter(code=course_code).first()
        created = False
        defaults = {
            "department": department,
            "name": course_data["name"],
            "duration_years": course_data.get("duration_years", 4),
            "description": course_data.get(
                "description", f"{course_data['name']} ({course_code})"
            ),
            "is_active": True,
        }

        if course is None:
            course = Course(code=course_code, **defaults)
            course.slug = self._build_unique_course_slug(department.faculty.code, course_code)
            course.save()
            created = True
            return course, created

        updated_fields = []
        for field, value in defaults.items():
            if getattr(course, field) != value:
                setattr(course, field, value)
                updated_fields.append(field)

        desired_slug = self._build_unique_course_slug(
            department.faculty.code, course_code, existing_pk=course.pk
        )
        if course.slug != desired_slug:
            course.slug = desired_slug
            updated_fields.append("slug")

        if updated_fields:
            updated_fields.append("updated_at")
            course.save(update_fields=updated_fields)

        return course, created

    @staticmethod
    def _append_code_suffix(base_code, suffix):
        suffix = re.sub(r"[^A-Z0-9]+", "", suffix.upper())[:6] or "ALT"
        candidate_suffix = f"-{suffix}"
        max_base_length = 20 - len(candidate_suffix)
        trimmed_base = base_code[:max_base_length].rstrip()
        return f"{trimmed_base}{candidate_suffix}"

    @staticmethod
    def _build_unique_course_slug(faculty_code, course_code, existing_pk=None):
        base_slug = slugify(f"{faculty_code}-{course_code}")[:255] or slugify(course_code)
        candidate = base_slug
        counter = 2
        queryset = Course.objects.all()
        if existing_pk:
            queryset = queryset.exclude(pk=existing_pk)
        while queryset.filter(slug=candidate).exists():
            suffix = f"-{counter}"
            candidate = f"{base_slug[:255 - len(suffix)]}{suffix}"
            counter += 1
        return candidate

    @staticmethod
    def _build_unique_unit_slug(course_code, unit_code, semester):
        base_slug = slugify(f"{course_code}-{unit_code}-s{semester}")[:255] or slugify(
            f"{course_code}-s{semester}"
        )
        candidate = base_slug
        counter = 2
        while Unit.objects.filter(slug=candidate).exclude(
            course__code=course_code, code=unit_code, semester=semester
        ).exists():
            suffix = f"-{counter}"
            candidate = f"{base_slug[:255 - len(suffix)]}{suffix}"
            counter += 1
        return candidate

    @staticmethod
    def _tokenize_label(label):
        upper = label.upper()
        if "SSP" in upper:
            return "SSP"
        label_map = {
            "ACCOUNTING": "ACC",
            "BANKING": "BNK",
            "FINANCE": "FIN",
            "MARKETING": "MKT",
        }
        for key, token in label_map.items():
            if key in upper:
                return token
        parts = re.findall(r"[A-Z0-9]+", upper)
        if not parts:
            return "ALT"
        return "".join(part[:2] for part in parts[:3])[:6]

    @staticmethod
    def _parse_year_semester(value):
        match = re.search(r"Year\s+(\d+)\s+(?:Semester|Sem)\s+(\d+)", value, flags=re.I)
        if not match:
            raise ValueError(f"Could not parse year/semester from {value!r}")
        year = int(match.group(1))
        semester = str(int(match.group(2)))
        label = value[match.end():].strip(" -")
        return year, semester, label or None
