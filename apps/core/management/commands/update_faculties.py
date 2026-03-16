#!/usr/bin/env python3
"""
Django management command to update faculties, departments, and courses.
"""
from django.core.management.base import BaseCommand
from apps.faculties.models import Faculty, Department, Course


class Command(BaseCommand):
    help = 'Update faculties, departments, and courses'

    def handle(self, *args, **options):
        self.stdout.write('Clearing existing faculties, departments, and courses...')
        
        # Clear existing data
        Course.objects.all().delete()
        Department.objects.all().delete()
        Faculty.objects.all().delete()
        
        # Faculty of Computing and Information Technology (CIT)
        self.stdout.write(self.style.SUCCESS('\nCreating Faculty of Computing and Information Technology (CIT)...'))
        cit = Faculty.objects.create(
            name="Faculty of Computing and Information Technology",
            code="CIT",
            description="This faculty clusters all programs focused on computer science, IT, and data."
        )
        
        # Department of Computer Science
        cs_dept = Department.objects.create(
            name="Department of Computer Science",
            code="DCS",
            faculty=cit
        )
        Course.objects.create(name="BSc. Computer Science", code="BCS", department=cs_dept, years=4)
        Course.objects.create(name="Diploma in Computer Science", code="DCS", department=cs_dept, years=3)
        
        # Department of Information Technology
        it_dept = Department.objects.create(
            name="Department of Information Technology",
            code="DIT",
            faculty=cit
        )
        Course.objects.create(name="Bachelor of Information Technology", code="BIT", department=it_dept, years=4)
        Course.objects.create(name="Bachelor of Business Information Technology", code="BBIT", department=it_dept, years=4)
        Course.objects.create(name="Diploma in Information Technology", code="DIT", department=it_dept, years=3)
        Course.objects.create(name="Diploma in Cyber Security", code="DCY", department=it_dept, years=3)
        
        # Department of Software Engineering
        se_dept = Department.objects.create(
            name="Department of Software Engineering",
            code="DSE",
            faculty=cit
        )
        Course.objects.create(name="Bachelor of Software Engineering", code="BSEN", department=se_dept, years=4)
        
        # Department of Data Science
        ds_dept = Department.objects.create(
            name="Department of Data Science",
            code="DDS",
            faculty=cit
        )
        Course.objects.create(name="Bachelor of Data Science", code="BDAT", department=ds_dept, years=4)
        Course.objects.create(name="BSc. Applied Statistics", code="BSCAS", department=ds_dept, years=4)
        Course.objects.create(name="BSc. Statistics and Information Technology", code="BSIT", department=ds_dept, years=4)
        
        # Faculty of Business and Economics
        self.stdout.write(self.style.SUCCESS('\nCreating Faculty of Business and Economics...'))
        fbe = Faculty.objects.create(
            name="Faculty of Business and Economics",
            code="FBE",
            description="This faculty includes all the core business, finance, and economics programs."
        )
        
        # Department of Accounting and Finance
        af_dept = Department.objects.create(
            name="Department of Accounting and Finance",
            code="DAF",
            faculty=fbe
        )
        Course.objects.create(name="Bachelor of Applied Statistics and Economics", code="BASE", department=af_dept, years=4)
        Course.objects.create(name="Bachelor of Accounting", code="BSACC", department=af_dept, years=4)
        Course.objects.create(name="Bachelor of Banking and Finance", code="BBFI", department=af_dept, years=4)
        Course.objects.create(name="Bachelor of Science in Finance", code="BSCFIN", department=af_dept, years=4)
        Course.objects.create(name="Bachelor of Commerce - Accounting", code="BCOM-A", department=af_dept, years=4)
        Course.objects.create(name="Bachelor of Commerce - Finance", code="BCOM-F", department=af_dept, years=4)
        Course.objects.create(name="Bachelor of Commerce - Banking", code="BCOM-B", department=af_dept, years=4)
        Course.objects.create(name="Diploma in Accounting and Finance", code="DAF", department=af_dept, years=3)
        Course.objects.create(name="Diploma in Banking and Finance", code="DBF", department=af_dept, years=3)
        
        # Department of Management and Entrepreneurship
        me_dept = Department.objects.create(
            name="Department of Management and Entrepreneurship",
            code="DME",
            faculty=fbe
        )
        Course.objects.create(name="Bachelor of Science in Entrepreneurship", code="BENT", department=me_dept, years=4)
        Course.objects.create(name="Bachelor of Business Management", code="BBM", department=me_dept, years=4)
        Course.objects.create(name="Bachelor of Human Resource Management", code="BHRM", department=me_dept, years=4)
        Course.objects.create(name="Bachelor of Commerce - Marketing", code="BCOM-M", department=me_dept, years=4)
        Course.objects.create(name="Diploma in Business Administration", code="DBA", department=me_dept, years=3)
        Course.objects.create(name="Diploma in Human Resource Management", code="DHRM", department=me_dept, years=3)
        Course.objects.create(name="Diploma in Business Management", code="DBM", department=me_dept, years=3)
        Course.objects.create(name="Certificate in Business Management", code="CBM", department=me_dept, years=2)
        
        # Department of Economics
        econ_dept = Department.objects.create(
            name="Department of Economics",
            code="DEC",
            faculty=fbe
        )
        Course.objects.create(name="Bachelor of Science in Economics", code="BECO", department=econ_dept, years=4)
        
        # Faculty of Social Sciences and Development Studies
        self.stdout.write(self.style.SUCCESS('\nCreating Faculty of Social Sciences and Development Studies...'))
        fss = Faculty.objects.create(
            name="Faculty of Social Sciences and Development Studies",
            code="FSS",
            description="This faculty includes programs related to community, society, and development."
        )
        
        # Department of Community Development and Environmental Studies
        cd_dept = Department.objects.create(
            name="Department of Community Development and Environmental Studies",
            code="DCD",
            faculty=fss
        )
        Course.objects.create(name="Bachelor of Co-operatives and Community Development", code="BCCD", department=cd_dept, years=4)
        Course.objects.create(name="Bachelor of Disaster Risk Management", code="BDRM", department=cd_dept, years=4)
        Course.objects.create(name="Bachelor of Environmental Studies", code="BBEST", department=cd_dept, years=4)
        Course.objects.create(name="Bachelor of Environmental Economics and Policy", code="BEEP", department=cd_dept, years=4)
        Course.objects.create(name="Bachelor of Agricultural Economics", code="BAGE", department=cd_dept, years=4)
        
        # Department of Procurement and Supply Chain Management
        psc_dept = Department.objects.create(
            name="Department of Procurement and Supply Chain Management",
            code="DPS",
            faculty=fss
        )
        Course.objects.create(name="Bachelor of Purchasing and Supplies Management", code="BPSM", department=psc_dept, years=4)
        Course.objects.create(name="Diploma in Supply Chain Management", code="DSCM", department=psc_dept, years=3)
        
        # Department of Co-operative and Business Studies
        cob_dept = Department.objects.create(
            name="Department of Co-operative and Business Studies",
            code="DCB",
            faculty=fss
        )
        Course.objects.create(name="Bachelor of Co-operative Business", code="BCOB", department=cob_dept, years=4)
        
        # Faculty of Hospitality and Tourism Management
        self.stdout.write(self.style.SUCCESS('\nCreating Faculty of Hospitality and Tourism Management...'))
        fhtm = Faculty.objects.create(
            name="Faculty of Hospitality and Tourism Management",
            code="FHTM",
            description="This faculty contains all programs related to the service and tourism industry."
        )
        
        # Department of Hospitality Management
        hm_dept = Department.objects.create(
            name="Department of Hospitality Management",
            code="DHM",
            faculty=fhtm
        )
        Course.objects.create(name="Bachelor of Catering and Hospitality Management", code="BCHM", department=hm_dept, years=4)
        Course.objects.create(name="Diploma in Catering and Accommodation Management", code="DCAM", department=hm_dept, years=3)
        Course.objects.create(name="Diploma in Catering and Hotel Management", code="DCHM", department=hm_dept, years=3)
        
        # Department of Tourism and Travel Management
        ttm_dept = Department.objects.create(
            name="Department of Tourism and Travel Management",
            code="DTM",
            faculty=fhtm
        )
        Course.objects.create(name="Bachelor of Tourism Management", code="BTM", department=ttm_dept, years=4)
        Course.objects.create(name="Diploma in Tour and Travel Management", code="DTTM", department=ttm_dept, years=3)
        
        # Faculty of Arts and Social Communication
        self.stdout.write(self.style.SUCCESS('\nCreating Faculty of Arts and Social Communication...'))
        fsc = Faculty.objects.create(
            name="Faculty of Arts and Social Communication",
            code="FASC",
            description="This faculty contains programs related to media, communication, and arts."
        )
        
        # Department of Media and Public Relations
        mpr_dept = Department.objects.create(
            name="Department of Media and Public Relations",
            code="DMPR",
            faculty=fsc
        )
        Course.objects.create(name="Bachelor of Arts in Public Relations and Advertising", code="BPRA", department=mpr_dept, years=4)
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS(f'Faculties created: {Faculty.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'Departments created: {Department.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'Courses created: {Course.objects.count()}'))
        self.stdout.write(self.style.SUCCESS('\nDone!'))
