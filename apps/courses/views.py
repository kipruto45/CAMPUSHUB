"""
Views for courses app.
"""

from rest_framework import generics, status, viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.core.permissions import IsAdminOrModerator

from .models import Course, Unit
from .serializers import (CourseDetailSerializer, CourseSerializer,
                          UnitSerializer)


class CourseViewSet(viewsets.ModelViewSet):
    """ViewSet for Course model."""

    queryset = Course.objects.filter(is_active=True)
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = "slug"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CourseDetailSerializer
        return CourseSerializer

    def get_queryset(self):
        queryset = Course.objects.filter(is_active=True)
        department_id = self.request.query_params.get("department_id")
        department_slug = self.request.query_params.get("department_slug")
        faculty_id = self.request.query_params.get("faculty_id")

        if department_id:
            queryset = queryset.filter(department_id=department_id)
        elif department_slug:
            queryset = queryset.filter(department__slug=department_slug)
        elif faculty_id:
            queryset = queryset.filter(department__faculty_id=faculty_id)

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


class UnitViewSet(viewsets.ModelViewSet):
    """ViewSet for Unit model."""

    queryset = Unit.objects.filter(is_active=True)
    serializer_class = UnitSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = "slug"

    def get_queryset(self):
        queryset = Unit.objects.filter(is_active=True)
        course_id = self.request.query_params.get("course_id")
        course_slug = self.request.query_params.get("course_slug")
        department_id = self.request.query_params.get("department_id")
        semester = self.request.query_params.get("semester")
        year = self.request.query_params.get("year")

        if course_id:
            queryset = queryset.filter(course_id=course_id)
        elif course_slug:
            queryset = queryset.filter(course__slug=course_slug)
        elif department_id:
            queryset = queryset.filter(course__department_id=department_id)

        if semester:
            queryset = queryset.filter(semester=semester)
        if year:
            queryset = queryset.filter(year_of_study=year)

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


class CourseListView(generics.ListAPIView):
    """List all courses."""

    queryset = Course.objects.filter(is_active=True)
    serializer_class = CourseSerializer


class UnitListView(generics.ListAPIView):
    """List all units."""

    queryset = Unit.objects.filter(is_active=True)
    serializer_class = UnitSerializer
