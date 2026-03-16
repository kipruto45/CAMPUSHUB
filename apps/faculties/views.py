"""
Views for faculties app.
"""

from rest_framework import generics, status, viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.core.permissions import IsAdminOrModerator

from .models import Department, Faculty
from .serializers import (DepartmentSerializer, FacultyDetailSerializer,
                          FacultySerializer)


class FacultyViewSet(viewsets.ModelViewSet):
    """ViewSet for Faculty model."""

    queryset = Faculty.objects.filter(is_active=True)
    serializer_class = FacultySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = "slug"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return FacultyDetailSerializer
        return FacultySerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminOrModerator()]
        return super().get_permissions()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DepartmentViewSet(viewsets.ModelViewSet):
    """ViewSet for Department model."""

    queryset = Department.objects.filter(is_active=True)
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = "slug"

    def get_queryset(self):
        queryset = Department.objects.filter(is_active=True)
        faculty = self.request.query_params.get("faculty")
        faculty_slug = self.request.query_params.get("faculty_slug")
        faculty_id = self.request.query_params.get("faculty_id")
        if faculty_id:
            queryset = queryset.filter(faculty_id=faculty_id)
        elif faculty_slug:
            queryset = queryset.filter(faculty__slug=faculty_slug)
        elif faculty:
            queryset = queryset.filter(faculty__slug=faculty)
        return queryset

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminOrModerator()]
        return super().get_permissions()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FacultyListView(generics.ListAPIView):
    """List all faculties."""

    queryset = Faculty.objects.filter(is_active=True)
    serializer_class = FacultySerializer


