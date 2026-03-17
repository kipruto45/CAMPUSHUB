import re
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.faculties.models import Faculty, Department
from apps.courses.models import Course, Unit


TEXT = r"""
Faculty of Computing and Information Technology (CIT)
Department of Computer Science
BSc. Computer Science (BCS)

Year 1 Semester 2: DIGITAL LOGIC AND ELECTRONICS (BPHY 1204), DATA STRUCTURES AND ALGORITHMS (BCSC 1204), ELECTRONICS I (BPHY 1205), PROBABILITY AND STATISTICS I (BSTA 1203), DISCRETE MATHEMATICS (BMAT 1204), CALCULUS I (BMAT 1205), STRUCTURED PROGRAMMING LAB (BCSE 1203), COMPUTER APPLICATIONS (SSP) (BUCI 1104), COMPUTER DESIGN AND ORGANIZATION (SSP) (BCSC 2103), SYSTEM ANALYSIS AND DESIGN (SSP) (BCIT 2112), LINEAR ALGEBRA (SSP) (BMAT 2109), INTRODUCTION TO PROGRAMMING (SSP) (BCSC 1102), COMMUNICATION SKILLS (SSP) (BUCI 1101), LIFE SKILLS (SSP) (BUCI 1102), BASIC MATHEMATICS (SSP) (BMAT 1101)

Year 2 Semester 2: DATABASE MANAGEMENT SYSTEMS (BCIT 1210), COMPUTER NETWORKS (BCIT 1208), OBJECT ORIENTED PROGRAMMING II (BCIT 2217), SCIENTIFIC COMPUTING (BCSC 2207), INTERNET APPLICATION PROGRAMMING (BCIT 2218), SOFTWARE ENGINEERING (BCIT 2214), ENTREPRENEURSHIP SKILLS (BENT 1207)

Year 3 Semester 2: COMPILER CONSTRUCTION AND DESIGN (BCSC 3220), QUANTUM COMPUTER SCIENCE (BCSC 3212), MOBILE APPLICATION DEVELOPMENT (BCIT 3238), DATABASE PROGRAMMING (BCIT 3262), SYSTEM SECURITY AND AUDIT (BCIT 4261), RESEARCH METHODS FOR IT (BCIT 3260), ARTIFICIAL INTELLIGENCE (BCSC 3225)

Year 4 Semester 2: COMPUTER GRAPHICS (BCSC 4234), COMPUTING LAW AND ETHICS (BCIT 4266), PROJECT II (SYSTEM DEVELOPMENT) (BCIT 4264), DATA SCIENCE (BSCS 4227), EXPERT SYSTEMS (BCSC 4232), PATTERN RECOGNITION (BCSC 4248), NETWORK PROGRAMMING (BCSC 4250)

Diploma in Computer Science (DCS)

Year 1 Semester 2: Apply Business Maths and Statistics (DCS 1.20412 551 10A), Cooperative Practices (DCS 1.20412 551 22A), Apply Mathematics for Computer Science (DCS 1.20613 554 10A), Networking and Distributed Systems (DCS 1.20613 554 03A), Graphics Design (DCS 1.20613 554 04A)

Department of Information Technology
BIT (Bachelor of Information Technology)

Year 1 Semester 2: ENTREPRENEURSHIP SKILLS (BENT 1207), CALCULUS I (BMAT 1205), DATA COMMUNICATION AND COMPUTER NETWORKS (BCIT 1202), DATABASE MANAGEMENT SYSTEMS (BCIT 1210), DISCRETE MATHEMATICS (BMAT 1204), DATA STRUCTURES AND ALGORITHMS (CSC 1204), STRUCTURED PROGRAMMING LAB (CSE 1203)

Year 2 Semester 2: ADVANCED OPERATING SYSTEMS (BCIT 2230), COMPUTER AIDED ART AND DESIGN (BCSC 2205), OBJECT ORIENTED PROGRAMMING II (BCIT 2217), DIGITAL LOGIC AND ELECTRONICS (BPHY 1204), PROBABILITY AND STATISTICS I (BSTA 1203), SOFTWARE ENGINEERING (BCIT 2214), NETWORKS AND SYSTEMS ADMINISTRATION (BCIT 2213)

Year 3 Semester 2: MOBILE APPLICATION DEVELOPMENT (BCIT 3238), ELECTRONIC COMMERCE (BCIT 3237), ADVANCED DATABASE MANAGEMENT SYSTEMS (BCIT 3242), ARTIFICIAL INTELLIGENCE (BCSC 3225), RESEARCH METHODS FOR IT (BCIT 3260), DISTRIBUTED SYSTEMS (BCIT 3265), MULTIMEDIA SYSTEMS (BCIT 3244)

Year 4 Semester 2: DATA SCIENCE (BCSC 4227), INFORMATION SYSTEMS AUDIT (BCIT 4255), KNOWLEDGE BASED SYSTEMS (BCSC 4231), COMPUTING LAW AND ETHICS (BCIT 4266), PROJECT II (SYSTEM DEVELOPMENT) (BCIT 4264)

BBIT (Bachelor of Business Information Technology)

Year 1 Semester 2: INTRODUCTION TO INFORMATION SYSTEMS (BCIT 1207), PRINCIPLES AND PRACTICE OF MANAGEMENT (BMGT 1201), BUSINESS LAW (BLAW 1201), PRINCIPLES OF MARKETING (BMKT 1202), ENTREPRENEURSHIP SKILLS (BENT 1207)

Year 2 Semester 1 (SSP): SYSTEMS ANALYSIS AND DESIGN (BCIT 2112), COMMUNICATION SKILLS (BUCI 1101), INTRODUCTION TO PROGRAMMING (BCSC 1102), PRINCIPLES OF MICROECONOMICS (BECO 1101), STATISTICS (BSTA 2101), LIFE SKILLS (BUCI 1102), COOPERATIVE PHILOSOPHY (BUCI 1105), DATABASE MANAGEMENT SYSTEMS (BCIT 1210), MANAGEMENT INFORMATION SYSTEMS (BCIT 2219)

Year 2 Semester 2: COMPUTER NETWORKS (BCIT 1208), DATABASE MANAGEMENT SYSTEMS (BCIT 1210), PRINCIPLES OF MACROECONOMICS (BECO 1202), MANAGEMENT INFORMATION SYSTEMS (BCIT 2219), MATHEMATICS II (BMAT 1207)

Year 3 Semester 2: OBJECT ORIENTED PROGRAMMING (BCIT 2122), RESEARCH METHODS FOR IT (BCIT 3260), ELECTRONIC COMMERCE (BCIT 3237), WEB DEVELOPMENT (BCIT 2132), PRINCIPLES OF MICROECONOMICS (SSP) (BECO 1101), MATHEMATICS I (SSP) (BMAT 1102), COMMUNICATION SKILLS (SSP) (BUCI 1101), LIFE SKILLS (SSP) (BUCI 1102), COOPERATIVE PHILOSOPHY (SSP) (BUCI 1105)

Year 4 Semester 2: FINANCIAL ETHICS AND STANDARDS (BFIN 2225), ICT COMMERCIALIZATION (BCIT 4254), INFORMATION SYSTEMS AUDIT (BCIT 4255), PROJECT II (SYSTEM DEVELOPMENT) (BCIT 4264), MOBILE COMPUTING (BCSC 4214), SIMULATION AND MODELLING (BCSC 4126), ENTREPRENEURSHIP SKILLS (SSP) (BENT 1207), PRINCIPLES AND PRACTICE OF MANAGEMENT (SSP) (BMGT 1201)

Diploma in Information Technology (DIT)

Year 1 Semester 2: Cooperative Practices (DIT 1.2 0031 441 05A), Computer Software (DIT 1.2 0619 451 06A), Network Design and Management (DIT 1.2 0612 451 07A), Computer Programming Principles (DIT 1.2 0613 451 05A), Computerized Database System (DIT 1.2 0612 451 08A), Discrete Mathematical Concepts (DIT 1.2 0541 541 01A)

Year 2 Semester 2: WEB ENGINEERING(CLOUD AND MOBILE) (DIT 2.2 DCIT 1208), NETWORK DESIGN AND SETUP (DIT 2.2 DCSC 2212), PROJECT WORK ( DOCUMENTATION AND SYSTEM IMPLEMENTATION) (DIT 2.2 DCIT 2215), EVENT DRIVEN PROGRAMMING (DIT 2.2 DCSC 2207), DIGITAL ELECTRONICS CONSTRUCTION (DIT 2.2 DCSC 2210)

Diploma in Cyber Security (DCY)

Year 1 Semester 2: Install and Configure Linux (DCY 1.2 0612554 05A), Secure Software Application (DCY 1.2 0612554 06A), Apply Cooperative Practices (DCY 1.2 0612554 03A)

Year 2 Semester 2: Security Assessment and Testing (DCY 2.2 DICY 2218), Security Operations management (DCY 2.2 DICY 2219)
"""


