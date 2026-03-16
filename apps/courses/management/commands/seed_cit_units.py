"""
Seed CIT (Computing & IT) units with explicit year/semester mappings.
This uses a hard-coded mapping derived from the provided curriculum list.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.courses.models import Course, Unit


COURSE_UNITS = {
    # BSc Computer Science
    "BCS": {
        (1, 2): [
            ("BPHY 1204", "DIGITAL LOGIC AND ELECTRONICS"),
            ("BCSC 1204", "DATA STRUCTURES AND ALGORITHMS"),
            ("BPHY 1205", "ELECTRONICS I"),
            ("BSTA 1203", "PROBABILITY AND STATISTICS I"),
            ("BMAT 1204", "DISCRETE MATHEMATICS"),
            ("BMAT 1205", "CALCULUS I"),
            ("BCSE 1203", "STRUCTURED PROGRAMMING LAB"),
            ("BUCI 1104", "COMPUTER APPLICATIONS (SSP)"),
            ("BCSC 2103", "COMPUTER DESIGN AND ORGANIZATION (SSP)"),
            ("BCIT 2112", "SYSTEM ANALYSIS AND DESIGN (SSP)"),
            ("BMAT 2109", "LINEAR ALGEBRA (SSP)"),
            ("BCSC 1102", "INTRODUCTION TO PROGRAMMING (SSP)"),
            ("BUCI 1101", "COMMUNICATION SKILLS (SSP)"),
            ("BUCI 1102", "LIFE SKILLS (SSP)"),
            ("BMAT 1101", "BASIC MATHEMATICS (SSP)"),
        ],
        (2, 2): [
            ("BCIT 1210", "DATABASE MANAGEMENT SYSTEMS"),
            ("BCIT 1208", "COMPUTER NETWORKS"),
            ("BCIT 2217", "OBJECT ORIENTED PROGRAMMING II"),
            ("BCSC 2207", "SCIENTIFIC COMPUTING"),
            ("BCIT 2218", "INTERNET APPLICATION PROGRAMMING"),
            ("BCIT 2214", "SOFTWARE ENGINEERING"),
            ("BENT 1207", "ENTREPRENEURSHIP SKILLS"),
        ],
        (3, 2): [
            ("BCSC 3220", "COMPILER CONSTRUCTION AND DESIGN"),
            ("BCSC 3212", "QUANTUM COMPUTER SCIENCE"),
            ("BCIT 3238", "MOBILE APPLICATION DEVELOPMENT"),
            ("BCIT 3262", "DATABASE PROGRAMMING"),
            ("BCIT 4261", "SYSTEM SECURITY AND AUDIT"),
            ("BCIT 3260", "RESEARCH METHODS FOR IT"),
            ("BCSC 3225", "ARTIFICIAL INTELLIGENCE"),
        ],
        (4, 2): [
            ("BCSC 4234", "COMPUTER GRAPHICS"),
            ("BCIT 4266", "COMPUTING LAW AND ETHICS"),
            ("BCIT 4264", "PROJECT II (SYSTEM DEVELOPMENT)"),
            ("BSCS 4227", "DATA SCIENCE"),
            ("BCSC 4232", "EXPERT SYSTEMS"),
            ("BCSC 4248", "PATTERN RECOGNITION"),
            ("BCSC 4250", "NETWORK PROGRAMMING"),
        ],
    },
    # Diploma Computer Science
    "DCS": {
        (1, 2): [
            ("DCS 1.20412 551 10A", "Apply Business Maths and Statistics"),
            ("DCS 1.20412 551 22A", "Cooperative Practices"),
            ("DCS 1.20613 554 10A", "Apply Mathematics for Computer Science"),
            ("DCS 1.20613 554 03A", "Networking and Distributed Systems"),
            ("DCS 1.20613 554 04A", "Graphics Design"),
        ],
    },
    # BIT
    "BIT": {
        (1, 2): [
            ("BENT 1207", "ENTREPRENEURSHIP SKILLS"),
            ("BMAT 1205", "CALCULUS I"),
            ("BCIT 1202", "DATA COMMUNICATION AND COMPUTER NETWORKS"),
            ("BCIT 1210", "DATABASE MANAGEMENT SYSTEMS"),
            ("BMAT 1204", "DISCRETE MATHEMATICS"),
            ("CSC 1204", "DATA STRUCTURES AND ALGORITHMS"),
            ("CSE 1203", "STRUCTURED PROGRAMMING LAB"),
        ],
        (2, 2): [
            ("BCIT 2230", "ADVANCED OPERATING SYSTEMS"),
            ("BCSC 2205", "COMPUTER AIDED ART AND DESIGN"),
            ("BCIT 2217", "OBJECT ORIENTED PROGRAMMING II"),
            ("BPHY 1204", "DIGITAL LOGIC AND ELECTRONICS"),
            ("BSTA 1203", "PROBABILITY AND STATISTICS I"),
            ("BCIT 2214", "SOFTWARE ENGINEERING"),
            ("BCIT 2213", "NETWORKS AND SYSTEMS ADMINISTRATION"),
        ],
        (3, 2): [
            ("BCIT 3238", "MOBILE APPLICATION DEVELOPMENT"),
            ("BCIT 3237", "ELECTRONIC COMMERCE"),
            ("BCIT 3242", "ADVANCED DATABASE MANAGEMENT SYSTEMS"),
            ("BCSC 3225", "ARTIFICIAL INTELLIGENCE"),
            ("BCIT 3260", "RESEARCH METHODS FOR IT"),
            ("BCIT 3265", "DISTRIBUTED SYSTEMS"),
            ("BCIT 3244", "MULTIMEDIA SYSTEMS"),
        ],
        (4, 2): [
            ("BCSC 4227", "DATA SCIENCE"),
            ("BCIT 4255", "INFORMATION SYSTEMS AUDIT"),
            ("BCSC 4231", "KNOWLEDGE BASED SYSTEMS"),
            ("BCIT 4266", "COMPUTING LAW AND ETHICS"),
            ("BCIT 4264", "PROJECT II (SYSTEM DEVELOPMENT)"),
        ],
    },
    # BBIT
    "BBIT": {
        (1, 2): [
            ("BCIT 1207", "INTRODUCTION TO INFORMATION SYSTEMS"),
            ("BMGT 1201", "PRINCIPLES AND PRACTICE OF MANAGEMENT"),
            ("BLAW 1201", "BUSINESS LAW"),
            ("BMKT 1202", "PRINCIPLES OF MARKETING"),
            ("BENT 1207", "ENTREPRENEURSHIP SKILLS"),
        ],
        (2, 1): [  # SSP term
            ("BCIT 2112", "SYSTEMS ANALYSIS AND DESIGN"),
            ("BUCI 1101", "COMMUNICATION SKILLS"),
            ("BCSC 1102", "INTRODUCTION TO PROGRAMMING"),
            ("BECO 1101", "PRINCIPLES OF MICROECONOMICS"),
            ("BSTA 2101", "STATISTICS"),
            ("BUCI 1102", "LIFE SKILLS"),
            ("BUCI 1105", "COOPERATIVE PHILOSOPHY"),
            ("BCIT 1210", "DATABASE MANAGEMENT SYSTEMS"),
            ("BCIT 2219", "MANAGEMENT INFORMATION SYSTEMS"),
        ],
        (2, 2): [
            ("BCIT 1208", "COMPUTER NETWORKS"),
            ("BCIT 1210", "DATABASE MANAGEMENT SYSTEMS"),
            ("BECO 1202", "PRINCIPLES OF MACROECONOMICS"),
            ("BCIT 2219", "MANAGEMENT INFORMATION SYSTEMS"),
            ("BMAT 1207", "MATHEMATICS II"),
        ],
        (3, 2): [
            ("BCIT 2122", "OBJECT ORIENTED PROGRAMMING"),
            ("BCIT 3260", "RESEARCH METHODS FOR IT"),
            ("BCIT 3237", "ELECTRONIC COMMERCE"),
            ("BCIT 2132", "WEB DEVELOPMENT"),
            ("BECO 1101", "PRINCIPLES OF MICROECONOMICS (SSP)"),
            ("BMAT 1102", "MATHEMATICS I (SSP)"),
            ("BUCI 1101", "COMMUNICATION SKILLS (SSP)"),
            ("BUCI 1102", "LIFE SKILLS (SSP)"),
            ("BUCI 1105", "COOPERATIVE PHILOSOPHY (SSP)"),
        ],
        (4, 2): [
            ("BFIN 2225", "FINANCIAL ETHICS AND STANDARDS"),
            ("BCIT 4254", "ICT COMMERCIALIZATION"),
            ("BCIT 4255", "INFORMATION SYSTEMS AUDIT"),
            ("BCIT 4264", "PROJECT II (SYSTEM DEVELOPMENT)"),
            ("BCSC 4214", "MOBILE COMPUTING"),
            ("BCSC 4126", "SIMULATION AND MODELLING"),
            ("BENT 1207", "ENTREPRENEURSHIP SKILLS (SSP)"),
            ("BMGT 1201", "PRINCIPLES AND PRACTICE OF MANAGEMENT (SSP)"),
        ],
    },
    # Diploma IT
    "DIT": {
        (1, 2): [
            ("DIT 1.2 0031 441 05A", "Cooperative Practices"),
            ("DIT 1.2 0619 451 06A", "Computer Software"),
            ("DIT 1.2 0612 451 07A", "Network Design and Management"),
            ("DIT 1.2 0613 451 05A", "Computer Programming Principles"),
            ("DIT 1.2 0612 451 08A", "Computerized Database System"),
            ("DIT 1.2 0541 541 01A", "Discrete Mathematical Concepts"),
        ],
        (2, 2): [
            ("DIT 2.2 DCIT 1208", "WEB ENGINEERING (CLOUD AND MOBILE)"),
            ("DIT 2.2 DCSC 2212", "NETWORK DESIGN AND SETUP"),
            ("DIT 2.2 DCIT 2215", "PROJECT WORK (DOCUMENTATION AND SYSTEM IMPLEMENTATION)"),
            ("DIT 2.2 DCSC 2207", "EVENT DRIVEN PROGRAMMING"),
            ("DIT 2.2 DCSC 2210", "DIGITAL ELECTRONICS CONSTRUCTION"),
        ],
    },
    # Diploma Cyber Security
    "DCY": {
        (1, 2): [
            ("DCY 1.2 0612554 05A", "Install and Configure Linux"),
            ("DCY 1.2 0612554 06A", "Secure Software Application"),
            ("DCY 1.2 0612554 03A", "Apply Cooperative Practices"),
        ],
        (2, 2): [
            ("DCY 2.2 DICY 2218", "Security Assessment and Testing"),
            ("DCY 2.2 DICY 2219", "Security Operations management"),
        ],
    },
    # Bachelor of Software Engineering
    "BSEN": {
        (1, 2): [
            ("BCSE 1203", "STRUCTURED PROGRAMMING LAB"),
            ("BCSC 1204", "DATA STRUCTURES AND ALGORITHMS"),
            ("BMAT 1204", "DISCRETE MATHEMATICS"),
            ("BMAT 1205", "CALCULUS I"),
            ("BSTA 1203", "PROBABILITY AND STATISTICS I"),
            ("BPHY 1204", "DIGITAL LOGIC AND ELECTRONICS"),
        ],
        (2, 2): [
            ("BCIT 1210", "DATABASE MANAGEMENT SYSTEMS"),
            ("BCSE 2206", "SOFTWARE REQUIREMENTS ENGINEERING"),
            ("BCSE 2207", "SOFTWARE METRICS"),
            ("BCIT 2218", "INTERNET APPLICATION PROGRAMMING"),
            ("BCSE 2208", "FUNDAMENTALS OF OBJECT ORIENTED PROGRAMMING WITH JAVA"),
            ("BCIT 3262", "DATABASE PROGRAMMING"),
            ("BENT 1207", "ENTREPRENEURSHIP SKILLS"),
        ],
        (3, 2): [
            ("BCSC 3220", "COMPILER CONSTRUCTION AND DESIGN"),
            ("BCIT 3238", "MOBILE APPLICATION DEVELOPMENT"),
            ("BCIT 3260", "RESEARCH METHODS FOR IT"),
            ("BCSE 3211", "SOFTWARE VERIFICATION AND VALIDATION"),
            ("BCSE 3212", "OBJECT ORIENTED ANALYSIS AND DESIGN WITH UML"),
            ("BCSE 3213", "ADVANCED OBJECT-ORIENTED PROGRAMMING WITH JAVA"),
            ("BCSE 3214", "SOFTWARE ARCHITECTURE"),
        ],
        (4, 2): [
            ("BCIT 4264", "PROJECT II (SYSTEM DEVELOPMENT)"),
            ("BCSE 4221", "SOFTWARE ENGINEERING PROFESSION AND ETHICS"),
            ("BCSE 4222", "SOFTWARE MAINTENANCE AND EVOLUTION"),
            ("BCSE 4224", "COMPONENT BASED SOFTWARE DEVELOPMENT"),
            ("BCSC 3225", "ARTIFICIAL INTELLIGENCE"),
            ("BCIT 4261", "SYSTEM SECURITY AND AUDIT"),
            ("BCSE 4225", "ADVANCED BACK-END WEB DEVELOPMENT"),
        ],
    },
    # Bachelor of Data Science
    "BDAT": {
        (1, 2): [
            ("BSTA 1203", "PROBABILITY AND STATISTICS I"),
            ("BCSC 1204", "DATA STRUCTURES AND ALGORITHMS"),
            ("BMAT 1204", "DISCRETE MATHEMATICS"),
            ("BMAT 1205", "CALCULUS I"),
            ("BCIT 1208", "COMPUTER NETWORKS"),
            ("BCIT 1210", "DATABASE MANAGEMENT SYSTEMS"),
            ("BENT 1207", "ENTREPRENEURSHIP SKILLS"),
        ],
        (2, 2): [
            ("BDSC 2203", "DATA PREPARATION"),
            ("BSTA 2206", "PROBABILITY AND STATISTICS III"),
            ("BCSC 2207", "SCIENTIFIC COMPUTING"),
            ("BCIT 2218", "INTERNET APPLICATION PROGRAMMING"),
            ("BSTA 2235", "LINEAR MODELS II"),
            ("BCSC 2256", "DATA COMMUNICATION"),
            ("BCIT 2214", "SOFTWARE ENGINEERING"),
        ],
        (3, 2): [
            ("BDSC 3208", "DATA VISUALIZATION"),
            ("BDSC 3217", "VIDEO ANALYTICS"),
            ("BSTA 3253", "RESEARCH METHODS"),
            ("BDSC 3211", "TEXT ANALYTICS"),
            ("BDSC 3212", "DATA ENGINEERING"),
            ("BCIT 3260", "RESEARCH METHODS FOR IT"),
            ("BSTA 3239", "ECONOMETRICS"),
        ],
        (4, 2): [
            ("BSTA 4248", "STATISTICS AND BIG DATA ANALYTICS"),
            ("BCSC 4235", "DATA MINING"),
            ("BDSC 4219", "CYBERSECURITY AND DATA SCIENCE"),
            ("BSTA 4251", "PROJECT II (RESEARCH PROJECT REPORT)"),
            ("BDSC 4215", "STRATEGIC INFORMATION SYSTEMS"),
            ("BCIT 4266", "COMPUTING LAW AND ETHICS"),
        ],
    },
    # BSc Applied Statistics
    "BSCAS": {
        (1, 2): [
            ("BSTA 1203", "PROBABILITY AND STATISTICS I"),
            ("BPHY 1203", "PHYSICS"),
            ("BMAT 1205", "CALCULUS I"),
            ("BMAT 1204", "DISCRETE MATHEMATICS"),
            ("BCSC 1204", "DATA STRUCTURES AND ALGORITHMS"),
            ("BCIT 1210", "DATABASE MANAGEMENT SYSTEMS"),
            ("BENT 1207", "ENTREPRENEURSHIP SKILLS"),
        ],
        (2, 2): [
            ("BSTA 2237", "ECONOMETRICS I"),
            ("BSTA 2235", "LINEAR MODELS II"),
            ("BSTA 2207", "OPERATIONS RESEARCH I"),
            ("BSTA 2206", "PROBABILITY AND STATISTICS III"),
            ("BMAT 2210", "LINEAR ALGEBRA II"),
            ("BCSC 2207", "SCIENTIFIC COMPUTING"),
            ("BMAT 2217", "VECTOR ANALYSIS"),
        ],
        (3, 2): [
            ("BMAT 3213", "NUMERICAL ANALYSIS"),
            ("BSTA 3253", "RESEARCH METHODS"),
            ("BSTA 3221", "THEORY OF ESTIMATION"),
            ("BSTA 3219", "ECONOMIC AND SOCIAL STATISTICS"),
            ("BSTA 3213", "STOCHASTIC PROCESSES"),
            ("BSTA 3228", "SURVIVAL MODELS"),
            ("BSTA 4147", "HYPOTHESIS TESTING"),
        ],
        (4, 2): [
            ("BSTA 4251", "PROJECT II"),
            ("BSTA 4267", "DESIGN AND ANALYSIS OF CLINICAL TRIALS"),
            ("BSTA 4218", "NON-PARAMETRIC AND ROBUST METHODS"),
            ("BSTA 4254", "CATEGORICAL DATA ANALYSIS"),
            ("BSTA 4248", "STATISTICS AND BIG DATA ANALYTICS"),
            ("BCSC 4248", "DATA SCIENCE"),
            ("BSTA 4229", "BAYESIAN DATA ANALYSIS"),
        ],
    },
    # BSc Statistics & IT
    "BSIT": {
        (1, 2): [
            ("BMAT 1204", "DISCRETE MATHEMATICS"),
            ("BMAT 1205", "CALCULUS I"),
            ("BSTA 1203", "PROBABILITY AND STATISTICS I"),
            ("BCSC 1204", "DATA STRUCTURES AND ALGORITHMS"),
            ("BCIT 1208", "COMPUTER NETWORKS"),
            ("BCIT 1210", "DATABASE MANAGEMENT SYSTEMS"),
            ("BENT 1207", "ENTREPRENEURSHIP SKILLS"),
        ],
        (2, 2): [
            ("BCSC 2207", "SCIENTIFIC COMPUTING"),
            ("BSTA 2235", "LINEAR MODELS II"),
            ("BSTA 2207", "OPERATIONS RESEARCH I"),
            ("BSTA 2206", "PROBABILITY AND STATISTICS III"),
            ("BCIT 2219", "MANAGEMENT INFORMATION SYSTEMS"),
            ("BCIT 2217", "OBJECT ORIENTED PROGRAMMING II"),
            ("BSTA 3210", "STATISTICAL DATA ANALYSIS"),
        ],
        (3, 2): [
            ("BCIT 3237", "ELECTRONIC COMMERCE"),
            ("BSTA 3253", "RESEARCH METHODS FOR IT"),
            ("BSTA 3221", "THEORY OF ESTIMATION"),
            ("BCSC 3225", "ARTIFICIAL INTELLIGENCE"),
            ("BCIT 3262", "DATABASE PROGRAMMING"),
            ("BMAT 3213", "NUMERICAL ANALYSIS"),
        ],
        (4, 2): [
            ("BCIT 3242", "ADVANCED DATABASE MANAGEMENT SYSTEMS"),
            ("BCIT 4264", "PROJECT II"),
            ("BSTA 4218", "NON-PARAMETRIC AND ROBUST METHODS"),
            ("BSCC 4250", "NETWORK PROGRAMMING"),
            ("BSCC 4227", "DATA SCIENCE"),
            ("BSTA 4105", "DESIGN AND ANALYSIS OF SAMPLE SURVEY"),
        ],
    },
}


class Command(BaseCommand):
    help = "Seed CIT units (hard-coded curriculum mapping)"

    def handle(self, *args, **options):
        created = 0
        missing_courses = []
        for course_code, year_map in COURSE_UNITS.items():
            qs = Course.objects.filter(code=course_code).order_by("id")
            if not qs.exists():
                missing_courses.append(course_code)
                continue
            course = qs.first()
            for (year, sem), units in year_map.items():
                for code, name in units:
                    obj, was_created = Unit.objects.get_or_create(
                        course=course,
                        code=code,
                        semester=str(sem),
                        year_of_study=year,
                        defaults={"name": name},
                    )
                    if was_created:
                        created += 1
        if missing_courses:
            self.stdout.write(
                self.style.WARNING(
                    f"Courses missing (units skipped): {', '.join(sorted(set(missing_courses)))}"
                )
            )
        self.stdout.write(self.style.SUCCESS(f"Units created: {created}"))
