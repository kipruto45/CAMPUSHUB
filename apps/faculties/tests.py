"""
Tests for faculties app.
"""
import pytest

from apps.faculties.models import Faculty, Department


@pytest.mark.django_db
class TestFacultyModel:
    """Tests for Faculty model."""

    def test_faculty_creation(self):
        """Test faculty creation."""
        faculty = Faculty.objects.create(
            name="Engineering",
            code="ENG",
        )
        assert faculty.id is not None
        assert faculty.name == "Engineering"
        assert faculty.code == "ENG"
        assert faculty.slug == "eng"

    def test_faculty_str(self):
        """Test faculty string representation."""
        faculty = Faculty.objects.create(
            name="Engineering",
            code="ENG",
        )
        assert str(faculty) == "Engineering"

    def test_faculty_slug_auto_generation(self):
        """Test slug is auto-generated from code."""
        faculty = Faculty.objects.create(
            name="Test Faculty",
            code="TF",
        )
        assert faculty.slug == "tf"


@pytest.mark.django_db
class TestDepartmentModel:
    """Tests for Department model."""

    def test_department_creation(self):
        """Test department creation."""
        faculty = Faculty.objects.create(
            name="Engineering",
            code="ENG",
        )
        department = Department.objects.create(
            name="Computer Science",
            code="CS",
            faculty=faculty,
        )
        assert department.id is not None
        assert department.name == "Computer Science"
        assert department.faculty == faculty

    def test_department_str(self):
        """Test department string representation."""
        faculty = Faculty.objects.create(
            name="Engineering",
            code="ENG",
        )
        department = Department.objects.create(
            name="Computer Science",
            code="CS",
            faculty=faculty,
        )
        assert str(department) == "Computer Science (ENG)"

    def test_department_slug_generation(self):
        """Test department slug is auto-generated."""
        faculty = Faculty.objects.create(
            name="Engineering",
            code="ENG",
        )
        department = Department.objects.create(
            name="Computer Science",
            code="CS",
            faculty=faculty,
        )
        assert department.slug == "eng-cs"