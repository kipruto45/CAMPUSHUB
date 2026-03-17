"""
Management command to seed faculties, departments, courses, and units.
"""

from django.core.management.base import BaseCommand
from apps.faculties.models import Faculty, Department
from apps.courses.models import Course, Unit


def create_unit(course, code, name, semester, year_of_study):
    """Helper function to create unit, skipping if exists"""
    if not Unit.objects.filter(course=course, code=code, semester=semester).exists():
        Unit.objects.create(
            course=course, code=code, name=name, semester=semester, year_of_study=year_of_study
        )


class Command(BaseCommand):
    help = "Seed faculties, departments, courses, and units"

    def handle(self, *args, **options):
        # SCHOOL OF COOPERATIVE AND COMMUNITY DEVELOPMENT (SCCD)
        sccd, _ = Faculty.objects.get_or_create(
            name="SCHOOL OF COOPERATIVE AND COMMUNITY DEVELOPMENT",
            code="SCCD",
            defaults={"description": "School of Cooperative and Community Development"}
        )
        
        # Department of Community Development and Environment Management (DCDEM)
        dcdem, _ = Department.objects.get_or_create(
            faculty=sccd,
            name="Department of Community Development and Environment Management",
            code="DCDEM",
            defaults={"description": "Department of Community Development and Environment Management"}
        )
        
        # Bachelor of Co-operatives and Community Development (BCCD)
        bccd, _ = Course.objects.get_or_create(
            department=dcdem,
            name="Bachelor of Co-operatives and Community Development",
            code="BCCD",
            defaults={"duration_years": 4}
        )
        create_unit(bccd, "BUCIU 1101", "COMMUNICATION SKILLS", "1", 1)
        create_unit(bccd, "BUCI 1105", "COOPERATIVE PHILOSOPHY", "1", 1)
        create_unit(bccd, "BCIT 1103", "COMPUTER APPLICATIONS", "1", 1)
        create_unit(bccd, "BOCD 1101", "INTRODUCTION TO COMMUNITY DEVELOPMENT", "1", 1)
        create_unit(bccd, "BSTA 2101", "BUSINESS STATISTICS", "1", 2)
        create_unit(bccd, "BCOB 2112", "MANAGEMENT OF SACCOS", "1", 2)
        create_unit(bccd, "BSOC 2103", "RURAL SOCIOLOGY", "1", 2)
        create_unit(bccd, "BCOB 3106", "CO-OPERATIVE EDUCATION AND TRAINING", "1", 3)
        create_unit(bccd, "BSC 3105", "DEVELOPMENT ANTHROPOLOGY", "1", 3)
        create_unit(bccd, "BCCD 3108", "PARTICIPATORY DEVELOPMENT APPROACHES", "1", 3)
        create_unit(bccd, "BPSY 3117", "SOCIAL PSYCHOLOGY", "1", 3)
        create_unit(bccd, "BSWK 3105", "SOCIAL POLICY & ADMINISTRATION", "1", 3)
        create_unit(bccd, "BOCD 4113", "PARTICIPATORY TRAINING FOR COMMUNITY LIVELIHOODS", "1", 4)
        create_unit(bccd, "BOCD 4116", "COMMUNITY ASSETS AND SERVICES", "1", 4)
        create_unit(bccd, "BMFI 4105", "RISK MANAGEMENT IN MICROFINANCE", "1", 4)
        create_unit(bccd, "BOCD 4114", "FUNDRAISING FOR COMMUNITY PROJECTS", "1", 4)
        
        # Bachelor of Community Development (BCD)
        bcd, _ = Course.objects.get_or_create(
            department=dcdem, name="Bachelor of Community Development", code="BCD", defaults={"duration_years": 4}
        )
        create_unit(bcd, "BUCIU 1101", "COMMUNICATION SKILLS", "1", 1)
        create_unit(bcd, "BUCI 1105", "COOPERATIVE PHILOSOPHY", "1", 1)
        create_unit(bcd, "BCIT 1103", "COMPUTER APPLICATIONS", "1", 1)
        create_unit(bcd, "BOCD 1101", "INTRODUCTION TO COMMUNITY DEVELOPMENT", "1", 1)
        create_unit(bcd, "BSWK 1101", "INTRODUCTION TO SOCIAL WORK", "1", 1)
        create_unit(bcd, "BSTA 2101", "BUSINESS STATISTICS", "1", 2)
        create_unit(bcd, "BCOB 2112", "MANAGEMENT OF SACCOS", "1", 2)
        create_unit(bcd, "BETH 2102", "LEADERSHIP AND ETHICS", "1", 2)
        create_unit(bcd, "BSOC 2103", "RURAL SOCIOLOGY", "1", 2)
        
        # Bachelor of Disaster Risk Management (BDRM)
        bdrm, _ = Course.objects.get_or_create(
            department=dcdem, name="Bachelor of Disaster Risk Management", code="BDRM", defaults={"duration_years": 4}
        )
        create_unit(bdrm, "BUCIU 1101", "COMMUNICATION SKILLS", "1", 1)
        create_unit(bdrm, "BUCI 1102", "COOPERATIVE PHILOSOPHY", "1", 1)
        create_unit(bdrm, "BCIT 1103", "COMPUTER APPLICATIONS", "1", 1)
        create_unit(bdrm, "BDRM 1101", "INTRODUCTION TO DISASTER MANAGEMENT", "1", 1)
        create_unit(bdrm, "BSOC 1206", "FUNDAMENTALS OF SOCIOLOGY", "1", 1)
        
        # Bachelor of Environmental Studies (BSET)
        bset, _ = Course.objects.get_or_create(
            department=dcdem, name="Bachelor of Environmental Studies", code="BSET", defaults={"duration_years": 4}
        )
        create_unit(bset, "BUCIU 1101", "COMMUNICATION SKILLS", "1", 1)
        create_unit(bset, "BUCU 1105", "CO-OPERATIVE PHILOSOPHY", "1", 1)
        create_unit(bset, "BCIT 1103", "COMPUTER APPLICATIONS", "1", 1)
        create_unit(bset, "BUCU 1103", "LIFE SKILLS", "1", 1)
        create_unit(bset, "BENV 1121", "INTRODUCTION TO ENVIRONMENTAL SCIENCE", "1", 1)
        
        # Department of Cooperatives and Agribusiness Management (DCAM)
        dcam, _ = Department.objects.get_or_create(
            faculty=sccd,
            name="Department of Cooperatives and Agribusiness Management",
            code="DCAM",
            defaults={"description": "Department of Cooperatives and Agribusiness Management"}
        )
        
        # Bachelor of Co-operative Business (BCOB)
        bcob, _ = Course.objects.get_or_create(
            department=dcam, name="Bachelor of Co-operative Business", code="BCOB", defaults={"duration_years": 4}
        )
        create_unit(bcob, "BUCI 1104", "COMPUTER APPLICATIONS", "1", 1)
        create_unit(bcob, "BUCI 1105", "COOPERATIVE PHILOSOPHY", "1", 1)
        create_unit(bcob, "BSOC 1102", "INTRODUCTION TO SOCIOLOGY", "1", 1)
        create_unit(bcob, "BCOB 2102", "CO-OPERATIVE MANAGEMENT", "1", 2)
        create_unit(bcob, "BSTA 2101", "STATISTICS", "1", 2)
        create_unit(bcob, "BACC 2106", "ACCOUNTING FOR ASSETS", "1", 2)
        
        # Bachelor of Agricultural Economics and Management (BSc. A.M)
        bscam, _ = Course.objects.get_or_create(
            department=dcam, name="Bachelor of Agricultural Economics and Management", code="BSCAM", defaults={"duration_years": 4}
        )
        create_unit(bscam, "BUCIU 1101", "COMMUNICATION SKILLS", "1", 1)
        create_unit(bscam, "BUCI 1105", "COOPERATIVE PHILOSOPHY", "1", 1)
        create_unit(bscam, "BUCI 1104", "COMPUTER APPLICATIONS", "1", 1)
        
        self.stdout.write(self.style.SUCCESS(f"Created SCCD school"))

        # SCHOOL OF BUSINESS AND ECONOMICS (SBE)
        sbe, _ = Faculty.objects.get_or_create(
            name="SCHOOL OF BUSINESS AND ECONOMICS", code="SBE", defaults={"description": "School of Business and Economics"}
        )
        
        # Department of Accounting and Finance (DAF)
        daf, _ = Department.objects.get_or_create(
            faculty=sbe, name="Department of Accounting and Finance", code="DAF", defaults={"description": "Department of Accounting and Finance"}
        )
        
        # Bachelor of Commerce (BCOM)
        bcom, _ = Course.objects.get_or_create(
            department=daf, name="Bachelor of Commerce", code="BCOM", defaults={"duration_years": 4}
        )
        create_unit(bcom, "BUCU 1101", "COMMUNICATION SKILLS", "1", 1)
        create_unit(bcom, "BUCI 1105", "COOPERATIVE PHILOSOPHY", "1", 1)
        create_unit(bcom, "BUCI 1104", "COMPUTER APPLICATIONS", "1", 1)
        create_unit(bcom, "BUCU 1102", "LIFE SKILLS", "1", 1)
        create_unit(bcom, "BECO 1101", "PRINCIPLES OF MICROECONOMICS", "1", 1)
        create_unit(bcom, "BECO 2103", "INTERMEDIATE MICROECONOMICS", "1", 2)
        create_unit(bcom, "BSTA 2101", "STATISTICS", "1", 2)
        create_unit(bcom, "BACC 2105", "COST ACCOUNTING", "1", 2)
        create_unit(bcom, "BACC 2106", "ACCOUNTING FOR ASSETS", "1", 2)
        create_unit(bcom, "BHRM 1101", "PRINCIPLES OF HUMAN RESOURCE MANAGEMENT", "1", 2)
        
        # Bachelor of Accounting (BSA)
        bsa, _ = Course.objects.get_or_create(
            department=daf, name="Bachelor of Accounting", code="BSA", defaults={"duration_years": 4}
        )
        create_unit(bsa, "BUCU 1101", "COMMUNICATION SKILLS", "1", 1)
        create_unit(bsa, "BUCI 1105", "COOPERATIVE PHILOSOPHY", "1", 1)
        create_unit(bsa, "BUCI 1104", "COMPUTER APPLICATIONS", "1", 1)
        
        # Bachelor of Banking and Finance (BBF)
        bbf, _ = Course.objects.get_or_create(
            department=daf, name="Bachelor of Banking and Finance", code="BBF", defaults={"duration_years": 4}
        )
        create_unit(bbf, "BUCU 1101", "COMMUNICATION SKILLS", "1", 1)
        create_unit(bbf, "BUCI 1105", "COOPERATIVE PHILOSOPHY", "1", 1)
        create_unit(bbf, "BBAN 1101", "PRINCIPLES OF BANKING", "1", 1)
        
        # Bachelor of Business Management (BBM)
        bbm, _ = Course.objects.get_or_create(
            department=daf, name="Bachelor of Business Management", code="BBM", defaults={"duration_years": 4}
        )
        create_unit(bbm, "BUCU 1101", "COMMUNICATION SKILLS", "1", 1)
        create_unit(bbm, "BUCI 1105", "COOPERATIVE PHILOSOPHY", "1", 1)
        
        # Bachelor of Human Resource Management (BHRM)
        bhrm, _ = Course.objects.get_or_create(
            department=daf, name="Bachelor of Human Resource Management", code="BHRM", defaults={"duration_years": 4}
        )
        create_unit(bhrm, "BUCU 1101", "COMMUNICATION SKILLS", "1", 1)
        create_unit(bhrm, "BUCI 1105", "COOPERATIVE PHILOSOPHY", "1", 1)
        create_unit(bhrm, "BHRM 1101", "PRINCIPLES OF HUMAN RESOURCE MANAGEMENT", "1", 1)
        
        # Bachelor of Purchasing and Supplies Management (BPSM)
        bpsm, _ = Course.objects.get_or_create(
            department=daf, name="Bachelor of Purchasing and Supplies Management", code="BPSM", defaults={"duration_years": 4}
        )
        create_unit(bpsm, "BUCU 1101", "COMMUNICATION SKILLS", "1", 1)
        create_unit(bpsm, "BUCI 1105", "CO-OPERATIVE PHILOSOPHY", "1", 1)
        
        # Bachelor of Economics (BECO)
        beco, _ = Course.objects.get_or_create(
            department=daf, name="Bachelor of Economics", code="BECO", defaults={"duration_years": 4}
        )
        create_unit(beco, "BUCU 1101", "COMMUNICATION SKILLS", "1", 1)
        create_unit(beco, "BUCI 1105", "COOPERATIVE PHILOSOPHY", "1", 1)
        create_unit(beco, "BMAT 1101", "BASIC MATHEMATICS", "1", 1)
        
        # Department of Entrepreneurship (DE)
        de, _ = Department.objects.get_or_create(
            faculty=sbe, name="Department of Entrepreneurship", code="DE", defaults={"description": "Department of Entrepreneurship"}
        )
        
        # Bachelor of Marketing and Management (BMM)
        bmm, _ = Course.objects.get_or_create(
            department=de, name="Bachelor of Marketing and Management", code="BMM", defaults={"duration_years": 4}
        )
        
        self.stdout.write(self.style.SUCCESS(f"Created SBE school"))

        # SCHOOL OF COMPUTING AND MATHEMATICS (SCM)
        scm, _ = Faculty.objects.get_or_create(
            name="SCHOOL OF COMPUTING AND MATHEMATICS", code="SCM", defaults={"description": "School of Computing and Mathematics"}
        )
        
        # Department of Mathematical Sciences (DMS)
        dms, _ = Department.objects.get_or_create(
            faculty=scm, name="Department of Mathematical Sciences", code="DMS", defaults={"description": "Department of Mathematical Sciences"}
        )
        
        # Bachelor of Science in Actuarial Science (BSAS)
        bsas, _ = Course.objects.get_or_create(
            department=dms, name="Bachelor of Science in Actuarial Science", code="BSAS", defaults={"duration_years": 4}
        )
        create_unit(bsas, "BUCU 1101", "COMMUNICATION SKILLS", "1", 1)
        create_unit(bsas, "BUCI 1105", "COOPERATIVE PHILOSOPHY", "1", 1)
        create_unit(bsas, "BMAT 1101", "BASIC MATHEMATICS", "1", 1)
        
        # Bachelor of Applied Statistics and Economics (BASE)
        base, _ = Course.objects.get_or_create(
            department=dms, name="Bachelor of Applied Statistics and Economics", code="BASE", defaults={"duration_years": 4}
        )
        
        # Bachelor of Applied Statistics and Data Science (BASD)
        basd, _ = Course.objects.get_or_create(
            department=dms, name="Bachelor of Applied Statistics and Data Science", code="BASD", defaults={"duration_years": 4}
        )
        
        # Bachelor of Science in Applied Statistics (BSCAS)
        bscas, _ = Course.objects.get_or_create(
            department=dms, name="Bachelor of Science in Applied Statistics", code="BSCAS", defaults={"duration_years": 4}
        )
        
        # Department of Computer Science and Information Technology (CSIT)
        csit, _ = Department.objects.get_or_create(
            faculty=scm, name="Department of Computer Science and Information Technology", code="CSIT", defaults={"description": "Department of Computer Science and Information Technology"}
        )
        
        # Bachelor of Information Technology (BIT)
        bit, _ = Course.objects.get_or_create(
            department=csit, name="Bachelor of Information Technology", code="BIT", defaults={"duration_years": 4}
        )
        create_unit(bit, "BUCU 1101", "COMMUNICATION SKILLS", "1", 1)
        create_unit(bit, "BUCI 1105", "COOPERATIVE PHILOSOPHY", "1", 1)
        create_unit(bit, "BCSC 1102", "INTRODUCTION TO PROGRAMMING", "1", 1)
        
        # Bachelor of Business Information Technology (BBIT)
        bbit, _ = Course.objects.get_or_create(
            department=csit, name="Bachelor of Business Information Technology", code="BBIT", defaults={"duration_years": 4}
        )
        
        # Bachelor of Science in Computer Science (BCS)
        bcs, _ = Course.objects.get_or_create(
            department=csit, name="Bachelor of Science in Computer Science", code="BCS", defaults={"duration_years": 4}
        )
        create_unit(bcs, "BUCU 1101", "COMMUNICATION SKILLS", "1", 1)
        create_unit(bcs, "BUCI 1105", "COOPERATIVE PHILOSOPHY", "1", 1)
        create_unit(bcs, "BCSC 1102", "INTRODUCTION TO PROGRAMMING", "1", 1)
        
        # Bachelor of Software Engineering (BSSE)
        bsse, _ = Course.objects.get_or_create(
            department=csit, name="Bachelor of Software Engineering", code="BSSE", defaults={"duration_years": 4}
        )
        
        # Bachelor of Data Science (BDAT)
        bdat, _ = Course.objects.get_or_create(
            department=csit, name="Bachelor of Data Science", code="BDAT", defaults={"duration_years": 4}
        )
        
        # Bachelor of Science in Statistics and Information Technology (BSIT)
        bsit, _ = Course.objects.get_or_create(
            department=csit, name="Bachelor of Science in Statistics and Information Technology", code="BSIT", defaults={"duration_years": 4}
        )
        
        self.stdout.write(self.style.SUCCESS(f"Created SCM school"))

        # FACULTY OF ARTS AND SOCIAL COMMUNICATION
        fasc, _ = Faculty.objects.get_or_create(
            name="FACULTY OF ARTS AND SOCIAL COMMUNICATION", code="FASC", defaults={"description": "Faculty of Arts and Social Communication"}
        )
        
        # Bachelor of Public Relations and Advertising (BPRA)
        bpra, _ = Course.objects.get_or_create(
            department=daf, name="Bachelor of Public Relations and Advertising", code="BPRA", defaults={"duration_years": 4}
        )
        create_unit(bpra, "BUCU 1101", "COMMUNICATION SKILLS", "1", 1)
        create_unit(bpra, "BUCU 1105", "CO-OPERATIVE PHILOSOPHY", "1", 1)
        create_unit(bpra, "BPRA 1101", "INTRODUCTION TO PUBLIC RELATIONS AND ADVERTISING", "1", 1)
        
        self.stdout.write(self.style.SUCCESS(f"Created FASC"))

        # FACULTY OF HOSPITALITY AND TOURISM MANAGEMENT
        fhtm, _ = Faculty.objects.get_or_create(
            name="FACULTY OF HOSPITALITY AND TOURISM MANAGEMENT", code="FHTM", defaults={"description": "Faculty of Hospitality and Tourism Management"}
        )
        
        # Bachelor of Catering and Hospitality Management (BCHM)
        bchm, _ = Course.objects.get_or_create(
            department=daf, name="Bachelor of Catering and Hospitality Management", code="BCHM", defaults={"duration_years": 4}
        )
        create_unit(bchm, "BUCU 1101", "COMMUNICATION SKILLS", "1", 1)
        create_unit(bchm, "BUCU 1105", "CO-OPERATIVE PHILOSOPHY", "1", 1)
        create_unit(bchm, "BCHM 1101", "INTRODUCTION TO HOSPITALITY AND TOURISM INDUSTRY", "1", 1)
        
        # Bachelor of Tourism Management (BTM)
        btm, _ = Course.objects.get_or_create(
            department=daf, name="Bachelor of Tourism Management", code="BTM", defaults={"duration_years": 4}
        )
        create_unit(btm, "BUCU 1101", "COMMUNICATION SKILLS", "1", 1)
        create_unit(btm, "BUCU 1105", "CO-OPERATIVE PHILOSOPHY", "1", 1)
        create_unit(btm, "BTRM 1106", "TOURISM PRINCIPLES AND PRACTICES", "1", 1)
        
        self.stdout.write(self.style.SUCCESS(f"Created FHTM"))

        # Summary
        faculty_count = Faculty.objects.count()
        dept_count = Department.objects.count()
        course_count = Course.objects.count()
        unit_count = Unit.objects.count()
        
        self.stdout.write(self.style.SUCCESS(
            f"\nSeeding complete! Created:\n"
            f"- {faculty_count} faculties\n"
            f"- {dept_count} departments\n"
            f"- {course_count} courses\n"
            f"- {unit_count} units"
        ))
