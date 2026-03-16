"""
Management command to seed courses/programs for CampusHub.
Based on the user's specification for all faculties and departments.
"""

from django.core.management.base import BaseCommand
from apps.faculties.models import Faculty, Department
from apps.courses.models import Course


class Command(BaseCommand):
    help = 'Seed courses/programs for all faculties and departments'

    def handle(self, *args, **options):
        self.stdout.write('Seeding courses and programs...')
        
        courses_created = 0
        
        # ========================================
        # FACULTY OF COMPUTING & INFORMATION TECHNOLOGY (FCIT)
        # ========================================
        fcit, _ = Faculty.objects.get_or_create(
            code='FCIT',
            defaults={'name': 'Faculty of Computing & Information Technology', 'description': 'Faculty of Computing and Information Technology'}
        )
        
        # DCS - Department of Computer Science
        dcs, _ = Department.objects.get_or_create(
            code='DCS', faculty=fcit,
            defaults={'name': 'Department of Computer Science', 'description': 'Department of Computer Science'}
        )
        course_data = [
            {'code': 'BCS', 'name': 'Bachelor of Computer Science', 'duration': 4},
        ]
        courses_created += self._create_courses(dcs, course_data)
        
        # DIT - Department of Information Technology
        dit, _ = Department.objects.get_or_create(
            code='DIT', faculty=fcit,
            defaults={'name': 'Department of Information Technology', 'description': 'Department of Information Technology'}
        )
        course_data = [
            {'code': 'BIT', 'name': 'Bachelor of Information Technology', 'duration': 4},
            {'code': 'BBIT', 'name': 'Bachelor of Business Information Technology', 'duration': 4},
            {'code': 'BSIT', 'name': 'Bachelor of Science in Information Technology', 'duration': 4},
            {'code': 'BMIT', 'name': 'Bachelor of Management of Information Technology', 'duration': 4},
        ]
        courses_created += self._create_courses(dit, course_data)
        
        # DDSA - Department of Data Science & Analytics
        ddsa, _ = Department.objects.get_or_create(
            code='DDSA', faculty=fcit,
            defaults={'name': 'Department of Data Science & Analytics', 'description': 'Department of Data Science and Analytics'}
        )
        course_data = [
            {'code': 'BDAT', 'name': 'Bachelor of Data Science and Analytics', 'duration': 4},
        ]
        courses_created += self._create_courses(ddsa, course_data)
        
        # DCN - Department of Computer Networks
        dcn, _ = Department.objects.get_or_create(
            code='DCN', faculty=fcit,
            defaults={'name': 'Department of Computer Networks', 'description': 'Department of Computer Networks'}
        )
        course_data = [
            {'code': 'BNCS', 'name': 'Bachelor of Networks and Computer Security', 'duration': 4},
        ]
        courses_created += self._create_courses(dcn, course_data)
        
        # ========================================
        # FACULTY OF BUSINESS & ECONOMICS (FBE)
        # ========================================
        fbe, _ = Faculty.objects.get_or_create(
            code='FBE',
            defaults={'name': 'Faculty of Business & Economics', 'description': 'Faculty of Business and Economics'}
        )
        
        # DAF - Department of Accounting & Finance
        daf, _ = Department.objects.get_or_create(
            code='DAF', faculty=fbe,
            defaults={'name': 'Department of Accounting & Finance', 'description': 'Department of Accounting and Finance'}
        )
        course_data = [
            {'code': 'BBFI', 'name': 'Bachelor of Banking and Finance', 'duration': 4},
            {'code': 'BSCFIN', 'name': 'Bachelor of Science in Finance', 'duration': 4},
            {'code': 'BSACC', 'name': 'Bachelor of Science in Accounting', 'duration': 4},
        ]
        courses_created += self._create_courses(daf, course_data)
        
        # DBAM - Department of Business Administration & Management
        dbam, _ = Department.objects.get_or_create(
            code='DBAM', faculty=fbe,
            defaults={'name': 'Department of Business Administration & Management', 'description': 'Department of Business Administration and Management'}
        )
        course_data = [
            {'code': 'BBM', 'name': 'Bachelor of Business Management', 'duration': 4},
            {'code': 'BABM', 'name': 'Bachelor of Arts in Business Management', 'duration': 4},
            {'code': 'BAGE', 'name': 'Bachelor of Agribusiness', 'duration': 4},
            {'code': 'BASE', 'name': 'Bachelor of Agricultural Science and Entrepreneurship', 'duration': 4},
            {'code': 'BTM', 'name': 'Bachelor of Tourism Management', 'duration': 4},
            {'code': 'BBEST', 'name': 'Bachelor of Business and Enterprise Management', 'duration': 4},
            {'code': 'BPSM', 'name': 'Bachelor of Purchasing and Supply Management', 'duration': 4},
        ]
        courses_created += self._create_courses(dbam, course_data)
        
        # DHRP - Department of Human Resource Management
        dhrp, _ = Department.objects.get_or_create(
            code='DHRP', faculty=fbe,
            defaults={'name': 'Department of Human Resource Management', 'description': 'Department of Human Resource Management'}
        )
        course_data = [
            {'code': 'BHRM', 'name': 'Bachelor of Human Resource Management', 'duration': 4},
        ]
        courses_created += self._create_courses(dhrp, course_data)
        
        # DECO - Department of Economics
        deco, _ = Department.objects.get_or_create(
            code='DECO', faculty=fbe,
            defaults={'name': 'Department of Economics', 'description': 'Department of Economics'}
        )
        course_data = [
            {'code': 'BECO', 'name': 'Bachelor of Economics', 'duration': 4},
        ]
        courses_created += self._create_courses(deco, course_data)
        
        # DEI - Department of Economics & International Relations
        dei, _ = Department.objects.get_or_create(
            code='DEI', faculty=fbe,
            defaults={'name': 'Department of Economics & International Relations', 'description': 'Department of Economics and International Relations'}
        )
        course_data = [
            {'code': 'BENT', 'name': 'Bachelor of Economics and International Trade', 'duration': 4},
            {'code': 'BEEP', 'name': 'Bachelor of Economics and Economic Policy', 'duration': 4},
        ]
        courses_created += self._create_courses(dei, course_data)
        
        # ========================================
        # FACULTY OF COMMUNICATION & CREATIVE DIGITAL MEDIA (FCCD)
        # ========================================
        fccd, _ = Faculty.objects.get_or_create(
            code='FCCD',
            defaults={'name': 'Faculty of Communication & Creative Digital Media', 'description': 'Faculty of Communication and Creative Digital Media'}
        )
        
        # DCB - Department of Commerce
        dcb, _ = Department.objects.get_or_create(
            code='DCB', faculty=fccd,
            defaults={'name': 'Department of Commerce', 'description': 'Department of Commerce'}
        )
        course_data = [
            {'code': 'BCOB', 'name': 'Bachelor of Commerce', 'duration': 4},
            {'code': 'BCOM', 'name': 'Bachelor of Commerce (Online)', 'duration': 4},
        ]
        courses_created += self._create_courses(dcb, course_data)
        
        # DRCD - Department of Recreation & Digital Media
        drcd, _ = Department.objects.get_or_create(
            code='DRCD', faculty=fccd,
            defaults={'name': 'Department of Recreation & Digital Media', 'description': 'Department of Recreation and Digital Media'}
        )
        course_data = [
            {'code': 'BDRM', 'name': 'Bachelor of Digital Recreation and Media', 'duration': 4},
            {'code': 'BDVS', 'name': 'Bachelor of Digital Video Production', 'duration': 4},
        ]
        courses_created += self._create_courses(drcd, course_data)
        
        # ========================================
        # FACULTY OF APPLIED SCIENCES (FAS)
        # ========================================
        fas, _ = Faculty.objects.get_or_create(
            code='FAS',
            defaults={'name': 'Faculty of Applied Sciences', 'description': 'Faculty of Applied Sciences'}
        )
        
        # DASM - Department of Arts in Social Sciences
        dasm, _ = Department.objects.get_or_create(
            code='DASM', faculty=fas,
            defaults={'name': 'Department of Arts in Social Sciences', 'description': 'Department of Arts in Social Sciences'}
        )
        course_data = [
            {'code': 'BASD', 'name': 'Bachelor of Arts in Social Development', 'duration': 4},
            {'code': 'BSAS', 'name': 'Bachelor of Science in Applied Statistics', 'duration': 4},
            {'code': 'BSCAS', 'name': 'Bachelor of Science in Actuarial Science', 'duration': 4},
        ]
        courses_created += self._create_courses(dasm, course_data)
        
        # DPBS - Department of Pure & Biological Sciences
        dpbs, _ = Department.objects.get_or_create(
            code='DPBS', faculty=fas,
            defaults={'name': 'Department of Pure & Biological Sciences', 'description': 'Department of Pure and Biological Sciences'}
        )
        course_data = [
            {'code': 'BBIO', 'name': 'Bachelor of Biology', 'duration': 4},
            {'code': 'BCHM', 'name': 'Bachelor of Chemistry', 'duration': 4},
        ]
        courses_created += self._create_courses(dpbs, course_data)
        
        # ========================================
        # FACULTY OF ENVIRONMENTAL & LIFE SCIENCES (FELS)
        # ========================================
        fels, _ = Faculty.objects.get_or_create(
            code='FELS',
            defaults={'name': 'Faculty of Environmental & Life Sciences', 'description': 'Faculty of Environmental and Life Sciences'}
        )
        
        # DES - Department of Environmental Science
        des, _ = Department.objects.get_or_create(
            code='DES', faculty=fels,
            defaults={'name': 'Department of Environmental Science', 'description': 'Department of Environmental Science'}
        )
        course_data = [
            {'code': 'BSEN', 'name': 'Bachelor of Science in Environmental Science', 'duration': 4},
            {'code': 'BELSI', 'name': 'Bachelor of Environmental Leadership and Sustainability', 'duration': 4},
            {'code': 'BSF', 'name': 'Bachelor of Science in Forestry', 'duration': 4},
        ]
        courses_created += self._create_courses(des, course_data)
        
        # ========================================
        # FACULTY OF ARTS, MEDIA & COMMUNICATION (FAMC)
        # ========================================
        famc, _ = Faculty.objects.get_or_create(
            code='FAMC',
            defaults={'name': 'Faculty of Arts, Media & Communication', 'description': 'Faculty of Arts, Media and Communication'}
        )
        
        # DCMT - Department of Community Media & Technology
        dcmt, _ = Department.objects.get_or_create(
            code='DCMT', faculty=famc,
            defaults={'name': 'Department of Community Media & Technology', 'description': 'Department of Community Media and Technology'}
        )
        course_data = [
            {'code': 'BPRA', 'name': 'Bachelor of Public Relations and Advertising', 'duration': 4},
            {'code': 'BCCD', 'name': 'Bachelor of Creative and Cultural Development', 'duration': 4},
            {'code': 'BCD', 'name': 'Bachelor of Communication and Development', 'duration': 4},
        ]
        courses_created += self._create_courses(dcmt, course_data)
        
        # DLGS - Department of Library & Information Science
        dlgs, _ = Department.objects.get_or_create(
            code='DLGS', faculty=famc,
            defaults={'name': 'Department of Library & Information Science', 'description': 'Department of Library and Information Science'}
        )
        course_data = [
            {'code': 'BLIS', 'name': 'Bachelor of Library and Information Science', 'duration': 4},
        ]
        courses_created += self._create_courses(dlgs, course_data)
        
        self.stdout.write(self.style.SUCCESS(
            f'Successfully seeded {courses_created} courses!'
        ))
        
        # Display all courses by faculty
        self.stdout.write('\nAll Courses by Faculty:')
        for faculty in Faculty.objects.all().order_by('code'):
            self.stdout.write(f'\n{faculty.code} - {faculty.name}:')
            for dept in faculty.departments.all().order_by('code'):
                self.stdout.write(f'  {dept.code} - {dept.name}:')
                for course in dept.courses.all().order_by('code'):
                    self.stdout.write(f'    {course.code} - {course.name}')

    def _create_courses(self, department, courses_data):
        """Helper method to create courses for a department"""
        created_count = 0
        for data in courses_data:
            course, created = Course.objects.get_or_create(
                code=data['code'],
                department=department,
                defaults={
                    'name': data['name'],
                    'duration_years': data['duration']
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f'Created course: {course.code} - {course.name} ({department.code})')
        return created_count
