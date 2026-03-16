"""
Serializers for courses app.
"""

from rest_framework import serializers

from apps.faculties.serializers import DepartmentSerializer

from .models import Course, Unit


class CourseSerializer(serializers.ModelSerializer):
    """Serializer for Course model."""

    department_name = serializers.CharField(source="department.name", read_only=True)
    department_code = serializers.CharField(source="department.code", read_only=True)
    faculty_name = serializers.CharField(
        source="department.faculty.name", read_only=True
    )
    units_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id",
            "department",
            "department_name",
            "department_code",
            "faculty_name",
            "name",
            "code",
            "slug",
            "description",
            "duration_years",
            "is_active",
            "units_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]

    def get_units_count(self, obj) -> int:
        return obj.units.filter(is_active=True).count()


class UnitSerializer(serializers.ModelSerializer):
    """Serializer for Unit model."""

    course_name = serializers.CharField(source="course.name", read_only=True)
    course_code = serializers.CharField(source="course.code", read_only=True)
    department_name = serializers.CharField(
        source="course.department.name", read_only=True
    )

    class Meta:
        model = Unit
        fields = [
            "id",
            "course",
            "course_name",
            "course_code",
            "department_name",
            "name",
            "code",
            "slug",
            "description",
            "semester",
            "year_of_study",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class CourseDetailSerializer(CourseSerializer):
    """Detailed serializer for Course model."""

    department_details = DepartmentSerializer(source="department", read_only=True)
    units = UnitSerializer(many=True, read_only=True)

    class Meta(CourseSerializer.Meta):
        fields = CourseSerializer.Meta.fields + ["units", "department_details"]