def dept_code_from_name(name: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", name)
    if not words:
        return "DEP"
    code = "".join(w[0] for w in words)[:5].upper()
    return code or "DEP"


class Command(BaseCommand):
    help = "Seed faculties, departments, courses, and units from embedded full-text curriculum."

    def handle(self, *args, **options):
        current_faculty = None
        current_department = None
        current_course = None

        faculty_re = re.compile(r"Faculty of .*?\(([A-Z0-9]+)\)", re.IGNORECASE)
        dept_re = re.compile(r"Department of (.+)", re.IGNORECASE)
        course_re = re.compile(r"\((?P<code>[A-Z0-9\-]+)\)")
        year_re = re.compile(r"Year\\s+(\\d+)\\s+Semester\\s+(\\d+)\\s*[:：]\\s*(.+)", re.IGNORECASE)

        lines = TEXT.splitlines()
        created_units = 0
        updated_units = 0
        missing_courses = set()

        for raw in lines:
            line = raw.strip()
            if not line:
                continue

            fac_m = faculty_re.search(line)
            if fac_m:
                fac_code = fac_m.group(1)
                current_faculty, _ = Faculty.objects.get_or_create(
                    code=fac_code,
                    defaults={"name": line, "description": line},
                )
                # default department reset
                current_department = None
                current_course = None
                continue

            dept_m = dept_re.match(line)
            if dept_m and current_faculty:
                dept_name = dept_m.group(1).strip()
                dept_code = dept_code_from_name(dept_name)
                current_department, _ = Department.objects.get_or_create(
                    code=dept_code,
                    faculty=current_faculty,
                    defaults={"name": dept_name},
                )
                current_course = None
                continue

            # Course line
            if "(" in line and ")" in line and not line.lower().startswith("year"):
                c_match = course_re.search(line)
                if c_match and current_department:
                    code = c_match.group("code")
                    name = line[: line.rfind("(")].strip(" -")
                    current_course, _ = Course.objects.get_or_create(
                        code=code,
                        department=current_department,
                        defaults={
                            "name": name,
                            "description": name,
                            "duration_years": 4,
                        },
                    )
                continue

            # Year/Semester line with units
            y_match = year_re.match(line)
            if y_match and current_course:
                year = int(y_match.group(1))
                sem = y_match.group(2)
                body = y_match.group(3)
                parts = [p.strip() for p in body.split(",") if p.strip()]
                for part in parts:
                    codes = re.findall(r"\\(([^()]+)\\)", part)
                    if not codes:
                        continue
                    unit_code = codes[-1].strip()
                    unit_name = part[: part.rfind("(")].strip(" ,")
                    unit_name = re.sub(r"\\(SSP\\)", "", unit_name).strip()
                    obj, created = Unit.objects.update_or_create(
                        course=current_course,
                        code=unit_code,
                        defaults={
                            "name": unit_name or unit_code,
                            "year_of_study": year,
                            "semester": str(sem),
                            "is_active": True,
                        },
                    )
                    created_units += 1 if created else 0
                    updated_units += 0 if created else 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Units created: {created_units}, updated: {updated_units}"
            )
        )