class SeedCoursesView(generics.GenericAPIView):
    """Seed courses from user's specification."""
    permission_classes = [IsAdminOrModerator]

    def post(self, request, *args, **kwargs):
        """Seed all courses to the database."""
        from apps.courses.models import Course
        
        courses_created = 0
        
        # FCIT - Faculty of Computing & Information Technology
        fcit, _ = Faculty.objects.get_or_create(
            code='FCIT',
            defaults={'name': 'Faculty of Computing & Information Technology', 'description': 'Faculty of Computing and Information Technology'}
        )
        
        # DCS - Department of Computer Science
        dcs, _ = Department.objects.get_or_create(code='DCS', faculty=fcit, defaults={'name': 'Department of Computer Science', 'description': 'Department of Computer Science'})
        for code, name, duration in [('BCS', 'Bachelor of Computer Science', 4)]:
            course, created = Course.objects.get_or_create(code=code, department=dcs, defaults={'name': name, 'duration_years': duration})
            if created: courses_created += 1
        
        # DIT - Department of Information Technology
        dit, _ = Department.objects.get_or_create(code='DIT', faculty=fcit, defaults={'name': 'Department of Information Technology', 'description': 'Department of Information Technology'})
        for code, name, duration in [('BIT', 'Bachelor of Information Technology', 4), ('BBIT', 'Bachelor of Business Information Technology', 4), ('BSIT', 'Bachelor of Science in Information Technology', 4), ('BMIT', 'Bachelor of Management of Information Technology', 4)]:
            course, created = Course.objects.get_or_create(code=code, department=dit, defaults={'name': name, 'duration_years': duration})
            if created: courses_created += 1
        
        # DDSA - Department of Data Science & Analytics
        ddsa, _ = Department.objects.get_or_create(code='DDSA', faculty=fcit, defaults={'name': 'Department of Data Science & Analytics', 'description': 'Department of Data Science and Analytics'})
        for code, name, duration in [('BDAT', 'Bachelor of Data Science and Analytics', 4)]:
            course, created = Course.objects.get_or_create(code=code, department=ddsa, defaults={'name': name, 'duration_years': duration})
            if created: courses_created += 1
        
        # DCN - Department of Computer Networks
        dcn, _ = Department.objects.get_or_create(code='DCN', faculty=fcit, defaults={'name': 'Department of Computer Networks', 'description': 'Department of Computer Networks'})
        for code, name, duration in [('BNCS', 'Bachelor of Networks and Computer Security', 4)]:
            course, created = Course.objects.get_or_create(code=code, department=dcn, defaults={'name': name, 'duration_years': duration})
            if created: courses_created += 1
        
        # FBE - Faculty of Business & Economics
        fbe, _ = Faculty.objects.get_or_create(code='FBE', defaults={'name': 'Faculty of Business & Economics', 'description': 'Faculty of Business and Economics'})
        
        # DAF - Department of Accounting & Finance
        daf, _ = Department.objects.get_or_create(code='DAF', faculty=fbe, defaults={'name': 'Department of Accounting & Finance', 'description': 'Department of Accounting and Finance'})
        for code, name, duration in [('BBFI', 'Bachelor of Banking and Finance', 4), ('BSCFIN', 'Bachelor of Science in Finance', 4), ('BSACC', 'Bachelor of Science in Accounting', 4)]:
            course, created = Course.objects.get_or_create(code=code, department=daf, defaults={'name': name, 'duration_years': duration})
            if created: courses_created += 1
        
        # DBAM - Department of Business Administration & Management
        dbam, _ = Department.objects.get_or_create(code='DBAM', faculty=fbe, defaults={'name': 'Department of Business Administration & Management', 'description': 'Department of Business Administration and Management'})
        for code, name, duration in [('BBM', 'Bachelor of Business Management', 4), ('BABM', 'Bachelor of Arts in Business Management', 4), ('BAGE', 'Bachelor of Agribusiness', 4), ('BASE', 'Bachelor of Agricultural Science and Entrepreneurship', 4), ('BTM', 'Bachelor of Tourism Management', 4), ('BBEST', 'Bachelor of Business and Enterprise Management', 4), ('BPSM', 'Bachelor of Purchasing and Supply Management', 4)]:
            course, created = Course.objects.get_or_create(code=code, department=dbam, defaults={'name': name, 'duration_years': duration})
            if created: courses_created += 1
        
        # DHRP - Department of Human Resource Management
        dhrp, _ = Department.objects.get_or_create(code='DHRP', faculty=fbe, defaults={'name': 'Department of Human Resource Management', 'description': 'Department of Human Resource Management'})
        for code, name, duration in [('BHRM', 'Bachelor of Human Resource Management', 4)]:
            course, created = Course.objects.get_or_create(code=code, department=dhrp, defaults={'name': name, 'duration_years': duration})
            if created: courses_created += 1
        
        # DECO - Department of Economics
        deco, _ = Department.objects.get_or_create(code='DECO', faculty=fbe, defaults={'name': 'Department of Economics', 'description': 'Department of Economics'})
        for code, name, duration in [('BECO', 'Bachelor of Economics', 4)]:
            course, created = Course.objects.get_or_create(code=code, department=deco, defaults={'name': name, 'duration_years': duration})
            if created: courses_created += 1
        
        # DEI - Department of Economics & International Relations
        dei, _ = Department.objects.get_or_create(code='DEI', faculty=fbe, defaults={'name': 'Department of Economics & International Relations', 'description': 'Department of Economics and International Relations'})
        for code, name, duration in [('BENT', 'Bachelor of Economics and International Trade', 4), ('BEEP', 'Bachelor of Economics and Economic Policy', 4)]:
            course, created = Course.objects.get_or_create(code=code, department=dei, defaults={'name': name, 'duration_years': duration})
            if created: courses_created += 1
        
        # FCCD - Faculty of Communication & Creative Digital Media
        fccd, _ = Faculty.objects.get_or_create(code='FCCD', defaults={'name': 'Faculty of Communication & Creative Digital Media', 'description': 'Faculty of Communication and Creative Digital Media'})
        
        # DCB - Department of Commerce
        dcb, _ = Department.objects.get_or_create(code='DCB', faculty=fccd, defaults={'name': 'Department of Commerce', 'description': 'Department of Commerce'})
        for code, name, duration in [('BCOB', 'Bachelor of Commerce', 4), ('BCOM', 'Bachelor of Commerce (Online)', 4)]:
            course, created = Course.objects.get_or_create(code=code, department=dcb, defaults={'name': name, 'duration_years': duration})
            if created: courses_created += 1
        
        # DRCD - Department of Recreation & Digital Media
        drcd, _ = Department.objects.get_or_create(code='DRCD', faculty=fccd, defaults={'name': 'Department of Recreation & Digital Media', 'description': 'Department of Recreation and Digital Media'})
        for code, name, duration in [('BDRM', 'Bachelor of Digital Recreation and Media', 4), ('BDVS', 'Bachelor of Digital Video Production', 4)]:
            course, created = Course.objects.get_or_create(code=code, department=drcd, defaults={'name': name, 'duration_years': duration})
            if created: courses_created += 1
        
        # FAS - Faculty of Applied Sciences
        fas, _ = Faculty.objects.get_or_create(code='FAS', defaults={'name': 'Faculty of Applied Sciences', 'description': 'Faculty of Applied Sciences'})
        
        # DASM - Department of Arts in Social Sciences
        dasm, _ = Department.objects.get_or_create(code='DASM', faculty=fas, defaults={'name': 'Department of Arts in Social Sciences', 'description': 'Department of Arts in Social Sciences'})
        for code, name, duration in [('BASD', 'Bachelor of Arts in Social Development', 4), ('BSAS', 'Bachelor of Science in Applied Statistics', 4), ('BSCAS', 'Bachelor of Science in Actuarial Science', 4)]:
            course, created = Course.objects.get_or_create(code=code, department=dasm, defaults={'name': name, 'duration_years': duration})
            if created: courses_created += 1
        
        # DPBS - Department of Pure & Biological Sciences
        dpbs, _ = Department.objects.get_or_create(code='DPBS', faculty=fas, defaults={'name': 'Department of Pure & Biological Sciences', 'description': 'Department of Pure and Biological Sciences'})
        for code, name, duration in [('BBIO', 'Bachelor of Biology', 4), ('BCHM', 'Bachelor of Chemistry', 4)]:
            course, created = Course.objects.get_or_create(code=code, department=dpbs, defaults={'name': name, 'duration_years': duration})
            if created: courses_created += 1
        
        # FELS - Faculty of Environmental & Life Sciences
        fels, _ = Faculty.objects.get_or_create(code='FELS', defaults={'name': 'Faculty of Environmental & Life Sciences', 'description': 'Faculty of Environmental and Life Sciences'})
        
        # DES - Department of Environmental Science
        des, _ = Department.objects.get_or_create(code='DES', faculty=fels, defaults={'name': 'Department of Environmental Science', 'description': 'Department of Environmental Science'})
        for code, name, duration in [('BSEN', 'Bachelor of Science in Environmental Science', 4), ('BELSI', 'Bachelor of Environmental Leadership and Sustainability', 4), ('BSF', 'Bachelor of Science in Forestry', 4)]:
            course, created = Course.objects.get_or_create(code=code, department=des, defaults={'name': name, 'duration_years': duration})
            if created: courses_created += 1
        
        # FAMC - Faculty of Arts, Media & Communication
        famc, _ = Faculty.objects.get_or_create(code='FAMC', defaults={'name': 'Faculty of Arts, Media & Communication', 'description': 'Faculty of Arts, Media and Communication'})
        
        # DCMT - Department of Community Media & Technology
        dcmt, _ = Department.objects.get_or_create(code='DCMT', faculty=famc, defaults={'name': 'Department of Community Media & Technology', 'description': 'Department of Community Media and Technology'})
        for code, name, duration in [('BPRA', 'Bachelor of Public Relations and Advertising', 4), ('BCCD', 'Bachelor of Creative and Cultural Development', 4), ('BCD', 'Bachelor of Communication and Development', 4)]:
            course, created = Course.objects.get_or_create(code=code, department=dcmt, defaults={'name': name, 'duration_years': duration})
            if created: courses_created += 1
        
        # DLGS - Department of Library & Information Science
        dlgs, _ = Department.objects.get_or_create(code='DLGS', faculty=famc, defaults={'name': 'Department of Library & Information Science', 'description': 'Department of Library and Information Science'})
        for code, name, duration in [('BLIS', 'Bachelor of Library and Information Science', 4)]:
            course, created = Course.objects.get_or_create(code=code, department=dlgs, defaults={'name': name, 'duration_years': duration})
            if created: courses_created += 1
        
        return Response({
            'status': 'success',
            'message': f'Successfully seeded {courses_created} courses!',
            'courses_created': courses_created
        }, status=status.HTTP_200_OK)

class DepartmentListView(generics.ListAPIView):
    """List all departments."""

    queryset = Department.objects.filter(is_active=True)
    serializer_class = DepartmentSerializer

    def get_queryset(self):
        queryset = Department.objects.filter(is_active=True)
        faculty_id = self.request.query_params.get("faculty_id")
        faculty_slug = self.request.query_params.get("faculty_slug")
        if faculty_id:
            queryset = queryset.filter(faculty_id=faculty_id)
        elif faculty_slug:
            queryset = queryset.filter(faculty__slug=faculty_slug)
        return queryset
