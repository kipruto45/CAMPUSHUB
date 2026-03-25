"""
Tests for courses app.
"""
import pytest
from django.contrib.auth import get_user_model

from apps.courses.models import Course, Unit

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def faculty(db):
    """Create a test faculty."""
    from apps.faculties.models import Faculty
    return Faculty.objects.create(
        name="Test Faculty",
        code="TF",
    )


@pytest.fixture
def department(db, faculty):
    """Create a test department."""
    from apps.faculties.models import Department
    return Department.objects.create(
        name="Test Department",
        code="TD",
        faculty=faculty,
    )


@pytest.mark.django_db
class TestCourseModel:
    """Tests for Course model."""

    def test_course_creation(self, department):
        """Test course creation."""
        course = Course.objects.create(
            name="Computer Science",
            code="CS",
            department=department,
        )
        assert course.id is not None
        assert course.name == "Computer Science"
        assert course.code == "CS"
        assert course.slug == "tf-cs"

    def test_course_str(self, department):
        """Test course string representation."""
        course = Course.objects.create(
            name="Computer Science",
            code="CS",
            department=department,
        )
        assert str(course) == "Computer Science (CS)"

    def test_course_slug_auto_generation(self, department):
        """Test slug is auto-generated."""
        course = Course.objects.create(
            name="Test Course",
            code="TC",
            department=department,
        )
        assert course.slug is not None


@pytest.mark.django_db
class TestUnitModel:
    """Tests for Unit model."""

    def test_unit_creation(self, department):
        """Test unit creation."""
        course = Course.objects.create(
            name="Computer Science",
            code="CS",
            department=department,
        )
        unit = Unit.objects.create(
            course=course,
            name="Introduction to Programming",
            code="CS101",
            semester="1",
            year_of_study=1,
        )
        assert unit.id is not None
        assert unit.name == "Introduction to Programming"
        assert unit.code == "CS101"

    def test_unit_str(self, department):
        """Test unit string representation."""
        course = Course.objects.create(
            name="Computer Science",
            code="CS",
            department=department,
        )
        unit = Unit.objects.create(
            course=course,
            name="Introduction to Programming",
            code="CS101",
        )
        assert str(unit) == "CS101 - Introduction to Programming"

    def test_unit_slug_generation(self, department):
        """Test unit slug is auto-generated."""
        course = Course.objects.create(
            name="Computer Science",
            code="CS",
            department=department,
        )
        unit = Unit.objects.create(
            course=course,
            name="Test Unit",
            code="TU101",
            semester="1",
        )
        assert "cs-tu101" in unit.slug

    def test_unit_semester_choices(self, department):
        """Test unit semester choices."""
        course = Course.objects.create(
            name="Computer Science",
            code="CS",
            department=department,
        )
        unit = Unit.objects.create(
            course=course,
            name="Test Unit",
            code="TU101",
            semester="2",
        )
        assert unit.get_semester_display() == "Semester 2"