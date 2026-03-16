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
