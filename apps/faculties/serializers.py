"""
Serializers for faculties app.
"""

from rest_framework import serializers

from .models import Department, Faculty


class FacultySerializer(serializers.ModelSerializer):
    """Serializer for Faculty model."""

    departments_count = serializers.SerializerMethodField()

    class Meta:
        model = Faculty
        fields = [
            "id",
            "name",
            "code",
            "slug",
            "description",
            "is_active",
            "departments_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]

    def get_departments_count(self, obj) -> int:
        return obj.departments.filter(is_active=True).count()


class DepartmentSerializer(serializers.ModelSerializer):
    """Serializer for Department model."""

    faculty_name = serializers.CharField(source="faculty.name", read_only=True)
    faculty_code = serializers.CharField(source="faculty.code", read_only=True)
    courses_count = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = [
            "id",
            "faculty",
            "faculty_name",
            "faculty_code",
            "name",
            "code",
            "slug",
            "description",
            "is_active",
            "courses_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]

    def get_courses_count(self, obj) -> int:
        from apps.courses.models import Course

        return Course.objects.filter(department=obj, is_active=True).count()


class FacultyDetailSerializer(FacultySerializer):
    """Detailed serializer for Faculty model."""

    departments = DepartmentSerializer(many=True, read_only=True)

    class Meta(FacultySerializer.Meta):
        fields = FacultySerializer.Meta.fields + ["departments"]
